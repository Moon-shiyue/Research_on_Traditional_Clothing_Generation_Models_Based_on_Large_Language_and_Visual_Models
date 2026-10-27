"""Restore committed design files only; tasks, uploads and confirmation tokens expire."""
import copy
import hashlib
import json
import math
import re
from xml.etree import ElementTree as ET

from .exporting import REQUIRED
from .outfits import GROUPS, member_id
from .patterns import body_from, finite_tree
from .body_layout import tag
from .design_integrity import verify_design
from .whole_catalog import WHOLE
from training.schema import validate_patch, form_errors, finite_number


def _read(folder,name):
    path=folder/name
    if not path.resolve().is_relative_to(folder.resolve()):
        raise ValueError('Saved design file leaves its folder')
    return json.loads(path.read_text(encoding='utf-8'))


def _member(service,folder,component):
    if component not in service.names:
        raise ValueError('Unsupported saved component')
    if not all((folder/name).is_file() for name in REQUIRED):
        raise ValueError('Incomplete saved design')
    patch=_read(folder,'design.json')
    raw_patch=copy.deepcopy(patch)
    meta=_read(folder,'metadata.json')
    geometry=_read(folder,'pattern.json')
    compatibility=[]
    if (component=='cloud-shoulder' and meta.get('assembly',{}).get('version')=='traditional-basics-2026-10-18'
            and meta.get('assembly',{}).get('variant')=='layered-front-opening-cloud-lobes'):
        fields=patch[component];assembly=meta['assembly']
        if 'petal_length' not in fields:
            # Read the actual old outline, not today's default. Its first
            # outer vertex follows the documented radial cloud equation.
            x,y=geometry['panels']['cloud_layer_01']['vertices'][0]
            angle=math.atan2(x,-y);phase=fields['petal_count']['v']*angle
            factor=.52+.28*math.cos(phase)-.25*math.cos(2*phase)+(fields['layers']['v']-1)*.32
            shoulder=_read(folder,'body.json')['shoulder_w']
            if not all(finite_number(v) for v in [x,y,factor,shoulder,assembly['neck_radius']]) or shoulder<=0 or abs(factor)<1e-8:
                raise ValueError('Invalid legacy cloud outline dimensions')
            fields['petal_length']={'v':round((math.hypot(x,y)-assembly['neck_radius']-1.8)/factor/shoulder,8)}
            compatibility.append(component+'.petal_length')
        if 'front_extension' not in fields:
            fields['front_extension']={'v':0.}
            compatibility.append(component+'.front_extension')
    if (component in WHOLE and meta.get('assembly',{}).get('version') in {
            'whole-garments-2026-10-25-v1','whole-garments-2026-10-25-v2','whole-garments-2026-10-25-v3'}
            and isinstance(patch.get(component),dict) and 'side_slit' not in patch[component]):
        patch[component]['side_slit']={'v':0.};compatibility.append(component+'.side_slit')
    # Only the first application whole-garment template had these additive
    # controls. Infer their old values from the sealed geometry, never from
    # today's defaults (which would add a belt or change a sleeve on restart).
    if (component in WHOLE and meta.get('assembly',{}).get('version') in {'whole-garments-2026-10-25-v1','whole-garments-2026-10-25-v2'}
            and isinstance(patch.get(component),dict)):
        fields=patch[component]
        inferred={'sleeve_type':int(meta['assembly'].get('sleeve_type')=='pipa'),
                  'cuff_band_height':float(meta['assembly'].get('cuff_band_finished_height',0.))}
        if component.endswith('robe'):
            inferred['belt']=int(component+'_belt' in geometry.get('panels',{}))
        if not component.startswith('cross'):
            inferred['opening_type']=0
        for key,value in inferred.items():
            if key not in fields:
                fields[key]={'v':value};compatibility.append(component+'.'+key)
        if not component.startswith('cross') and 'overlap' in fields:
            obsolete=fields['overlap']
            if not isinstance(obsolete,dict) or set(obsolete)!={'v'} or not finite_number(obsolete['v']) or not 6<=obsolete['v']<=22:
                raise ValueError('Invalid legacy overlap field')
            fields.pop('overlap');compatibility.append(component+'.overlap')
    if set(patch)!={component,'traditional'} or validate_patch(patch,service.schema) or form_errors(patch,service.template):
        raise ValueError('Saved parameters no longer satisfy the supported schema')
    if (meta['component']!=component or meta.get('geometry_finite') is not True
            or meta.get('is_self_intersecting') is not False
            or len(geometry['panels'])!=meta['panel_count'] or not finite_tree(geometry)
            or len(meta['panel_measurements'])!=meta['panel_count']
            or {p['panel_id'] for p in meta['panel_measurements']}!=set(geometry['panels'])):
        raise ValueError('Invalid saved geometry')
    for name in ['pattern.svg','pattern-dimensions.svg']:
        svg=ET.parse(folder/name).getroot()
        if svg.tag!=tag('svg') or len(list(svg.iter(tag('path'))))<meta['panel_count']:
            raise ValueError('Incomplete saved SVG')
    sources=meta.get('parameter_sources',{})
    defaults=meta.get('default_fields',[])
    absolute=meta.get('absolute_lengths_cm',{})
    if (not isinstance(sources,dict) or not all(isinstance(k,str) and isinstance(v,str) for k,v in sources.items())
            or not isinstance(defaults,list) or not all(isinstance(v,str) for v in defaults)
            or not isinstance(absolute,dict)):
        raise ValueError('Invalid saved parameter provenance')
    for path in compatibility:
        if path.split('.')[1] in patch[component]:sources[path]='restored_geometry'
        else:
            sources.pop(path,None)
            defaults=[key for key in defaults if key!=path]
    for path,value in absolute.items():
        if not isinstance(path,str) or not finite_number(value) or len(path.split('.'))!=2:
            raise ValueError('Invalid saved fixed length')
        section,key=path.split('.')
        if section not in patch or key not in patch[section]:
            raise ValueError('Unknown saved fixed length')
        service.length_reference(section,key,{})
    member={'component':component,'patch':patch,'raw_patch':raw_patch,'compatibility':compatibility,'sources':sources,
            'default_fields':defaults,'absolute_lengths_cm':absolute}
    if meta.get('component_source')=='user_confirmation':
        member.update(component_source='user_confirmation',selection_note=meta.get('selection_note',''),
                      note=meta.get('selection_note',''))
    return member


def _restore(service,folder,sid):
    if not all((folder/name).is_file() for name in REQUIRED):
        raise ValueError('Incomplete saved design')
    meta=_read(folder,'metadata.json')
    verify_design(folder,meta.get('integrity_version'))
    if (not meta.get('updated_at') or not meta.get('panel_measurements')
            or meta.get('geometry_finite') is not True or meta.get('is_self_intersecting') is not False
            or len(meta['panel_measurements'])!=meta['panel_count']):
        raise ValueError('Not a complete application design')
    prefix=f'/static/patterns/{sid}/{folder.name}/'
    for key,value in list(meta.items()):
        if key.endswith('_url') and value is not None:
            if not isinstance(value,str) or not value.startswith(prefix):
                raise ValueError('Saved URL does not belong to this design')
            target=folder/value[len(prefix):]
            if not target.resolve().is_relative_to(folder.resolve()):
                raise ValueError('Saved resource is missing or outside this design')
            if key=='reference_image_url':
                if (not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()
                        !=meta.get('reference_image_sha256')):
                    meta.pop('reference_image_url',None)
                    meta.pop('reference_image_sha256',None)
                continue
            if not target.is_file():
                raise ValueError('Saved resource is missing or outside this design')
    raw_body=_read(folder,'body.json')
    body={k:v for k,v in raw_body.items() if not k.startswith('_')}
    if not {'height','bust','waist','hips'}<=set(body):
        raise ValueError('Incomplete saved body')
    body_from(body)  # Validate before exposing a restored state.
    if meta['component']=='outfit':
        garments=meta['garments']
        if (tuple(g['component'] for g in garments) not in GROUPS
                or [g['id'] for g in garments]!=[member_id(g['component'],[item['component'] for item in garments]) for g in garments]):
            raise ValueError('Unsupported saved outfit')
        members=[]
        for g in garments:
            child=folder/g['id']
            if child.resolve().parent!=folder.resolve() or _read(child,'body.json')!=raw_body:
                raise ValueError('Saved outfit body references differ')
            member=_member(service,child,g['component'])
            member['id']=g['id'];members.append(member)
        if any(m['patch']['traditional']!=members[0]['patch']['traditional'] for m in members):
            raise ValueError('Saved outfit contexts differ')
        expected={'version':meta['outfit_version'],'garments':
                  [dict(id=m['id'],component=m['component'],patch=m['raw_patch']) for m in members]}
        if _read(folder,'design.json')!=expected:
            raise ValueError('Saved outfit parameters disagree')
        if meta['panel_count']!=sum(g['panel_count'] for g in garments):
            raise ValueError('Saved outfit cut list disagrees')
        geometry=_read(folder,'pattern.json')
        expected_panels={m['id']+'__'+k:v for m in members
                         for k,v in _read(folder/m['id'],'pattern.json')['panels'].items()}
        if geometry['panels']!=expected_panels or not finite_tree(geometry):
            raise ValueError('Saved outfit geometry disagrees')
        if {p['panel_id'] for p in meta['panel_measurements']}!=set(expected_panels):
            raise ValueError('Saved outfit measurements disagree')
        patch=members[0]['patch']
    else:
        member=_member(service,folder,meta['component'])
        patch=member['patch'];members=None
    migrated=[path for m in (members or [member]) for path in m.get('compatibility',[])]
    if migrated:
        meta['restored_compatibility_fields']=migrated
        meta['warnings']=list(meta.get('warnings',[]))+['已兼容读取旧版纸样参数，保持原裁片不变；再次编辑时按当前模板重新生成。']
        for m in (members or [member]):
            meta.setdefault('parameter_sources',{}).update(m['sources'])
            for path in m.get('compatibility',[]):
                if path not in m['sources']:
                    meta['parameter_sources'].pop(path,None)
                    meta['default_fields']=[k for k in meta.get('default_fields',[]) if k!=path]
    return {'folder':folder,'pattern':meta,'body':body,'patch':patch,'outfit':members,
            'sources':meta.get('parameter_sources',{}),'defaults':meta.get('default_fields',[]),
            'absolute_lengths_cm':meta.get('absolute_lengths_cm',{}),
            'body_sources':meta.get('body_parameter_sources',{})}


def restore_last_design(service,root,sid):
    """Newest complete result wins; incomplete/corrupt directories are ignored."""
    parent=root/'patterns'/sid
    selected=None
    selected_full=False
    try:
        selected=_read(parent,'current.json')['design_id']
        return restore_saved_design(service,root,sid,selected)
    except (ValueError,KeyError,TypeError,OSError):
        pass
    if selected and isinstance(selected,str) and re.fullmatch(r'[0-9a-f]{32}',selected):
        try:
            selected_full=_read(parent/selected,'metadata.json').get('component') in WHOLE|{'outfit'}
        except (ValueError,KeyError,TypeError,OSError):pass
    for folder in saved_candidates(root,sid):
        try:
            restored=copy.deepcopy(_restore(service,folder,sid))
            if selected_full and restored['pattern']['component'] not in WHOLE|{'outfit'}:
                # A failed complete outfit must not silently reappear as an
                # older collar/sleeve/skirt while the user expects a full design.
                continue
            if selected_full and folder.name!=selected:
                restored['pattern']['recovery_notice']='上次所选整件/整套纸样未能完整恢复，当前显示较早的完整版本，请核对款式与裁片数。'
            return restored
        except (ValueError,KeyError,TypeError,AttributeError,OSError,ET.ParseError):
            continue
    return None


def saved_candidates(root,sid):
    parent=root/'patterns'/sid
    if not parent.is_dir() or parent.resolve().parent!=(root/'patterns').resolve():
        return []
    candidates=[]
    for folder in parent.iterdir():
        if not re.fullmatch(r'[0-9a-f]{32}',folder.name) or folder.resolve().parent!=parent.resolve():
            continue
        try:
            candidates.append(((folder/'metadata.json').stat().st_mtime_ns,folder))
        except OSError:
            continue
    return [folder for _,folder in sorted(candidates,key=lambda v:v[0],reverse=True)]


def restore_saved_design(service,root,sid,ident):
    """Only complete, validated designs owned by this session may be selected."""
    parent=root/'patterns'/sid
    if not isinstance(ident,str) or not re.fullmatch(r'[0-9a-f]{32}',ident):
        raise ValueError('Invalid saved design identifier')
    folder=parent/ident
    if (parent.resolve().parent!=(root/'patterns').resolve()
            or folder.resolve().parent!=parent.resolve()):
        raise ValueError('Saved design is outside the current session')
    try:
        return copy.deepcopy(_restore(service,folder,sid))
    except (ValueError,KeyError,TypeError,AttributeError,OSError,ET.ParseError):
        raise ValueError('Saved design is incomplete or no longer valid') from None


def remember_design(root,sid,folder):
    parent=root/'patterns'/sid
    if (not re.fullmatch(r'[0-9a-f]{32}',folder.name)
            or folder.resolve().parent!=parent.resolve()
            or parent.resolve().parent!=(root/'patterns').resolve()):
        raise ValueError('Cannot select a design outside its session')
    temporary=parent/'current.json.tmp'
    temporary.write_text(json.dumps({'version':1,'design_id':folder.name}),encoding='utf-8')
    temporary.replace(parent/'current.json')


def save_body_draft(root,sid,body,sources):
    parent=root/'patterns'/sid
    if parent.resolve().parent!=(root/'patterns').resolve():
        raise ValueError('Body draft is outside its session')
    parent.mkdir(parents=True,exist_ok=True)
    temporary=parent/'body-draft.json.tmp'
    temporary.write_text(json.dumps({'version':1,'body':body,'body_sources':sources},
        ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(parent/'body-draft.json')


def restore_body_draft(root,sid):
    parent=root/'patterns'/sid
    if parent.resolve().parent!=(root/'patterns').resolve():
        return None
    try:
        value=_read(parent,'body-draft.json')
        body=value['body'];sources=value['body_sources']
        expected={k for k in body_from().params if not k.startswith('_')}
        if (value.get('version')!=1 or not isinstance(body,dict) or set(body)!=expected
                or not isinstance(sources,dict) or not set(sources)<=expected
                or any(v not in ('manual','text') for v in sources.values())):
            return None
        body_from(body)
        return {'body':copy.deepcopy(body),'body_sources':copy.deepcopy(sources)}
    except (ValueError,KeyError,TypeError,OSError):
        return None


def recent_designs(service,root,sid,limit=10):
    results=[]
    # Bounded scan: corrupt leftovers must not make a menu unresponsive.
    for folder in saved_candidates(root,sid)[:60]:
        try:
            results.append(restore_saved_design(service,root,sid,folder.name))
        except (ValueError,KeyError,TypeError,AttributeError,OSError,ET.ParseError):
            continue
        if len(results)>=limit:
            break
    return results
