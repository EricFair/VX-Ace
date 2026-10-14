#!/usr/bin/env python3
"""Compare two VX Ace Project Reader indexes without trusting timestamps/paths."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

VERSION='0.8.0'
INCLUDE_ROOTS=('database','maps','scripts','analysis','codex')

def digest(path: Path) -> str:
    h=hashlib.sha256(); h.update(path.read_bytes()); return h.hexdigest()

def inventory(root: Path) -> dict[str,str]:
    out={}
    for name in INCLUDE_ROOTS:
        base=root/name
        if not base.exists(): continue
        for p in base.rglob('*'):
            if p.is_file(): out[p.relative_to(root).as_posix()]=digest(p)
    return out

def compare(before: Path, after: Path) -> dict:
    a=inventory(before); b=inventory(after)
    keys=sorted(set(a)|set(b))
    added=[k for k in keys if k not in a]
    removed=[k for k in keys if k not in b]
    changed=[k for k in keys if k in a and k in b and a[k]!=b[k]]
    unchanged=sum(1 for k in keys if k in a and k in b and a[k]==b[k])
    return {'version':VERSION,'added':added,'removed':removed,'changed':changed,'unchanged_count':unchanged,'changed_count':len(changed),'added_count':len(added),'removed_count':len(removed)}

def render(r:dict)->str:
    lines=['# VX Ace index diff','',f"Changed: **{r['changed_count']}** · Added: **{r['added_count']}** · Removed: **{r['removed_count']}** · Unchanged: **{r['unchanged_count']}**",'']
    for title,key in [('Changed','changed'),('Added','added'),('Removed','removed')]:
        lines += [f'## {title}','']
        lines += [f'- `{x}`' for x in r[key]] or ['- None']
        lines.append('')
    return '\n'.join(lines)

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('before'); ap.add_argument('after'); ap.add_argument('--json'); ap.add_argument('--markdown'); a=ap.parse_args(argv)
    r=compare(Path(a.before).resolve(),Path(a.after).resolve())
    if a.json: Path(a.json).write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
    if a.markdown: Path(a.markdown).write_text(render(r),encoding='utf-8')
    print(json.dumps(r)); return 0
if __name__=='__main__': raise SystemExit(main())
