#!/usr/bin/env python3
"""Find the installed RPG Maker VX Ace RTP (read-only); shared by every tool that takes --rtp."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import sys

VERSION = '1.0.0'
ENV_DISABLE = 'VXACE_NO_RTP_AUTODETECT'
REGISTRY_KEYS = (('HKLM', r'SOFTWARE\WOW6432Node\Enterbrain\RGSS3\RTP'), ('HKLM', r'SOFTWARE\Enterbrain\RGSS3\RTP'))
COMMON_PATHS = (r'C:\Program Files (x86)\Common Files\Enterbrain\RGSS3\RPGVXAce',
                r'C:\Program Files\Common Files\Enterbrain\RGSS3\RPGVXAce')
STEAM_DEFAULTS = (r'C:\Program Files (x86)\Steam', r'C:\Program Files\Steam')
STEAM_RTP = ('steamapps', 'common', 'RPGVXAce', 'rtp')
DEFAULT_NAME = 'RPGVXAce'


def autodetect_disabled():
    return os.environ.get(ENV_DISABLE, '').strip().lower() in ('1', 'true', 'yes')


def valid_rtp(path):
    """An RTP root has Graphics/ or Audio/ (any casing)."""
    try:
        path = Path(path)
        return path.is_dir() and any(p.is_dir() and p.name.casefold() in ('graphics', 'audio') for p in path.iterdir())
    except OSError:
        return False


def game_ini_rtp(project):
    """The RTP= name from Game.ini, or None."""
    project = Path(project)
    if project.is_file():
        project = project.parent
    ini = next((p for p in project.iterdir() if p.is_file() and p.name.casefold() == 'game.ini'), None) if project.is_dir() else None
    if ini is None:
        return None
    for line in ini.read_bytes().decode('utf-8', 'replace').splitlines():
        match = re.match(r'\s*RTP\s*=\s*(.*?)\s*$', line, re.I)
        if match:
            return match.group(1) or None
    return None


def registry_value(hive, key, name):
    """Read one registry string value; None when absent or off Windows. Isolated so tests can mock it."""
    if sys.platform != 'win32':
        return None
    try:
        import winreg
        root = {'HKLM': winreg.HKEY_LOCAL_MACHINE, 'HKCU': winreg.HKEY_CURRENT_USER}[hive]
        with winreg.OpenKey(root, key) as handle:
            value, kind = winreg.QueryValueEx(handle, name)
        return value if isinstance(value, str) and value else None
    except OSError:
        return None


def steam_libraries():
    """Steam library roots: the Steam folder itself plus the paths listed in libraryfolders.vdf."""
    homes = []
    for hive, key in (('HKCU', r'Software\Valve\Steam'), ('HKLM', r'SOFTWARE\WOW6432Node\Valve\Steam')):
        for name in ('SteamPath', 'InstallPath'):
            value = registry_value(hive, key, name)
            if value:
                homes.append(value)
    homes += list(STEAM_DEFAULTS)
    libraries, seen = [], set()
    def add(text):
        folder = Path(text)
        marker = str(folder).casefold()
        if marker not in seen:
            seen.add(marker); libraries.append(folder)
    for home in homes:
        add(home)
        vdf = Path(home) / 'steamapps' / 'libraryfolders.vdf'
        try:
            text = vdf.read_text(encoding='utf-8', errors='replace') if vdf.is_file() else ''
        except OSError:
            text = ''
        for match in re.finditer(r'"path"\s+"([^"]+)"', text):
            add(match.group(1).replace('\\\\', '\\'))
    return libraries


def find_rtp(project=None, explicit=None, autodetect=True):
    """Resolve the RTP root. Returns {'path': Path|None, 'source': str, 'tried': [...]}.

    Order: explicit --rtp; Game.ini RTP= name in the registry (WOW6432Node, then native); Steam libraries; the
    Enterbrain common-files folder. `autodetect=False` (or env VXACE_NO_RTP_AUTODETECT=1) skips everything but an explicit path.
    """
    tried = []
    if explicit:
        path = Path(explicit)
        tried.append('explicit ' + str(path))
        return {'path': path, 'source': 'explicit', 'tried': tried}
    if not autodetect or autodetect_disabled():
        return {'path': None, 'source': 'autodetect-disabled', 'tried': tried}
    name = game_ini_rtp(project) if project is not None else None
    if name:
        for hive, key in REGISTRY_KEYS:
            value = registry_value(hive, key, name)
            tried.append('registry %s\\%s [%s]' % (hive, key, name))
            if value and valid_rtp(value):
                return {'path': Path(value), 'source': 'registry %s\\%s' % (hive, key), 'tried': tried}
    for library in steam_libraries():
        candidate = library.joinpath(*STEAM_RTP)
        tried.append('steam ' + str(candidate))
        if valid_rtp(candidate):
            return {'path': candidate, 'source': 'steam library ' + str(library), 'tried': tried}
    for text in COMMON_PATHS:
        tried.append('common ' + text)
        if valid_rtp(text):
            return {'path': Path(text), 'source': 'common path ' + text, 'tried': tried}
    return {'path': None, 'source': 'not-found', 'tried': tried}


def add_arguments(parser):
    parser.add_argument('--no-rtp-autodetect', action='store_true', help='Do not look for the installed RTP when --rtp is omitted (deterministic runs)')


def resolve(project, explicit, no_autodetect=False, announce=True):
    """CLI helper: returns the RTP path (or None) and prints the source on stderr when one was auto-detected."""
    found = find_rtp(project, explicit, not no_autodetect)
    if announce and found['source'] not in ('explicit', 'autodetect-disabled'):
        print('RTP: ' + (str(found['path']) + ' (' + found['source'] + ')' if found['path'] else 'not found (' + str(len(found['tried'])) + ' places tried)'), file=sys.stderr)
    return found['path'] if found['path'] is None else str(found['path']), found


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('project', nargs='?'); ap.add_argument('--rtp'); add_arguments(ap)
    a = ap.parse_args(argv)
    found = find_rtp(a.project, a.rtp, not a.no_rtp_autodetect)
    print(json.dumps({'path': str(found['path']) if found['path'] else None, 'source': found['source'], 'tried': found['tried']}, indent=2))
    return 0 if found['path'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
