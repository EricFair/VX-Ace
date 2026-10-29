#!/usr/bin/env python3
"""Read-only blank-map append evidence and pure native candidate construction."""
from __future__ import annotations
import argparse,hashlib,json,re,sys
from pathlib import Path
from vxace_index_query import execute,unlinked
from vxace_map_regions import integer,table_for
from vxace_map_events import exact,text,events_for,template

VERSION='1.2.0'
INFO_FIELDS={'name','parent_id','order','expanded','scroll_x','scroll_y'}
MAP_FIELDS={'autoplay_bgm','autoplay_bgs','battleback1_name','battleback2_name','bgm','bgs','data','disable_dashing',
            'display_name','encounter_list','encounter_step','events','height','note','parallax_loop_x','parallax_loop_y',
            'parallax_name','parallax_show','parallax_sx','parallax_sy','scroll_type','specify_battleback','tileset_id','width'}
FIELDS={'action','template_map_id','new_id','name','expected_infos_sha256','expected_template_sha256',
        'expected_inventory_sha256','expected_tilesets_sha256'}
# v1.26 optional parameters: a size / tileset / parent override and a bounded A5 floor fill (see references/new-areas.md).
OPTIONS=('width','height','tileset_id','parent_id','fill_floor')
FRESH_KEYS={'width','height','tileset_id'}   # all three given: fresh-map mode, the template supplies only the native schema (no content is copied)
MIN_WIDTH,MIN_HEIGHT,MAX_SIZE=17,13,500
A5_BASE,A5_COUNT=1536,128   # Tilemap A5: tile ids 1536..1663 are plain (non-autotile) tiles of the A5 sheet (tileset_names[4])


def schema_ok(mutation,with_template=True):
    """Exact required fields plus any subset of the optional ones."""
    required=FIELDS if with_template else FIELDS-{'template_map_id'}
    return isinstance(mutation,dict) and required<=set(mutation)<=required|set(OPTIONS)


def digest(value):
    from vxace_python_mutator import marshal_rb
    return hashlib.sha256(marshal_rb.dump(value)).hexdigest()


def info_table(root):
    from vxace_python_mutator import RubyHash,RubyString
    if not isinstance(root,RubyHash) or root.default is not None or not 1<=len(root.pairs)<=999:raise ValueError('Bounded native map-info hash required')
    ids=set();orders=set();owners=set()
    for key,info in root.pairs:
        integer(key,'map-info ID',1,999)
        if key in ids or id(info) in owners:raise ValueError('Ambiguous map-info identities')
        ids.add(key);owners.add(id(info));exact(info,'RPG::MapInfo',INFO_FIELDS)
        name=info.get('name')
        if not isinstance(name,RubyString) or name.ivars not in ({},{'E':True},{'E':False}):raise ValueError('Native map-info name required')
        name.data.decode('utf-8','strict')
        integer(info.get('parent_id'),'parent map ID',0,999)
        order=integer(info.get('order'),'map order',1,2**31-1)
        if order in orders:raise ValueError('Ambiguous map-tree order')
        orders.add(order)
        if type(info.get('expanded')) is not bool:raise ValueError('Native expanded flag required')
        for field in ('scroll_x','scroll_y'):integer(info.get(field),field,0,2**31-1)
    lookup=dict(root.pairs)
    for key in ids:
        seen=set();current=key
        while current:
            if current in seen or current not in lookup:raise ValueError('Map-tree parent is cyclic or missing')
            seen.add(current);current=lookup[current].get('parent_id')
    return lookup


def inert_map(root):
    from vxace_python_mutator import RubyString
    exact(root,'RPG::Map',MAP_FIELDS);table=table_for(root)
    if any(value>15 for value in table.data[table.xsize*table.ysize*3:]):raise ValueError('Blank-map template cannot copy region IDs or opaque lower metadata')
    for field in ('autoplay_bgm','autoplay_bgs','specify_battleback','parallax_loop_x','parallax_loop_y','parallax_show'):
        if root.get(field) is not False:raise ValueError('Select an inert non-looping template without automatic audio/background behavior')
    if type(root.get('disable_dashing')) is not bool:raise ValueError('Native dashing flag required')
    for field in ('battleback1_name','battleback2_name','display_name','note','parallax_name'):
        value=root.get(field)
        if not isinstance(value,RubyString) or value.data or value.ivars not in ({},{'E':True},{'E':False}):raise ValueError('Template names/notes/backgrounds must be empty')
    for field,cls in (('bgm','RPG::BGM'),('bgs','RPG::BGS')):
        audio=exact(root.get(field),cls,{'name','volume','pitch'})
        if not isinstance(audio.get('name'),RubyString) or audio.get('name').data:raise ValueError('Template audio must be empty')
        integer(audio.get('volume'),'audio volume',0,100);integer(audio.get('pitch'),'audio pitch',50,150)
    if root.get('encounter_list')!=[]:raise ValueError('Template encounters must be empty')
    integer(root.get('encounter_step'),'encounter step',1,999)
    integer(root.get('scroll_type'),'scroll type',0,0)
    for field in ('parallax_sx','parallax_sy'):integer(root.get(field),field,0,0)
    integer(root.get('tileset_id'),'tileset ID',1,999)
    events=events_for(root)
    for key,_ in events.pairs:template(root,key)
    return root


def schema_map(root):
    """Fresh-map mode: the template only has to be a native RPG::Map with the exact field set, a valid Table and native audio objects.
    None of its content (events, encounters, regions, notes, audio names, backgrounds) is copied, so none of it is judged."""
    from vxace_python_mutator import RubyString
    exact(root,'RPG::Map',MAP_FIELDS);table_for(root);events_for(root)
    for field,cls in (('bgm','RPG::BGM'),('bgs','RPG::BGS')):
        exact(root.get(field),cls,{'name','volume','pitch'})
    for field in ('battleback1_name','battleback2_name','display_name','note','parallax_name'):
        if not isinstance(root.get(field),RubyString):raise ValueError('Native string field required in the schema template')
    return root


def fresh_map(native,plan):
    """The editor's new-map defaults (RPG::Map#initialize; confirmed on the editor-created default map of project2.zip) in the template's object shapes."""
    from vxace_python_mutator import marshal_rb,RubyString,RubyHash
    new_map=marshal_rb.load(marshal_rb.dump(native))
    empty=lambda:RubyString(b'',{})
    for field,value in (('encounter_list',[]),('encounter_step',30),('autoplay_bgm',False),('autoplay_bgs',False),('specify_battleback',False),('disable_dashing',False),
                        ('scroll_type',0),('parallax_loop_x',False),('parallax_loop_y',False),('parallax_show',False),('parallax_sx',0),('parallax_sy',0)):
        new_map.set(field,value)
    for field in ('display_name','note','parallax_name','battleback1_name','battleback2_name'):new_map.set(field,empty())
    for field,volume in (('bgm',100),('bgs',80)):
        audio=new_map.get(field);audio.set('name',empty());audio.set('volume',volume);audio.set('pitch',100)
    new_map.set('events',RubyHash([],None))
    new_map.set('width',plan['width']);new_map.set('height',plan['height']);new_map.set('tileset_id',plan['tileset_id']);new_map.set('data',new_table(plan))
    return new_map


def inventory(project):
    directory=unlinked(Path(project)/'Data');rows=[];total=0
    for file in sorted(directory.iterdir()):
        match=re.fullmatch(r'map([0-9]+)\.rvdata2',file.name,re.IGNORECASE)
        if not match:continue
        identifier=integer(int(match[1]),'native map-file ID',1,999)
        if file.name!=f'Map{identifier:03d}.rvdata2':raise ValueError('Noncanonical or case-aliased map filename')
        file=unlinked(file);size=file.stat().st_size;total+=size
        if not file.is_file() or size>64*1024*1024 or total>128*1024*1024:raise ValueError('Map inventory byte budget exceeded')
        with file.open('rb') as stream:raw=stream.read(64*1024*1024+1)
        if len(raw)!=size:raise ValueError('Map inventory changed while reading')
        rows.append({'id':identifier,'sha256':hashlib.sha256(raw).hexdigest()})
    if not rows or len(rows)>999:raise ValueError('Bounded native map inventory required')
    return rows,hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def context(infos,project,template_id,fresh=False):
    from vxace_python_mutator import load,RubyObject
    project=unlinked(project)
    actual,_=load(unlinked(project/'Data/MapInfos.rvdata2'))
    if digest(actual)!=digest(infos):raise ValueError('Actual native map tree disagrees with supplied candidate context')
    lookup=info_table(infos);integer(template_id,'template map ID',1,999)
    if template_id not in lookup:raise ValueError('Template map missing from native map tree')
    rows,inventory_hash=inventory(project)
    if {row['id'] for row in rows}!=set(lookup):raise ValueError('Native map files/tree disagree; orphan files or missing maps refuse append')
    native,raw=load(unlinked(project/f'Data/Map{template_id:03d}.rvdata2'));schema_map(native) if fresh else inert_map(native)
    from vxace_python_mutator import marshal_rb
    if marshal_rb.dump(native)!=raw:raise ValueError('Template map must round-trip byte-identically immediately before use')
    tilesets,_=load(unlinked(project/'Data/Tilesets.rvdata2'));identifier=native.get('tileset_id')
    if fresh:
        if not isinstance(tilesets,list):raise ValueError('Native Tilesets array required')
    elif not isinstance(tilesets,list) or identifier>=len(tilesets) or not isinstance(tilesets[identifier],RubyObject) or tilesets[identifier].cls!='RPG::Tileset' or type(tilesets[identifier].get('id')) is not int or tilesets[identifier].get('id')!=identifier:
        raise ValueError('Actual native template tileset is missing or ambiguous')
    return native,{'expected_infos_sha256':digest(infos),'expected_template_sha256':digest(native),
                   'expected_inventory_sha256':inventory_hash,'expected_tilesets_sha256':digest(tilesets)},lookup


def plain(value,depth=0):
    from vxace_python_mutator import RubyObject,RubyHash,RubyString,Table
    if depth>128:raise ValueError('Native snapshot nesting budget exceeded')
    if value is None or type(value) in (int,bool):return value
    if isinstance(value,RubyString):return value.data.decode('utf-8','strict')
    if isinstance(value,list):return [plain(item,depth+1) for item in value]
    if isinstance(value,RubyObject):return {'__class__':value.cls,**{key[1:]:plain(item,depth+1) for key,item in value.ivars.items()}}
    if isinstance(value,RubyHash):return {str(key):plain(item,depth+1) for key,item in value.pairs}
    if isinstance(value,Table):return {'__class__':'Table','dimensions':value.dim,'xsize':value.xsize,'ysize':value.ysize,'zsize':value.zsize,'data':list(value.data)}
    raise ValueError('Opaque native snapshot value')


def passable_floor(names,flags,index):
    """Refuse unless the tileset's A5 sheet is set and the chosen plain A5 tile blocks no direction (same flag rules as tile_passage)."""
    from vxace_map_audit import tile_passage
    if type(index) is not int or not 0<=index<A5_COUNT:raise ValueError(f'fill_floor must be an A5 tile index 0..{A5_COUNT-1}')
    if not names[4]:raise ValueError('fill_floor needs a tileset whose A5 sheet (tileset_names[4]) is set')
    tile_id=A5_BASE+index
    if not all(tile_passage([tile_id],flags).values()):raise ValueError('fill_floor tile is not passable in every direction (or carries the star flag) in this tileset')
    return tile_id


def resolve_options(native,lookup,project,options):
    """Validated v1.26 options of a blank map: size, tileset, parent and floor fill. Returns the resolved plan of the new map."""
    from vxace_python_mutator import RubyObject
    from vxace_upper_tiles import tileset
    if not isinstance(options,dict) or set(options)-set(OPTIONS):raise ValueError('Unknown blank-map option')
    width=integer(options['width'],'new map width',MIN_WIDTH,MAX_SIZE) if 'width' in options else native.get('width')
    height=integer(options['height'],'new map height',MIN_HEIGHT,MAX_SIZE) if 'height' in options else native.get('height')
    tileset_id=integer(options['tileset_id'],'new map tileset ID',1,999) if 'tileset_id' in options else native.get('tileset_id')
    parent=integer(options.get('parent_id',0),'parent map ID',0,999)
    if parent and parent not in lookup:raise ValueError('Parent map is missing from the native map tree')
    tile_id=None
    if 'fill_floor' in options or tileset_id!=native.get('tileset_id'):   # the template's own tileset was already bound by context()
        _,names,flags=tileset(RubyObject('RPG::Map',{'@tileset_id':tileset_id}),project)
        if 'fill_floor' in options:tile_id=passable_floor(names,flags,options['fill_floor'])
    fresh=FRESH_KEYS<=set(options)
    rebuilt=fresh or tile_id is not None or (width,height,tileset_id)!=(native.get('width'),native.get('height'),native.get('tileset_id'))
    return {'fresh':fresh,'width':width,'height':height,'tileset_id':tileset_id,'parent_id':parent,'fill_floor':options.get('fill_floor'),'floor_tile_id':tile_id,'tiles_rebuilt':rebuilt}


def new_table(plan):
    """Empty Table (all layers, regions and shadows 0); layer 0 is filled with the single A5 floor tile when requested."""
    from vxace_python_mutator import Table
    cells=plan['width']*plan['height']
    return Table(plan['width'],plan['height'],4,dim=3,data=[plan['floor_tile_id'] or 0]*cells+[0]*(cells*3))


def native_snapshot(project,template_id,options=None):
    """Snapshot fields computed from the native files only (also used by the recipe dry-run on its in-memory state)."""
    from vxace_python_mutator import load
    infos,_=load(unlinked(Path(project)/'Data/MapInfos.rvdata2'))
    native,guard,lookup=context(infos,project,template_id,FRESH_KEYS<=set(options or {}))
    plan=resolve_options(native,lookup,project,options or {})
    return infos,native,{'version':VERSION,'template_map_id':template_id,'new_id':integer(max(lookup)+1,'next map ID',1,999),'width':native.get('width'),'height':native.get('height'),
            'template_inert_event_count':len(native.get('events').pairs),'guard':guard,
            'planned_map':{key:plan[key] for key in ('fresh','width','height','tileset_id','parent_id','fill_floor','floor_tile_id','tiles_rebuilt')},
            'limits':['One new map at the next maximum ID, root-level unless a parent is given; inherited dimensions/tiles/tileset unless a size, tileset or floor fill is given, and no events.',
                      'A size, tileset change or fill_floor rebuilds the tile Table: every layer, region and shadow is 0 except an optional single passable A5 tile on layer 0 (a walkable placeholder room, not level design).',
                      'Template must have no logic, conditions, encounters, notes or automatic backgrounds/audio; only inert placeholder events can be discarded in the new map.',
                      'No delete, reparent, ID reuse, transfer authoring in this operation or general map writer; review dynamic map/save consumers.']}


def snapshot(data,project,template_id,options=None):
    infos,native,result=native_snapshot(project,template_id,options)
    if json.dumps(data.json('database/map-infos.json'),sort_keys=True)!=json.dumps(plain(infos),sort_keys=True):raise ValueError('Native/indexed map template or tree disagree')
    indexed=data.json(f'maps/map-{template_id:03d}.json')
    if result['planned_map']['fresh']:   # only the schema is used: size and tileset of the indexed template must agree, its content is never copied
        if not isinstance(indexed,dict) or any(indexed.get(key)!=native.get(key) for key in ('width','height','tileset_id')):raise ValueError('Native/indexed map template or tree disagree')
    elif json.dumps(indexed,sort_keys=True)!=json.dumps(plain(native),sort_keys=True):raise ValueError('Native/indexed map template or tree disagree')
    return result


def candidates(infos,mutation,project):
    from vxace_python_mutator import marshal_rb,RubyString,RubyHash
    if not schema_ok(mutation) or mutation.get('action')!='append_blank_map':raise ValueError('Exact append_blank_map schema required')
    native,guard,lookup=context(infos,project,mutation['template_map_id'],FRESH_KEYS<=set(mutation))
    for field,value in guard.items():
        if not isinstance(mutation[field],str) or mutation[field]!=value:raise ValueError('Stale actual native map/tree/tileset/inventory guard')
    identifier=integer(mutation['new_id'],'new map ID',1,999)
    if identifier!=max(lookup)+1:raise ValueError('Append at next maximum map ID; no hole reuse')
    name=text(mutation['name'],'new map name',100)
    if any(info.get('name').data.decode('utf-8','strict')==name for info in lookup.values()):raise ValueError('Choose a unique new map name')
    plan=resolve_options(native,lookup,project,{key:mutation[key] for key in OPTIONS if key in mutation})
    updated=marshal_rb.load(marshal_rb.dump(infos))
    new_info=marshal_rb.load(marshal_rb.dump(lookup[mutation['template_map_id']]))
    new_info.set('name',RubyString(name.encode('utf-8'),{'E':True}))
    order=integer(max(info.get('order') for info in lookup.values())+1,'next map order',1,2**31-1)
    for key,value in {'parent_id':plan['parent_id'],'order':order,'expanded':False,'scroll_x':0,'scroll_y':0}.items():new_info.set(key,value)
    updated.pairs.append((identifier,new_info))
    if plan['fresh']:return updated,fresh_map(native,plan)
    new_map=marshal_rb.load(marshal_rb.dump(native));new_map.set('events',RubyHash([],None))
    if plan['tiles_rebuilt']:
        new_map.set('width',plan['width']);new_map.set('height',plan['height']);new_map.set('tileset_id',plan['tileset_id']);new_map.set('data',new_table(plan))
    return updated,new_map


def verify(infos,after_infos,after_map,mutation,project):
    from vxace_python_mutator import marshal_rb
    expected_info,expected_map=candidates(infos,mutation,project)
    if marshal_rb.dump(after_infos)!=marshal_rb.dump(expected_info) or marshal_rb.dump(after_map)!=marshal_rb.dump(expected_map):
        raise ValueError('New map/tree candidate changed unapproved bytes or fields')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('index');parser.add_argument('--project',required=True)
    parser.add_argument('--template-map',type=int,required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--width',type=int);parser.add_argument('--height',type=int);parser.add_argument('--tileset-id',type=int)
    parser.add_argument('--parent-id',type=int);parser.add_argument('--fill-floor',type=int,help='A5 tile index 0..127 for layer 0 of the whole new map')
    args=parser.parse_args(argv)
    options={key:getattr(args,key) for key in OPTIONS if getattr(args,key) is not None}
    try:result=execute(args.index,args.project,args.output,lambda data:snapshot(data,args.project,args.template_map,options),'map-append-snapshot')
    except Exception as error:print('Map append snapshot refused: '+str(error),file=sys.stderr);return 2
    print(json.dumps({'status':'ok','new_id':result['new_id'],'mutation_authorized':False}));return 0


if __name__=='__main__':raise SystemExit(main())
