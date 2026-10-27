"""Two overlapping skirt widths with explicit pleats; application template v2.

This is an adjustable basic construction, not a measured museum reproduction.
All coordinates are centimetres. No simulation or fit claim is made.
"""
import math
from xml.etree import ElementTree as ET

from pygarment.pattern.wrappers import VisPattern


def rectangle(width, height, top_breaks=()):
    vertices = [[0., 0.]] + [[float(x), 0.] for x in top_breaks]
    vertices += [[float(width), 0.], [float(width), -float(height)], [0., -float(height)]]
    return {'vertices': vertices, 'edges': [
        {'endpoints': [i, (i+1) % len(vertices)]} for i in range(len(vertices))],
        'translation': [0., 0., 0.], 'rotation': [0., 0., 0.]}


def pleats(start, visible, ratio, count=4):
    """Piecewise isometric fold map: each path length equals fabric width."""
    pitch = visible/count
    depth = pitch*(ratio-1)/2
    cell = pitch+2*depth
    marks, mapping = [], [[start, start]]
    for i in range(count):
        # Mirrored groups fold towards the skirt-door sides.
        turn = (pitch+depth)/2
        if i >= count//2:
            turn = cell-turn-depth
        u, v = start+i*cell, start+i*pitch
        mapping += [[u+turn, v+turn], [u+turn+depth, v+turn-depth], [u+cell, v+pitch]]
        marks += [{'x':u+turn, 'kind':'mountain' if i<count//2 else 'valley',
                   'direction':'left' if i<count//2 else 'right'},
                  {'x':u+turn+depth, 'kind':'valley' if i<count//2 else 'mountain',
                   'direction':'left' if i<count//2 else 'right'}]
    return marks, mapping, depth


def build_mamian(body, design):
    d = design['mamian-skirt']
    length = float(d['length']['v'])*body['_leg_length']
    door = float(d['mamian_width']['v'])
    ratio = float(d['pleat_ruffle']['v'])
    rise = float(d['rise']['v'])
    waist = body['hips']+(body['waist']-body['hips'])*rise
    visible = waist/2-door
    if not all(math.isfinite(v) for v in [length, door, ratio, waist]) or min(length, door, visible) <= 0:
        raise ValueError(f'马面宽{door:g}cm与当前穿着位置围度{waist:.1f}cm不相容；'
                         f'马面宽须小于{waist/2:.1f}cm，为两侧褶区留出宽度。')
    if not 1 < ratio <= 3:
        raise ValueError('基础马面裙褶量比须大于1且不超过3。')
    flat_side = visible*ratio
    flat_width = 2*door+flat_side
    folded_width = 2*door+visible
    band_length = waist+door
    band_height = float(d['waistband_width']['v'])*body['hips_line']
    tie = 45.0  # Disclosed construction default; not inferred from image.
    marks, mapping, depth = pleats(door, visible, ratio)
    pattern = VisPattern()
    pattern.name = 'MamianOverlapV2'
    panels = pattern.pattern['panels']
    for suffix in ['a', 'b']:
        panels['mamian_width_'+suffix] = rectangle(flat_width, length, [door,door+flat_side])
    # Five belt attachment intervals: door, pleats, shared rear door, pleats, door.
    breaks = [tie, tie+door, tie+door+visible, tie+2*door+visible,
              tie+2*door+2*visible, tie+band_length]
    panels['mamian_waistband'] = rectangle(band_length+2*tie, 2*band_height, breaks)
    pattern.pattern['stitches'] = [
        [{'panel':'mamian_waistband','edge':belt}, {'panel':'mamian_width_'+suffix,'edge':edge}]
        for suffix, offset in [('a',1),('b',3)] for edge,belt in enumerate(range(offset,offset+3))]
    construction = {
        'version':'mamian-overlap-v2', 'units':'cm', 'scope':'basic-two-width-overlap',
        'wearing_circumference':waist, 'body_waist':body['waist'],
        'skirt_length':length, 'door_width':door, 'overlap_each_end':door,
        'side_folded_width':visible, 'side_flat_width':flat_side,
        'flat_width_each':flat_width, 'folded_width_each':folded_width,
        'pleat_count_each':4, 'pleat_depth':depth, 'fold_map':mapping,
        'fold_lines':marks, 'waistband_attachment_length':band_length,
        'waistband_finished_height':band_height, 'tie_length_each':tie,
        'layered_seam':{'panel':'mamian_waistband','edge':3,
                        'reason':'后裙门双层叠合后共同夹入腰头；此段连接两幅裙门'},
        'simulation_supported':False,
        'notes':[
            '两幅裙身各含两端平整裙门和中间褶区；前后裙门交叠，不缝成闭合裙筒。',
            '后裙门重叠段为多层共同接腰头；两幅裙身其余纵边保持自由。',
            '褶数每幅4个、系带每端45cm为基础模板默认值；不是由照片测量所得。',
            '当前按基础相向褶组表达样式，不复原照片中的刺绣、面料或隐藏结构。',
        ]}
    pattern.pattern['construction'] = construction
    return pattern, construction


def add_marks(group, name, construction, tag):
    c = construction
    if name.startswith('mamian_width_'):
        length, width, door = c['skirt_length'], c['flat_width_each'], c['door_width']
        for x, label in [(0,'裙门'), (width-door,'裙门')]:
            ET.SubElement(group,tag('rect'),{'x':str(x),'y':'0','width':str(door),
                'height':str(length),'fill':'#dcecf1','opacity':'.55','class':'skirt-door'})
            t=ET.SubElement(group,tag('text'),{'x':str(x+door/2),'y':'5','text-anchor':'middle',
                'font-size':'1.5','fill':'#24576b'})
            t.text=label
        for mark in c['fold_lines']:
            ET.SubElement(group,tag('line'),{'x1':str(mark['x']),'x2':str(mark['x']),
                'y1':'0','y2':str(length),'stroke':'#a64c43' if mark['kind']=='mountain' else '#3d7398',
                'stroke-width':'.12','stroke-dasharray':'1.1 .5' if mark['kind']=='mountain' else '.3 .5',
                'class':'fold-'+mark['kind']})
        for x, direction in [(door+c['side_flat_width']/4,'←'),(door+3*c['side_flat_width']/4,'→')]:
            t=ET.SubElement(group,tag('text'),{'x':str(x),'y':'9','font-size':'2.4','text-anchor':'middle'})
            t.text=direction
        t=ET.SubElement(group,tag('text'),{'x':str(width/2),'y':str(length*.65),
            'font-size':'1.4','text-anchor':'middle','fill':'#536479'})
        t.text='经向 ↕  | 裙幅'+('A' if name.endswith('_a') else 'B')
    elif name=='mamian_waistband':
        width=c['waistband_attachment_length']+2*c['tie_length_each']
        ET.SubElement(group,tag('line'),{'x1':'0','x2':str(width),'y1':str(c['waistband_finished_height']),
            'y2':str(c['waistband_finished_height']),'stroke':'#3d7398','stroke-width':'.12',
            'stroke-dasharray':'1 .5','class':'waistband-fold'})
        for x, label in [(c['tie_length_each']/2,'系带'),(width/2,'腰头对折线'),
                         (width-c['tie_length_each']/2,'系带')]:
            t=ET.SubElement(group,tag('text'),{'x':str(x),'y':'3','font-size':'1.4','text-anchor':'middle'})
            t.text=label


def render_structure(path, c):
    ns='http://www.w3.org/2000/svg'
    def tag(name): return '{'+ns+'}'+name
    width=c['waistband_attachment_length']+12
    height=2*c['skirt_length']+42
    svg=ET.Element(tag('svg'),{'viewBox':f'0 0 {width} {height}',
        'width':f'{width}cm','height':f'{height}cm'})
    def text(x,y,value,size=2):
        t=ET.SubElement(svg,tag('text'),{'x':str(x),'y':str(y),'font-size':str(size),'fill':'#173b55'})
        t.text=value
    text(4,5,'马面裙：折后裙幅与搭接位置示意（不是裁剪图）')
    text(4,9,'红虚线为山折、蓝点线为谷折；尺寸单位 cm。此图不代表上衣或整套服装。',1.5)
    for i,label in enumerate(['裙幅 A：折后','裙幅 B：折后']):
        x,y=6,18+i*(c['skirt_length']+12)
        w,h=c['folded_width_each'],c['skirt_length']
        ET.SubElement(svg,tag('rect'),{'x':str(x),'y':str(y),'width':str(w),'height':str(h),
            'fill':'#f3f7fb','stroke':'#173b55','stroke-width':'.15'})
        for start in [0,w-c['door_width']]:
            ET.SubElement(svg,tag('rect'),{'x':str(x+start),'y':str(y),'width':str(c['door_width']),
                'height':str(h),'fill':'#dcecf1'})
        for j in range(5):
            px=x+c['door_width']+c['side_folded_width']*j/4
            ET.SubElement(svg,tag('line'),{'x1':str(px),'x2':str(px),'y1':str(y),'y2':str(y+h),
                'stroke':'#3d7398','stroke-width':'.12'})
        text(x,y-2,f'{label} | {w:.1f} × {h:.1f} cm',1.6)
        text(x+w+3,y+8,'两端：平整裙门',1.6)
        text(x+w+3,y+12,'中间：侧褶区',1.6)
    text(4,height-8,f'两幅折后总宽 {2*c["folded_width_each"]:.1f} − 前后搭接 {2*c["overlap_each_end"]:.1f}'
         f' = 穿着围度 {c["wearing_circumference"]:.1f}',1.6)
    text(4,height-4,'裙门纵边不缝合；后裙门叠合后共同接腰头，系带围合。',1.6)
    ET.ElementTree(svg).write(path,encoding='utf-8',xml_declaration=True)
