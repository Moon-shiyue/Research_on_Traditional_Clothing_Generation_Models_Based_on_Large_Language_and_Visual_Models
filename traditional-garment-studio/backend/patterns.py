"""Generate real pygarment panels and lay them out at their true cm scale."""
import copy
import importlib
import json
import math
import warnings
from xml.etree import ElementTree as ET

import numpy as np
from .settings import GARMENT_ROOT
from assets.bodies.body_params import BodyParameters
from training.common import generator_constants
from training.evaluate import MODULE_MAP
from training.schema import finite_number, merge_defaults
from .mamian_v2 import build_mamian, add_marks, render_structure
from .mamian_drafting import render_drafting
from .traditional_templates import SUPPORTED, build_traditional
from .traditional_style import render_style
from .body_layout import render_body_layout
from .geometry_validation import validate_geometry
from .sleeve_finishing import finish_sleeves
from .panel_measurements import measure_panels
from .whole_catalog import WHOLE, label as garment_label
from .whole_templates import build_whole
from .vest_template import build_bijia
from .drape_template import build_pibo
from .chest_wrap import build_chest_wrap


def body_from(values=None):
    body = BodyParameters(str(GARMENT_ROOT / 'assets/bodies/mean_female.yaml'))
    if values:
        for key, value in values.items():
            if key not in body.params or key.startswith('_') or not finite_number(value):
                raise ValueError('人体尺寸必须是有效数值，派生尺寸不能直接修改。')
            if ('angle' not in key and 'inclination' not in key and value <= 0) or abs(value) > 250:
                raise ValueError('人体尺寸超出支持范围，请使用厘米并检查输入。')
            body.params[key] = value
        body.eval_dependencies()
    if body['_leg_length'] <= 10:
        raise ValueError('人体高度与腰线、臀线不相容，请检查人体尺寸。')
    return body


def finite_tree(value):
    if isinstance(value, (int, float, np.number)):
        return finite_number(float(value))
    if isinstance(value, dict):
        return all(finite_tree(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(finite_tree(v) for v in value)
    return True


def build_geometry(patch, template, body_values):
    """Build and validate the same geometry used by exports and audit tools."""
    body = body_from(body_values)
    component = next(key for key in patch if key != 'traditional')
    construction = None
    assembly = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', RuntimeWarning)
        if component == 'mamian-skirt':
            pattern, construction = build_mamian(body, merge_defaults(patch, template))
            notes = list(construction['notes'])
        elif component=='chest-wrap':
            pattern,assembly=build_chest_wrap(body,merge_defaults(patch,template))
            notes=list(assembly['notes'])
        elif component=='pibo':
            pattern,assembly=build_pibo(body,merge_defaults(patch,template))
            notes=list(assembly['notes'])
        elif component=='bijia':
            pattern,assembly=build_bijia(body,merge_defaults(patch,template))
            notes=list(assembly['notes'])
        elif component in WHOLE:
            pattern, assembly = build_whole(body, merge_defaults(patch, template), component)
            notes = list(assembly['notes'])
        elif component in SUPPORTED:
            pattern, assembly = build_traditional(body, merge_defaults(patch, template), component)
            notes = list(assembly['notes'])
        else:
            module, class_name = MODULE_MAP[component]
            cls = getattr(importlib.import_module('traditional_ext.' + module), class_name)
            obj = cls(body, merge_defaults(patch, template))
            pattern = obj.assembly()
            notes = list(getattr(obj, 'warnings', []))
            notes += finish_sleeves(pattern,component)
    if not pattern.pattern['panels'] or not finite_tree(pattern.pattern):
        raise ValueError('当前尺寸不能生成有效裁片，请调整参数。')
    validation = validate_geometry(pattern, construction, assembly)
    validation['runtime_warnings'] = sorted({str(w.message) for w in caught if issubclass(w.category,RuntimeWarning)})
    notes += sorted({str(w.message) for w in caught})
    return pattern, body, construction, assembly, notes, validation


def generate_pattern(patch, template, body_values, folder):
    pattern, body, construction, assembly, notes, validation = build_geometry(patch,template,body_values)
    component = next(key for key in patch if key != 'traditional')
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'pattern.json').write_text(json.dumps(pattern.pattern, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    (folder / 'design.json').write_text(json.dumps(patch, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder / 'body.json').write_text(json.dumps(body.params, ensure_ascii=False, indent=2), encoding='utf-8')
    notes.append('精细裁片图另含明确标注的接腰与折边余量；pattern.svg 为不含余量的净样。打印请用100%比例并核对尺寸。'
                 if construction else '当前为'+('整件基础净样' if (assembly or {}).get('whole_garment') else '组件纸样草稿')+'；未添加缝份，打印请使用100%比例，裁剪前核对人体尺寸与缝合关系。')
    render_svg(pattern, component, folder / 'pattern.svg')
    render_svg(pattern, component, folder / 'pattern-dimensions.svg', show_dimensions=True)
    render_svg(pattern, component, folder / 'preview.svg', simple=True)
    render_svg(pattern, component, folder / 'preview-dimensions.svg', show_dimensions=True, simple=True)
    if construction:
        (folder/'construction.json').write_text(json.dumps(construction,ensure_ascii=False,indent=2),encoding='utf-8')
        render_structure(folder/'structure.svg',construction)
        drafting = render_drafting(folder,construction)
    if assembly:
        (folder/'assembly.json').write_text(json.dumps(assembly,ensure_ascii=False,indent=2),encoding='utf-8')
        render_style(folder/'style.svg',component,pattern,assembly)
    layout=render_body_layout(pattern,component,body,folder,construction,assembly)
    result = {'panel_count': len(pattern.pattern['panels']), 'stitch_count': len(pattern.pattern.get('stitches', [])),
            'is_self_intersecting': False, 'geometry_finite': True, 'geometry_validation':validation, 'warnings': notes,
            'body_outline_url': None, 'component': component, 'body_values': body.params}
    result['panel_measurements']=measure_panels(pattern)
    result['body_layout']={'version':layout['version'],'units':'cm','shared_scale':1.,
        'scope':'左侧为二维定位与折叠示意，非布料仿真；右侧为完整净样。'}
    if construction:
        result['construction'] = construction
        result['drafting'] = {'version':drafting['version'], 'notes':drafting['notes'],
                              'pieces':drafting['pieces']}
    if assembly:
        result['assembly'] = assembly
        result['is_self_intersecting'] = False
    return result


def render_svg(pattern, component, path, show_dimensions=False, simple=False):
    namespace = 'http://www.w3.org/2000/svg'
    ET.register_namespace('', namespace)
    def tag(name):
        return '{' + namespace + '}' + name
    svg = ET.Element(tag('svg'))
    x, y, row_height, right = 3.0, 3.0 if simple else 12.0, 0.0, 0.0
    gores_on_row=0
    previous_gore=False
    for name in sorted(pattern.pattern['panels']):
        curve, _, _ = pattern._draw_a_panel(name, apply_transform=False, fill=False)
        xmin, xmax, ymin, ymax = curve.bbox()
        width, height = xmax - xmin, ymax - ymin
        if not all(math.isfinite(v) for v in [xmin, xmax, ymin, ymax]) or min(width, height) <= 0:
            raise ValueError('检测到退化裁片，请调整尺寸。')
        is_gore=component=='ruqun-skirt' and name.startswith('ruqun_gore_')
        cloud_new_row=component=='cloud-shoulder' and name in {'cloud_layer_03','cloud_neck_binding'}
        if x > 3 and (x + width > 220 or (is_gore and gores_on_row==3) or (previous_gore and not is_gore) or cloud_new_row):
            x, y, row_height = 3.0, y + row_height + 8, 0.0
            gores_on_row=0
        if is_gore:
            gores_on_row+=1
        previous_gore=is_gore
        group = ET.SubElement(svg, tag('g'), {'transform': f'translate({x - xmin:.8f},{y - ymin:.8f})'})
        ET.SubElement(group, tag('path'), {'d': curve.d(), 'fill': '#73717d' if simple else '#f3f7fb',
            'stroke': '#333333' if simple else '#173b55', 'stroke-width': '0.2' if simple else '0.08'})
        # VisPattern normalizes each panel's flipped vertex box to zero.
        # Drafting marks use the original centimetre coordinates.
        raw_vertices=pattern.pattern['panels'][name]['vertices']
        origin_x=min(v[0] for v in raw_vertices)
        origin_y=min(-v[1] for v in raw_vertices)
        for mark in pattern.pattern.get('drafting_marks',[]):
            if mark['panel'] != name:
                continue
            if mark['kind']=='fold':
                a,b=mark['start'],mark['end']
                ET.SubElement(group,tag('line'),{'x1':str(a[0]-origin_x),'y1':str(-a[1]-origin_y),
                    'x2':str(b[0]-origin_x),'y2':str(-b[1]-origin_y),'stroke':'#c4c2cc' if simple else '#3d7398',
                    'stroke-width':'.14','stroke-dasharray':'1 .7','class':'preview-fold' if simple else 'fold-line'})
            elif mark['kind']=='tie-attachment':
                px,py=mark['point'][0]-origin_x,-mark['point'][1]-origin_y
                ET.SubElement(group,tag('circle'),{'cx':str(px),'cy':str(py),'r':'.35',
                    'fill':'none','stroke':'#795368','stroke-width':'.12','class':'tie-attachment'})
                if show_dimensions:
                    note=ET.SubElement(group,tag('text'),{'x':str(px+1),'y':str(py+.5),'font-size':'1.3','fill':'#795368','class':'tie-attachment-label'})
                    note.text='系带'+str(mark['number'])
            elif mark['kind']=='tassel-position':
                p=mark['point']
                ET.SubElement(group,tag('circle'),{'cx':str(p[0]-origin_x),'cy':str(-p[1]-origin_y),'r':'.22',
                    'fill':'#e0dce7' if simple else '#3d7398','class':'tassel-position'})
            elif mark['kind']=='side-slit':
                a,b=mark['start'],mark['end']
                ET.SubElement(group,tag('line'),{'x1':str(a[0]-origin_x),'y1':str(-a[1]-origin_y),
                    'x2':str(b[0]-origin_x),'y2':str(-b[1]-origin_y),'stroke':'#8b6679',
                    'stroke-width':'.25','stroke-dasharray':'.7 .45','class':'side-slit-open'})
                ET.SubElement(group,tag('circle'),{'cx':str(a[0]-origin_x),'cy':str(-a[1]-origin_y),
                    'r':'.3','fill':'#8b6679','class':'side-slit-stop'})
                if show_dimensions:
                    inset=2. if a[0]<0 else -2.
                    note=ET.SubElement(group,tag('text'),{'x':str(a[0]-origin_x+inset),
                        'y':str(-(a[1]+b[1])/2-origin_y),'font-size':'1.45',
                        'text-anchor':'start' if inset>0 else 'end','fill':'#795368',
                        'font-family':'Microsoft YaHei, sans-serif','class':'side-slit-label'})
                    note.text=f'侧衩{mark["height_cm"]:g}cm · 不缝'
        if pattern.pattern.get('construction'):
            c=pattern.pattern['construction']
            if simple and name.startswith('mamian_width_'):
                for mark in c['fold_lines']:
                    ET.SubElement(group,tag('line'),{'x1':str(mark['x']),'x2':str(mark['x']),
                        'y1':'0','y2':str(c['skirt_length']),'stroke':'#c4c2cc','stroke-width':'.14',
                        'stroke-dasharray':'1 .7','class':'preview-fold'})
            elif not simple:
                add_marks(group,name,c,tag)
        if show_dimensions and component=='cloud-shoulder' and name.startswith('cloud_layer_'):
            # Small Hermite segments are an implementation detail, not 60
            # separate measurements useful to a person cutting this shape.
            for px,py,value in [(xmin+width/2,ymin-1.2,f'总宽 {width:.1f} cm'),
                                (xmin+width/2,ymax+1.5,f'总高 {height:.1f} cm')]:
                t=ET.SubElement(group,tag('text'),{'x':str(px),'y':str(py),
                    'font-size':'1','text-anchor':'middle','fill':'#536479',
                    'class':'overall-dimension','stroke':'white','stroke-width':'.2','paint-order':'stroke'})
                t.text=value
        elif show_dimensions:
            center = complex((xmin+xmax)/2, (ymin+ymax)/2)
            for segment in curve:
                length = float(segment.length())
                if not math.isfinite(length) or length <= 0:
                    raise ValueError('裁片边长无效，请检查尺寸。')
                midpoint = segment.point(0.5)
                tangent = segment.derivative(0.5)
                if abs(tangent) < 1e-12:
                    tangent = segment.end - segment.start
                if abs(tangent) < 1e-12:
                    tangent = 1
                normal = complex(-tangent.imag, tangent.real) / abs(tangent)
                if (normal.real*(midpoint-center).real + normal.imag*(midpoint-center).imag) < 0:
                    normal = -normal
                position = midpoint + 1.3*normal
                annotation = ET.SubElement(group, tag('text'), {
                    'x':f'{position.real:.8f}', 'y':f'{position.imag:.8f}',
                    'class':'edge-dimension', 'data-length-cm':f'{length:.8f}',
                    'font-size':'1.5' if simple else '0.9', 'text-anchor':'middle', 'dominant-baseline':'middle',
                    'fill':'#5f416e', 'stroke':'none'})
                annotation.text = f'{length:.1f}'
        if simple and show_dimensions:
            # Readable overall bounds supplement the finer edge arc lengths.
            # Bounds are measured from the curve, including Bezier extrema.
            caption=ET.SubElement(group,tag('text'),{
                'x':str((xmin+xmax)/2),'y':str(ymax+6.1),
                'font-size':str(min(4.2,(width+3)/8)), 'text-anchor':'middle',
                'fill':'#24364d','stroke':'none',
                'class':'panel-size-label','data-width-cm':f'{width:.8f}',
                'data-height-cm':f'{height:.8f}'})
            caption.text=f'{width:.1f} × {height:.1f} cm'
        if not simple:
            label = ET.SubElement(svg, tag('text'), {'x': str(x), 'y': str(y - 1), 'font-size': '1.5', 'fill': '#173b55'})
            label.text = f'{name} | {width:.1f} x {height:.1f} cm'
        right = max(right, x + width)
        row_height = max(row_height, height)
        x += width + 5
    width, height = right + 3, y + row_height + 8
    svg.set('viewBox', f'0 0 {width:.8f} {height:.8f}')
    svg.set('width', f'{width:.8f}cm')
    svg.set('height', f'{height:.8f}cm')
    if simple:
        ET.ElementTree(svg).write(path,encoding='utf-8',xml_declaration=True)
        return
    title = ET.SubElement(svg, tag('text'), {'x': '3', 'y': '4', 'font-size': '2', 'fill': '#173b55'})
    title.text = garment_label(component) + ' | 1:1 cm | 净样草稿（未加缝份）'
    ET.SubElement(svg, tag('path'), {'d': 'M 3,7 L 13,7 M 3,6.5 L 3,7.5 M 13,6.5 L 13,7.5', 'stroke': '#173b55', 'stroke-width': '0.1'})
    label = ET.SubElement(svg, tag('text'), {'x': '14', 'y': '7.5', 'font-size': '1.5'})
    label.text = '10 cm'
    if show_dimensions:
        label = ET.SubElement(svg, tag('text'), {'x':'35','y':'7.5','font-size':'1.3'})
        label.text = '边段长度：cm；曲线为弧长；不含缝份'
    if pattern.pattern.get('construction'):
        label = ET.SubElement(svg,tag('text'),{'x':'3','y':'10','font-size':'1.2'})
        label.text = '浅蓝区：裙门；红虚线：山折；蓝点线：谷折；箭头：折向；两幅裙身交叠，不缝成筒。'
    ET.ElementTree(svg).write(path, encoding='utf-8', xml_declaration=True)
