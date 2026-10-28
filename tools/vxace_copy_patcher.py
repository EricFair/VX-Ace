#!/usr/bin/env python3
"""Apply tightly-scoped VX Ace mutations to a disposable project copy, never the source."""
from __future__ import annotations
import argparse, difflib, hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

VERSION='1.0.0'
def mutator_command(ruby, mutator, *args):
    return [sys.executable if mutator.suffix == '.py' else ruby, str(mutator), *map(str, args)]
DB_FILES={'actors':'Actors.rvdata2','classes':'Classes.rvdata2','skills':'Skills.rvdata2','items':'Items.rvdata2','weapons':'Weapons.rvdata2','armors':'Armors.rvdata2','enemies':'Enemies.rvdata2','troops':'Troops.rvdata2','states':'States.rvdata2','animations':'Animations.rvdata2','tilesets':'Tilesets.rvdata2','common-events':'CommonEvents.rvdata2','common_events':'CommonEvents.rvdata2','system':'System.rvdata2','map-infos':'MapInfos.rvdata2','map_infos':'MapInfos.rvdata2'}

ENTRY_TABLES={'items','enemies','skills','states','weapons','armors','troops'}


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
        elif kind=='database_entry' and isinstance(loc,dict) and loc.get('table')=='classes':
            from vxace_class_learning import native_mutation
            out.append({'kind':'database_entry','target':'Data/'+DB_FILES['classes'],
                        'ruby_spec':{'type':'database_entry','mutation':native_mutation(loc,mut)},'description':c.get('description',''),
                        'locator':loc,'mutation':mut})
        elif kind=='database_entry':
            if not isinstance(loc,dict) or set(loc)!={'table'} or loc['table'] not in ENTRY_TABLES:
                raise ValueError('Entry creation supports only an exact items or append-table locator')
            action=mut.get('action') if isinstance(mut,dict) else None
            if (loc['table']=='items',action)not in ((True,'append_key_item'),(False,'append_database_entry')):
                raise ValueError('Entry action does not match the table: items use append_key_item; enemies/skills/states/weapons/armors/troops use append_database_entry')
            out.append({'kind':'database_entry','target':'Data/'+DB_FILES[loc['table']],
                        'ruby_spec':{'type':'database_entry','mutation':mut},'description':c.get('description',''),
                        'locator':loc,'mutation':mut})
        elif kind=='map_entry':
            from vxace_maps import FIELDS,integer
            if not isinstance(loc,dict) or set(loc)!={'template_map_id'}:raise ValueError('Map append requires exactly template_map_id locator')
            tid=integer(loc['template_map_id'],'template map ID',1,999)
            if not isinstance(mut,dict) or set(mut)!=FIELDS-{'template_map_id'} or mut.get('action')!='append_blank_map':raise ValueError('Exact append_blank_map mutation required')
            native_mutation={'template_map_id':tid,**mut}
            out.append({'kind':'map_entry','target':'Data/MapInfos.rvdata2','ruby_spec':{'type':'map_entry','mutation':native_mutation},
                        'description':c.get('description',''),'locator':loc,'mutation':native_mutation})
        elif kind=='map_event':
            from vxace_map_events import schema,integer
            if not isinstance(loc,dict) or set(loc)!={'map_id'}:raise ValueError('Map event locator requires exactly map_id')
            mid=integer(loc['map_id'],'map ID',1,999999)
            schema(mut)
            out.append({'kind':'map_event','target':f'Data/Map{mid:03d}.rvdata2',
                        'ruby_spec':{'type':'map_event','mutation':mut},'description':c.get('description',''),
                        'locator':loc,'mutation':mut})
        elif kind=='map_shop':
            from vxace_map_shops import schema,integer
            if not isinstance(loc,dict) or set(loc)!={'map_id','event_id'}:raise ValueError('Shop locator requires exactly map_id and event_id')
            mid=integer(loc['map_id'],'map ID',1,999);eid=integer(loc['event_id'],'event ID',1,999)
            schema(mut)
            out.append({'kind':'map_shop','target':f'Data/Map{mid:03d}.rvdata2',
                        'ruby_spec':{'type':'map_shop','mutation':{'event_id':eid,**mut}},'description':c.get('description',''),
                        'locator':loc,'mutation':mut})
        elif kind=='map_tile':
            from vxace_upper_tiles import FIELDS,integer
            if not isinstance(loc,dict) or set(loc)!={'map_id'}:raise ValueError('Upper tile locator must contain exactly map_id')
            mid=integer(loc['map_id'],'map ID',1,999999)
            if not isinstance(mut,dict) or set(mut)!=FIELDS or mut.get('action')!='paint_upper_tiles':raise ValueError('Upper tile edits require the exact paint_upper_tiles schema')
            out.append({'kind':'map_tile','target':f'Data/Map{mid:03d}.rvdata2',
                        'ruby_spec':{'type':'map_tile','mutation':mut},'description':c.get('description',''),
                        'locator':loc,'mutation':mut})
        elif kind=='map_label':
            from vxace_map_labels import FIELDS,integer
            if not isinstance(loc,dict) or set(loc)!={'map_id'}:raise ValueError('Map label locator requires exactly map_id')
            mid=integer(loc['map_id'],'map ID',1,999)
            if not isinstance(mut,dict) or set(mut)!=FIELDS-{'map_id'} or mut.get('action')!='set_tree_name':raise ValueError('Exact set_tree_name mutation required')
            native_mutation={'map_id':mid,**mut}
            out.append({'kind':'map_label','target':'Data/MapInfos.rvdata2','ruby_spec':{'type':'map_label','mutation':native_mutation},
                        'description':c.get('description',''),'locator':loc,'mutation':native_mutation})
        elif kind=='map_name':
            from vxace_map_names import FIELDS,integer
            if not isinstance(loc,dict) or set(loc)!={'map_id'}:raise ValueError('Display-name locator requires exactly map_id')
            mid=integer(loc['map_id'],'map ID',1,999)
            if not isinstance(mut,dict) or set(mut)!=FIELDS or mut.get('action')!='set_display_name':raise ValueError('Exact set_display_name mutation required')
            out.append({'kind':'map_name','target':f'Data/Map{mid:03d}.rvdata2',
                        'ruby_spec':{'type':'map_name','mutation':mut},'description':c.get('description',''),
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
        elif kind=='map_encounter':
            from vxace_map_encounters import FIELDS,ACTION,integer
            if not isinstance(loc,dict) or set(loc)!={'map_id'}:raise ValueError('Encounter locator must contain exactly map_id')
            mid=integer(loc['map_id'],'map ID',1,999)
            if not isinstance(mut,dict) or set(mut)!=FIELDS or mut.get('action')!=ACTION:raise ValueError('Exact append_encounter mutation required')
            out.append({'kind':'map_encounter','target':f'Data/Map{mid:03d}.rvdata2',
                        'ruby_spec':{'type':'map_encounter','mutation':mut},'description':c.get('description',''),
                        'locator':loc,'mutation':mut})
        elif kind=='event':
            rows=mut.get('commands',[])
            if isinstance(rows,list) and any(isinstance(row,dict) and type(row.get('code')) is int and row['code']==201 for row in rows):
                from vxace_transfers import validate_locator
                validate_locator(loc)
                if set(mut)!={'action','expected_list_sha256','commands','transfer_guard'} or mut.get('action')!='insert_commands':raise ValueError('Exact direct transfer insertion schema required')
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

def apply_map_append(copy_root,change,audit_dir,index):
    """Coordinated two-file operation on the already verified fresh clone only."""
    from vxace_python_mutator import load,marshal_rb,inspect
    from vxace_index_query import unlinked
    from vxace_maps import candidates
    target=unlinked(copy_root/'Data/MapInfos.rvdata2');before=current_inventory(copy_root)
    infos,before_raw=load(target);mutation=change['ruby_spec']['mutation']
    proposed_info,proposed_map=candidates(infos,mutation,copy_root)
    info_raw=marshal_rb.dump(proposed_info);map_raw=marshal_rb.dump(proposed_map)
    retained=marshal_rb.load(info_raw);retained.pairs.pop()
    if marshal_rb.dump(retained)!=before_raw:raise ValueError('Map append changed existing map-info entries or aliases')
    new_rel=f"Data/Map{mutation['new_id']:03d}.rvdata2";new_file=unlinked(copy_root/new_rel)
    if new_file.exists():raise ValueError('New map file already exists; never overwrite maps')
    dump_json(audit_dir/f'mutation-{index:03d}.json',change['ruby_spec'])
    temporary=None
    try:
        with new_file.open('xb') as stream:stream.write(map_raw)
        with tempfile.NamedTemporaryFile(mode='wb',dir=target.parent,prefix='.vxace-map-',delete=False) as stream:
            temporary=Path(stream.name);stream.write(info_raw)
        os.replace(temporary,target);temporary=None
        after_info,after_raw=load(target);after_map,after_map_raw=load(new_file)
        if after_raw!=info_raw or after_map_raw!=map_raw:raise ValueError('Map/tree candidate changed during staged write')
        expected={**before,'Data/MapInfos.rvdata2':hashlib.sha256(info_raw).hexdigest(),new_rel:hashlib.sha256(map_raw).hexdigest()}
        if current_inventory(copy_root)!=expected:raise ValueError('Map append changed unapproved copied files')
        change['_expected_copy_inventory']=expected
        return {'kind':'map_entry','target':'Data/MapInfos.rvdata2','description':change.get('description',''),
                'before_sha256':hashlib.sha256(before_raw).hexdigest(),'after_sha256':expected['Data/MapInfos.rvdata2'],
                'before_semantic_sha256':inspect(infos)['semantic_sha256'],'after_semantic_sha256':inspect(after_info)['semantic_sha256'],
                'new_map':{'target':new_rel,'sha256':expected[new_rel],'new_id':mutation['new_id'],'name':mutation['name'],
                           'width':after_map.get('width'),'height':after_map.get('height'),'events':len(after_map.get('events').pairs),
                           'old_entries_and_existing_maps_preserved':True,'system_version_unchanged':True}}
    finally:
        if temporary is not None and temporary.exists():temporary.unlink()


def apply_one(ruby:str, mutator:Path, copy_root:Path, change:dict, audit_dir:Path, index:int)->dict:
    if change['kind']=='map_entry':return apply_map_append(copy_root,change,audit_dir,index)
    rel=safe_rel(change['target']); target=(copy_root/rel).resolve()
    if copy_root.resolve() not in target.parents: raise ValueError(f'target escapes copy: {rel}')
    if not target.is_file(): raise FileNotFoundError(rel)
    before_raw=sha256(target); before_sem=inspect_file(ruby,mutator,target)['semantic_sha256']
    mutation=change.get('ruby_spec',{}).get('mutation',{})
    structural_action=mutation.get('action') in {'insert_commands','delete_commands','insert_page','delete_page'}
    from vxace_event_rewards import has_rewards
    reward_root=None
    if structural_action and has_rewards(mutation):
        from vxace_python_mutator import load
        from vxace_event_rewards import validate as validate_rewards
        reward_root=load(target)[0];reward_evidence=validate_rewards(reward_root,mutation,target)
    from vxace_transfers import has_transfers,validate as validate_transfer
    transfer_root=None
    if structural_action and has_transfers(mutation):
        from vxace_python_mutator import load
        transfer_root=load(target)[0];transfer_evidence=validate_transfer(transfer_root,mutation,target)
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
    before_encounter_root=None
    if change['kind']=='map_encounter':
        from vxace_python_mutator import load
        from vxace_map_encounters import existing as encounter_rows,troops_for
        before_encounter_root=load(target)[0];encounter_troops=troops_for(target);before_encounters=encounter_rows(before_encounter_root)
        before_encounter_step=before_encounter_root.get('encounter_step')
    before_entry_root=None
    if change['kind']=='database_entry':
        from vxace_python_mutator import load
        from vxace_database_entries import snapshot as items_snapshot
        from vxace_database_append import snapshot as table_snapshot, enemies_for
        entry_table=change['locator']['table']
        entry_enemies=enemies_for(target) if entry_table=='troops' else None
        if entry_table=='classes':
            from vxace_class_learning import snapshot as learning_snapshot, skills_for
            entry_skills=skills_for(target);entry_skills_sha=sha256(target.parent/'Skills.rvdata2')
            entry_snapshot=lambda root,cid:learning_snapshot(root,entry_skills,cid)
            entry_key=mutation['class_id']
        else:
            entry_snapshot=(lambda root,tid:items_snapshot(root,tid)) if entry_table=='items' else (lambda root,tid:table_snapshot(root,entry_table,tid,entry_enemies))
            entry_key=mutation['template_id']
        before_entry_root=load(target)[0]
        before_entry=entry_snapshot(before_entry_root,entry_key)
    before_shop_root=None
    if change['kind']=='map_shop':
        from vxace_python_mutator import load
        from vxace_map_shops import goods_arrays
        before_shop_root=load(target)[0];shop_arrays=goods_arrays(target)
    before_event_root=None
    if change['kind']=='map_event':
        from vxace_python_mutator import load
        from vxace_map_events import snapshot as event_snapshot,blank_snapshot
        before_event_root=load(target)[0]
        before_event=blank_snapshot(before_event_root,mutation['donor_event_id']) if mutation['action']=='append_blank_event' else event_snapshot(before_event_root,mutation['template_id'])
    before_tile_root=None
    if change['kind']=='map_tile':
        from vxace_python_mutator import load
        from vxace_upper_tiles import snapshot as upper_snapshot
        before_tile_root=load(target)[0]
        tile_cells=[{'x':c['x'],'y':c['y']} for c in mutation['cells']]
        tile_values=sorted({c['value'] for c in mutation['cells']})
        tile_rtp=change['ruby_spec']['context']['rtp']
        before_tiles=upper_snapshot(before_tile_root,copy_root,tile_cells,tile_values,tile_rtp)
    before_label_root=None
    if change['kind']=='map_label':
        from vxace_python_mutator import load
        from vxace_maps import info_table
        before_label_root=load(target)[0];before_label=info_table(before_label_root)[mutation['map_id']].get('name').data.decode('utf-8')
    before_name_root=None
    if change['kind']=='map_name':
        from vxace_python_mutator import load
        from vxace_map_names import current as display_name
        before_name_root=load(target)[0];before_name=display_name(before_name_root)
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
    if reward_root is not None:
        from vxace_event_rewards import verify_transition as verify_rewards
        verify_rewards(reward_root,load(tmp)[0],mutation,target)
    if transfer_root is not None:
        from vxace_transfers import verify_transition as verify_transfer
        verify_transfer(transfer_root,load(tmp)[0],mutation,target)
    if region_cells:
        from vxace_map_regions import verify_transition
        verify_transition(before_region_root,load(tmp)[0],mutation)
    if change['kind']=='map_shop':
        from vxace_map_shops import verify_transition as verify_shop
        verify_shop(before_shop_root,load(tmp)[0],mutation,shop_arrays)
    if change['kind']=='map_encounter':
        from vxace_map_encounters import verify_transition as verify_encounter
        verify_encounter(before_encounter_root,load(tmp)[0],mutation,encounter_troops)
    if change['kind']=='database_entry':
        if entry_table=='items':
            from vxace_database_entries import verify_transition as verify_entry
            verify_entry(before_entry_root,load(tmp)[0],mutation)
        elif entry_table=='classes':
            from vxace_class_learning import verify_transition as verify_learning
            verify_learning(before_entry_root,load(tmp)[0],mutation,entry_skills)
        else:
            from vxace_database_append import verify_transition as verify_table_entry
            verify_table_entry(before_entry_root,load(tmp)[0],entry_table,mutation,entry_enemies)
    if change['kind']=='map_event':
        from vxace_map_events import verify_transition as verify_event
        verify_event(before_event_root,load(tmp)[0],mutation,copy_root,change['ruby_spec'].get('context',{}).get('rtp'))
    if change['kind']=='map_tile':
        from vxace_upper_tiles import verify_transition as verify_upper
        verify_upper(before_tile_root,load(tmp)[0],mutation)
    if change['kind']=='map_label':
        from vxace_map_labels import verify_transition as verify_label
        verify_label(before_label_root,load(tmp)[0],mutation,copy_root)
    if change['kind']=='map_name':
        from vxace_map_names import verify_transition as verify_name
        verify_name(before_name_root,load(tmp)[0],mutation)
    if change['kind']=='script_slot':
        from vxace_script_slots import verify_transition as verify_slot
        verify_slot(before_slot_root,load(tmp)[0],mutation)
    if before_sem==after_sem: raise RuntimeError(f'mutation produced no semantic change: {rel}')
    os.replace(tmp,target)
    rec={'kind':change['kind'],'target':rel,'description':change.get('description',''),'before_sha256':before_raw,'after_sha256':after_raw,'before_semantic_sha256':before_sem,'after_semantic_sha256':after_sem}
    if reward_root is not None:rec['one_time_rewards']={**reward_evidence,'only_approved_native_map_change':True}
    if transfer_root is not None:rec['direct_transfer']={**transfer_evidence,'only_approved_native_map_change':True}
    if change['kind']=='map_label':
        after_label=info_table(load(target)[0])[mutation['map_id']].get('name').data.decode('utf-8')
        rec['map_label']={'map_id':mutation['map_id'],'before':before_label,'after':after_label,
                          'other_entries_metadata_aliases_and_all_maps_preserved':True,'system_version_unchanged':True}
        rec['diff']=''.join(difflib.unified_diff([before_label+'\n'],[after_label+'\n'],fromfile='source-tree-name',tofile='staged-tree-name'))
    if change['kind']=='map_name':
        rec['map_name']={'map_id':change['locator']['map_id'],'before':before_name,'after':display_name(load(target)[0]),
                         'only_display_name_changed':True,'other_native_fields_and_aliases_preserved':True}
        rec['diff']=''.join(difflib.unified_diff([before_name+'\n'],[rec['map_name']['after']+'\n'],fromfile='source-display-name',tofile='staged-display-name'))
    if change['kind']=='map_encounter':
        final_map=load(target)[0]
        rec['encounter']={'locator':change['locator'],'before':{'encounters':before_encounters,'encounter_step':before_encounter_step},
                          'after':{'encounters':encounter_rows(final_map),'encounter_step':final_map.get('encounter_step')},
                          'existing_encounters_unchanged':True,'other_map_fields_unchanged':True,'troops_unchanged':True}
        rec['diff']=''.join(difflib.unified_diff(json.dumps(rec['encounter']['before'],indent=2).splitlines(True),json.dumps(rec['encounter']['after'],indent=2).splitlines(True),fromfile='source-encounters',tofile='staged-encounters'))
    if change['kind']=='map_shop':
        from vxace_map_shops import validate as validate_shop
        rows,evidence=validate_shop(before_shop_root,mutation,shop_arrays)
        rec['shop']={'locator':change['locator'],**evidence,'inserted_rows':[{'code':code,'indent':0,'parameters':params} for code,params in rows],
                     'only_approved_event_list_changed':True,'goods_arrays_unchanged':True}
        rec['diff']=''.join(difflib.unified_diff([],[json.dumps(row)+chr(10) for row in rec['shop']['inserted_rows']],fromfile='source-shop-rows',tofile='staged-shop-rows'))
    if change['kind']=='map_event':
        blank=mutation['action']=='append_blank_event'
        rec['map_event']={'before':before_event,'after':blank_snapshot(load(target)[0],mutation['donor_event_id']) if blank else event_snapshot(load(target)[0],mutation['template_id']),
                          'new_id':mutation['new_id'],'name':mutation['name'],'x':mutation['x'],'y':mutation['y'],
                          'old_events_and_other_map_fields_preserved':True}
        if blank:rec['map_event'].update(action='append_blank_event',donor_event_id=mutation['donor_event_id'],blank_template_predicate_ok=True)
        else:rec['map_event']['text']=mutation['text']
        if 'graphic' in mutation:rec['map_event'].update(graphic=mutation['graphic'],asset=mutation['expected_asset'])
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
        after_entry=entry_snapshot(load(target)[0],entry_key)
        if entry_table=='classes':
            if sha256(target.parent/'Skills.rvdata2')!=entry_skills_sha:raise RuntimeError('Skills file changed during class learning append')
            rec['entry']={'before':before_entry,'after':after_entry,'class_id':mutation['class_id'],'skill_id':mutation['skill_id'],'level':mutation['level'],
                          'other_classes_and_existing_learnings_unchanged':True,'skills_unchanged':True,'approved_class_learning_verified':True,'table':'classes'}
        else:rec['entry']={'before':before_entry,'after':after_entry,'created_id':mutation['new_id'],
                      'existing_entries_unchanged':True,
                      ('approved_inert_key_item_verified' if entry_table=='items' else 'approved_template_clone_verified'):True,
                      'table':entry_table}
        rec['diff']=''.join(difflib.unified_diff(json.dumps(before_entry,indent=2).splitlines(True),json.dumps(after_entry,indent=2).splitlines(True),fromfile='source-'+entry_table,tofile='staged-'+entry_table))
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
    from vxace_event_rewards import has_rewards
    reward_changes=[c for c in structural if has_rewards(c['ruby_spec']['mutation'])]
    if reward_changes and len(changes)!=1:raise ValueError('One-time reward insertion requires its own single-change transaction')
    for c in reward_changes:
        from vxace_map_regions import integer
        loc=c['locator']
        if set(loc)!={'map_id','event_id','page','command_index'}:raise ValueError('Exact reward map/page/root locator required')
        integer(loc['map_id'],'reward map ID',1,999);integer(loc['event_id'],'reward event ID',1,999)
    regions=[c for c in changes if c['kind']=='map_region']
    entries=[c for c in changes if c['kind']=='database_entry']
    slots=[c for c in changes if c['kind']=='script_slot']
    upper_tiles=[c for c in changes if c['kind']=='map_tile']
    map_events=[c for c in changes if c['kind']=='map_event']
    map_entries=[c for c in changes if c['kind']=='map_entry']
    from vxace_transfers import has_transfers
    transfers=[c for c in structural if has_transfers(c['ruby_spec']['mutation'])]
    if transfers and len(changes)!=1:raise ValueError('Direct transfer requires its own single-change transaction')
    map_names=[c for c in changes if c['kind']=='map_name']
    if map_names:
        if len(changes)!=1:raise ValueError('Display-name edit requires its own single-change transaction')
        if no_reindex or mutator.resolve()!=(Path(__file__).resolve().parent/'vxace_python_mutator.py'):
            raise ValueError('Display-name edits require the explicit Python backend and mandatory post-copy re-indexing')
        from vxace_index_query import Index,unlinked
        from vxace_python_mutator import load
        from vxace_map_names import indexed_snapshot,validate as validate_name
        for c in map_names:
            name_data=Index(index);indexed_snapshot(name_data,project,c['locator']['map_id']);name_data.unchanged()
            validate_name(load(unlinked(project/c['target']))[0],c['mutation'])
    encounters=[c for c in changes if c['kind']=='map_encounter']
    if encounters:
        if len(encounters)!=1:raise ValueError('Use one map encounter append per transaction')
        if any(c is not encounters[0] and c['target'] in (encounters[0]['target'],'Data/Troops.rvdata2') for c in changes):
            raise ValueError('Encounter append cannot be combined with other changes to the same map or to Troops')
        if no_reindex or mutator.resolve()!=(Path(__file__).resolve().parent/'vxace_python_mutator.py'):
            raise ValueError('Encounter appends require the explicit Python backend and mandatory post-copy re-indexing')
        from vxace_index_query import Index,unlinked
        from vxace_python_mutator import load
        from vxace_map_encounters import indexed_snapshot as encounter_snapshot,troops_for,apply as encounter_apply
        for c in encounters:
            encounter_data=Index(index);encounter_snapshot(encounter_data,project,c['locator']['map_id']);encounter_data.unchanged()
            encounter_apply(load(unlinked(project/c['target']))[0],c['mutation'],troops_for(project/c['target']))
    shops=[c for c in changes if c['kind']=='map_shop']
    if shops:
        if len(shops)!=1:raise ValueError('Use one shop append per transaction')
        if any(c is not shops[0] and c['target'] in (shops[0]['target'],'Data/Items.rvdata2','Data/Weapons.rvdata2','Data/Armors.rvdata2') for c in changes):
            raise ValueError('Shop append cannot be combined with other changes to the same map or to Items/Weapons/Armors')
        if no_reindex or mutator.resolve()!=(Path(__file__).resolve().parent/'vxace_python_mutator.py'):
            raise ValueError('Shop appends require the explicit Python backend and mandatory post-copy re-indexing')
        from vxace_index_query import Index,unlinked
        from vxace_python_mutator import load
        from vxace_map_shops import indexed_snapshot as shop_snapshot,goods_arrays as shop_goods,apply as shop_apply
        for c in shops:
            shop_data=Index(index);shop_snapshot(shop_data,project,c['locator']['map_id'],c['locator']['event_id']);shop_data.unchanged()
            shop_apply(load(unlinked(project/c['target']))[0],c['ruby_spec']['mutation'],shop_goods(project/c['target']))
    reload_required=bool(structural or regions or upper_tiles or map_events or map_names or encounters or shops)
    map_labels=[c for c in changes if c['kind']=='map_label']
    if map_labels:
        if len(changes)!=1:raise ValueError('Map-tree name edit requires its own single-change transaction')
        if no_reindex or mutator.resolve()!=(Path(__file__).resolve().parent/'vxace_python_mutator.py'):
            raise ValueError('Map-tree name edits require explicit Python backend and mandatory post-copy re-indexing')
        from vxace_index_query import Index,unlinked
        from vxace_python_mutator import load
        from vxace_map_labels import indexed_snapshot,validate as validate_label
        for c in map_labels:
            label_data=Index(index);indexed_snapshot(label_data,project,c['locator']['map_id']);label_data.unchanged()
            validate_label(load(unlinked(project/c['target']))[0],c['mutation'],project)
    post_required=bool(reload_required or entries or slots or map_entries or map_labels)
    if map_entries:
        if len(changes)!=1:raise ValueError('Map append requires its own single-change transaction')
        if no_reindex or mutator.resolve()!=(Path(__file__).resolve().parent/'vxace_python_mutator.py'):
            raise ValueError('Map append requires explicit Python backend and mandatory post-copy indexing')
        from vxace_maps import snapshot as map_snapshot,candidates as map_candidates
        from vxace_index_query import Index,unlinked
        from vxace_python_mutator import load
        for c in map_entries:
            map_data=Index(index);map_snapshot(map_data,project,c['mutation']['template_map_id']);map_data.unchanged()
            map_candidates(load(unlinked(project/c['target']))[0],c['mutation'],project)
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
            blank=c['mutation']['action']=='append_blank_event'
            event_indexed_snapshot(event_data,project,c['locator']['map_id'],c['mutation']['donor_event_id'] if blank else c['mutation']['template_id'],c['mutation'].get('graphic'),rtp,blank)
            event_data.unchanged()
            new_event(load(unlinked(project/c['target']))[0],c['mutation'],project,rtp)
            if 'graphic' in c['mutation']:c['ruby_spec']['context']={'rtp':str(rtp) if rtp else None}
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
        if len(entries)!=1 or any(c['target']==entries[0]['target'] and c['kind']!='database_entry' for c in changes):
            raise ValueError('Append one database entry per transaction without other mutations to the same table')
        if no_reindex or mutator.resolve() != (Path(__file__).resolve().parent/'vxace_python_mutator.py'):
            raise ValueError('Entry creation requires the explicit Python backend and mandatory post-copy re-indexing')
        from vxace_python_mutator import load
        from vxace_database_entries import new_key_item, indexed_snapshot
        from vxace_database_append import new_entry, enemies_for
        from vxace_index_query import Index, unlinked
        for c in entries:
            table=c['locator']['table']
            if table=='classes':
                if any(o['target']=='Data/Skills.rvdata2' for o in changes):
                    raise ValueError('Class learning append reads Skills read-only; it cannot be combined with changes to Skills')
                from vxace_class_learning import indexed_snapshot as learning_indexed, validate as learning_validate, skills_for as learning_skills
                learning_data=Index(index);learning_indexed(learning_data,project,c['locator']['id']);learning_data.unchanged()
                learning_validate(load(unlinked(project/c['target']))[0],c['ruby_spec']['mutation'],learning_skills(project/c['target']))
                continue
            indexed_snapshot(Index(index),project,c['mutation']['template_id'],table)
            native=load(unlinked(project/c['target']))[0]
            if table=='items':new_key_item(native,c['mutation'])
            else:new_entry(native,table,c['mutation'],enemies_for(project/c['target']) if table=='troops' else None)
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
        for c in structural: validate_project_references(index,c['ruby_spec']['mutation'],project/c['target'])
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
    targets={c['target'] for c in changes}|{f"Data/Map{c['mutation']['template_map_id']:03d}.rvdata2" for c in map_entries}
    for rel in sorted(targets):
        preflights.append(roundtrip_preflight(ruby,mutator,project/safe_rel(rel)))
    shutil.copytree(project,copy_root)
    try:
        if current_inventory(copy_root)!=source_before: raise RuntimeError('clone inventory differs from the verified source snapshot')
        applied=[]
        for i,c in enumerate(changes,1): applied.append(apply_one(ruby,mutator,copy_root,c,audit_dir,i))
        label_inventory=None
        if map_labels:
            label_inventory={**source_before,**{record['target']:record['after_sha256'] for record in applied}}
            if current_inventory(copy_root)!=label_inventory:raise RuntimeError('Map-tree name edit changed unapproved copied files')
        name_inventory=None
        if map_names:
            name_inventory={**source_before,**{record['target']:record['after_sha256'] for record in applied}}
            if current_inventory(copy_root)!=name_inventory:raise RuntimeError('Display-name edit changed unapproved copied files')
        shop_inventory=None
        if shops:
            shop_inventory={**source_before,**{record['target']:record['after_sha256'] for record in applied}}
            if current_inventory(copy_root)!=shop_inventory:raise RuntimeError('Shop append changed unapproved copied files')
        transfer_inventory=None
        if transfers:
            transfer_inventory={**source_before,**{record['target']:record['after_sha256'] for record in applied}}
            if current_inventory(copy_root)!=transfer_inventory:
                raise RuntimeError('Transfer changed unapproved copied files')
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
                if regions or upper_tiles or map_entries or transfers or map_names or map_labels or encounters or shops:
                    from vxace_map_audit import audit as map_audit
                    from vxace_index_query import Index
                    reports=[map_audit(Index(post),c['locator']['map_id']) for c in regions+upper_tiles+map_names+map_labels+encounters+shops]
                    reports += [map_audit(Index(post),c['mutation']['new_id']) for c in map_entries]
                    reports += [map_audit(Index(post),mid) for c in transfers for mid in (c['locator']['map_id'],c['ruby_spec']['mutation']['commands'][0]['parameters'][1])]
                    if any(r['findings'] for r in reports): raise RuntimeError('post-copy selected-map tile audit failed')
                    dump_json(audit_dir/'post-map-audit.json',reports)
        if upper_tiles:
            from vxace_upper_tiles import asset_context
            from vxace_python_mutator import load
            for c in upper_tiles:asset_context(load(copy_root/c['target'])[0],c['mutation'],copy_root,rtp)
        if map_events:
            from vxace_character_graphics import binding
            for c in map_events:
                if 'graphic' in c['mutation'] and binding(copy_root,rtp,c['mutation']['graphic'])!=c['mutation']['expected_asset']:
                    raise RuntimeError('Character asset changed during final verification')
        if reward_changes:
            from vxace_event_rewards import item_context
            for c in reward_changes:item_context(c['ruby_spec']['mutation'],copy_root/c['target'])
        for c in map_entries:
            if current_inventory(copy_root)!=c['_expected_copy_inventory']:raise RuntimeError('Map append final copied-file preservation check failed')
        if transfers:
            from vxace_transfers import final_context
            for c in transfers:final_context(c['ruby_spec']['mutation'],copy_root)
            if current_inventory(copy_root)!=transfer_inventory:raise RuntimeError('Transfer final copied-file preservation check failed')
        if shops:
            from vxace_map_shops import final_context as shop_final_context
            for c in shops:shop_final_context(c['ruby_spec']['mutation'],copy_root)
            if current_inventory(copy_root)!=shop_inventory:raise RuntimeError('Shop final copied-file preservation check failed')
        if map_labels and current_inventory(copy_root)!=label_inventory:raise RuntimeError('Map-tree name final copied-file preservation check failed')
        if map_names and current_inventory(copy_root)!=name_inventory:raise RuntimeError('Display-name final copied-file preservation check failed')
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
