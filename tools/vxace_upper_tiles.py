#!/usr/bin/env python3
"""Guarded ordinary B-E painting on existing native map graphic layer two only."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from vxace_index_query import execute,unlinked
from vxace_map_regions import table_for,fingerprint,integer
from vxace_map_audit import tile_info,tile_passage
from vxace_asset_audit import catalog,safe_name
from vxace_image_headers import read_header

VERSION='0.25.0'
MAX_CELLS=256
MAX_IMAGE_BYTES=32*1024*1024
FIELDS={'action','expected_table_sha256','expected_tileset_sha256','expected_assets','cells'}


def digest(value):
    from vxace_python_mutator import marshal_rb
    return hashlib.sha256(marshal_rb.dump(value)).hexdigest()


def coordinates(cells,table,snapshot=False):
    if not isinstance(cells,list) or not 1<=len(cells)<=MAX_CELLS:raise ValueError('Select 1..256 unique upper graphic cells')
    seen=set()
    for cell in cells:
        fields={'x','y'} if snapshot else {'x','y','expected_tile','value'}
        if not isinstance(cell,dict) or set(cell)!=fields:raise ValueError('Unsupported upper-cell fields; layer is fixed at two')
        x=integer(cell['x'],'cell x',0,table.xsize-1);y=integer(cell['y'],'cell y',0,table.ysize-1)
        if (x,y) in seen:raise ValueError('Duplicate upper tile cell')
        seen.add((x,y))
        if not snapshot:
            integer(cell['expected_tile'],'expected B-E tile',0,1023);integer(cell['value'],'new B-E tile',0,1023)
        yield cell,x+y*table.xsize+2*table.xsize*table.ysize


def tileset(root,project):
    from vxace_python_mutator import load,RubyObject,RubyString,Table
    identifier=integer(root.get('tileset_id'),'native map tileset ID',1,999999)
    values,_=load(unlinked(Path(project)/'Data/Tilesets.rvdata2'))
    if not isinstance(values,list) or identifier>=len(values):raise ValueError('Native tileset entry is missing')
    selected=values[identifier]
    if not isinstance(selected,RubyObject) or selected.cls!='RPG::Tileset' or type(selected.get('id')) is not int or selected.get('id')!=identifier:
        raise ValueError('Native tileset identity is ambiguous')
    names=selected.get('tileset_names');flags=selected.get('flags')
    if not isinstance(names,list) or len(names)!=9 or any(not isinstance(name,RubyString) for name in names):raise ValueError('Exactly nine native tileset names required')
    names=[name.data.decode('utf-8','strict') for name in names]
    if not isinstance(flags,Table) or (flags.dim,flags.xsize,flags.ysize,flags.zsize,len(flags.data))!=(1,8192,1,1,8192):
        raise ValueError('Exact native 8192-entry tileset flag Table required')
    if not flags.data[0]&0x10:raise ValueError('Native empty B tile must retain the star flag')
    return selected,names,flags.data


def asset_digest(path):
    path=unlinked(path)
    if not path.is_file():raise ValueError('Selected tileset asset must be a regular file')
    before=path.stat()
    if before.st_size>MAX_IMAGE_BYTES:raise ValueError('Selected tileset image exceeds 32 MiB')
    sha=hashlib.sha256();count=0
    with path.open('rb') as stream:
        opened=os.fstat(stream.fileno())
        for block in iter(lambda:stream.read(1024*1024),b''):
            count+=len(block)
            if count>MAX_IMAGE_BYTES:raise ValueError('Selected tileset image grew beyond byte budget')
            sha.update(block)
        after=os.fstat(stream.fileno())
    unlinked(path)
    stamp=lambda value:(value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns)
    if not stamp(before)==stamp(opened)==stamp(after)==stamp(path.stat()):raise ValueError('Selected tileset asset changed during hashing')
    header,_=read_header(path)
    if header.get('status')!='header_observed' or (header.get('width'),header.get('height'))!=(512,512):
        raise ValueError('Ordinary B-E painting requires a standard 512x512 PNG header')
    # Recheck around the separate header observation too.
    if stamp(before)!=stamp(path.stat()):raise ValueError('Selected tileset asset changed during header observation')
    return sha.hexdigest(),header


def assets(project,rtp,names,numbers):
    project=unlinked(project);roots=[('project',project)]
    if rtp is not None:
        rtp=unlinked(rtp)
        if rtp==project or project in rtp.parents or rtp in project.parents:raise ValueError('RTP must be an explicit separate read-only root')
        if not rtp.is_dir():raise ValueError('Explicit RTP root is missing')
        roots.append(('rtp',rtp))
    catalogs=[(label,root,*catalog(root)) for label,root in roots]
    bindings=[]
    for slot in sorted({tile_info(number)['sheet_slot'] for number in numbers if number}):
        name=names[slot]
        if not safe_name(name):raise ValueError('Selected B-E sheet name is empty or unsafe')
        wanted='Graphics/Tilesets/'+name.replace('\\','/')
        explicit=Path(wanted).suffix
        if explicit and explicit.lower()!='.png':raise ValueError('Only standard PNG B-E sheets are supported')
        key=str(Path(wanted).with_suffix('')) if explicit else wanted
        for label,root,entries,_ in catalogs:
            matches=entries.get(key.casefold(),[])
            if not matches:continue
            expected=wanted if explicit else wanted+'.png'
            if len(matches)!=1 or matches[0]!=expected or Path(matches[0]).suffix!='.png':
                raise ValueError('Selected tileset asset is ambiguous, case-mismatched or not PNG')
            sha,header=asset_digest(root/matches[0])
            bindings.append({'slot':slot,'name':name,'origin':label,'path':matches[0],
                             'sha256':sha,'width':header['width'],'height':header['height']})
            break
        else:raise ValueError('Selected tileset image is unresolved; provide the correct explicit RTP root if needed')
    # Catalog stamps bind resolution/casing and detect new competing overrides.
    for _,root,entries,stamp in catalogs:
        if catalog(root)!=(entries,stamp):raise ValueError('Asset catalog changed during upper tile review')
    return bindings


def schema(mutation):
    if not isinstance(mutation,dict) or set(mutation)!=FIELDS or mutation.get('action')!='paint_upper_tiles':
        raise ValueError('Only the exact paint_upper_tiles schema is supported')
    for field in ('expected_table_sha256','expected_tileset_sha256'):
        if not isinstance(mutation[field],str) or not re.fullmatch('[a-f0-9]{64}',mutation[field]):raise ValueError('Exact map Table/tileset SHA-256 preconditions required')


def asset_context(root,mutation,project,rtp=None):
    schema(mutation);table=table_for(root)
    selected,names,flags=tileset(root,project)
    if digest(selected)!=mutation['expected_tileset_sha256']:raise ValueError('Native tileset fingerprint is stale')
    numbers=set()
    for cell,_ in coordinates(mutation['cells'],table):numbers.update((cell['expected_tile'],cell['value']))
    bindings=assets(project,rtp,names,numbers)
    if mutation['expected_assets']!=bindings:raise ValueError('Selected tileset asset bindings are stale or inconsistent')
    return flags,bindings


def apply(root,mutation,project,rtp=None):
    from vxace_python_mutator import Table
    flags,bindings=asset_context(root,mutation,project,rtp)
    table=table_for(root)
    if fingerprint(table)!=mutation['expected_table_sha256']:raise ValueError('Native map Table fingerprint is stale')
    changes=[]
    for cell,pos in coordinates(mutation['cells'],table):
        if table.data[pos]!=cell['expected_tile']:raise ValueError('Native upper tile precondition is stale')
        if cell['expected_tile']==cell['value']:raise ValueError('No-op upper tile cell refused')
        changes.append((pos,cell['value']))
    updated=Table.from_payload(table.to_payload())
    for pos,value in changes:updated.data[pos]=value
    root.set('data',updated)


def snapshot(root,project,cells,tiles,rtp=None):
    table=table_for(root);selected,names,flags=tileset(root,project)
    if not isinstance(tiles,list) or not 1<=len(tiles)<=MAX_CELLS:raise ValueError('Select 1..256 prospective B-E tile IDs')
    prospective={integer(value,'prospective B-E tile ID',0,1023) for value in tiles}
    if len(prospective)!=len(tiles):raise ValueError('Duplicate prospective tile IDs')
    rows=[];numbers=set(prospective)
    for cell,pos in coordinates(cells,table,True):
        current=integer(table.data[pos],'existing upper B-E tile',0,1023);numbers.add(current)
        layers=[table.data[cell['x']+cell['y']*table.xsize+z*table.xsize*table.ysize] for z in (2,1,0)]
        rows.append({**cell,'layer':2,'tile_id':current,'passage':tile_passage(layers,flags)})
    bindings=assets(project,rtp,names,numbers)
    return {'version':VERSION,'width':table.xsize,'height':table.ysize,'layer':2,
            'table_sha256':fingerprint(table),'tileset_id':selected.get('id'),'tileset_sha256':digest(selected),
            'assets':bindings,'cells':rows,
            'prospective_tiles':[{'tile_id':number,**tile_info(number),'flag':flags[number],
                                 'passage_bits':flags[number]&15,'star':bool(flags[number]&16)} for number in sorted(prospective)],
            'limits':['Ordinary B-E graphics on layer2 only; ground/A5/autotiles/shadows/regions are never changed.',
                      'PNG header/layout and full file hashes do not prove full decoding or native runtime behavior.']}


def indexed_snapshot(data,project,map_id,cells,tiles,rtp=None):
    from vxace_python_mutator import load
    from vxace_map_regions import indexed_snapshot as region_snapshot
    region_snapshot(data,project,map_id,cells)
    root,_=load(unlinked(Path(project)/f'Data/Map{map_id:03d}.rvdata2'))
    selected,names,flags=tileset(root,project)
    indexed=data.json('database/tilesets.json');identifier=selected.get('id')
    if not isinstance(indexed,list) or identifier>=len(indexed):raise ValueError('Indexed native tileset is missing')
    # The reader's inert bridge normalization is compared on selected fields;
    # full native object preservation is separately anchored by its Marshal SHA.
    observed=indexed[identifier]
    if not isinstance(observed,dict) or observed.get('id')!=identifier or observed.get('tileset_names')!=names or observed.get('flags')!={'__class__':'Table','dimensions':1,'xsize':8192,'ysize':1,'zsize':1,'data':list(flags)}:
        raise ValueError('Native/indexed tileset identities, sheets or flags disagree')
    return {'map_id':map_id,**snapshot(root,project,cells,tiles,rtp)}


def verify_transition(before,after,mutation):
    from vxace_python_mutator import RubyObject,marshal_rb
    schema(mutation);previous=table_for(before);current=table_for(after)
    if (previous.dim,previous.xsize,previous.ysize,previous.zsize)!=(current.dim,current.xsize,current.ysize,current.zsize):raise ValueError('Upper tile candidate changed Table shape')
    expected=bytearray(previous.to_payload())
    for cell,pos in coordinates(mutation['cells'],previous):
        expected[20+pos*2:22+pos*2]=cell['value'].to_bytes(2,'little')
    if bytes(expected)!=current.to_payload():raise ValueError('Upper tile candidate changed unapproved Table bytes')
    def unrelated(root):return marshal_rb.dump(RubyObject(root.cls,{key:value for key,value in root.ivars.items() if key!='@data'}))
    if unrelated(before)!=unrelated(after):raise ValueError('Upper tile candidate changed other map fields or unknown aliases')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('index');parser.add_argument('--project',required=True)
    parser.add_argument('--map',dest='map_id',type=int,required=True);parser.add_argument('--cell',type=int,nargs=2,action='append',required=True)
    parser.add_argument('--tile',type=int,action='append',required=True);parser.add_argument('--rtp');parser.add_argument('--output',required=True);args=parser.parse_args(argv)
    try:
        project=unlinked(args.project)
        if project.is_file() and project.suffix.lower()=='.rvproj2':project=project.parent
        rtp=unlinked(args.rtp) if args.rtp else None
        output=unlinked(args.output)
        if rtp is not None and (output==rtp or rtp in output.parents):raise ValueError('Snapshot output must be outside read-only RTP')
        result=execute(args.index,project,output,lambda data:indexed_snapshot(data,project,args.map_id,[{'x':x,'y':y} for x,y in args.cell],args.tile,rtp),'upper-tile-snapshot')
    except Exception as error:print('Upper tile snapshot refused: '+str(error),file=sys.stderr);return 2
    print(json.dumps({'version':VERSION,'map_id':result['map_id'],'cells':len(result['cells'])}));return 0


if __name__=='__main__':raise SystemExit(main())
