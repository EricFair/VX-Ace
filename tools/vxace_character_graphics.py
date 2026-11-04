"""Exact read-only character-sheet and face-sheet bindings for new stationary dialogue events, staged pages and appended actors."""
from pathlib import Path
from vxace_index_query import unlinked
from vxace_asset_audit import catalog,safe_name
from vxace_image_headers import layout_checks
from vxace_map_regions import integer
from vxace_upper_tiles import asset_digest

FACE_CELL=96
FACE_COLUMNS,FACE_ROWS=4,2


def sheet_name(name,what):
    """An exact asset basename: no path, no extension, no control characters."""
    if not isinstance(name,str) or not 1<=len(name)<=100 or not safe_name(name) or '/' in name or '\\' in name or Path(name).suffix or any(ord(c)<32 or ord(c)==127 for c in name):
        raise ValueError('Select an exact '+what+' basename without extension or path')
    name.encode('utf-8','strict')
    return name


def graphic_schema(graphic):
    if not isinstance(graphic,dict) or set(graphic)!={'character_name','character_index','direction','pattern'}:
        raise ValueError('Exact character name/index/direction/pattern fields required')
    name=sheet_name(graphic['character_name'],'character')
    single=len(name)>=2 and name[0] in '!$' and '$' in name[:2]
    integer(graphic['character_index'],'character index',0,0 if single else 7)
    if type(graphic['direction']) is not int or graphic['direction'] not in (2,4,6,8):raise ValueError('Native character direction required')
    integer(graphic['pattern'],'character pattern',0,2)
    return name,single


def face_schema(name,index):
    """Face basename and index. Default RGSS3 draws face `index` as the 96x96 cell (index % 4, index / 4) of a 4x2 sheet;
    a `$`-prefixed face is treated as a single face (index 0 only), which is a conservative restriction, not an engine rule."""
    name=sheet_name(name,'face')
    single=name.startswith('$')
    integer(index,'face index',0,0 if single else FACE_COLUMNS*FACE_ROWS-1)
    return name,single


def resolve(project,rtp,folder,name,describe,what):
    """Locate `folder/name.png` in the project (first) or the explicit RTP, hash it and let `describe(header)` check its layout.
    Returns {'name','origin','path','sha256','width','height',...describe()}. Re-catalogs every root to detect changes during review."""
    if project is None:raise ValueError(what.capitalize()+' graphics require actual native project context')
    project=unlinked(project);roots=[('project',project)]
    if rtp is not None:
        rtp=unlinked(rtp)
        if not rtp.is_dir() or rtp==project or project in rtp.parents or rtp in project.parents:raise ValueError('Explicit RTP must be a separate read-only directory')
        roots.append(('rtp',rtp))
    catalogs=[(label,root,*catalog(root)) for label,root in roots]
    wanted=folder+'/'+name;selected=None
    for label,root,entries,_ in catalogs:
        matches=entries.get(wanted.casefold(),[])
        if not matches:continue
        if matches!=[wanted+'.png']:raise ValueError('Selected '+what+' image is ambiguous, case-mismatched or not PNG')
        sha,header=asset_digest(root/matches[0],dimensions=None)
        selected={'name':name,'origin':label,'path':matches[0],'sha256':sha,'width':header['width'],'height':header['height'],**describe(header)}
        break
    if selected is None:raise ValueError(what.capitalize()+' image unresolved; select the correct project asset or explicit RTP')
    for _,root,entries,stamp in catalogs:
        if catalog(root)!=(entries,stamp):raise ValueError(what.capitalize()+' asset resolution changed during review')
    return selected


def binding(project,rtp,graphic):
    name,single=graphic_schema(graphic)

    def describe(header):
        checks=layout_checks('Graphics/Characters',name,header)
        if len(checks)!=1 or checks[0]['status']!='standard_layout':raise ValueError('Selected character sheet has an incomplete native frame grid')
        frame=checks[0]
        if not 1<=frame['default_frame_width']<=256 or not 1<=frame['default_frame_height']<=256:raise ValueError('Character frame exceeds the supported 256x256 bounds')
        return {'layout':frame['layout'],'frame_width':frame['default_frame_width'],'frame_height':frame['default_frame_height'],
                'object_character':name.startswith('!')}
    return resolve(project,rtp,'Graphics/Characters',name,describe,'character')


def face_binding(project,rtp,name):
    """Binding of a face sheet by name (index 0 is valid for every layout; use face_cell for a concrete index)."""
    name,single=face_schema(name,0)

    def describe(header):
        if single:
            ok=header['width']>=FACE_CELL and header['height']>=FACE_CELL
        else:
            ok=(header['width'],header['height'])==(FACE_COLUMNS*FACE_CELL,FACE_ROWS*FACE_CELL)
        if not ok:raise ValueError('Selected face sheet is not a '+('single 96x96 face' if single else '4x2 sheet of 96x96 faces (384x192)'))
        return {'layout':'single_face' if single else 'face_sheet','frame_width':FACE_CELL,'frame_height':FACE_CELL,
                'columns':1 if single else FACE_COLUMNS,'rows':1 if single else FACE_ROWS}
    return resolve(project,rtp,'Graphics/Faces',name,describe,'face')


def write_graphic(page,graphic):
    """Write a validated graphic onto the page's detached blank native graphic (tile_id stays 0)."""
    from vxace_python_mutator import convert
    graphic_schema(graphic)
    native=page.get('graphic')
    native.set('character_name',convert(graphic['character_name']))
    for key in ('character_index','direction','pattern'):native.set(key,graphic[key])


def set_graphic(page,graphic,asset,project,rtp=None):
    actual=binding(project,rtp,graphic)
    if asset!=actual:raise ValueError('Character asset binding is stale or inconsistent')
    # The new record is already a detached, validated blank native template.
    write_graphic(page,graphic)


def staged_assets(project,rtp,names):
    """Exact asset bindings for the character sheets of staged pages: {name: binding}. Index 0 is valid for every sheet layout."""
    return {name:binding(project,rtp,{'character_name':name,'character_index':0,'direction':2,'pattern':0}) for name in sorted(names)}


def actor_assets(project,rtp,characters,faces):
    """Exact bindings for an appended actor's graphics: {'characters': {name: binding}, 'faces': {name: binding}} (only non-empty groups)."""
    out={}
    if characters:out['characters']=staged_assets(project,rtp,characters)
    if faces:out['faces']={name:face_binding(project,rtp,name) for name in sorted(faces)}
    return out
