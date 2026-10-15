#!/usr/bin/env python3
"""Read-only Python regex search with a fixed, isolated matching deadline."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

VERSION='1.1.0'
WORKER_TIMEOUT=10
MAX_INPUT_BYTES=4*1024*1024
MAX_OUTPUT_BYTES=512*1024
MAX_RESULT_BYTES=2*1024*1024
MAX_TEXT_CHARS=65536
MAX_CANDIDATES=50000


def request(pattern,case_sensitive,texts):
    if not isinstance(pattern,str) or not 1<=len(pattern)<=512 or '\n' in pattern or '\r' in pattern:
        raise ValueError('Pattern must be a nonempty single-line Python regex of at most 512 characters')
    if type(case_sensitive) is not bool:raise ValueError('Case-sensitive option requires a boolean')
    if not isinstance(texts,list) or len(texts)>MAX_CANDIDATES or any(not isinstance(text,str) or len(text)>MAX_TEXT_CHARS for text in texts):
        raise ValueError('Regex candidate text budget exceeded; narrow the scope')
    return {'pattern':pattern,'case_sensitive':case_sensitive,'texts':texts}


def match_worker():
    """Private protocol: only bounded text in, boolean matches out; no file access."""
    try:
        raw=sys.stdin.buffer.read(MAX_INPUT_BYTES+1)
        if len(raw)>MAX_INPUT_BYTES:raise ValueError('Regex worker input budget exceeded')
        value=json.loads(raw.decode('utf-8','strict'))
        if not isinstance(value,dict) or set(value)!={'pattern','case_sensitive','texts'}:raise ValueError('Invalid regex worker request')
        checked=request(**value)
        try:expression=re.compile(checked['pattern'],0 if checked['case_sensitive'] else re.IGNORECASE)
        except (re.error,OverflowError,RecursionError) as error:raise ValueError('Invalid Python regex: '+str(error)[:300]) from None
        response={'matched':[expression.search(text) is not None for text in checked['texts']]}
    except Exception as error:
        response={'error':str(error)[:400]}
    raw=json.dumps(response,separators=(',',':')).encode('utf-8')
    if len(raw)>MAX_OUTPUT_BYTES:raise ValueError('Regex worker output budget exceeded')
    sys.stdout.buffer.write(raw)
    return 0


def bounded_matches(pattern,case_sensitive,texts):
    raw=json.dumps(request(pattern,case_sensitive,texts),ensure_ascii=True,separators=(',',':')).encode('utf-8')
    if len(raw)>MAX_INPUT_BYTES:raise ValueError('Regex input budget exceeded; narrow the scope')
    command=[sys.executable,'-I','-B',str(Path(__file__).resolve()),'--worker']
    try:result=subprocess.run(command,input=raw,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=WORKER_TIMEOUT)
    except subprocess.TimeoutExpired:raise ValueError('Regex matching deadline exceeded; no complete result produced') from None
    if result.returncode or len(result.stdout)>MAX_OUTPUT_BYTES:raise ValueError('Regex worker failed or exceeded output bounds')
    try:response=json.loads(result.stdout.decode('utf-8','strict'))
    except (ValueError,UnicodeError):raise ValueError('Invalid regex worker response') from None
    if not isinstance(response,dict):raise ValueError('Invalid regex worker response')
    if set(response)=={'error'} and isinstance(response['error'],str):raise ValueError(response['error'][:400])
    if set(response)!={'matched'} or not isinstance(response['matched'],list) or len(response['matched'])!=len(texts) or any(type(value) is not bool for value in response['matched']):
        raise ValueError('Incomplete or invalid regex worker matches')
    return response['matched']


def search(data,pattern,code=None,scopes=None,case_sensitive=False,limit=100,offset=0):
    from vxace_index_query import Index
    from vxace_search import candidates,SCOPES
    if not isinstance(data,Index):data=Index(data)
    request(pattern,case_sensitive,[])
    if code is not None and (type(code) is not int or not 0<=code<=9999):raise ValueError('Invalid command code')
    scopes=SCOPES if scopes is None else scopes
    if not isinstance(scopes,(list,tuple)) or not scopes or any(not isinstance(scope,str) or scope not in SCOPES for scope in scopes):raise ValueError('Unknown regex search scope')
    scopes=tuple(scope for scope in SCOPES if scope in scopes)
    if code is not None and 'events' not in scopes:raise ValueError('Command code filtering requires events scope')
    if type(limit) is not int or not 1<=limit<=1000 or type(offset) is not int or not 0<=offset<=100000:raise ValueError('Limit must be 1..1000 and offset 0..100000')
    selected=[];texts=[];scanned=bytes_used=0
    for evidence,text in candidates(data,scopes,code):
        scanned+=1
        if text is None:continue
        if len(text)>MAX_TEXT_CHARS or len(texts)>=MAX_CANDIDATES:raise ValueError('Regex candidate budget exceeded; no complete result produced')
        bytes_used+=len(json.dumps(text,ensure_ascii=True).encode('utf-8'))+1
        if bytes_used>MAX_INPUT_BYTES:raise ValueError('Regex text budget exceeded; narrow the scope')
        selected.append(evidence);texts.append(text)
    matched=bounded_matches(pattern,case_sensitive,texts)
    hits=[];count=0
    for evidence,text,found in zip(selected,texts,matched):
        if not found:continue
        if offset<=count<offset+limit:hits.append({**evidence,'excerpt':text[:300],'excerpt_truncated':len(text)>300})
        count+=1
    data.unchanged()
    result={'version':VERSION,'read_only':True,'mutation_authorized':False,'mode':'python-regex','pattern':pattern,'command_code':code,
            'scopes':list(scopes),'case_sensitive':case_sensitive,'offset':offset,'limit':limit,'matches':count,'returned':len(hits),
            'truncated':count>offset+len(hits),'next_offset':offset+len(hits) if count>offset+len(hits) else None,
            'coverage_complete':True,'candidates_scanned':scanned,'matching_deadline_seconds':WORKER_TIMEOUT,'hits':hits,
            'limits':['Counts matching fields/script lines, not individual occurrences; empty matches are permitted.',
                      'Python regex semantics with IGNORECASE by default; inline flags can override base case behavior. This differs from literal Unicode case folding.',
                      'Script search is per line; other normalized text fields can contain multiple lines. No project Ruby or formula is evaluated.',
                      'Fixed worker deadline, candidate/text/IPC/report budgets and shared index budgets refuse instead of claiming complete partial results.',
                      'Opaque/custom encodings and dynamic/generated text remain outside normalized scope; inspect exact evidence beyond clipped excerpts.']}
    published={**result,'source_unchanged':True,'read_index_files_unchanged':True,'source_freshness':'fresh'}
    if len((json.dumps(published,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))>MAX_RESULT_BYTES:raise ValueError('Regex result budget exceeded; reduce limit')
    return result


def main(argv=None):
    if argv==['--worker'] or argv is None and sys.argv[1:]==['--worker']:return match_worker()
    from vxace_index_query import execute
    from vxace_search import SCOPES
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('index');parser.add_argument('--project',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--pattern',required=True);parser.add_argument('--code',type=int);parser.add_argument('--scope',choices=SCOPES,action='append')
    parser.add_argument('--case-sensitive',action='store_true');parser.add_argument('--limit',type=int,default=100);parser.add_argument('--offset',type=int,default=0)
    args=parser.parse_args(argv)
    try:
        result=execute(args.index,args.project,args.output,lambda data:search(data,args.pattern,args.code,args.scope,args.case_sensitive,args.limit,args.offset),'regex-search')
    except Exception as error:print('Regex search refused: '+str(error),file=sys.stderr);return 2
    print(json.dumps({'status':'ok','matches':result['matches'],'returned':result['returned'],'truncated':result['truncated']}));return 0


if __name__=='__main__':raise SystemExit(main())
