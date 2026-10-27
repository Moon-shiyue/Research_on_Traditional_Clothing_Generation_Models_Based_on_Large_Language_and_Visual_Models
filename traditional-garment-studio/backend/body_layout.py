"""One centimetre coordinate system: body placement left, net pieces right.

The left side is a 2D placement / folding illustration, not cloth simulation.
The right side reuses the exact net SVG paths, without a body or rescaling.
"""
import copy
import json
import math
from xml.etree import ElementTree as ET

from svgpathtools import parse_path, Path as SvgPath, Line
from .whole_catalog import WHOLE

NS='http://www.w3.org/2000/svg'
VERSION='body-centred-layout-v3'


def tag(name):
    return '{'+NS+'}'+name


def raw_curve(pattern,name):
    p=pattern.pattern['panels'][name]
    curve=pattern._draw_a_panel(name,apply_transform=False,fill=False)[0]
    return curve.translated(complex(min(v[0] for v in p['vertices']),min(-v[1] for v in p['vertices'])))


def pibo_projections(body,report,shoulder_y):
    """Two visible folded fronts; the connecting segment lies behind shoulders.

    The centreline budget is the net length. Projected width is half the net
    width, illustrating a loose longitudinal fold, not a different cutting net.
    """
    folded=report['strip_width']/2
    start=body['neck_w']/2+folded/2+2.
    hidden=2*start;available=(report['strip_length']-hidden)/2
    arm=min(body['shoulder_w']/2+body['arm_length']*.55,start+available*.35)
    bend=min(18.,available*.15)
    base=parse_path(f'M {start},{shoulder_y} C {start},{shoulder_y+bend*.25} '
        f'{arm},{shoulder_y+bend*.6} {arm},{shoulder_y+bend}')
    tail=available-float(base.length())
    if tail<=0:raise ValueError('披帛长度不足以完成当前肩臂披搭示意，请增加长度。')
    base.append(Line(base.end,base.end+complex(0,tail)))
    inner=base.translated(complex(-folded/2,0))
    outer=base.translated(complex(folded/2,0)).reversed()
    strip=SvgPath(*inner,Line(inner.end,outer.start),*outer,Line(outer.end,inner.start))
    return [strip,strip.scaled(-1,1,origin=0)],{
        'net_length_cm':report['strip_length'],'net_width_cm':report['strip_width'],
        'visible_folded_width_cm':folded,'hidden_shoulder_length_cm':hidden,
        'visible_centerline_length_each_cm':float(base.length()),'scope':'2D folded placement; no fabric simulation'}


def whole_neck_projection(pattern,component,report):
    """Front collar cue from the actual neckline, not a cutting outline."""
    width=report['collar_finished_width'];items=[]
    def ribbon(base,offset):
        other=base.translated(offset).reversed()
        return SvgPath(*base,Line(base.end,other.start),*other,Line(other.end,base.start))
    if report.get('neckline_projection_edges'):
        for group in report['neckline_projection_edges']:
            base=SvgPath(*(raw_curve(pattern,r['panel'])[r['edge']] for r in group))
            if report.get('open_front'):
                offset=complex(width if base.end.real>0 else -width,0)
            elif component.startswith('cross'):
                vector=base.end-base.start;normal=complex(-vector.imag,vector.real)/abs(vector)
                if normal.imag<0:normal=-normal
                offset=normal*width
            else:offset=complex(0,-width if component.startswith('stand') else width)
            collar=ribbon(base,offset)
            if report.get('open_front'):
                collar=collar.translated(complex(1.3 if base.end.real>0 else -1.3,0))
            items.append(collar)
        return items
    if component.startswith('cross'):
        for side in ['right','left']:
            edge=raw_curve(pattern,component+'_front_'+side)[5]
            vector=edge.end-edge.start
            normal=complex(-vector.imag,vector.real)/abs(vector)
            if normal.imag<0:normal=-normal
            items.append(ribbon(SvgPath(edge),normal*width))
    elif report.get('front_opening')=='center':
        for side in ['right','left']:
            front=raw_curve(pattern,component+'_front_'+side)
            items.append(ribbon(SvgPath(front[6]),complex(0,-width if component.startswith('stand') else width)))
    else:
        front=raw_curve(pattern,component+'_front_left')
        items.append(ribbon(SvgPath(front[6],front[7]),complex(0,-width if component.startswith('stand') else width)))
    return items


def landmarks(body):
    height=float(body['height'])
    head=min(float(body['head_l']),height*.2)
    shoulder=head
    waist=height-float(body['_waist_level'])
    return {'height':height,'head':head,'shoulder_y':shoulder,'waist_y':waist,
            'hips_y':waist+float(body['hips_line']),
            'underbust_y':shoulder+float(body['bust_line']),
            'shoulder_half':float(body['shoulder_w'])/2,'arm_length':float(body['arm_length'])}


def ruqun_wearing_y(body,position):
    lm=landmarks(body)
    if position<=.85:
        fraction=max(0.,min(1.,(position-.7)/.15))
        return lm['waist_y']+(lm['underbust_y']-lm['waist_y'])*fraction
    fraction=max(0.,min(1.,(position-.85)/.1))
    return lm['underbust_y']-fraction*body['bust_line']*.18


def mamian_front_dimensions(c):
    """Release side-pleat intake at the hem; retain the flat front door.

    This is a schematic envelope, not a simulated surface or a cutting outline.
    Its additional hem width is bounded by the available side fabric.
    """
    waist=c['wearing_circumference']/2
    hem=c['door_width']+c['side_flat_width']
    return {'waist_width':waist,'hem_width':hem,'door_width':c['door_width'],
            'length':c['skirt_length'],'mode':'side-pleat-release-envelope',
            'scope':'schematic envelope, not measured silhouette or cutting outline'}


def body_paths(body,lm):
    """Neutral T-pose outline; circumferences give schematic front widths."""
    h,head=lm['height'],lm['head']
    sy,wy,hy=lm['shoulder_y'],lm['waist_y'],lm['hips_y']
    sh=lm['shoulder_half'];wrist=sh+lm['arm_length'];hand=head*.36
    neck=min(float(body['neck_w'])/2,head*.2)
    bust=float(body['bust'])/(2*math.pi)
    waist=float(body['waist'])/(2*math.pi)
    hips=float(body['hips'])/(2*math.pi)
    armpit=sy+max(10.,float(body['armscye_depth']))
    knee=hy+(h-hy)*.53
    crotch=hy+float(body['crotch_hip_diff'])
    # Right side from neck through hand, waist, leg and inner leg.
    right=(f'M {neck},{head*.80} L {neck},{sy-2} Q {sh*.7},{sy-1} {sh},{sy} '
           f'Q {sh+10},{sy+1.2} {wrist},{sy+4} '
           f'Q {wrist+hand*.6},{sy+2.8} {wrist+hand},{sy+5.5} '
           f'Q {wrist+hand*.4},{sy+8.2} {wrist},{sy+7.8} '
           f'L {sh+5},{sy+10} Q {sh},{sy+10.5} {bust},{armpit} '
           f'C {bust},{wy-8} {waist},{wy-4} {waist},{wy} '
           f'C {waist},{wy+8} {hips},{hy-7} {hips},{hy} '
           f'C {hips},{hy+13} {hips*.65},{knee-8} {hips*.62},{knee} '
           f'L {hips*.45},{h-5} L {hips*.62},{h-1} Q {hips*.65},{h} {hips*.45},{h} '
           f'L {hips*.18},{h} L {hips*.13},{h-4} '
           f'C {hips*.15},{knee+10} {hips*.25},{knee-4} {hips*.24},{knee-7} '
           f'L 1.2,{crotch} Q 0,{crotch-2} 0,{crotch}')
    p=parse_path(right)
    mirror=p.scaled(-1,1,origin=0).reversed()
    # Keep paths separate to avoid relying on a string's float formatting.
    head_path=parse_path(f'M {-head*.27},{head*.43} '
        f'A {head*.27},{head*.43} 0 1 1 {head*.27},{head*.43} '
        f'A {head*.27},{head*.43} 0 1 1 {-head*.27},{head*.43} Z')
    return [head_path,p,mirror]


def placements(pattern,component,body,construction,assembly,lm):
    items=[]
    sy=lm['shoulder_y']
    def add(name,path,mode='net',clip_y=None):
        items.append({'panel':name,'path':path,'mode':mode,'clip_y':clip_y})
    if component=='chest-wrap':
        top=lm['underbust_y']-8.;half=float(body['bust'])/4
        add('chest_wrap_front_projection',parse_path(f'M {-half},{top} L {half},{top} L {half},{top+assembly["panel_height"]} L {-half},{top+assembly["panel_height"]} Z'),'front-wrap-projection')
    elif component=='pibo':
        paths,_=pibo_projections(body,assembly,sy)
        for side,path in zip(['left','right'],paths):
            add('pibo_'+side+'_projection',path,'folded-front-drape-projection')
    elif component in WHOLE:
        c=assembly
        # Underlap first, wearer-left outer front last; same exact net curves.
        for side in ['right','left']:
            name=component+'_front_'+side
            gap=(1.3 if side=='left' else -1.3) if c.get('open_front') else 0.
            add(name,raw_curve(pattern,name).translated(complex(gap,sy)),
                'open-front' if c.get('open_front') else 'overlapped-front')
        for index,path in enumerate(whole_neck_projection(pattern,component,c)):
            add(component+'_collar_projection_'+str(index),path.translated(complex(0,sy)),
                'front-collar-projection')
        for side,sign in [('left',1),('right',-1)]:
            if c.get('sleeveless'):break
            name=component+'_sleeve_'+side
            sleeve=raw_curve(pattern,name)
            if sign<0:sleeve=sleeve.scaled(-1,1,origin=0)
            gap=1.3 if c.get('open_front') else 0.
            add(name,sleeve.translated(complex(sign*(c['body_half_width']+gap),sy-c['armhole_depth'])),
                'folded-at-centre',clip_y=sy)
            band=c.get('cuff_band_finished_height',0.)
            if band:
                x=c['body_half_width']+c['sleeve_body_length']+gap;end=x+band;half=c['sleeve_opening_circumference']/2
                add(component+'_cuff_'+side+'_projection',parse_path(f'M {sign*x},{sy} L {sign*end},{sy} L {sign*end},{sy+half} L {sign*x},{sy+half} Z'),
                    'folded-cuff-projection')
        if c.get('belt_length'):
            y=lm['waist_y'];half=float(body['waist'])/4
            add(component+'_belt_projection',parse_path(f'M {-half},{y-4} L {half},{y-4} L {half},{y} L {-half},{y} Z'),
                'folded-belt-projection')
    elif component in {'beizi','banbi'}:
        c=assembly
        opening_gap=1.3
        for side,sign in [('left',-1),('right',1)]:
            f=component+'_front_'+side
            add(f,raw_curve(pattern,f).translated(complex(sign*opening_gap,sy)))
            name=component+'_sleeve_'+side
            sleeve=raw_curve(pattern,name)
            if sign<0:
                sleeve=sleeve.scaled(-1,1,origin=0)
            add(name,sleeve.translated(complex(sign*(c['body_half_width']+opening_gap),sy-c['armhole_depth'])),
                'folded-at-centre',clip_y=sy)
    elif component=='mamian-skirt':
        c=construction
        difference=body['hips']-body['waist']
        rise=(body['hips']-c['wearing_circumference'])/difference if abs(difference)>1e-8 else 1.
        waist_y=lm['waist_y']+(1.-rise)*body['hips_line']
        # The pleat intake can release below the waist. A constant-width
        # rectangle wrongly depicts a straight skirt, even for a wide pleat setting.
        front=mamian_front_dimensions(c)
        w=front['waist_width'];hem=front['hem_width'];length=front['length'];door=front['door_width']
        add('mamian_front_projection',parse_path(f'M {-w/2},{waist_y} L {w/2},{waist_y} '
            f'L {hem/2},{waist_y+length} L {-hem/2},{waist_y+length} Z'),'folded-front-projection')
        for x in [-door/2,door/2]:
            add('mamian_door_boundary',parse_path(f'M {x},{waist_y} L {x},{waist_y+length}'),'fold-line')
        side=max(0.,(w-door)/2);hem_side=max(0.,(hem-door)/2)
        for sign in [-1,1]:
            for i in range(1,c['pleat_count_each']+1):
                fraction=i/(c['pleat_count_each']+1)
                x=sign*(door/2+side*fraction)
                hx=sign*(door/2+hem_side*fraction)
                add('mamian_side_pleat',parse_path(f'M {x},{waist_y} L {hx},{waist_y+length}'),'fold-line')
        band=c['waistband_finished_height']
        add('mamian_waistband_projection',parse_path(f'M {-w/2},{waist_y-band} L {w/2},{waist_y-band} '
            f'L {w/2},{waist_y} L {-w/2},{waist_y} Z'),'folded-front-projection')
    elif component=='ruqun-skirt':
        c=assembly;position=c['waist_position']
        y=ruqun_wearing_y(body,position)
        first=pattern.pattern['panels']['ruqun_gore_01']['vertices'][0]
        r=(first[0]**2+first[1]**2)/(2*first[1])
        angle=2*math.atan2(abs(first[0]),r-first[1])
        for i,phi in enumerate([-angle,0.,angle]):
            name=f'ruqun_gore_{i+1:02d}'
            p=raw_curve(pattern,name).translated(complex(0,r)).rotated(-math.degrees(phi),origin=0)
            p=p.translated(complex(0,y-r))
            add(name,p,'front-three-gores')
        w=c['waistband_attachment_length']/2;band=c['waistband_finished_height']
        add('ruqun_waistband_projection',parse_path(f'M {-w/2},{y-band} L {w/2},{y-band} L {w/2},{y} L {-w/2},{y} Z'),'folded-front-projection')
    elif component=='cloud-shoulder':
        y=sy-assembly['neck_radius']/2
        for name in sorted(pattern.pattern['panels']):
            if name.startswith('cloud_layer_'):
                add(name,raw_curve(pattern,name).translated(complex(0,y)),'front-half-projection',clip_y=y)
    elif component=='round-collar' and assembly:
        for name in sorted(pattern.pattern['panels']):
            add(name,raw_curve(pattern,name).translated(complex(0,sy)),
                'front-half-projection',clip_y=sy)
    elif component.endswith('sleeve'):
        for name in sorted(pattern.pattern['panels']):
            p=raw_curve(pattern,name)
            side=-1 if 'left' in name else 1
            if component in {'narrow-sleeve','wide-sleeve'}:
                # Restore the original root-centre before rotating to T-pose.
                vertices=pattern.pattern['panels'][name]['vertices']
                root=(vertices[0][0]+vertices[-1][0])/2
                p=p.translated(complex(-root,0)).rotated(-90*side,origin=0)
            else:
                panel=pattern.pattern['panels'][name]
                a,b=(panel['vertices'][i] for i in panel['edges'][0]['endpoints'])
                p=p.translated(complex(-(a[0]+b[0])/2,(a[1]+b[1])/2))
            # An entire unfolded sleeve drawn over the arm puts half its
            # fabric above the shoulder. Show the lower folded half as for
            # whole upper garments; keep the right-hand cutting paths intact.
            add(name,p.translated(complex(side*lm['shoulder_half'],sy)),
                'folded-arm-placement',clip_y=sy)
    else:
        for name,panel in pattern.pattern['panels'].items():
            if 'back' in name:
                continue
            p=raw_curve(pattern,name)
            p=p.translated(complex(panel['translation'][0],sy))
            add(name,p,'neck-placement')
    return items


def render_body_layout(pattern,component,body,folder,construction=None,assembly=None):
    lm=landmarks(body)
    human=body_paths(body,lm)
    items=placements(pattern,component,body,construction,assembly,lm)
    left_bounds=[p.bbox() for p in human]
    for item in items:
        x0,x1,y0,y1=item['path'].bbox()
        if item['clip_y'] is not None:
            y0=max(y0,item['clip_y'])
        if y1>=y0:
            left_bounds.append((x0,x1,y0,y1))
    left_min=min(b[0] for b in left_bounds);left_max=max(b[1] for b in left_bounds)
    top=min(b[2] for b in left_bounds);bottom=max(b[3] for b in left_bounds)
    plain=ET.parse(folder/'preview.svg').getroot()
    plain_box=[float(v) for v in plain.attrib['viewBox'].split()]
    # A long facing or waistband must not also enlarge the body column.
    # Both columns keep the same centimetre scale; only unused whitespace is removed.
    left_col=max(left_max-left_min+12,80.)
    right_col=plain_box[2]+8
    gutter=12.
    plain_y=lm['shoulder_y'] if component in {'beizi','banbi'} else (lm['waist_y'] if component in {'mamian-skirt','ruqun-skirt'} else lm['shoulder_y'])
    # Keep tall net layouts within the same scene, while retaining true scale.
    if plain_box[3]+plain_y>max(bottom,lm['height'])+20:
        plain_y=0.
    content_top=min(top,plain_y)
    content_bottom=max(bottom,plain_y+plain_box[3])
    offset_y=12-content_top
    height=content_bottom-content_top+20
    width=left_col+right_col+gutter
    center=left_col/2-(left_min+left_max)/2
    report={'version':VERSION,'units':'cm','body_landmarks':lm,'shared_scale':1.,
        'left':{'role':'body-centred-2d-placement','center_x':center,'offset_y':offset_y,
                'pieces':[{'panel':i['panel'],'mode':i['mode']} for i in items]},
        'right':{'role':'unaltered-net-pieces','contains_body':False,
                 'panels':sorted(pattern.pattern['panels'])},
        'scope':'2D placement and fold illustration; not cloth simulation or fit validation',
        'column_widths_cm':{'body':left_col,'net':right_col,'gutter':gutter},
        'view_box':[0,0,width,height]}
    if component=='mamian-skirt':
        report['left']['construction_projection']=mamian_front_dimensions(construction)
    for dimensions,source,target in [(False,'preview.svg','body-layout.svg'),
                                     (True,'preview-dimensions.svg','body-layout-dimensions.svg')]:
        svg=ET.Element(tag('svg'),{'viewBox':f'0 0 {width:.8f} {height:.8f}',
            'width':f'{width:.8f}cm','height':f'{height:.8f}cm','role':'img',
            'aria-label':'左侧人体定位与右侧无人体裁片平铺对照'})
        for x,label in [(left_col/2,'人体定位 · 二维穿着示意'),
                        (left_col+gutter+right_col/2,'裁片净样 · 宽 × 高 / 边长：cm' if dimensions else '裁片平铺 · 无人体')]:
            t=ET.SubElement(svg,tag('text'),{'x':str(x),'y':'5','text-anchor':'middle',
                'font-size':'3.2','font-family':'Microsoft YaHei, sans-serif','fill':'#65758a'})
            t.text=label
        left=ET.SubElement(svg,tag('g'),{'id':'body-placement','transform':f'translate({center},{offset_y})'})
        person=ET.SubElement(left,tag('g'),{'class':'body-outline','fill':'none',
            'stroke':'#bac4d1','stroke-width':'.24'})
        for p in human:
            ET.SubElement(person,tag('path'),{'d':p.d()})
        for index,item in enumerate(items):
            group=ET.SubElement(left,tag('g'),{'data-panel':item['panel'],'data-mode':item['mode']})
            if item['clip_y'] is not None:
                clip=ET.SubElement(group,tag('clipPath'),{'id':f'placement-clip-{index}'})
                ET.SubElement(clip,tag('rect'),{'x':str(-width),'y':str(item['clip_y']),
                    'width':str(2*width),'height':str(height*2)})
                group.set('clip-path',f'url(#placement-clip-{index})')
            line=item['mode']=='fold-line'
            ET.SubElement(group,tag('path'),{'d':item['path'].d(),'class':'placed-piece',
                'fill':'none' if line else '#b5d5f6','fill-opacity':'.55',
                'stroke':'#397dcb','stroke-width':'.18' if line else '.28'})
        right=ET.SubElement(svg,tag('g'),{'id':'net-layout','transform':
            f'translate({left_col+gutter+(right_col-plain_box[2])/2},{offset_y+plain_y})'})
        net=ET.parse(folder/source).getroot()
        names=iter(sorted(pattern.pattern['panels']))
        for node in net:
            node=copy.deepcopy(node)
            if node.tag==tag('g'):
                node.set('data-panel',next(names))
            for path in node.iter(tag('path')):
                path.set('fill','#b5d5f6');path.set('fill-opacity','.55');path.set('stroke','#397dcb');path.set('stroke-width','.28')
            for mark in node.iter(tag('line')):
                mark.set('stroke','#7099c6')
            right.append(node)
        if dimensions:
            # Placement has folds/projections: show the body's height as a
            # reference, with all true cutting-edge lengths on the right.
            t=ET.SubElement(left,tag('text'),{'x':str(left_min+1),'y':str(lm['height']+4),
                'font-size':'1.7','fill':'#89709c'})
            t.text=f'身高 {lm["height"]:.1f} cm'
        ET.ElementTree(svg).write(folder/target,encoding='utf-8',xml_declaration=True)
    (folder/'body-layout.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report
