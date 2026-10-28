import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from vxace_balance import EvalError, Opaque, analyze, base_value, exp_for_level, main, parse, unresolved
from vxace_copy_patcher import current_inventory
from vxace_index_query import Index


def calc(text, a=None, b=None, variables=None):
    return base_value(parse(text), a or {}, b or {}, variables)


def command(code, parameters=None):
    return {'__class__': 'RPG::EventCommand', 'code': code, 'indent': 0, 'parameters': parameters or []}


def table(rows):
    return {'__class__': 'Table', 'dimensions': 2, 'xsize': 8, 'ysize': len(rows), 'zsize': 1, 'data': [v for row in rows for v in row]}


class FormulaTests(unittest.TestCase):
    def test_ruby_integer_semantics(self):
        self.assertEqual(calc('7 / 2'), 3)
        self.assertEqual(calc('-7 / 2'), -4)
        self.assertEqual(calc('7 / 2.0'), 3)  # 3.5 truncated like to_i
        self.assertEqual(calc('-7 % 3'), 2)
        self.assertEqual(calc('2 + 3 * 4 - (1 + 1) * 2'), 10)
        self.assertEqual(calc('-(3 + 2) * 2'), -10)
        self.assertEqual(calc('a.atk * 4 - b.def * 2', {'atk': 20}, {'def': 5}), 70)
        self.assertEqual(calc('a.atk / 3', {'atk': 10}), 3)
        self.assertEqual(calc('a.atk / 3.0 * 3', {'atk': 10}), 10)

    def test_division_by_zero_is_an_error_not_a_guess(self):
        with self.assertRaisesRegex(EvalError, 'zero'): calc('1 / 0')
        with self.assertRaises(EvalError): calc('a.atk / (a.def - a.def)', {'atk': 1, 'def': 1})

    def test_variable_reference_is_flagged_and_defaulted(self):
        tree = parse('a.atk * 4 + v[12] * 2')
        self.assertEqual(unresolved(tree), {12})
        self.assertEqual(base_value(tree, {'atk': 5}, {}), 20)
        self.assertEqual(base_value(tree, {'atk': 5}, {}, {12: 10}), 40)

    def test_opaque_formulas_never_evaluate(self):
        for text, reason in (('rand(10)', 'random'), ('a.atk > 3 ? 1 : 2', 'conditional'), ('x = 5; x', 'statement'),
                             ('b.states.size', 'state'), ('a.atk ** 2', 'exponent'), ('a.skill_level(1)', 'unsupported'),
                             ('Math.sqrt(4)', 'method'), ('a.foo', 'unsupported'), ('$game_variables[1]', 'global'), ('', 'empty'),
                             ('1 +', 'incomplete'), ('(1', 'parenthesis')):
            with self.subTest(text=text):
                with self.assertRaises(Opaque) as ctx: parse(text)
                self.assertIn(reason, str(ctx.exception))
        with self.assertRaises(Opaque): parse(None)
        with self.assertRaises(Opaque): parse('1' * 600)

    def test_missing_attribute_for_battler_is_an_eval_error(self):
        with self.assertRaisesRegex(EvalError, 'unavailable'): calc('b.level', {}, {'atk': 1})


class ExpTests(unittest.TestCase):
    def test_default_formula(self):
        params = [30, 20, 30, 30]
        self.assertEqual(exp_for_level(1, params), 0)
        lv = 2.0
        expected = round(30 * ((lv - 1) ** (0.9 + 30 / 250.0)) * lv * (lv + 1) / (6 + lv ** 2 / 50.0 / 30) + 20)
        self.assertEqual(exp_for_level(2, params), expected)
        self.assertGreater(exp_for_level(50, params), exp_for_level(49, params))

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError): exp_for_level(0, [1, 1, 1, 1])
        with self.assertRaises(ValueError): exp_for_level(5, [1, 1, 1])
        with self.assertRaises(ValueError): exp_for_level(5, [1, 1, 1, 0])


class IndexCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.index = self.base / 'index'; self.game = self.base / 'game'
        (self.game / 'Data').mkdir(parents=True); (self.game / 'Data/Actors.rvdata2').write_bytes(b'hashed fixture only')
        (self.index / 'maps').mkdir(parents=True)
        self.write('project.json', {'errors': [], 'map_count': 1, 'database_files_decoded': ['Actors.rvdata2']})
        rows = [[0] * 8] + [[100 + 10 * lv, 20, 10 + 2 * lv, 5 + lv, 8, 8, 10, 10] for lv in range(1, 51)]
        dmg = lambda t, f: {'__class__': 'RPG::UsableItem::Damage', 'type': t, 'element_id': 0, 'formula': f, 'variance': 20, 'critical': False}
        self.write('database/actors.json', [None, {'__class__': 'RPG::Actor', 'id': 1, 'name': 'Hero', 'class_id': 1, 'initial_level': 1, 'max_level': 40}])
        self.write('database/classes.json', [None, {'__class__': 'RPG::Class', 'id': 1, 'name': 'Fighter', 'params': table(rows), 'exp_params': [30, 20, 30, 30],
                                                    'learnings': [{'level': 5, 'skill_id': 2}, {'level': 10, 'skill_id': 3}]}])
        self.write('database/skills.json', [None,
            {'id': 1, 'name': 'Attack', 'damage': dmg(1, 'a.atk * 4 - b.def * 2')},
            {'id': 2, 'name': 'Power', 'damage': dmg(1, 'a.atk * 40 - v[1] * 2')},
            {'id': 3, 'name': 'Gamble', 'damage': dmg(1, 'a.atk * rand(3)')},
            {'id': 4, 'name': 'Bite', 'damage': dmg(1, 'a.atk * 2 - b.def')},
            {'id': 5, 'name': 'Heal', 'damage': dmg(3, 'a.mat * 2')}])
        self.write('database/items.json', [None, {'id': 1, 'name': 'Potion', 'price': 50, 'damage': dmg(0, '0')},
                                           {'id': 2, 'name': 'Bomb', 'price': 100, 'damage': dmg(1, '100')}])
        self.write('database/weapons.json', [None, {'id': 1, 'name': 'Sword', 'price': 300}])
        self.write('database/armors.json', [None, {'id': 1, 'name': 'Shield', 'price': 200}])
        self.write('database/enemies.json', [None,
            {'id': 1, 'name': 'Slime', 'params': [30, 0, 5, 20, 0, 0, 5, 5], 'exp': 10, 'gold': 5,
             'drop_items': [{'kind': 1, 'data_id': 1, 'denominator': 4}, {'kind': 0, 'data_id': 1, 'denominator': 1}], 'actions': [{'skill_id': 1}]},
            {'id': 2, 'name': 'Golem', 'params': [500000, 0, 60, 30, 0, 0, 5, 5], 'exp': 100, 'gold': 50, 'drop_items': [], 'actions': [{'skill_id': 4}]}])
        self.write('database/troops.json', [None, {'__class__': 'RPG::Troop', 'id': 1, 'name': 'Slimes',
                                                   'members': [{'enemy_id': 1}, {'enemy_id': 1}, {'enemy_id': 9}], 'pages': [{'list': [command(0)]}]}])
        self.write('database/common-events.json', [None, {'__class__': 'RPG::CommonEvent', 'id': 1, 'trigger': 0, 'list': [
            command(302, [0, 1, 1, 10, 0]), command(605, [1, 1, 0, 0]), command(605, [2, 1, 1, 0]), command(0)]}])
        page = {'list': [command(302, [0, 1, 0, 0, 0]), command(605, [1, 1, 1, 400]), command(0)]}
        self.write('maps/map-001.json', {'__class__': 'RPG::Map', 'events': {'1': {'__class__': 'RPG::Event', 'id': 1, 'pages': [page]}}})
        self.refresh()

    def write(self, name, value):
        file = self.index / name; file.parent.mkdir(parents=True, exist_ok=True); file.write_text(json.dumps(value), encoding='utf-8')

    def refresh(self):
        self.write('manifest.json', {'read_only': True, 'files': [{'path': k, 'sha256': v} for k, v in current_inventory(self.game).items()]})


class EndToEndTests(IndexCase):
    def test_analysis(self):
        r = analyze(Index(self.index), levels=(1, 10), variables={})
        self.assertFalse(r['mutation_authorized'])
        hero = r['actors'][0]
        self.assertEqual([p['level'] for p in hero['curve']], [1, 10, 20, 30, 40])
        self.assertEqual(hero['curve'][0]['total_exp'], 0)
        self.assertEqual(hero['curve'][1]['params']['mhp'], 200)
        self.assertIn('verify against', hero['exp_formula'])
        by = {(f['kind'], f['id']): f for f in r['formulas']}
        self.assertEqual(by[('skill', 3)]['status'], 'opaque'); self.assertEqual(by[('skill', 2)]['unresolved_variables'], [1])
        self.assertEqual(by[('item', 2)]['status'], 'evaluable')
        rows = {(x['level'], x['skill_id'], x['enemy_id']): x for x in r['matchups']['actor_vs_enemy']}
        self.assertEqual(rows[(1, 1, 1)]['base_damage'], 8)  # atk 12 * 4 - def 20 * 2
        self.assertEqual(rows[(1, 1, 1)]['hits_to_kill'], 4)
        self.assertEqual(rows[(10, 1, 2)]['base_damage'], 60); self.assertEqual(rows[(10, 1, 2)]['hits_to_kill'], 8334)
        self.assertEqual(rows[(1, 1, 2)]['hits_to_kill'], None)  # negative base damage
        self.assertNotIn((1, 2, 1), rows)  # Power is learned at level 5
        self.assertEqual(rows[(10, 2, 1)]['unresolved_variables'], [1])
        self.assertFalse(any(x['skill_id'] == 3 for x in r['matchups']['actor_vs_enemy']))
        self.assertTrue(any(x['skill_id'] == 4 and x['actor_mhp'] == 110 for x in r['matchups']['enemy_vs_actor']))

    def test_troops_economy_and_warnings(self):
        r = analyze(Index(self.index))
        troop = r['troops'][0]
        self.assertEqual((troop['total_exp'], troop['total_gold'], troop['missing_enemy_ids']), (20, 10, [9]))
        self.assertEqual(troop['drops'][0]['name'], 'Potion'); self.assertEqual(troop['drops'][0]['chance'], 0.25)
        self.assertEqual(len(troop['drops']), 2)  # the kind 0 'none' slot is ignored
        self.assertEqual(len(r['shops']), 5)
        common = [s for s in r['shops'] if s['evidence'].get('common_event_id') == 1]
        self.assertEqual([(s['goods_type'], s['price']) for s in common], [('item', 10), ('weapon', 300), ('armor', 0)])
        self.assertEqual(common[0]['evidence']['path'], [1, 'list', 0])
        codes = {w['code'] for w in r['warnings']}
        self.assertTrue({'troop_missing_enemy', 'shop_arbitrage', 'shop_free_good', 'many_hits_to_kill', 'nonpositive_damage', 'enemy_one_shots_actor'} <= codes)
        self.assertTrue(all(w['heuristic'] for w in r['warnings']))

    def test_row_budget_truncates_output_but_not_counts(self):
        r = analyze(Index(self.index), max_rows=2)
        self.assertEqual(len(r['matchups']['actor_vs_enemy']), 2); self.assertTrue(r['matchups']['actor_vs_enemy_truncated'])
        self.assertGreater(r['counts']['actor_vs_enemy_rows'], 2)

    def test_cli_outputs_and_stale_refusal(self):
        before = (current_inventory(self.game), current_inventory(self.index))
        j, m = self.base / 'out/balance.json', self.base / 'out/balance.md'
        args = [str(self.index), '--project', str(self.game), '--json', str(j), '--markdown', str(m), '--var', '1=5']
        self.assertEqual(main(args), 0)
        self.assertEqual(before, (current_inventory(self.game), current_inventory(self.index)))
        report = json.loads(j.read_text(encoding='utf-8'))
        self.assertTrue(report['source_unchanged']); self.assertEqual(report['variable_defaults'], {'1': 5})
        self.assertIn('Static base values only', m.read_text(encoding='utf-8'))
        self.assertEqual(main(args), 2)  # outputs already exist
        (self.game / 'Data/new.txt').write_text('x')
        args[args.index(str(j))] = str(self.base / 'out/stale.json'); args[args.index(str(m))] = str(self.base / 'out/stale.md')
        self.assertEqual(main(args), 2); self.assertFalse((self.base / 'out/stale.json').exists())

    def test_output_inside_project_or_index_is_refused(self):
        for target in (self.game / 'report.json', self.game / 'Data/report.md', self.index / 'report.json', self.index / 'sub/report.md'):
            with self.subTest(target=target):
                flag = '--json' if target.suffix == '.json' else '--markdown'
                self.assertEqual(main([str(self.index), '--project', str(self.game), flag, str(target)]), 2)
                self.assertFalse(target.exists())
        same = str(self.base / 'same.json')
        self.assertEqual(main([str(self.index), '--project', str(self.game), '--json', same, '--markdown', same]), 2)
        self.assertEqual(main([str(self.index), '--project', str(self.game)]), 2)


if __name__ == '__main__':
    unittest.main()
