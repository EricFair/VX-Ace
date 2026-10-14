#!/usr/bin/env python3
"""Read-only indexed graphics/audio reference checks with explicit optional RTP."""
from __future__ import annotations
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
from vxace_index_query import Index, execute, unlinked

VERSION = '0.16.0'
MAX_ASSET_FILES = 20000
MAX_REFERENCES = 10000
EXTENSIONS = {'Graphics': {'.png', '.jpg', '.jpeg'},
              'Audio': {'.ogg', '.wav', '.mp3', '.mid', '.midi'}}
KNOWN_EXTENSIONS = set.union(*EXTENSIONS.values()) | {'.bmp', '.gif', '.webp', '.wma', '.aac', '.flac', '.m4a'}
FIELDS = {
    'RPG::Actor': {'character_name': 'Characters', 'face_name': 'Faces'},
    'RPG::Enemy': {'battler_name': 'Battlers'},
    'RPG::Animation': {'animation1_name': 'Animations', 'animation2_name': 'Animations'},
    'RPG::Map': {'parallax_name': 'Parallaxes', 'battleback1_name': 'Battlebacks1', 'battleback2_name': 'Battlebacks2'},
    'RPG::System': {'title1_name': 'Titles1', 'title2_name': 'Titles2',
                    'battleback1_name': 'Battlebacks1', 'battleback2_name': 'Battlebacks2', 'battler_name': 'Battlers'},
    'RPG::System::Vehicle': {'character_name': 'Characters'},
    'RPG::Event::Page::Graphic': {'character_name': 'Characters'},
}
LIMITS = [
    'Checks indexed database/map/event references, including inactive content; not runtime reachability.',
    'Does not evaluate scripts, note tags, dynamic names, encrypted archives or implicit engine assets.',
    'Presence and filename casing only; format decoding, sound playback, dimensions and licensing are not validated.',
    'No supplied RTP means unresolved files remain uncertain, not proven missing.',
    'Multiple matching files/formats remain ambiguous; no engine extension-priority claim is made.',
    'Asset names and file size/mtime metadata are rechecked, not full RTP file hashes.',
]


def safe_name(name):
    if not isinstance(name, str) or len(name) > 512 or any(ord(c) < 32 for c in name):
        return False
    parts = name.replace('\\', '/').split('/')
    return bool(name) and not any(p in ('', '.', '..') or any(c in p for c in ':*?"<>|') for p in parts)


def catalog(root):
    root = unlinked(root)
    if not root.is_dir():
        raise ValueError('Asset root is not a directory')
    entries, snapshot = {}, {}
    # Walk only Graphics/Audio, but preserve actual root/folder casing.
    for n, top in enumerate(root.iterdir()):
        if n >= MAX_ASSET_FILES:
            raise ValueError('Asset root entry budget exceeded')
        if top.name.casefold() not in ('graphics', 'audio'):
            continue
        unlinked(top)
        if not top.is_dir():
            continue
        pending = [(top, 0)]; visited = 0
        while pending:
            directory, depth = pending.pop()
            if depth > 32:
                raise ValueError('Asset directory depth budget exceeded')
            with os.scandir(directory) as children:
                for child in children:
                    visited += 1
                    if visited > MAX_ASSET_FILES:
                        raise ValueError('Asset entry budget exceeded')
                    file = unlinked(child.path)
                    if file.is_dir():
                        pending.append((file, depth + 1)); continue
                    stat = file.stat()
                    if not file.is_file():
                        raise ValueError('Non-regular asset file')
                    relative = file.relative_to(root).as_posix()
                    snapshot[relative] = (stat.st_size, stat.st_mtime_ns)
                    if len(snapshot) > MAX_ASSET_FILES:
                        raise ValueError('Asset file budget exceeded')
                    # RTP tileset .txt sidecars are metadata, not competing images.
                    if file.suffix.lower() in KNOWN_EXTENSIONS:
                        entries.setdefault(str(Path(relative).with_suffix('')).replace('\\', '/').casefold(), []).append(relative)
    return entries, snapshot


def references(data):
    found = []
    def add(folder, name, file, path, audio=False):
        if name == '':
            return
        if len(found) >= MAX_REFERENCES:
            raise ValueError('Asset reference budget exceeded')
        found.append({'folder': ('Audio/' if audio else 'Graphics/') + folder,
                      'name': name, 'evidence': {'file': file, 'path': path}})
    def walk(obj, file, path=()):
        data.spend()
        if len(path) > 128:
            raise ValueError('Asset reference nesting budget exceeded')
        if isinstance(obj, dict):
            cls = obj.get('__class__')
            if cls in ('Table', 'Color', 'Tone'):
                return
            if cls in ('RPG::BGM', 'RPG::BGS', 'RPG::ME', 'RPG::SE'):
                add(cls.split('::')[-1], obj.get('name'), file, [*path, 'name'], True)
            for field, folder in FIELDS.get(cls, {}).items():
                if field in obj:
                    if cls == 'RPG::Event::Page::Graphic' and obj.get('tile_id', 0) != 0:
                        continue
                    add(folder, obj[field], file, [*path, field])
            if cls == 'RPG::Tileset':
                names = obj.get('tileset_names')
                if not isinstance(names, list):
                    raise ValueError('Opaque tileset sheet references')
                for i, name in enumerate(names):
                    add('Tilesets', name, file, [*path, 'tileset_names', i])
            if cls in ('RPG::EventCommand', 'RPG::MoveCommand'):
                code = obj.get('code'); params = obj.get('parameters')
                positions = ({101: [(0, 'Faces')], 231: [(1, 'Pictures')],
                              283: [(0, 'Battlebacks1'), (1, 'Battlebacks2')],
                              284: [(0, 'Parallaxes')], 322: [(1, 'Characters'), (3, 'Faces')],
                              323: [(1, 'Characters')]} if cls == 'RPG::EventCommand' else {41: [(0, 'Characters')]})
                if code in positions:
                    if not isinstance(params, list):
                        raise ValueError('Opaque event asset parameters')
                    for i, folder in positions[code]:
                        if len(params) <= i:
                            raise ValueError('Incomplete event asset parameters')
                        add(folder, params[i], file, [*path, 'parameters', i])
            for key, value in obj.items():
                if not key.startswith('__'):
                    walk(value, file, (*path, key))
        elif isinstance(obj, list):
            for i, value in enumerate(obj):
                walk(value, file, (*path, i))
    for directory in ('database', 'maps'):
        for file in data.paths(directory):
            walk(data.json(file), file)
    return found


def audit(index, project, rtp=None):
    data = index if isinstance(index, Index) else Index(index)
    project = unlinked(project)
    roots = [('project', project)]
    if rtp is not None:
        rtp = unlinked(rtp)
        if rtp == project or project in rtp.parents or rtp in project.parents:
            raise ValueError('RTP must be a separate explicit directory')
        if not rtp.is_dir() or not any(unlinked(p).is_dir() for p in rtp.iterdir()
                                      if p.name.casefold() in ('graphics', 'audio')):
            raise ValueError('RTP root must contain Graphics/ or Audio/')
        roots.append(('rtp', rtp))
    catalogs = [(label, root, *catalog(root)) for label, root in roots]
    unique = {}
    for ref in references(data):
        name = ref['name']
        if not isinstance(name, str):
            name = None
        key = (ref['folder'], name)
        if key not in unique:
            if len(unique) >= 2000:
                raise ValueError('Distinct asset report budget exceeded')
            unique[key] = {'folder': ref['folder'], 'name': name, 'reference_count': 0, 'evidence': []}
        row = unique[key]; row['reference_count'] += 1
        if len(row['evidence']) < 3:
            row['evidence'].append(ref['evidence'])
    for (folder, name), row in unique.items():
        row['matches'] = []
        if name is None:
            row['status'] = 'opaque_reference'; continue
        if not safe_name(name):
            row['status'] = 'unsafe_reference'; continue
        wanted = folder + '/' + name.replace('\\', '/')
        suffix = Path(wanted).suffix.lower()
        explicit_extension = suffix if suffix in KNOWN_EXTENSIONS else ''
        key = str(Path(wanted).with_suffix('')).replace('\\', '/') if explicit_extension else wanted
        for label, root, entries, _ in catalogs:
            matches = entries.get(key.casefold(), [])
            if explicit_extension:
                matches = [x for x in matches if Path(x).suffix.lower() == explicit_extension]
            if not matches:
                continue
            row['matches'] = [{'source': label, 'path': x} for x in sorted(matches)[:8]]
            if len(matches) > 1:
                row['status'] = 'ambiguous'; break
            actual = matches[0]; extension = Path(actual).suffix.lower()
            if extension not in EXTENSIONS[folder.split('/')[0]]:
                row['status'] = 'unverified_extension'; break
            expected = wanted if explicit_extension else wanted + extension
            row['status'] = 'found' if actual == expected else 'case_mismatch'
            break
        else:
            row['status'] = 'missing' if rtp is not None else 'unresolved_without_rtp'
    data.unchanged()
    for label, root, _, before in catalogs:
        if catalog(root)[1] != before:
            raise ValueError('Asset names/metadata changed during audit')
    rows = list(unique.values())
    return {'version': VERSION, 'read_only': True, 'mutation_authorized': False,
            'rtp_supplied': rtp is not None, 'asset_names_and_metadata_unchanged': True,
            'references': rows, 'counts': dict(Counter(x['status'] for x in rows)),
            'limits': LIMITS}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('index'); ap.add_argument('--project', required=True); ap.add_argument('--output', required=True)
    ap.add_argument('--rtp', help='Explicit unpacked RTP root containing Graphics/ and Audio/')
    a = ap.parse_args(argv)
    try:
        project = unlinked(a.project)
        if project.is_file() and project.suffix.lower() == '.rvproj2':
            project = project.parent
        if a.rtp is not None:
            rtp = unlinked(a.rtp); output = unlinked(a.output)
            if output == rtp or rtp in output.parents:
                raise ValueError('Asset reports must be outside the read-only RTP root')
        result = execute(a.index, project, a.output, lambda data: audit(data, project, a.rtp), 'asset-audit')
        lines = ['# VX Ace asset references', '', 'Presence/casing checks only. See JSON for evidence.', '',
                 'Counts: ' + json.dumps(result['counts']), '']
        for row in result['references']:
            if row['status'] != 'found':
                lines.append('- ' + json.dumps({k: row[k] for k in ('status', 'folder', 'name')}, ensure_ascii=False))
        lines += ['', '## Limits', ''] + ['- ' + x for x in LIMITS]
        (Path(a.output) / 'asset-audit.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        review = any(x['status'] != 'found' for x in result['references'])
        print(json.dumps({'status': 'review_required' if review else 'ok', 'counts': result['counts']}))
        return 3 if review else 0
    except Exception as exc:
        print('Asset audit refused: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
