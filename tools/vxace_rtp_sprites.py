#!/usr/bin/env python3
"""Look up stock RTP character sprites by description (catalogue: tools/data/rtp_sprites.json) and resolve recipe {"sprite": ...} graphics."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys

VERSION = '1.0.0'
CATALOGUE = Path(__file__).resolve().parent / 'data' / 'rtp_sprites.json'
MAX_CANDIDATES = 10
SPRITE_KEYS = {'sprite', 'direction', 'pattern'}


class SpriteError(ValueError):
    pass


def load_catalogue(path=None):
    return json.loads(Path(path or CATALOGUE).read_text(encoding='utf-8'))


def entries(catalogue):
    """One row per (sheet, description); identical descriptions of several indices share a row (`indices` is a list)."""
    out = []
    for sheet in catalogue['sheets']:
        groups = {}
        for index, text in sheet['indices'].items():
            groups.setdefault(text, []).append(int(index))
        for text, indices in groups.items():
            out.append({'sheet': sheet['sheet'], 'indices': sorted(indices), 'text': text, 'single': sheet['single'], 'object': sheet['object']})
        for direction, text in (sheet.get('directions') or {}).items():
            out.append({'sheet': sheet['sheet'], 'indices': [0], 'text': text, 'single': True, 'object': sheet['object'], 'direction': int(direction)})
    return out


def words(text):
    return re.findall(r'[a-z0-9]+', text.lower())


def matches(query, catalogue=None):
    """Entries whose description (plus sheet name) contains every query word as a word prefix."""
    needed = words(query)
    if not needed:
        return []
    found = []
    for row in entries(catalogue or load_catalogue()):
        have = words(row['text'] + ' ' + row['sheet'])
        if all(any(h.startswith(w) for h in have) for w in needed):
            found.append(row)
    return found


def label(row):
    where = '%s %s' % (row['sheet'], '-'.join(map(str, row['indices'])) if len(row['indices']) == 1 else '%d..%d' % (row['indices'][0], row['indices'][-1]))
    if 'direction' in row:
        where += ' (direction %d)' % row['direction']
    return '%s: %s' % (where, row['text'])


def resolve_sprite(query, catalogue=None):
    """Return {'character_name', 'character_index', 'description', 'query'} for a unique match, else raise SpriteError listing candidates.
    An exact "Sheet:index" (e.g. "Monster3:4") always resolves."""
    if not isinstance(query, str) or not query.strip():
        raise SpriteError('sprite must be a non-empty description')
    catalogue = catalogue or load_catalogue()
    exact = re.fullmatch(r'\s*([^:\s]+)\s*:\s*(\d)\s*', query)
    if exact:
        for sheet in catalogue['sheets']:
            if sheet['sheet'].lower() == exact.group(1).lower():
                index = exact.group(2)
                if index not in sheet['indices']:
                    raise SpriteError('sheet %s has no index %s' % (sheet['sheet'], index))
                return {'character_name': sheet['sheet'], 'character_index': int(index), 'description': sheet['indices'][index], 'query': query}
        raise SpriteError('no RTP character sheet named %s' % exact.group(1))
    found = matches(query, catalogue)
    if not found:
        raise SpriteError('no RTP sprite matches "%s"; try other words or see references/rtp-sprites.md' % query)
    if len(found) > 1 or len(found[0]['indices']) > 1 or 'direction' in found[0]:
        shown = found[:MAX_CANDIDATES]
        extra = '' if len(found) <= MAX_CANDIDATES else ' (+%d more)' % (len(found) - MAX_CANDIDATES)
        if len(found) == 1:
            raise SpriteError('"%s" matches %s; give "Sheet:index" for one sprite' % (query, label(found[0])))
        raise SpriteError('"%s" matches %d sprites; be more specific or use "Sheet:index". Candidates: ' % (query, len(found)) + ' | '.join(label(r) for r in shown) + extra)
    row = found[0]
    return {'character_name': row['sheet'], 'character_index': row['indices'][0], 'description': row['text'], 'query': query}


def resolve_graphic(graphic, catalogue=None):
    """A `{"sprite": ...}` graphic becomes the exact four-field graphic; other graphics are returned unchanged (second value None)."""
    if not isinstance(graphic, dict) or 'sprite' not in graphic:
        return graphic, None
    extra = set(graphic) - SPRITE_KEYS
    if extra:
        raise SpriteError('a sprite graphic only takes sprite, direction and pattern (not %s)' % ', '.join(sorted(extra)))
    found = resolve_sprite(graphic['sprite'], catalogue)
    direction, pattern = graphic.get('direction', 2), graphic.get('pattern', 1)
    if type(direction) is not int or direction not in (2, 4, 6, 8) or type(pattern) is not int or not 0 <= pattern <= 2:
        raise SpriteError('sprite direction must be 2, 4, 6 or 8 and pattern 0..2')
    return ({'character_name': found['character_name'], 'character_index': found['character_index'], 'direction': direction, 'pattern': pattern},
            {'query': found['query'], 'sheet': found['character_name'], 'index': found['character_index'], 'description': found['description']})


def resolve_recipe_sprites(node, notes, where='recipe'):
    """Walk a loaded recipe and replace every {"sprite": ...} graphic in place; `notes` collects what was resolved."""
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if key == 'graphic' and isinstance(value, dict) and 'sprite' in value:
                try:
                    node[key], note = resolve_graphic(value)
                except SpriteError as error:
                    raise SpriteError('%s: %s' % (where, error))
                notes.append({'where': where, **note})
            else:
                resolve_recipe_sprites(value, notes, '%s.%s' % (where, key))
    elif isinstance(node, list):
        for number, item in enumerate(node):
            resolve_recipe_sprites(item, notes, '%s[%d]' % (where, number) if where != 'steps' else 'step %d' % (number + 1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('words', nargs='*', help='description words, or Sheet:index')
    ap.add_argument('--sheet', help='list one sheet'); ap.add_argument('--list', action='store_true', help='list every sheet name')
    a = ap.parse_args(argv)
    catalogue = load_catalogue()
    if a.list:
        for sheet in catalogue['sheets']:
            print(sheet['sheet'] + (' (object)' if sheet['object'] else '') + (' (single)' if sheet['single'] else ''))
        return 0
    if a.sheet:
        rows = [r for r in entries(catalogue) if r['sheet'].lower() == a.sheet.lower()]
        for row in rows: print(label(row))
        return 0 if rows else 1
    query = ' '.join(a.words)
    try:
        print(json.dumps(resolve_sprite(query, catalogue)))
        return 0
    except SpriteError as error:
        print('Sprite lookup refused: ' + str(error), file=sys.stderr)
        for row in matches(query, catalogue)[:MAX_CANDIDATES]: print(label(row))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
