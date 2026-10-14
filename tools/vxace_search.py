#!/usr/bin/env python3
"""Bounded literal text/command search in a fresh VX Ace index; never execute code."""
from __future__ import annotations
import argparse
import json
import sys
from vxace_index_query import Index, execute

SCOPES = ('events','database','maps','scripts')


def candidates(data, scopes, code=None):
    if 'events' in scopes:
        for loc,file,path,page,_ in data.event_lists():
            for n,cmd in enumerate(page['list']):
                data.spend()
                if not isinstance(cmd,dict) or cmd.get('__class__')!='RPG::EventCommand' or type(cmd.get('code')) is not int or not isinstance(cmd.get('parameters'),list):
                    raise ValueError('Opaque command cannot be searched completely')
                if code is not None and cmd['code'] != code: continue
                evidence={'scope':'events','file':file,'path':path+['list',n],**loc,'command_index':n,'command_code':cmd['code']}
                evidence['scope']='events'; evidence['event_scope']=loc['scope']
                yield evidence, None  # A code-only search has one hit per native command.
                for nested,text in data.strings(cmd.get('parameters'),('parameters',)):
                    yield {**evidence,'path':evidence['path']+nested},text
    if 'database' in scopes and code is None:
        for file in data.paths('database'):
            root=data.json(file)
            # Event commands are covered by events; tile tables are not text.
            def fields(value,path=()):
                data.spend()
                if len(path)>128: raise ValueError('Index nesting budget exceeded')
                if isinstance(value,str): yield list(path),value
                elif isinstance(value,list):
                    for n,item in enumerate(value): yield from fields(item,(*path,n))
                elif isinstance(value,dict):
                    for key,item in value.items():
                        if len(key)>256: raise ValueError('Oversized evidence key')
                        if not key.startswith('__') and key not in ('pages','list','data'):
                            yield from fields(item,(*path,key))
            for path,text in fields(root): yield {'scope':'database','file':file,'path':path},text
    if 'maps' in scopes and code is None:
        for file in data.paths('maps','map-*.json'):
            root=data.json(file)
            for key in ('display_name','note'):
                if isinstance(root.get(key),str): yield {'scope':'maps','file':file,'path':[key]},root[key]
            for key,event in sorted(root.get('events',{}).items()):
                data.spend()
                if isinstance(event,dict) and isinstance(event.get('name'),str):
                    yield {'scope':'maps','file':file,'path':['events',key,'name']},event['name']
    if 'scripts' in scopes and code is None:
        order=data.json('scripts/order.json')
        if not isinstance(order,dict) or not isinstance(order.get('scripts'),list): raise ValueError('Missing script order')
        if 'script_count' in data.project and data.project['script_count']!=len(order['scripts']): raise ValueError('Script order is incomplete')
        seen=set()
        for script in order['scripts']:
            data.spend()
            if not isinstance(script,dict) or not isinstance(script.get('path'),str) or script['path'] in seen:
                raise ValueError('Ambiguous script order')
            seen.add(script['path'])
            file='scripts/'+script['path']
            for line,text in enumerate(data.text(file).splitlines(),1):
                data.spend()
                yield {'scope':'scripts','file':file,'line':line,'script_index':script.get('index')},text


def search(data, query=None, code=None, scopes=SCOPES, case_sensitive=False, limit=100, offset=0):
    if not isinstance(data,Index): data=Index(data)
    if query is None and code is None: raise ValueError('Supply text or a command code')
    if query is not None and (not isinstance(query,str) or not 1<=len(query)<=512 or '\n' in query or '\r' in query):
        raise ValueError('Text must be a nonempty single-line literal of at most 512 characters')
    if code is not None and (type(code) is not int or not 0<=code<=9999): raise ValueError('Invalid command code')
    if not scopes or set(scopes)-set(SCOPES): raise ValueError('Unknown search scope')
    scopes=tuple(s for s in SCOPES if s in scopes)
    if code is not None and 'events' not in scopes: raise ValueError('Command code filtering requires events scope')
    if type(limit) is not int or not 1<=limit<=1000 or type(offset) is not int or not 0<=offset<=100000:
        raise ValueError('Limit must be 1..1000 and offset 0..100000')
    needle=query if case_sensitive or query is None else query.casefold()
    hits=[]; matched=scanned=0
    for evidence,text in candidates(data,scopes,code):
        scanned+=1
        if query is None:
            if text is not None: continue
        elif text is None or needle not in (text if case_sensitive else text.casefold()): continue
        if offset<=matched<offset+limit:
            hits.append({**evidence,'excerpt':text[:300] if text is not None else None,
                         'excerpt_truncated':text is not None and len(text)>300})
        matched+=1
    data.unchanged()
    return {'version':'0.13.0','read_only':True,'mutation_authorized':False,'query':query,'command_code':code,
            'scopes':list(scopes),'case_sensitive':case_sensitive,'offset':offset,'limit':limit,
            'matches':matched,'returned':len(hits),'truncated':matched>offset+len(hits),
            'next_offset':offset+len(hits) if matched>offset+len(hits) else None,
            'coverage_complete':True,'candidates_scanned':scanned,'hits':hits,
            'limits':['Literal search only; no regex or project Ruby evaluation.',
                      'Searches normalized UTF-8 text; opaque/custom encodings may not be faithfully represented.',
                      'Scopes cover command parameter strings, database text excluding command/page/table payloads, map display/note/event names, and ordered script lines.',
                      'Result pagination bounds output, not coverage; work/file/byte budget exhaustion refuses instead of claiming a complete empty result.',
                      'Excerpts show the first 300 characters; inspect the exact evidence path for later matches.']}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('index'); ap.add_argument('--project',required=True); ap.add_argument('--output',required=True)
    ap.add_argument('--text'); ap.add_argument('--code',type=int)
    ap.add_argument('--scope',choices=SCOPES,action='append'); ap.add_argument('--case-sensitive',action='store_true')
    ap.add_argument('--limit',type=int,default=100); ap.add_argument('--offset',type=int,default=0)
    a=ap.parse_args(argv)
    try:
        r=execute(a.index,a.project,a.output,lambda data:search(data,a.text,a.code,a.scope or SCOPES,a.case_sensitive,a.limit,a.offset),'search')
        print(json.dumps({'status':'ok','matches':r['matches'],'returned':r['returned'],'truncated':r['truncated']})); return 0
    except Exception as exc:
        print('Search refused: '+str(exc),file=sys.stderr); return 2


if __name__=='__main__': raise SystemExit(main())
