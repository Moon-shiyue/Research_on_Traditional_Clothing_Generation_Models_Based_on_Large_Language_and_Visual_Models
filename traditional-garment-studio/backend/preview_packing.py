"""Compact multi-garment previews with exact, unrotated centimetre net paths.

Only display translations change. Individual pattern SVGs, the sewing graph,
cut counts and A4 templates remain independent of this layout.
"""
import copy
import json
import math
from xml.etree import ElementTree as ET
from svgpathtools import parse_path
from .body_layout import tag

VERSION='outfit-preview-shelves-v1'


def shelf_pack(rectangles,width):
    """Deterministic height-first shelves; each rectangle reserves its labels."""
    shelves=[];placed={}
    for index,(w,h) in sorted(enumerate(rectangles),key=lambda p:(-p[1][1],p[0])):
        if w>width+1e-8:raise ValueError('Preview shelf is narrower than its panel')
        candidates=[i for i,s in enumerate(shelves) if s['used']+w<=width+1e-8 and h<=s['height']+1e-8]
        if candidates:
            shelf=shelves[min(candidates,key=lambda i:width-shelves[i]['used']-w)]
        else:
            shelf={'y':sum(s['height'] for s in shelves),'height':h,'used':0.}
            shelves.append(shelf)
        placed[index]={'x':shelf['used'],'y':shelf['y'],'width':w,'height':h}
        shelf['used']+=w
    return placed,max((s['used'] for s in shelves),default=0.),sum(s['height'] for s in shelves)


def compact_plan(folder,garments):
    members=[];left_width=80.;body_height=160.
    for garment in garments:
        child=folder/garment['id']
        source=ET.parse(child/'preview.svg').getroot()
        geometry=json.loads((child/'pattern.json').read_text(encoding='utf-8'))
        nodes=source.findall(tag('g'));names=sorted(geometry['panels'])
        if len(nodes)!=len(names):raise ValueError('预览裁片清单不完整，不能重新排布。')
        items=[]
        for name,node in zip(names,nodes):
            outline=node.find(tag('path'))
            if outline is None:raise ValueError('预览缺少裁片轮廓。')
            x0,x1,y0,y1=parse_path(outline.attrib['d']).bbox()
            if not all(math.isfinite(v) for v in [x0,x1,y0,y1]) or x1<=x0 or y1<=y0:
                raise ValueError('预览裁片尺寸无效。')
            items.append({'panel':name,'bounds':[x0,x1,y0,y1],
                          'width':x1-x0+8.,'height':y1-y0+12.})
        layout=json.loads((child/'body-layout.json').read_text(encoding='utf-8'))
        left_width=max(left_width,layout['column_widths_cm']['body'])
        body_height=max(body_height,layout['body_landmarks']['height'])
        members.append({'id':garment['id'],'component':garment['component'],'items':items})
    minimum=math.ceil(max(item['width'] for member in members for item in member['items'])/20)*20
    candidates=[]
    for width in range(max(160,minimum),max(460,minimum+100)+1,20):
        blocks=[];used=0.;height=0.
        for member in members:
            places,w,h=shelf_pack([(p['width'],p['height']) for p in member['items']],width)
            blocks.append(dict(member,placements=places,y=height+8.))
            used=max(used,w);height+=h+20.
        # Prefer a readable desktop canvas without stretching any garment.
        # This is a layout objective, not a physical or historical measurement.
        score=max((left_width+12+used)/1.45,max(body_height,height))
        candidates.append((score,width,used,height,blocks))
    _,limit,used,height,blocks=min(candidates,key=lambda p:(p[0],p[2]*p[3],p[1]))
    return {'version':VERSION,'units':'cm','shared_scale':1.,'rotation_degrees':0,
            'width':max(80.,used),'height':height,'shelf_width':limit,'members':blocks,
            'scope':'Preview translations only; exact net paths, dimensions and A4 cutting templates unchanged.'}


def render_compact_preview(folder,garments,source,target,plan):
    from .outfits import canvas,title,namespaced,LABELS
    svg=canvas(plan['width'],plan['height'],'整套服饰裁片净样，统一厘米比例')
    for block,garment in zip(plan['members'],garments):
        title(svg,3,block['y']-4,LABELS[garment['component']])
        group=ET.SubElement(svg,tag('g'),{'data-garment':garment['id'],'transform':f'translate(0,{block["y"]:.8f})'})
        nodes=ET.parse(folder/garment['id']/source).getroot().findall(tag('g'))
        if len(nodes)!=len(block['items']):raise ValueError('尺寸预览与裁片排布数量不同。')
        for index,(node,item) in enumerate(zip(nodes,block['items'])):
            node=copy.deepcopy(node);place=block['placements'][index]
            x0,_,y0,_=item['bounds']
            node.set('transform',f'translate({place["x"]+4-x0:.8f},{place["y"]+3-y0:.8f})')
            node.set('data-panel',item['panel'])
            group.append(namespaced(node,garment['id']))
    ET.ElementTree(svg).write(folder/target,encoding='utf-8',xml_declaration=True)
    return svg
