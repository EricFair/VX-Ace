"""Exact read-only character-sheet bindings for new stationary dialogue events."""
from pathlib import Path
from vxace_index_query import unlinked
from vxace_asset_audit import catalog,safe_name
from vxace_image_headers import layout_checks
from vxace_map_regions import integer
from vxace_upper_tiles import asset_digest


def graphic_schema(graphic):
    if not isinstance(graphic,dict) or set(graphic)!={'character_name','character_index','direction','pattern'}:
        raise ValueError('Exact character name/index/direction/pattern fields required')
    name=graphic['character_name']
    if not isinstance(name,str) or not 1<=len(name)<=100 or not safe_name(name) or '/' in name or '\\' in name or Path(name).suffix or any(ord(c)<32 or ord(c)==127 for c in name):
        raise ValueError('Select an exact character basename without extension or path')
    name.encode('utf-8','strict')
    single=len(name)>=2 and name[0] in '!$' and '$' in name[:2]
    integer(graphic['character_index'],'character index',0,0 if single else 7)
    if type(graphic['direction']) is not int or graphic['direction'] not in (2,4,6,8):raise ValueError('Native character direction required')
    integer(graphic['pattern'],'character pattern',0,2)
    return name,single


def binding(project,rtp,graphic):
    name,single=graphic_schema(graphic)
    if project is None:raise ValueError('Character graphics require actual native project context')
    project=unlinked(project);roots=[('project',project)]
    if rtp is not None:
        rtp=unlinked(rtp)
        if not rtp.is_dir() or rtp==project or project in rtp.parents or rtp in project.parents:raise ValueError('Explicit RTP must be a separate read-only directory')
        roots.append(('rtp',rtp))
    catalogs=[(label,root,*catalog(root)) for label,root in roots]
    wanted='Graphics/Characters/'+name;selected=None
    for label,root,entries,_ in catalogs:
        matches=entries.get(wanted.casefold(),[])
        if not matches:continue
        if matches!=[wanted+'.png']:raise ValueError('Selected character image is ambiguous, case-mismatched or not PNG')
        sha,header=asset_digest(root/matches[0],dimensions=None)
        checks=layout_checks('Graphics/Characters',name,header)
        if len(checks)!=1 or checks[0]['status']!='standard_layout':raise ValueError('Selected character sheet has an incomplete native frame grid')
        frame=checks[0]
        if not 1<=frame['default_frame_width']<=256 or not 1<=frame['default_frame_height']<=256:raise ValueError('Character frame exceeds the supported 256x256 bounds')
        selected={'name':name,'origin':label,'path':matches[0],'sha256':sha,
                  'width':header['width'],'height':header['height'],'layout':frame['layout'],
                  'frame_width':frame['default_frame_width'],'frame_height':frame['default_frame_height'],
                  'object_character':name.startswith('!')}
        break
    if selected is None:raise ValueError('Character image unresolved; select the correct project asset or explicit RTP')
    for _,root,entries,stamp in catalogs:
        if catalog(root)!=(entries,stamp):raise ValueError('Character asset resolution changed during review')
    return selected


def set_graphic(page,graphic,asset,project,rtp=None):
    from vxace_python_mutator import convert
    actual=binding(project,rtp,graphic)
    if asset!=actual:raise ValueError('Character asset binding is stale or inconsistent')
    native=page.get('graphic')
    # The new record is already a detached, validated blank native template.
    native.set('character_name',convert(graphic['character_name']))
    for key in ('character_index','direction','pattern'):native.set(key,graphic[key])
