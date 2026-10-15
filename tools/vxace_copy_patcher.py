#!/usr/bin/env python3
"""Apply tightly-scoped VX Ace mutations to a disposable project copy, never the source."""
from __future__ import annotations
import argparse, difflib, hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

VERSION='0.26.0'
def mutator_command(ruby, mutator, *args):
    return [sys.executable if mutator.suffix == '.py' else ruby, str(mutator), *map(str, args)]
DB_FILES={'actors':'Actors.rvdata2','classes':'Classes.rvdata2','skills':'Skills.rvdata2','items':'Items.rvdata2','weapons':'Weapons.rvdata2','armors':'Armors.rvdata2','enemies':'Enemies.rvdata2','troops':'Troops.rvdata2','states':'States.rvdata2','animations':'Animations.rvdata2','tilesets':'Tilesets.rvdata2','common-events':'CommonEvents.rvdata2','common_events':'CommonEvents.rvdata2','system':'System.rvdata2','map-infos':'MapInfos.rvdata2','map_infos':'MapInfos.rvdata2'}

def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def load_json(p:Path): return json.loads(p.read_text(encoding='utf-8'))
def dump_json(p:Path,obj): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def safe_rel(v:str)->str:
    p=Path(v)
    if p.is_absolute() or '..' in p.parts or not v: raise ValueError(f'unsafe relative path: {v}')
    return p.as_posix()

def current_inventory(project:Path)->dict[str,str]:
    return {p.relative_to(project).as_posix():sha256(p) for p in sorted(project.rglob('*')) if p.is_file()}

def verify_fresh(index:Path, project:Path)->dict:
    manifest=load_json(index/'manifest.json'); expected={safe_rel(str(x['path'])):str(x.get('sha256') or '') for x in manifest.get('files',[])}
    current=current_inventory(project); problems=[]
    for rel,h in expected.items():
        if rel not in current: problems.append({'path':rel,'reason':'missing'})
        elif h and current[rel]!=h: problems.append({'path':rel,'reason':'hash_mismatch','expected':h,'actual':current[rel]})
    for rel in sorted(set(current)-set(expected)): problems.append({'path':rel,'reason':'new_file'})
    return {'status':'fresh' if not problems else 'stale','problems':problems,'checked':len(expected)}

def run(cmd:list[str], *, capture=True)->subprocess.CompletedProcess:
    return subprocess.run(cmd,stdout=subprocess.PIPE if capture else None,stderr=subprocess.PIPE if capture else None,text=True,check=False)

def inspect_file(ruby:str, mutator:Path, file:Path)->dict:
    p=run(mutator_command(ruby,mutator,'inspect',file))
    if p.returncode: raise RuntimeError(f'inspect failed for {file.name}: {p.stderr.strip()}')
    return json.loads(p.stdout)

def roundtrip_preflight(ruby:str, mutator:Path, file:Path)->dict:
    with tempfile.TemporaryDirectory() as td:
        out=Path(td)/file.name
        before=inspect_file(ruby,mutator,file)
        p=run(mutator_command(ruby,mutator,'roundtrip',file,out))
        if p.returncode: raise RuntimeError(f'roundtrip failed for {file.name}: {p.stderr.strip()}')
        after=inspect_file(ruby,mutator,out)
        if before['semantic_sha256']!=after['semantic_sha256']:
            raise RuntimeError(f'roundtrip semantic mismatch for {file.name}')
        binary_identical = sha256(file)==sha256(out)
        if not binary_identical:
            raise RuntimeError(f'roundtrip binary mismatch for {file.name}; v0.8 refuses mutation')
        return {'file':file.name,'status':'passed','semantic_sha256':before['semantic_sha256'],'binary_identical':True}

def script_index(index:Path, rel:str)->int:
    order=load_json(index/'scripts'/'order.json').get('scripts',[])
    for item in order:
        if item.get('path')==rel: return int(item['index'])
    raise ValueError(f'script path not present in order.json: {rel}')

def normalize_changes(index:Path,spec:dict)->list[dict]:
    raw=spec.get('changes');
    if not isinstance(raw,list) or not raw: raise ValueError('spec requires non-empty changes array')
    out=[]
    for n,c in enumerate(raw,1):
        if not isinstance(c,dict): raise ValueError(f'change #{n} must be object')
        kind=c.get('kind'); loc=c.get('locator') or {}; mut=c.get('mutation') or {}
        if kind=='script':
            rel=safe_rel(str(c.get('script_path') or '')); search=str(c.get('search') or ''); replace=str(c.get('replace') or '')
            if not search: raise ValueError(f'script change #{n} missing search')
            out.append({'kind':'script','target':'Data/Scripts.rvdata2','ruby_spec':{'type':'scripts','mutation':{'script_index':script_index(index,rel),'search':search,'replace':replace}},'description':c.get('description',''),'script_path':rel,'search':search,'replace':replace})
        elif kind=='script_slot':
            from vxace_script_slots import integer
            if not isinstance(loc,dict) or set(loc)!={'before_index'}:
                raise ValueError('Script slot locator must contain exactly before_index')
            before=integer(loc['before_index'],'before script index',0,4095)
            fields={'action','expected_archive_sha256','expected_anchor_sha256','new_id','name','source'}
            if not isinstance(mut,dict) or set(mut)!=fields or mut.get('action')!='insert_before_main':
                raise ValueError('Script slot requires the exact insert_before_main mutation schema')
            out.append({'kind':'script_slot','target':'Data/Scripts.rvdata2',
                        'ruby_spec':{'type':'script_slot','mutation':{'before_index':before,**mut}},
                        'description':c.get('description',''),'locator':loc,'mutation':mut})
        elif kind=='database':
            table=str(loc.get('table') or '')
            if table not in DB_FILES: raise ValueError(f'unsupported database table: {table}')
            if 'id' not in loc or not mut.get('field'): raise ValueError(f'database change #{n} requires locator.id and mutation.field')
            out.append({'kind':'database','target':'Data/'+DB_FILES[table],'ruby_spec':{'type':'database','mutation':{'id':loc['id'],'field':mut['field'],'value':mut.get('value')}},'description':c.get('description',''),'locator':loc,'mutation':mut})
        elif kind=='database_entry':
            if not isinstance(loc,dict) or loc != {'table':'items'}:
                raise ValueError('Entry creation supports only the exact items table locator')
            if not isinstance(mut,dict) or mut.get('action')!='append_key_item':
                raise ValueError('Only append_key_item entry creation is enabled')
            out.append({'kind':'database_entry','target':'Data/Items.rvdata2',
                        'ruby_spec':{'type':'database_entry','mutation':mut},'description':c.get('description',''),
                        'locator':loc,'mutation':mut})
        elif kind=='map_event':
            from vxace_map_events import FIELDS,integer
            if not isinstance(loc,dict) or set(loc)!={'map_id'}:raise ValueError('Map event locator requires exactly map_id')
            mid=integer(loc['map_id'],'map ID',1,999999)
            if not isinstance(mut,dict) or set(mut)!=FIELDS or mut.get('action')!='append_dialogue_event':raise ValueError('Exact append_dialogue_event schema required')
            out.append({'kind':'map_event','target':f'Data/Map{mid:03d}.rvdata2',
                        'ruby_spec':{'type':'map_event','mutation':mut},'description':c.get('description',''),
                        'locator':loc,'mutation':mut})
        elif kind=='map_tile':
            from vxace_upper_tiles import FIELDS,integer
            if not isinstance(loc,dict) or set(loc)!={'map_id'}:raise ValueError('Upper tile locator must contain exactly map_id')
            mid=integer(loc['map_id'],'map ID',1,999999)
            if not isinstance(mut,dict) or set(mut)!=FIELDS or mut.get('action')!='paint_upper_tiles':raise ValueError('Upper tile edits require the exact paint_upper_tiles schema')
            out.append({'kind':'map_tile','target':f'Data/Map{mid:03d}.rvdata2',
                        'ruby_spec':{'type':'map_tile','mutation':mut},'description':c.get('description',''),
                        'locator':loc,'mutation':mut})
        elif kind=='map_region':
            from vxace_map_regions import integer
            if not isinstance(loc,dict) or set(loc) != {'map_id'}:
                raise ValueError('Region locator must contain exactly map_id')
            mid=integer(loc['map_id'],'map ID',1,999999)
            if not isinstance(mut,dict) or set(mut) != {'action','expected_table_sha256','cells'} or mut.get('action')!='set_regions':
                raise ValueError('Region edits require the exact set_regions schema')
            out.append({'kind':'map_region','target':f'Data/Map{mid:03d}.rvdata2',
                        'ruby_spec':{'type':'map_region','mutation':mut},'description':c.get('description',''),
                        'locator':loc,'mutation':mut})
        elif kind=='event':
            action=mut.get('action')
            structural={'insert_commands','delete_commands','insert_page','delete_page'}
            if action not in {'set_parameter','set_parameters'} | structural: raise ValueError(f'event change #{n} unsupported mutation.action')
            if sum(k in loc for k in ('map_id','common_event_id','troop_id')) != 1: raise ValueError('event locator must select exactly one scope')
            if set(mut) & {'scope','event_id','troop_id','common_event_id','page','command_index'}: raise ValueError('mutation cannot override event locator fields')
            if 'map_id' in loc:
                scope='map'; target=f"Data/Map{int(loc['map_id']):03d}.rvdata2"; base={'scope':scope,'event_id':loc.get('event_id'),'page':loc.get('page'),'command_index':loc.get('command_index')}
            elif 'common_event_id' in loc:
                scope='common_event'; target='Data/CommonEvents.rvdata2'; base={'scope':scope,'common_event_id':loc.get('common_event_id'),'command_index':loc.get('command_index')}
            elif 'troop_id' in loc:
                scope='troop'; target='Data/Troops.rvdata2'; base={'scope':scope,'troop_id':loc.get('troop_id'),'page':loc.get('page'),'command_index':loc.get('command_index')}
            else: raise ValueError(f'event change #{n} needs map/common-event/troop locator')
            if action in {'insert_page','delete_page'}:
                if scope=='common_event' or 'command_index' in loc: raise ValueError('Page edits require map/troop page locators without command indexes')
                base.pop('command_index',None)
            if any(v is None for k,v in base.items() if k not in {'scope'}): raise ValueError(f'event change #{n} locator incomplete')
            base.update(mut)
            out.append({'kind':'event','target':target,'ruby_spec':{'type':'event','mutation':base},'description':c.get('description',''),'locator':loc,'mutation':mut})
        else: raise ValueError(f'change #{n} unsupported kind: {kind}')
    return out

def apply_one(ruby:str, mutator:Path, copy_root:Path, change:dict, audit_dir:Path, index:int)->dict:
    rel=safe_rel(change['target']); target=(copy_root/rel).resolve()
    if copy_root.resolve() not in target.parents: raise ValueError(f'target escapes copy: {rel}')
    if not target.is_file(): raise FileNotFoundError(rel)
    before_raw=sha256(target); before_sem=inspect_file(ruby,mutator,target)['semantic_sha256']
    mutation=change.get('ruby_spec',{}).get('mutation',{})
    structural_action=mutation.get('action') in {'insert_commands','delete_commands','insert_page','delete_page'}
    def structural_snapshot(file,after=False):
        from vxace_python_mutator import load,object_by_id
        from vxace_event_structure import snapshot,owner_for
        root,_=load(file); loc=dict(mutation)
        if loc['scope']!='common_event':
            pages=owner_for(root,loc,object_by_id).get('pages')
            loc['page']=min(loc['page'],len(pages)) if after else (loc.get('template_page',loc['page']) if loc['action']=='insert_page' else loc['page'])
        return {'snapshot_page':loc.get('page'),**snapshot(root,loc,object_by_id)}
    before_structure=structural_snapshot(target) if structural_action else None
    region_cells=[{'x':c['x'],'y':c['y']} for c in mutation['cells']] if change['kind']=='map_region' else None
    def region_snapshot(file):
        from vxace_python_mutator import load
        from vxace_map_regions import snapshot
        return snapshot(load(file)[0],region_cells)
    before_regions=region_snapshot(target) if region_cells else None
    before_region_root=None
    if region_cells:
        from vxace_python_mutator import load
        before_region_root=load(target)[0]
    before_entry_root=None
    if change['kind']=='database_entry':
        from vxace_python_mutator import load
        from vxace_database_entries import snapshot as entry_snapshot
        before_entry_root=load(target)[0]
        before_entry=entry_snapshot(before_entry_root,mutation['template_id'])
    before_event_root=None
    if change['kind']=='map_event':
        from vxace_python_mutator import load
        from vxace_map_events import snapshot as event_snapshot
        before_event_root=load(target)[0]
        before_event=event_snapshot(before_event_root,mutation['template_id'])
    before_tile_root=None
    if change['kind']=='map_tile':
        from vxace_python_mutator import load
        from vxace_upper_tiles import snapshot as upper_snapshot
        before_tile_root=load(target)[0]
        tile_cells=[{'x':c['x'],'y':c['y']} for c in mutation['cells']]
        tile_values=sorted({c['value'] for c in mutation['cells']})
        tile_rtp=change['ruby_spec']['context']['rtp']
        before_tiles=upper_snapshot(before_tile_root,copy_root,tile_cells,tile_values,tile_rtp)
    before_slot_root=None
    if change['kind']=='script_slot':
        from vxace_python_mutator import load
        from vxace_script_slots import snapshot as slot_snapshot
        before_slot_root=load(target)[0]
        before_slot=slot_snapshot(before_slot_root,mutation['before_index'])
    specfile=audit_dir/f'mutation-{index:03d}.json'; dump_json(specfile,change['ruby_spec'])
    tmp=target.with_suffix(target.suffix+'.new')
    p=run(mutator_command(ruby,mutator,'mutate',target,tmp,specfile))
    if p.returncode: raise RuntimeError(f'mutation failed for {rel}: {p.stderr.strip()}')
    after_sem=inspect_file(ruby,mutator,tmp)['semantic_sha256']; after_raw=sha256(tmp)
    if region_cells:
        from vxace_map_regions import verify_transition
        verify_transition(before_region_root,load(tmp)[0],mutation)
    if change['kind']=='database_entry':
        from vxace_database_entries import verify_transition as verify_entry
        verify_entry(before_entry_root,load(tmp)[0],mutation)
    if change['kind']=='map_event':
        from vxace_map_events import verify_transition as verify_event
        verify_event(before_event_root,load(tmp)[0],mutation)
    if change['kind']=='map_tile':
        from vxace_upper_tiles import verify_transition as verify_upper
        verify_upper(before_tile_root,load(tmp)[0],mutation)
    if change['kind']=='script_slot':
        from vxace_script_slots import verify_transition as verify_slot
        verify_slot(before_slot_root,load(tmp)[0],mutation)
    if before_sem==after_sem: raise RuntimeError(f'mutation produced no semantic change: {rel}')
    os.replace(tmp,target)
    rec={'kind':change['kind'],'target':rel,'description':change.get('description',''),'before_sha256':before_raw,'after_sha256':after_raw,'before_semantic_sha256':before_sem,'after_semantic_sha256':after_sem}
    if change['kind']=='map_event':
        rec['map_event']={'before':before_event,'after':event_snapshot(load(target)[0],mutation['template_id']),
                          'new_id':mutation['new_id'],'name':mutation['name'],'x':mutation['x'],'y':mutation['y'],
                          'text':mutation['text'],'old_events_and_other_map_fields_preserved':True}
    if change['kind']=='map_tile':
        after_tiles=upper_snapshot(load(target)[0],copy_root,tile_cells,tile_values,tile_rtp)
        rec['upper_tiles']={'locator':change['locator'],'before':before_tiles,'after':after_tiles,
                            'only_approved_upper_bytes_changed':True,'ground_regions_shadows_other_fields_unchanged':True}
        rec['diff']=''.join(difflib.unified_diff(json.dumps(before_tiles,indent=2).splitlines(True),json.dumps(after_tiles,indent=2).splitlines(True),fromfile='source-upper-tiles',tofile='staged-upper-tiles'))
    if structural_action:
        after_structure=structural_snapshot(target,True)
        rec['structural']={'action':mutation['action'],'locator':change['locator'],'before':before_structure,'after':after_structure}
        rec['diff']=''.join(difflib.unified_diff(json.dumps(before_structure,ensure_ascii=False,indent=2).splitlines(True),json.dumps(after_structure,ensure_ascii=False,indent=2).splitlines(True),fromfile='source-event-snapshot',tofile='staged-event-snapshot'))
    if region_cells:
        after_regions=region_snapshot(target)
        rec['regions']={'locator':change['locator'],'before':before_regions,'after':after_regions,
                        'only_approved_region_bytes_changed':True,'other_map_fields_unchanged':True}
        rec['diff']=''.join(difflib.unified_diff(json.dumps(before_regions,indent=2).splitlines(True),json.dumps(after_regions,indent=2).splitlines(True),fromfile='source-regions',tofile='staged-regions'))
    if change['kind']=='database_entry':
        after_entry=entry_snapshot(load(target)[0],mutation['template_id'])
        rec['entry']={'before':before_entry,'after':after_entry,'created_id':mutation['new_id'],
                      'existing_entries_unchanged':True,'approved_inert_key_item_verified':True}
        rec['diff']=''.join(difflib.unified_diff(json.dumps(before_entry,indent=2).splitlines(True),json.dumps(after_entry,indent=2).splitlines(True),fromfile='source-items',tofile='staged-items'))
    if change['kind']=='script_slot':
        after_slot=slot_snapshot(load(target)[0],mutation['before_index']+1)
        rec['script_slot']={'locator':change['locator'],'before':before_slot,'after':after_slot,
                            'existing_entries_order_and_bytes_unchanged':True}
        rec['diff']=''.join(difflib.unified_diff([],mutation['source'].splitlines(True),fromfile='/dev/null',tofile='new-script-slot-source'))
    if change['kind']=='script':
        idxroot=change.get('_index_root')
        if idxroot:
            text=(Path(idxroot)/'scripts'/change['script_path']).read_bytes().decode('utf-8','strict')
            proposed=text.replace(change['search'],change['replace'],1)
            rec['diff']=''.join(difflib.unified_diff(text.splitlines(True),proposed.splitlines(True),fromfile='a/'+change['script_path'],tofile='b/'+change['script_path']))
    return rec

def render_audit(a:dict)->str:
    lines=[f"# {a['title']}",'',f"Status: **{a['status']}**",'', '## Safety','', '- Source project modified: **no**', '- All binary writes occurred only in the staged copy.', '- Every targeted `.rvdata2` file passed semantic and byte-identical no-op round-trip preflight before mutation.', '']
    lines += ['## Mutations','']
    for i,c in enumerate(a['changes'],1):
        lines += [f"### {i}. {c['kind']} — `{c['target']}`",'',c.get('description','') or '(no description)','']
        if c.get('diff'): lines += ['```diff',c['diff'].rstrip(),'```','']
    lines += ['## Validation','',f"- Source freshness before patch: **{a['freshness']['status']}**",f"- Source integrity after patch: **{a['source_integrity_after']['status']}**",f"- Re-index status: **{a['reindex']['status']}**",'']
    if a.get('index_diff'): lines += [f"- Re-index changed files: **{a['index_diff'].get('changed_count',0)}**",f"- Re-index added files: **{a['index_diff'].get('added_count',0)}**",f"- Re-index removed files: **{a['index_diff'].get('removed_count',0)}**",'']
    lines += ['## Rollback','','Delete the staged project copy. The original source project was not modified.','']
    return '\n'.join(lines)

def build(index:Path,project:Path,spec_path:Path,copy_root:Path,audit_dir:Path,ruby:str,mutator:Path,reader:Path|None,diff_tool:Path|None,no_reindex:bool=False,rtp:Path|None=None)->dict:
    index=index.resolve(); project=project.resolve(); copy_root=copy_root.resolve(); audit_dir=audit_dir.resolve()
    if not (project/'Data').is_dir(): raise ValueError('source is not a VX Ace project (missing Data/)')
    if rtp is not None:
        from vxace_index_query import unlinked
        rtp=unlinked(rtp)
        if any(path==rtp or rtp in path.parents for path in (copy_root,audit_dir)):
            raise ValueError('Copy and audit outputs must be outside read-only RTP')
    if project==copy_root or project in copy_root.parents: raise ValueError('copy destination may not be inside source project')
    if project==audit_dir or project in audit_dir.parents: raise ValueError('audit destination may not be inside source project')
    if copy_root==audit_dir or copy_root in audit_dir.parents or audit_dir in copy_root.parents: raise ValueError('copy and audit destinations must be separate non-nested paths')
    if copy_root.exists(): raise ValueError('copy destination already exists')
    if audit_dir.exists(): raise ValueError('audit destination already exists')
    if (index/'project.json').is_file():
        summary=load_json(index/'project.json')
        if not isinstance(summary,dict) or summary.get('errors'):
            raise ValueError('Complete Project Reader extraction is required before copy mutation')
    freshness=verify_fresh(index,project)
    if freshness['status']!='fresh': raise RuntimeError('STALE_INDEX:'+json.dumps(freshness))
    source_before=current_inventory(project)
    spec=load_json(spec_path); changes=normalize_changes(index,spec)
    structural=[c for c in changes if c.get('mutation',{}).get('action') in {'insert_commands','delete_commands','insert_page','delete_page'}]
    regions=[c for c in changes if c['kind']=='map_region']
    entries=[c for c in changes if c['kind']=='database_entry']
    slots=[c for c in changes if c['kind']=='script_slot']
    upper_tiles=[c for c in changes if c['kind']=='map_tile']
    map_events=[c for c in changes if c['kind']=='map_event']
    reload_required=bool(structural or regions or upper_tiles or map_events)
    post_required=bool(reload_required or entries or slots)
    if map_events:
        if len({c['target'] for c in map_events})!=len(map_events) or any(sum(other['target']==c['target'] for other in changes)!=1 for c in map_events):
            raise ValueError('Append one dialogue event per map without other edits to that map')
        if no_reindex or mutator.resolve()!=(Path(__file__).resolve().parent/'vxace_python_mutator.py'):
            raise ValueError('Event creation requires explicit Python backend and mandatory post-copy re-indexing')
        from vxace_map_events import indexed_snapshot as event_indexed_snapshot,new_event
        from vxace_index_query import Index,unlinked
        from vxace_python_mutator import load
        for c in map_events:
            event_data=Index(index)
            event_indexed_snapshot(event_data,project,c['locator']['map_id'],c['mutation']['template_id'])
            event_data.unchanged()
            new_event(load(unlinked(project/c['target']))[0],c['mutation'])
    if upper_tiles:
        if len({c['target'] for c in upper_tiles})!=len(upper_tiles) or any(sum(other['target']==c['target'] for other in changes)!=1 for c in upper_tiles):
            raise ValueError('Use one upper tile operation per map without other mutations to that map')
        if no_reindex or mutator.resolve()!=(Path(__file__).resolve().parent/'vxace_python_mutator.py'):
            raise ValueError('Upper tile edits require the explicit Python backend and mandatory post-copy re-indexing')
        from vxace_upper_tiles import apply as upper_apply,indexed_snapshot as upper_indexed_snapshot
        from vxace_index_query import Index,unlinked
        from vxace_python_mutator import load
        from vxace_map_audit import audit as map_audit
        for c in upper_tiles:
            cells=[{'x':cell['x'],'y':cell['y']} for cell in c['mutation']['cells']]
            values=sorted({cell['value'] for cell in c['mutation']['cells']})
            tile_data=Index(index)
            upper_indexed_snapshot(tile_data,project,c['locator']['map_id'],cells,values,rtp)
            if map_audit(tile_data,c['locator']['map_id'])['findings']:raise ValueError('Selected map has unresolved native tile diagnostics')
            tile_data.unchanged()
            upper_apply(load(unlinked(project/c['target']))[0],c['mutation'],project,rtp)
            c['ruby_spec']['context']={'rtp':str(rtp) if rtp else None}
    if slots:
        if len(slots)!=1 or any(c['target']=='Data/Scripts.rvdata2' and c['kind']!='script_slot' for c in changes):
            raise ValueError('Insert one script slot per transaction without other Scripts mutations')
        if no_reindex or mutator.resolve()!=(Path(__file__).resolve().parent/'vxace_python_mutator.py'):
            raise ValueError('Script slot insertion requires the explicit Python backend and mandatory post-copy re-indexing')
        from vxace_script_slots import indexed_snapshot as slot_indexed_snapshot, new_slot
        from vxace_index_query import Index, unlinked
        from vxace_python_mutator import load
        for c in slots:
            slot_data=Index(index)
            slot_indexed_snapshot(slot_data,project,c['locator']['before_index'])
            slot_data.unchanged()
            new_slot(load(unlinked(project/c['target']))[0],c['ruby_spec']['mutation'])
    if entries:
        if len(entries)!=1 or any(c['target']=='Data/Items.rvdata2' and c['kind']!='database_entry' for c in changes):
            raise ValueError('Append one key item per transaction without other Items mutations')
        if no_reindex or mutator.resolve() != (Path(__file__).resolve().parent/'vxace_python_mutator.py'):
            raise ValueError('Entry creation requires the explicit Python backend and mandatory post-copy re-indexing')
        from vxace_python_mutator import load
        from vxace_database_entries import new_key_item, indexed_snapshot
        from vxace_index_query import Index, unlinked
        for c in entries:
            indexed_snapshot(Index(index),project,c['mutation']['template_id'])
            new_key_item(load(unlinked(project/c['target']))[0],c['mutation'])
    if regions:
        if len({c['target'] for c in regions}) != len(regions):
            raise ValueError('Use one bounded region operation per map per transaction')
        if no_reindex or mutator.resolve() != (Path(__file__).resolve().parent/'vxace_python_mutator.py'):
            raise ValueError('Region edits require the explicit Python backend and mandatory post-copy re-indexing')
        from vxace_python_mutator import load
        from vxace_map_regions import apply as region_apply
        from vxace_index_query import unlinked
        for c in regions:
            # Validate every native precondition before creating the copy/audit.
            region_apply(load(unlinked(project/c['target']))[0],c['mutation'])
    if structural:
        if no_reindex: raise ValueError('Structural edits require post-copy re-indexing and semantic verification')
        if mutator.resolve() != (Path(__file__).resolve().parent/'vxace_python_mutator.py'):
            raise ValueError('Structural edits require the explicitly selected Python backend')
        from vxace_event_structure import validate_project_references
        for c in structural: validate_project_references(index,c['ruby_spec']['mutation'])
    if reload_required:
        system=load_json(index/'database/system.json')
        version=system.get('version_id')
        if type(version) is not int or not 0 <= version < 2**31-1: raise ValueError('Verified native System.version_id required for structural edits')
        changes.append({'kind':'system_version','target':'Data/System.rvdata2','description':'Advance the native project version so existing saves reload the edited map',
                        'ruby_spec':{'type':'system_version','mutation':{'expected_version':version}}})
    for c in changes: c['_index_root']=str(index)
    audit_dir.mkdir(parents=True)
    if post_required:
        from vxace_impact import build as build_impact
        dump_json(audit_dir/'structural-impact.json',build_impact(index,spec_path))
    # Programmatic project-wide gate for the exact selected backend, in addition
    # to the immediate per-target semantic and raw-byte gates below.
    from vxace_project_validator import validate
    validation=validate(project,audit_dir/'project-validation',ruby,mutator,skip_script_syntax=True,
                        backend='python' if mutator.suffix=='.py' else 'ruby')
    if not validation['copy_mutation_ready']:
        raise RuntimeError('project-wide byte-identical gate refused mutation')
    preflights=[]
    for rel in sorted({c['target'] for c in changes}):
        preflights.append(roundtrip_preflight(ruby,mutator,project/safe_rel(rel)))
    shutil.copytree(project,copy_root)
    try:
        if current_inventory(copy_root)!=source_before: raise RuntimeError('clone inventory differs from the verified source snapshot')
        applied=[]
        for i,c in enumerate(changes,1): applied.append(apply_one(ruby,mutator,copy_root,c,audit_dir,i))
        source_after=current_inventory(project); src_problems=[]
        if source_before!=source_after:
            for rel in sorted(set(source_before)|set(source_after)):
                if source_before.get(rel)!=source_after.get(rel): src_problems.append(rel)
        source_integrity={'status':'unchanged' if not src_problems else 'CHANGED','problems':src_problems}
        if src_problems: raise RuntimeError('SOURCE_CHANGED:'+json.dumps(source_integrity))
        reindex={'status':'skipped'}; index_diff=None
        if not no_reindex:
            if reader is None or not reader.is_file(): raise ValueError('reader required unless --no-reindex')
            post=audit_dir/'post-index'
            p=run([sys.executable,str(reader),str(copy_root),'--output',str(post),'--ruby',ruby])
            if p.returncode: raise RuntimeError('re-index failed: '+p.stderr.strip())
            reindex={'status':'ok','path':str(post)}
            if diff_tool and diff_tool.is_file():
                j=audit_dir/'index-diff.json'; m=audit_dir/'index-diff.md'
                p=run([sys.executable,str(diff_tool),str(index),str(post),'--json',str(j),'--markdown',str(m)])
                if p.returncode: raise RuntimeError('index diff failed: '+p.stderr.strip())
                index_diff=json.loads(p.stdout)
            if post_required:
                semantic_tool=Path(__file__).resolve().parent/'vxace_semantic_diff.py'
                p=run([sys.executable,str(semantic_tool),str(index),str(post),'--json',str(audit_dir/'semantic-diff.json'),'--markdown',str(audit_dir/'semantic-diff.md')])
                if p.returncode: raise RuntimeError('structural semantic verification failed: '+p.stderr.strip())
                post_validation=validate(copy_root,audit_dir/'post-validation',ruby,mutator,skip_script_syntax=True,backend='python')
                if not post_validation['copy_mutation_ready']: raise RuntimeError('post-copy project validation failed')
                if regions or upper_tiles:
                    from vxace_map_audit import audit as map_audit
                    from vxace_index_query import Index
                    reports=[map_audit(Index(post),c['locator']['map_id']) for c in regions+upper_tiles]
                    if any(r['findings'] for r in reports): raise RuntimeError('post-copy selected-map tile audit failed')
                    dump_json(audit_dir/'post-map-audit.json',reports)
        if upper_tiles:
            from vxace_upper_tiles import asset_context
            from vxace_python_mutator import load
            for c in upper_tiles:asset_context(load(copy_root/c['target'])[0],c['mutation'],copy_root,rtp)
        if current_inventory(project)!=source_before: raise RuntimeError('SOURCE_CHANGED: source changed during final verification')
        result={'version':VERSION,'title':str(spec.get('title') or 'VX Ace staged patch'),'status':'ok','source_project_omitted_from_persistent_output':True,'freshness':freshness,'roundtrip_preflight':preflights,'changes':applied,'source_integrity_after':source_integrity,'copy_path':str(copy_root),'reindex':reindex,'index_diff':index_diff,'rollback':{'strategy':'delete staged project copy','source_project_modified':False}}
        dump_json(audit_dir/'audit.json',result); (audit_dir/'audit.md').write_text(render_audit(result),encoding='utf-8')
        return result
    except Exception as exc:
        cleanup_error=None
        try:
            if copy_root.exists(): shutil.rmtree(copy_root)
        except OSError as cleanup_exc: cleanup_error=str(cleanup_exc)
        removed=not copy_root.exists()
        dump_json(audit_dir/'failure.json',{'version':VERSION,'status':'failed','reason':str(exc),'staged_copy_removed':removed,'cleanup_error':cleanup_error,'source_project_modified_by_tool':False})
        if not removed: raise RuntimeError('Invalid staged copy could not be removed; see failure.json') from exc
        raise

def main(argv=None)->int:
    here=Path(__file__).resolve().parent
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('index'); ap.add_argument('--project',required=True); ap.add_argument('--spec',required=True); ap.add_argument('--copy',required=True); ap.add_argument('--audit',required=True); ap.add_argument('--ruby',default=shutil.which('ruby')); ap.add_argument('--mutator'); ap.add_argument('--backend',choices=['ruby','python'],default='ruby'); ap.add_argument('--reader',default=str(here/'vxace_project_reader.py')); ap.add_argument('--diff-tool',default=str(here/'vxace_index_diff.py')); ap.add_argument('--no-reindex',action='store_true'); ap.add_argument('--rtp'); a=ap.parse_args(argv)
    if a.mutator is None: a.mutator=str(here/('vxace_python_mutator.py' if a.backend=='python' else 'rvdata2_mutator.rb'))
    try:
        if not a.ruby: raise ValueError('Ruby not found; pass --ruby PATH')
        r=build(Path(a.index),Path(a.project),Path(a.spec),Path(a.copy),Path(a.audit),a.ruby,Path(a.mutator),Path(a.reader),Path(a.diff_tool),a.no_reindex,Path(a.rtp) if a.rtp else None)
    except RuntimeError as e:
        msg=str(e)
        reason='stale_index' if msg.startswith('STALE_INDEX:') else ('source_changed' if msg.startswith('SOURCE_CHANGED:') else 'runtime_error')
        print(json.dumps({'status':'refused','reason':reason,'detail':msg}),file=sys.stderr); return 3
    except Exception as e:
        print(json.dumps({'status':'error','reason':str(e)}),file=sys.stderr); return 2
    print(json.dumps({'status':'ok','copy':r['copy_path'],'change_count':len(r['changes']),'reindex':r['reindex']['status']})); return 0
if __name__=='__main__': raise SystemExit(main())
