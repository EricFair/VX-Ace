#!/usr/bin/env python3
"""Bounded static game-balance analysis of a fresh VX Ace index; never executes project code."""
from __future__ import annotations
import argparse
import json
import math
import re
import sys
from pathlib import Path
from vxace_copy_patcher import verify_fresh, current_inventory
from vxace_index_query import Index, unlinked

VERSION = '1.7.0'
PARAMS = ('mhp', 'mmp', 'atk', 'def', 'mat', 'mdf', 'agi', 'luk')
ACTOR_ATTRS = PARAMS + ('hp', 'mp', 'level')
ENEMY_ATTRS = PARAMS + ('hp', 'mp')
HP_DAMAGE = {1: 'hp_damage', 5: 'hp_drain'}
MP_DAMAGE = {2: 'mp_damage', 6: 'mp_drain'}
DAMAGE_TYPES = {0: 'none', 1: 'hp_damage', 2: 'mp_damage', 3: 'hp_recover', 4: 'mp_recover', 5: 'hp_drain', 6: 'mp_drain'}
GOODS = {0: 'item', 1: 'weapon', 2: 'armor'}
EXP_NOTE = 'default formula â€” verify against the project\'s scripts if customized'
MANY_HITS = 20
MAX_FORMULA = 512
LIMITS = [
    'Static analysis of editor data only; no project Ruby is evaluated and custom scripts may change every number here.',
    'Damage is the base formula value only: element rate, variance, critical, guard, TCR/PDR/MDR, states and recover/drain handling apply afterwards and are not modelled.',
    'Formulas using anything beyond numbers, + - * / % ( ), a./b. battler parameters and v[n] are classified opaque and never guessed.',
    'v[n] variables are unresolved: they evaluate to the --var default (0) and the row is flagged.',
    'Ruby integer semantics are used: int/int floors toward negative infinity, mixed float arithmetic stays float; the final value is truncated like to_i.',
    'Battler hp and mp are assumed full. Actor stats come from the class parameter table without equipment, states or other features.',
    'The EXP curve uses the ' + EXP_NOTE + '.',
    'Enemy rows use database parameters only; enemy actions are listed regardless of conditions or rating.',
    'Only HP damage and HP drain skills are matched up for hits-to-kill; MP damage is listed in the formula table only.',
    'Shop prices follow command 302/605 as written; shops built with scripts or variables are not seen.',
    'Warnings are heuristics, not defects; no result authorizes mutation.',
]


class Opaque(ValueError):
    pass


class EvalError(ValueError):
    pass


# --- restricted Ruby-subset formula parser (no eval) -------------------------

TOKEN = re.compile(r'\s*(?:(?P<num>\d+(?:\.\d+)?)(?![\w.])|(?P<attr>[ab]\.(?:atk|def|mat|mdf|agi|luk|mhp|mmp|hp|mp|level)\b)|(?P<var>v\[\d+\])|(?P<op>[-+*/%()]))')
OPAQUE_HINTS = (
    (r'\brand\b|\bsrand\b', 'random call'), (r'\bif\b|\bunless\b|\bcase\b|\?', 'conditional'), (r';', 'statement separator'),
    (r'[^=!<>]=[^=]|\+=|-=', 'assignment'), (r'==|!=|<=|>=|<|>|&&|\|\||\bnot\b|\band\b|\bor\b', 'comparison or boolean logic'),
    (r'\*\*', 'exponent'), (r'\bstate|\bstates\b', 'state query'), (r'\bs\[|\bp\[|\$game|\$data', 'global access'),
    (r'\b[ab]\.\w+', 'unsupported battler method'), (r'\.\w+|\w+\(', 'method call'), (r'\b[A-Za-z_]\w*', 'identifier'),
)


def opaque_reason(text):
    for pattern, reason in OPAQUE_HINTS:
        if re.search(pattern, text):
            return reason
    return 'unsupported syntax'


def tokenize(text):
    out, pos = [], 0
    while pos < len(text):
        if not text[pos:].strip():
            break
        match = TOKEN.match(text, pos)
        if not match:
            raise Opaque(opaque_reason(text))
        out.append((match.lastgroup, match.group(match.lastgroup)))
        pos = match.end()
    if not out:
        raise Opaque('empty formula')
    return out


def parse(text):
    """Return an expression tree, or raise Opaque(reason). Never evaluates."""
    if not isinstance(text, str):
        raise Opaque('formula is not text')
    if len(text) > MAX_FORMULA:
        raise Opaque('formula too long')
    if '**' in text: raise Opaque('exponent operator')
    tokens = tokenize(text); pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else (None, None)

    def take():
        pos[0] += 1; return tokens[pos[0] - 1]

    def expr(depth):
        if depth > 64: raise Opaque('nesting too deep')
        node = term(depth)
        while peek()[1] in ('+', '-'):
            node = (take()[1], node, term(depth))
        return node

    def term(depth):
        node = unary(depth)
        while peek()[1] in ('*', '/', '%'):
            node = (take()[1], node, unary(depth))
        return node

    def unary(depth):
        if peek()[1] == '-':
            take(); return ('neg', unary(depth + 1))
        if peek()[1] == '+':
            take(); return unary(depth + 1)
        return atom(depth)

    def atom(depth):
        kind, value = peek()
        if kind is None: raise Opaque('incomplete expression')
        take()
        if kind == 'num': return ('num', float(value) if '.' in value else int(value))
        if kind == 'attr': return ('attr', value[0], value[2:])
        if kind == 'var': return ('var', int(value[2:-1]))
        if value == '(':
            node = expr(depth + 1)
            if peek()[1] != ')': raise Opaque('unbalanced parenthesis')
            take(); return node
        raise Opaque('unexpected operator')

    tree = expr(0)
    if pos[0] != len(tokens): raise Opaque('unexpected trailing syntax')
    return tree


def unresolved(tree, found=None):
    found = set() if found is None else found
    if tree[0] == 'var': found.add(tree[1])
    elif tree[0] in ('+', '-', '*', '/', '%'): unresolved(tree[1], found); unresolved(tree[2], found)
    elif tree[0] == 'neg': unresolved(tree[1], found)
    return found


def evaluate(tree, a, b, variables=None):
    """Evaluate with Ruby numeric semantics. a/b map attribute names to numbers."""
    kind = tree[0]
    if kind == 'num': return tree[1]
    if kind == 'attr':
        side = a if tree[1] == 'a' else b
        if tree[2] not in side: raise EvalError(tree[1] + '.' + tree[2] + ' unavailable on this battler')
        return side[tree[2]]
    if kind == 'var': return (variables or {}).get(tree[1], 0)
    if kind == 'neg': return -evaluate(tree[1], a, b, variables)
    left, right = evaluate(tree[1], a, b, variables), evaluate(tree[2], a, b, variables)
    if kind == '+': return left + right
    if kind == '-': return left - right
    if kind == '*': return left * right
    both_int = type(left) is int and type(right) is int
    if right == 0:
        if both_int: raise EvalError('division by zero')
        raise EvalError('non-finite result')
    if kind == '/': return left // right if both_int else left / right
    return left % right  # Ruby and Python share floored modulo


def base_value(tree, a, b, variables=None):
    value = evaluate(tree, a, b, variables)
    if isinstance(value, float) and not math.isfinite(value): raise EvalError('non-finite result')
    return int(value)  # Ruby to_i truncates toward zero


# --- default VX Ace curves ---------------------------------------------------

def exp_for_level(level, exp_params):
    if type(level) is not int or level < 1: raise ValueError('Invalid level')
    if level == 1: return 0
    if not isinstance(exp_params, list) or len(exp_params) != 4 or any(type(x) not in (int, float) for x in exp_params):
        raise ValueError('Invalid exp_params')
    basis, extra, acc_a, acc_b = exp_params; lv = float(level)
    if acc_b == 0: raise ValueError('exp_params accuracy B is zero')
    value = basis * ((lv - 1) ** (0.9 + acc_a / 250.0)) * lv * (lv + 1) / (6 + lv ** 2 / 50.0 / acc_b) + (lv - 1) * extra
    return int(math.floor(value + 0.5)) if value >= 0 else -int(math.floor(-value + 0.5))


def class_params(klass, level):
    """Eight base parameters at a level from the class Table (index x + y*xsize)."""
    table = klass.get('params') if isinstance(klass, dict) else None
    if not isinstance(table, dict) or table.get('__class__') != 'Table' or table.get('dimensions') != 2 or table.get('xsize') != 8 \
            or type(table.get('ysize')) is not int or table.get('zsize') != 1 or not isinstance(table.get('data'), list) \
            or len(table['data']) != 8 * table['ysize']:
        raise ValueError('Class params must be a fully decoded 8-column Table')
    if not 1 <= level < table['ysize']: raise ValueError('Level outside the class parameter table')
    return {name: table['data'][i + 8 * level] for i, name in enumerate(PARAMS)}


# --- index access ------------------------------------------------------------

def database(data, name, required=False):
    file = 'database/' + name + '.json'
    if not data.path(file).is_file():
        if required: raise ValueError('Missing database file ' + name)
        return file, []
    root = data.json(file)
    if not isinstance(root, list): raise ValueError('Expected normalized database array in ' + name)
    for slot, entry in enumerate(root):
        data.spend()
        if entry is not None and (not isinstance(entry, dict) or entry.get('id') != slot):
            raise ValueError('Database ids must match native array slots in ' + name)
    return file, root


def integer(value, label):
    if type(value) is not int: raise ValueError('Invalid ' + label)
    return value


def number(value, label):
    if type(value) not in (int, float): raise ValueError('Invalid ' + label)
    return value


def name_of(row):
    return row.get('name') if isinstance(row, dict) and isinstance(row.get('name'), str) else ''


def formulas(data, tables, var_defaults):
    """Parse every damaging skill/item formula; returns rows keyed by (kind, id)."""
    rows = {}
    for kind, (file, items) in tables.items():
        for slot, entry in enumerate(items):
            if entry is None: continue
            data.spend()
            damage = entry.get('damage')
            if not isinstance(damage, dict): continue
            dtype = damage.get('type')
            if dtype not in DAMAGE_TYPES: raise ValueError('Invalid damage type in ' + file)
            if dtype == 0: continue
            text = damage.get('formula')
            row = {'kind': kind, 'id': slot, 'name': name_of(entry), 'damage_type': DAMAGE_TYPES[dtype], 'damage_type_id': dtype,
                   'formula': text, 'evidence': {'file': file, 'path': [slot, 'damage', 'formula']}, 'tree': None}
            try:
                tree = parse(text); row['tree'] = tree; row['status'] = 'evaluable'
                vars_ = sorted(unresolved(tree))
                if vars_: row['unresolved_variables'] = vars_; row['variable_defaults'] = {str(n): var_defaults.get(n, 0) for n in vars_}
            except Opaque as exc:
                row['status'] = 'opaque'; row['reason'] = str(exc)
            rows[(kind, slot)] = row
    return rows


def shops(data, names):
    """Native 302 Shop Processing + following 605 lines in map/common/troop pages."""
    out = []
    for loc, file, path, page, _ in data.event_lists():
        commands = page['list']
        for n, cmd in enumerate(commands):
            data.spend()
            if not isinstance(cmd, dict) or cmd.get('code') != 302: continue
            goods, indices = [cmd.get('parameters')], [n]
            nxt = n + 1
            while nxt < len(commands) and isinstance(commands[nxt], dict) and commands[nxt].get('code') == 605:
                goods.append(commands[nxt].get('parameters')); indices.append(nxt); nxt += 1
            for position, (params, index) in enumerate(zip(goods, indices)):
                evidence = {**loc, 'file': file, 'path': path + ['list', index], 'command_index': index, 'command_code': commands[index].get('code')}
                if not isinstance(params, list) or len(params) < 4 or any(type(x) is not int for x in params[:4]) or params[0] not in GOODS or params[2] not in (0, 1):
                    out.append({'status': 'opaque', 'good_index': position, 'evidence': evidence}); continue
                kind = GOODS[params[0]]; base = names[kind].get(params[1])
                row = {'status': 'ok', 'good_index': position, 'goods_type': kind, 'goods_id': params[1], 'name': base['name'] if base else None,
                       'price_type': 'specified' if params[2] else 'standard', 'database_price': base['price'] if base else None,
                       'evidence': evidence}
                row['price'] = params[3] if params[2] else row['database_price']
                if position == 0 and len(params) > 4: row['purchase_only'] = bool(params[4])
                out.append(row)
    return out


# --- analysis ----------------------------------------------------------------

def level_set(requested, actor, ysize):
    top = min(actor.get('max_level') if type(actor.get('max_level')) is int else 99, ysize - 1)
    initial = actor.get('initial_level') if type(actor.get('initial_level')) is int else 1
    levels = {initial, top} | {min(max(x, 1), top) for x in requested}
    return sorted(x for x in levels if 1 <= x <= top)


def sample_levels(top):
    return sorted({1, top} | set(range(10, top, 10)))


def analyze(data, levels=(1, 10, 20, 50), max_rows=200, variables=None, actor_ids=None, enemy_ids=None):
    if type(max_rows) is not int or not 1 <= max_rows <= 5000: raise ValueError('max-rows must be 1..5000')
    variables = variables or {}
    levels = tuple(levels)
    if not levels or len(levels) > 20 or any(type(x) is not int or not 1 <= x <= 99 for x in levels): raise ValueError('levels must be 1..20 values in 1..99')
    t = {name: database(data, name) for name in ('actors', 'classes', 'skills', 'items', 'weapons', 'armors', 'enemies', 'troops')}
    actors, classes, skills, items, weapons, armors, enemies, troops = (t[n][1] for n in ('actors', 'classes', 'skills', 'items', 'weapons', 'armors', 'enemies', 'troops'))
    present = {n: bool(rows) for n, rows in t.items()}
    names = {kind: {i: {'name': name_of(e), 'price': e.get('price') if type(e.get('price')) is int else None} for i, e in enumerate(rows) if e}
             for kind, rows in (('item', items), ('weapon', weapons), ('armor', armors))}
    warnings = []

    def warn(code, detail, evidence, **extra):
        warnings.append({'code': code, 'severity': 'info', 'heuristic': True, 'detail': detail, 'evidence': evidence, **extra})

    formula_rows = formulas(data, {'skill': (t['skills'][0], skills), 'item': (t['items'][0], items)}, variables)
    formula_report = [{k: v for k, v in r.items() if k != 'tree'} for r in formula_rows.values()]

    # Actors: stats and EXP curve.
    actor_report, actor_stats = [], {}
    for slot, actor in enumerate(actors):
        if actor is None or (actor_ids and slot not in actor_ids): continue
        data.spend()
        klass = classes[actor['class_id']] if type(actor.get('class_id')) is int and 0 < actor['class_id'] < len(classes) else None
        if klass is None:
            warn('actor_missing_class', 'Actor references a class absent from Classes', {'file': t['actors'][0], 'path': [slot, 'class_id']}, actor_id=slot); continue
        ysize = klass['params']['ysize'] if isinstance(klass.get('params'), dict) and type(klass['params'].get('ysize')) is int else 0
        picked = level_set(levels, actor, ysize)
        stats = {lv: class_params(klass, lv) for lv in picked}
        actor_stats[slot] = {'name': name_of(actor), 'stats': stats, 'klass': klass, 'initial': actor['initial_level'] if type(actor.get('initial_level')) is int else 1}
        top = min(actor.get('max_level') if type(actor.get('max_level')) is int else 99, ysize - 1)
        curve = []
        for lv in sample_levels(top):
            data.spend(); total = exp_for_level(lv, klass.get('exp_params'))
            curve.append({'level': lv, 'total_exp': total, 'exp_to_next': exp_for_level(lv + 1, klass.get('exp_params')) - total if lv < top else None, 'params': class_params(klass, lv)})
        actor_report.append({'id': slot, 'name': name_of(actor), 'class_id': actor['class_id'], 'class_name': name_of(klass), 'initial_level': actor.get('initial_level'),
                             'max_level': top, 'exp_params': klass.get('exp_params'), 'exp_formula': EXP_NOTE, 'curve': curve,
                             'evidence': {'file': t['classes'][0], 'path': [actor['class_id'], 'params']}})

    # Enemy parameters.
    enemy_stats = {}
    for slot, enemy in enumerate(enemies):
        if enemy is None or (enemy_ids and slot not in enemy_ids): continue
        data.spend(); params = enemy.get('params')
        if not isinstance(params, list) or len(params) != 8 or any(type(x) is not int for x in params):
            warn('enemy_opaque_params', 'Enemy params are not eight integers', {'file': t['enemies'][0], 'path': [slot, 'params']}, enemy_id=slot); continue
        enemy_stats[slot] = dict(zip(PARAMS, params))

    def with_pools(stats, extra=None):
        return {**stats, 'hp': stats['mhp'], 'mp': stats['mmp'], **(extra or {})}

    # Matchups (streamed: aggregates over every row, only max_rows are kept).
    rows, counters = {'actor_vs_enemy': [], 'enemy_vs_actor': []}, {'actor_vs_enemy': 0, 'enemy_vs_actor': 0, 'skipped': {}}
    best_hits, oneshot, nonpositive = {}, {}, {}

    def record(side, row):
        counters[side] += 1
        if len(rows[side]) < max_rows: rows[side].append(row)

    def skip(reason):
        counters['skipped'][reason] = counters['skipped'].get(reason, 0) + 1

    for aid, info in sorted(actor_stats.items()):
        for lv, stats in info['stats'].items():
            usable = sorted({1} | {l['skill_id'] for l in info['klass'].get('learnings', []) if isinstance(l, dict) and type(l.get('skill_id')) is int and type(l.get('level')) is int and l['level'] <= lv})
            for sid in usable:
                f = formula_rows.get(('skill', sid))
                if not f or f['damage_type_id'] not in HP_DAMAGE: continue
                if f['status'] != 'evaluable': continue
                for eid, es in sorted(enemy_stats.items()):
                    data.spend()
                    try: dmg = base_value(f['tree'], with_pools(stats, {'level': lv}), with_pools(es), variables)
                    except EvalError as exc: skip(str(exc)); continue
                    hits = math.ceil(es['mhp'] / dmg) if dmg > 0 else None
                    row = {'actor_id': aid, 'actor': info['name'], 'level': lv, 'skill_id': sid, 'skill': name_of(skills[sid]), 'enemy_id': eid,
                           'enemy': name_of(enemies[eid]), 'base_damage': dmg, 'enemy_mhp': es['mhp'], 'hits_to_kill': hits}
                    if f.get('unresolved_variables'): row['unresolved_variables'] = f['unresolved_variables']
                    record('actor_vs_enemy', row)
                    if hits is not None and (eid not in best_hits or hits < best_hits[eid][0]): best_hits[eid] = (hits, row)
                    if dmg <= 0 and lv == min(info['stats']): nonpositive.setdefault((aid, sid), []).append(eid)
                    if hits == 1 and lv == info['initial']: oneshot.setdefault((aid, sid), []).append(eid)
    enemy_oneshot = {}
    for eid, es in sorted(enemy_stats.items()):
        actions = enemies[eid].get('actions')
        sids = sorted({a['skill_id'] for a in actions if isinstance(a, dict) and type(a.get('skill_id')) is int}) if isinstance(actions, list) else []
        for sid in sids:
            f = formula_rows.get(('skill', sid))
            if not f or f['damage_type_id'] not in HP_DAMAGE or f['status'] != 'evaluable': continue
            for aid, info in sorted(actor_stats.items()):
                for lv, stats in info['stats'].items():
                    data.spend()
                    try: dmg = base_value(f['tree'], with_pools(es), with_pools(stats, {'level': lv}), variables)
                    except EvalError as exc: skip(str(exc)); continue
                    row = {'enemy_id': eid, 'enemy': name_of(enemies[eid]), 'skill_id': sid, 'skill': name_of(skills[sid]), 'actor_id': aid, 'actor': info['name'],
                           'level': lv, 'base_damage': dmg, 'actor_mhp': stats['mhp'], 'hits_to_kill': math.ceil(stats['mhp'] / dmg) if dmg > 0 else None}
                    record('enemy_vs_actor', row)
                    if row['hits_to_kill'] == 1 and lv == info['initial']: enemy_oneshot.setdefault((eid, sid), []).append(aid)

    for (aid, sid), eids in sorted(nonpositive.items()):
        warn('nonpositive_damage', 'Base damage is zero or negative at the actor\'s lowest sampled level against these enemies', {'file': t['skills'][0], 'path': [sid, 'damage', 'formula']},
             actor_id=aid, skill_id=sid, enemy_ids=eids[:10], enemy_count=len(eids))
    for (aid, sid), eids in sorted(oneshot.items()):
        warn('one_shot_at_initial_level', 'Base damage alone kills these enemies at the actor\'s initial level', {'file': t['skills'][0], 'path': [sid, 'damage', 'formula']},
             actor_id=aid, skill_id=sid, enemy_ids=eids[:10], enemy_count=len(eids))
    for (eid, sid), aids in sorted(enemy_oneshot.items()):
        warn('enemy_one_shots_actor', 'Enemy skill base damage alone kills these actors at their initial level', {'file': t['enemies'][0], 'path': [eid, 'actions']},
             enemy_id=eid, skill_id=sid, actor_ids=aids[:10], actor_count=len(aids))
    for eid, (hits, row) in sorted(best_hits.items()):
        if hits > MANY_HITS:
            warn('many_hits_to_kill', 'Even the best evaluated skill needs more than %d hits' % MANY_HITS, {'file': t['enemies'][0], 'path': [eid, 'params', 0]}, enemy_id=eid, best_hits=hits,
                 actor_id=row['actor_id'], level=row['level'], skill_id=row['skill_id'])
    if not best_hits and enemy_stats and actor_stats:
        warn('no_evaluable_matchups', 'No evaluable HP-damage skill produced a matchup (opaque formulas, missing data or filters)', {'file': t['skills'][0], 'path': []})

    # Troops: EXP, gold, drops.
    troop_report = []
    for slot, troop in enumerate(troops):
        if troop is None: continue
        data.spend(); members = troop.get('members')
        if not isinstance(members, list): raise ValueError('Opaque troop members')
        exp = gold = 0; drops = []; missing = []
        for m, member in enumerate(members):
            eid = member.get('enemy_id') if isinstance(member, dict) else None
            enemy = enemies[eid] if type(eid) is int and 0 < eid < len(enemies) else None
            if enemy is None: missing.append(eid); continue
            exp += integer(enemy.get('exp'), 'enemy exp'); gold += integer(enemy.get('gold'), 'enemy gold')
            for d in enemy.get('drop_items') or []:
                if isinstance(d, dict) and d.get('kind') in (1, 2, 3) and type(d.get('data_id')) is int and type(d.get('denominator')) is int and d['denominator'] > 0:
                    kind = GOODS[d['kind'] - 1]; drops.append({'enemy_id': eid, 'goods_type': kind, 'goods_id': d['data_id'],
                                                              'name': (names[kind].get(d['data_id']) or {}).get('name'), 'chance': round(1 / d['denominator'], 4)})
        row = {'id': slot, 'name': name_of(troop), 'members': len(members), 'total_exp': exp, 'total_gold': gold, 'drops': drops, 'evidence': {'file': t['troops'][0], 'path': [slot, 'members']}}
        if missing: row['missing_enemy_ids'] = missing; warn('troop_missing_enemy', 'Troop member references an absent enemy', row['evidence'], troop_id=slot)
        elif not members: warn('troop_empty', 'Troop has no members', row['evidence'], troop_id=slot)
        troop_report.append(row)

    # Economy.
    economy = {}
    for kind, plural, rows_ in (('item', 'items', items), ('weapon', 'weapons', weapons), ('armor', 'armors', armors)):
        economy[plural] = [{'id': i, 'name': name_of(e), 'price': e.get('price'), 'sell_price': e['price'] // 2 if type(e.get('price')) is int else None,
                            'evidence': {'file': t[plural][0], 'path': [i, 'price']}} for i, e in enumerate(rows_) if e]
    shop_rows = shops(data, names)
    for row in shop_rows:
        if row['status'] != 'ok': warn('opaque_shop_good', 'Shop good has unrecognized parameters', row['evidence']); continue
        base, price = row['database_price'], row['price']
        if row['name'] is None: warn('shop_missing_good', 'Shop lists a good absent from the database', row['evidence'], goods_type=row['goods_type'], goods_id=row['goods_id'])
        elif price == 0: warn('shop_free_good', 'Shop sells this good for 0', row['evidence'], goods_type=row['goods_type'], goods_id=row['goods_id'])
        elif base is not None and row['price_type'] == 'specified' and price < base // 2:
            warn('shop_arbitrage', 'Shop price is below the half-price sell value, so buying and selling back earns gold', row['evidence'], goods_type=row['goods_type'], goods_id=row['goods_id'], price=price, sell_price=base // 2)
        elif base is not None and row['price_type'] == 'specified' and price < base:
            warn('shop_below_database_price', 'Shop override is below the database price', row['evidence'], goods_type=row['goods_type'], goods_id=row['goods_id'], price=price, database_price=base)
    counts = {'actors': len(actor_report), 'enemies': len(enemy_stats), 'formulas': len(formula_report),
              'formulas_opaque': sum(1 for r in formula_report if r['status'] == 'opaque'), 'troops': len(troop_report), 'shop_goods': len(shop_rows),
              'actor_vs_enemy_rows': counters['actor_vs_enemy'], 'enemy_vs_actor_rows': counters['enemy_vs_actor'], 'warnings': len(warnings)}
    return {'version': VERSION, 'read_only': True, 'mutation_authorized': False, 'levels_requested': list(levels), 'max_rows': max_rows,
            'variable_defaults': {str(k): v for k, v in sorted(variables.items())}, 'database_files_present': present, 'counts': counts,
            'exp_formula': EXP_NOTE, 'formulas': formula_report[:max_rows], 'formulas_truncated': len(formula_report) > max_rows,
            'actors': actor_report, 'matchups': {
                'actor_vs_enemy': rows['actor_vs_enemy'], 'actor_vs_enemy_total': counters['actor_vs_enemy'], 'actor_vs_enemy_truncated': counters['actor_vs_enemy'] > max_rows,
                'enemy_vs_actor': rows['enemy_vs_actor'], 'enemy_vs_actor_total': counters['enemy_vs_actor'], 'enemy_vs_actor_truncated': counters['enemy_vs_actor'] > max_rows,
                'skipped_rows': counters['skipped']},
            'troops': troop_report[:max_rows], 'troops_truncated': len(troop_report) > max_rows,
            'economy': {k: v[:max_rows] for k, v in economy.items()}, 'economy_truncated': any(len(v) > max_rows for v in economy.values()),
            'shops': shop_rows[:max_rows], 'shops_truncated': len(shop_rows) > max_rows,
            'warnings': warnings[:max_rows], 'warnings_truncated': len(warnings) > max_rows,
            'coverage_complete': True, 'limits': LIMITS}


def markdown(r):
    c = r['counts']; out = ['# VX Ace balance analysis', '', 'Static base values only. Counts: ' + json.dumps(c), '', 'EXP curve: ' + r['exp_formula'], '']
    out += ['## Warnings (heuristic)', ''] + (['- [%s] %s %s' % (w['code'], w['detail'], json.dumps({k: v for k, v in w.items() if k not in ('code', 'detail', 'severity', 'heuristic', 'evidence')})) for w in r['warnings']] or ['- none']) + ['']
    out += ['## Damage formulas', '', '| kind | id | name | type | formula | status |', '|---|---|---|---|---|---|']
    out += ['| %s | %d | %s | %s | `%s` | %s |' % (f['kind'], f['id'], f['name'], f['damage_type'], f['formula'], f['status'] + (': ' + f['reason'] if f.get('reason') else '') +
            (' (v%s defaults)' % f['unresolved_variables'] if f.get('unresolved_variables') else '')) for f in r['formulas']] + ['']
    out += ['## Actors', '']
    for a in r['actors']:
        out += ['### %d %s (class %s, levels %s..%s)' % (a['id'], a['name'], a['class_name'], a['initial_level'], a['max_level']), '', '| lv | total exp | to next | ' + ' | '.join(PARAMS) + ' |', '|' + '---|' * (3 + len(PARAMS))]
        out += ['| %d | %d | %s | %s |' % (p['level'], p['total_exp'], p['exp_to_next'] if p['exp_to_next'] is not None else '-', ' | '.join(str(p['params'][k]) for k in PARAMS)) for p in a['curve']] + ['']
    m = r['matchups']
    out += ['## Actor vs enemy (%d rows%s)' % (m['actor_vs_enemy_total'], ', truncated' if m['actor_vs_enemy_truncated'] else ''), '', '| actor | lv | skill | enemy | damage | hits |', '|---|---|---|---|---|---|']
    out += ['| %s | %d | %s | %s | %d | %s |' % (x['actor'], x['level'], x['skill'], x['enemy'], x['base_damage'], x['hits_to_kill'] if x['hits_to_kill'] is not None else '-') for x in m['actor_vs_enemy']] + ['']
    out += ['## Enemy vs actor (%d rows%s)' % (m['enemy_vs_actor_total'], ', truncated' if m['enemy_vs_actor_truncated'] else ''), '', '| enemy | skill | actor | lv | damage | hits |', '|---|---|---|---|---|---|']
    out += ['| %s | %s | %s | %d | %d | %s |' % (x['enemy'], x['skill'], x['actor'], x['level'], x['base_damage'], x['hits_to_kill'] if x['hits_to_kill'] is not None else '-') for x in m['enemy_vs_actor']] + ['']
    out += ['## Troops', '', '| id | name | members | exp | gold | drops |', '|---|---|---|---|---|---|']
    out += ['| %d | %s | %d | %d | %d | %s |' % (t['id'], t['name'], t['members'], t['total_exp'], t['total_gold'], ', '.join('%s %s (%s)' % (d['goods_type'], d['name'] or d['goods_id'], d['chance']) for d in t['drops'])) for t in r['troops']] + ['']
    out += ['## Shops', '', '| where | good | price | database price | price type |', '|---|---|---|---|---|']
    out += ['| %s | %s %s | %s | %s | %s |' % (json.dumps(s['evidence']['path']) + ' ' + s['evidence']['file'], s.get('goods_type', '?'), s.get('name') or s.get('goods_id', '?'), s.get('price', '?'), s.get('database_price', '?'), s.get('price_type', '?')) for s in r['shops']] + ['']
    out += ['## Prices', ''] + ['- %s: ' % k + ', '.join('%d %s=%s' % (x['id'], x['name'], x['price']) for x in v) for k, v in r['economy'].items()] + ['', '## Limits', ''] + ['- ' + x for x in r['limits']]
    return '\n'.join(out) + '\n'


# --- CLI transaction ---------------------------------------------------------

def guard_output(path, project, index_root, other):
    out = unlinked(path)
    if out.exists(): raise ValueError('Output files must be new')
    if out.suffix.lower() not in ('.json', '.md', '.markdown', '.txt'): raise ValueError('Unexpected report file extension')
    for root in (project, index_root):
        if out == root or root in out.parents: raise ValueError('Report files must be outside the source project and index')
    if other is not None and out == other: raise ValueError('JSON and Markdown paths must differ')
    return out


def run(index, project, json_path, markdown_path, **options):
    project = unlinked(project)
    if project.is_file() and project.suffix.lower() == '.rvproj2': project = project.parent
    if not (project / 'Data').is_dir(): raise ValueError('Expected a VX Ace project')
    if json_path is None and markdown_path is None: raise ValueError('Supply --json and/or --markdown')
    data = Index(index)
    jout = guard_output(json_path, project, data.root, None) if json_path else None
    mout = guard_output(markdown_path, project, data.root, jout) if markdown_path else None
    manifest = data.json('manifest.json')
    files = manifest.get('files') if isinstance(manifest, dict) else None
    if not files or manifest.get('read_only') is not True or any(not isinstance(x, dict) or not re.fullmatch('[0-9a-fA-F]{64}', str(x.get('sha256', ''))) for x in files):
        raise ValueError('A hashed Project Reader manifest is required')
    before = current_inventory(project)
    if verify_fresh(data.root, project)['status'] != 'fresh': raise ValueError('Stale index; re-index the current project')
    result = analyze(data, **options)
    data.unchanged()
    if current_inventory(project) != before: raise ValueError('Source project changed during analysis')
    result.update(source_unchanged=True, read_index_files_unchanged=True, source_freshness='fresh')
    for path, text in ((jout, lambda: json.dumps(result, ensure_ascii=False, indent=2) + '\n'), (mout, lambda: markdown(result))):
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text(), encoding='utf-8')
    return result


def parse_levels(text):
    try: return tuple(int(x) for x in text.split(',') if x.strip())
    except ValueError: raise argparse.ArgumentTypeError('levels must be comma-separated integers')


def parse_var(text):
    match = re.fullmatch(r'(\d+)=(-?\d+(?:\.\d+)?)', text)
    if not match: raise argparse.ArgumentTypeError('--var must look like N=VALUE')
    return int(match[1]), float(match[2]) if '.' in match[2] else int(match[2])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('index'); ap.add_argument('--project', required=True)
    ap.add_argument('--json', help='New JSON report file outside project and index'); ap.add_argument('--markdown', help='New Markdown report file outside project and index')
    ap.add_argument('--levels', type=parse_levels, default=(1, 10, 20, 50), help='Comma-separated actor levels to sample (initial and max levels are always added)')
    ap.add_argument('--var', type=parse_var, action='append', default=[], metavar='N=VALUE', help='Value for v[N] in formulas (default 0)')
    ap.add_argument('--actor', type=int, action='append'); ap.add_argument('--enemy', type=int, action='append')
    ap.add_argument('--max-rows', type=int, default=200)
    a = ap.parse_args(argv)
    try:
        r = run(a.index, a.project, a.json, a.markdown, levels=a.levels, max_rows=a.max_rows, variables=dict(a.var),
                actor_ids=set(a.actor) if a.actor else None, enemy_ids=set(a.enemy) if a.enemy else None)
        print(json.dumps({'status': 'ok', 'counts': r['counts']})); return 0
    except Exception as exc:
        print('Balance analysis refused: ' + str(exc), file=sys.stderr); return 2


if __name__ == '__main__': raise SystemExit(main())
