#!/usr/bin/env python3
"""Conservative read-only event diagnostics from a fresh VX Ace index."""
from __future__ import annotations
import argparse
from collections import Counter
import json
import sys
from pathlib import Path
from vxace_index_query import Index, execute
from vxace_common_event_graph import cycles

FLAGS=('switch1_valid','switch2_valid','variable_valid','self_switch_valid','item_valid','actor_valid')
CONTINUATIONS={401:101,405:105,408:108,505:205,605:302,655:355}
RELEASE={201,214,353,354}


def unconditional(page):
    condition=page.get('condition')
    if not isinstance(condition,dict) or any(type(condition.get(k)) is not bool for k in FLAGS): return None
    return not any(condition[k] for k in FLAGS)


def lint(data):
    if not isinstance(data,Index): data=Index(data)
    findings=[]; lists=commands=0; highest_unconditional={}
    common_ids=set(); calls=[]; entry_calls=opaque_calls=0
    if data.path('database/common-events.json').is_file():
        common=data.json('database/common-events.json')
        if not isinstance(common,list): raise ValueError('Opaque common-event database')
        for slot,owner in enumerate(common):
            data.spend()
            if owner is None: continue
            if (not isinstance(owner,dict) or owner.get('__class__')!='RPG::CommonEvent' or
                type(owner.get('id')) is not int or owner['id']!=slot or slot==0):
                raise ValueError('Common-event IDs must match native array slots')
            common_ids.add(slot)
    def emit(code,severity,detail,loc,file,path,**extra):
        if len(findings)>=5000: raise ValueError('Finding budget exceeded; no complete report produced')
        findings.append({'code':code,'severity':severity,'detail':detail,
                         'evidence':{'file':file,'path':path,**loc},**extra})
    for loc,file,path,page,pages in data.event_lists():
        lists+=1
        rows=page['list']; labels={}; jumps=[]; valid=True
        if not rows or not isinstance(rows[-1],dict) or rows[-1].get('code')!=0 or rows[-1].get('indent')!=0 or rows[-1].get('parameters')!=[]:
            emit('missing_root_terminator','error','List does not end with a native root terminator',loc,file,path+['list'])
        previous=None
        for n,row in enumerate(rows):
            data.spend(); commands+=1
            where=path+['list',n]
            if (not isinstance(row,dict) or row.get('__class__')!='RPG::EventCommand' or type(row.get('code')) is not int or
                type(row.get('indent')) is not int or row['indent']<0 or not isinstance(row.get('parameters'),list)):
                emit('opaque_command','warning','Command schema is incomplete; logic coverage is partial',loc,file,where)
                valid=False; previous=None; continue
            code,indent,p=row['code'],row['indent'],row['parameters']
            if code==117:
                if len(p)!=1 or type(p[0]) is not int or p[0]<1:
                    opaque_calls+=1
                    emit('opaque_common_event_call','warning','Call target is not one positive native common-event ID; graph coverage is partial',loc,file,where)
                elif p[0] not in common_ids:
                    emit('missing_common_event_call','warning','Call target is absent; the default native command performs no child event',loc,file,where,target_common_event_id=p[0])
                elif loc['scope']=='common_event':
                    if len(calls)>=10000: raise ValueError('Common-event call graph budget exceeded')
                    calls.append((loc['common_event_id'],p[0],{'file':file,'path':where,**loc}))
                else:
                    entry_calls+=1
            if code in CONTINUATIONS and (previous is None or previous[1]!=indent or previous[0] not in (code,CONTINUATIONS[code])):
                emit('orphan_continuation','error','Continuation has no matching preceding command at this indent',loc,file,where)
            if code in (118,119):
                if len(p)!=1 or not isinstance(p[0],str):
                    emit('opaque_label','warning','Label/jump target was not decoded as one string',loc,file,where); valid=False
                elif code==118: labels.setdefault(p[0],[]).append(n)
                else: jumps.append((n,p[0]))
            previous=(code,indent)
        for label,positions in labels.items():
            if len(positions)>1:
                emit('duplicate_label','warning','Multiple matching labels make jump intent ambiguous',loc,file,path+['list',positions[0]],command_indexes=positions)
        for n,label in jumps:
            if label not in labels and valid:
                emit('missing_label','error','Jump target is absent from this command list',loc,file,path+['list',n])
        if loc['scope']!='map': continue
        state=unconditional(page)
        if state is None:
            emit('unknown_page_conditions','warning','Native condition flags are incomplete; page-selection analysis is partial',loc,file,path+['condition'])
        # Report only the highest unconditional page, without mistaking a
        # conditionally valid later page for a permanent shadow.
        owner_key=(loc['map_id'],loc['event_id'])
        if owner_key not in highest_unconditional:
            data.spend(len(pages))
            highest_unconditional[owner_key]=max((n for n,p in enumerate(pages,1) if unconditional(p) is True),default=0)
        if state is True and loc['page']>1 and loc['page']==highest_unconditional[owner_key]:
            emit('unconditional_page_shadow','warning','This unconditional page permanently hides lower-numbered pages under default VX Ace selection',loc,file,path,
                 shadowed_pages=list(range(1,loc['page'])))
        if loc['page']!=len(pages) or state is not True or page.get('trigger')!=3: continue
        opaque=not valid
        release=False
        for row in rows:
            data.spend()
            if not isinstance(row,dict): continue
            code=row.get('code'); p=row.get('parameters',[])
            if type(code) is not int or not isinstance(p,list): opaque=True; continue
            if code in RELEASE: release=True
            if code in (117,205,301,355,655) or code==111 and p and p[0]==12 or code==122 and len(p)>3 and p[3]==4:
                opaque=True
        if opaque or release:
            emit('autorun_runtime_review','info','Highest unconditional autorun contains a possible release or opaque call/script; termination is not proven',loc,file,path)
        else:
            emit('possible_autorun_lock','warning','Highest unconditional autorun has no observed release or opaque command; the default runtime restarts it after completion',loc,file,path)
    graph_edges={(source,target) for source,target,_ in calls}
    components=cycles(common_ids,graph_edges,data.spend)
    for component in components:
        members=set(component)
        data.spend(len(calls))
        evidence=[e for source,target,e in calls if source in members and target in members]
        first=evidence[0]
        loc={k:v for k,v in first.items() if k not in ('file','path')}
        emit('possible_common_event_recursion','warning',
             'Direct common-event calls form a cycle; conditions, exits and scripts may prevent or bound recursion. Runtime review is required.',
             loc,first['file'],first['path'],common_event_ids=component,
             call_sites=len(evidence),call_evidence=evidence[:40],call_evidence_truncated=len(evidence)>40)
    data.unchanged()
    return {'version':'0.16.0','read_only':True,'mutation_authorized':False,'command_lists_checked':lists,'commands_checked':commands,
            'common_event_graph':{'nodes':len(common_ids),'direct_call_sites':len(calls),'unique_edges':len(graph_edges),
                                  'entry_call_sites':entry_calls,'cycle_components':len(components),'opaque_calls':opaque_calls},
            'findings':findings,'counts':dict(Counter(x['severity'] for x in findings)),
            'coverage_complete':not any(x['code'] in ('opaque_command','opaque_label','unknown_page_conditions','opaque_common_event_call') for x in findings),
            'limits':['Default VX Ace semantics only; custom interpreter/page-selection hooks require runtime review.',
                      'Checks root terminators, continuation adjacency, local labels, unconditional map-page shadows and highest unconditional map autoruns.',
                      'Direct common-event call cycles are potential recursion, including unused/conditional calls; scripts, reachability and termination are not proven.',
                      'No full branch/control-flow proof, conditional autorun termination proof, troop-page priority analysis or asset/RTP validation.',
                      'Possible release commands may be unreachable; an info result does not prove termination.',
                      'Every finding is diagnostic only; no automatic fixes or mutation readiness are granted.']}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('index'); ap.add_argument('--project',required=True); ap.add_argument('--output',required=True)
    a=ap.parse_args(argv)
    try:
        r=execute(a.index,a.project,a.output,lint,'event-lint')
        lines=['# VX Ace event diagnostics','',f"Lists checked: {r['command_lists_checked']}; findings: {len(r['findings'])}",'']
        for x in r['findings']: lines.append(f"- **{x['severity']}: {x['code']}** — {x['detail']} (`{x['evidence']['file']}`, {x['evidence']['path']})")
        lines+=['','## Coverage limits','']+['- '+x for x in r['limits']]
        (Path(a.output)/'event-lint.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        print(json.dumps({'status':'review_required' if any(x['severity']!='info' for x in r['findings']) else 'ok','findings':len(r['findings'])}))
        return 3 if any(x['severity']!='info' for x in r['findings']) else 0
    except Exception as exc:
        print('Event lint refused: '+str(exc),file=sys.stderr); return 2


if __name__=='__main__': raise SystemExit(main())
