"""Optional flat style diagrams derived from the exported basic templates.

These are explanatory silhouettes, not fabric simulation or cutting outlines.
The ordinary preview continues to show the actual, unassembled net pieces.
"""
from xml.etree import ElementTree as ET
import math
from .traditional_templates import curve_for


def render_style(path,component,pattern,report):
    ns='http://www.w3.org/2000/svg'
    def tag(name):return '{'+ns+'}'+name
    svg=ET.Element(tag('svg'),{'width':'1000','height':'1000','viewBox':'0 0 180 180',
                             'role':'img','aria-label':report['variant_label']+'款式示意'})
    ET.SubElement(svg,tag('rect'),{'width':'180','height':'180','fill':'white'})
    def text(x,y,value,size=3.1):
        t=ET.SubElement(svg,tag('text'),{'x':str(x),'y':str(y),'font-size':str(size),
                        'font-family':'Microsoft YaHei, sans-serif','fill':'#525363'})
        t.text=value
    def outline(d,fill='#d8d5df',stroke='#57515e',extra=None):
        return ET.SubElement(svg,tag('path'),{'d':d,'fill':fill,'stroke':stroke,
                             'stroke-width':'.35',**(extra or {})})
    text(7,9,report['variant_label'],4)
    text(7,15,'款式平铺示意；不是裁剪线，也不是试穿渲染。',2.8)
    if component=='chest-wrap':
        w=report['panel_width'];h=report['panel_height'];s=min(1.4,105/w,95/h)
        x=90-w*s/2;y=45
        outline(f'M {x},{y} h {w*s} v {h*s} h {-w*s} Z')
        for dy in [2.,h-2.]:
            for side in [-1,1]:
                start=x if side<0 else x+w*s
                outline(f'M {start},{y+dy*s} h {side*27} v {report["tie_unfolded_width"]*s/2} h {-side*27} Z',fill='#b8b1c1')
        text(7,151,'围前布净宽按胸围与覆盖比计算；后背四带系结，无肩带。',2.8)
        text(7,163,'平面基础示意；未做文物原裁法或合体性复原。',2.8)
    elif component=='pibo':
        length=report['strip_length'];width=report['strip_width'];scale=min(150./length,90./width)
        ET.SubElement(svg,tag('rect'),{'x':'15','y':'50','width':str(length*scale),
            'height':str(width*scale),'fill':'#d8d5df','stroke':'#57515e','stroke-width':'.35'})
        text(15,45,f'净长{length:g}cm × 净幅宽{width:g}cm；一整幅，不对折裁。',3)
        text(7,163,'四边另加工艺余量；披搭方式不形成衣物间缝合。',3)
        text(7,170,'尺寸可调整；不替代扇形披领或霞帔。',3)
    elif report.get('whole_garment'):
        from .body_layout import raw_curve,whole_neck_projection
        length=report['finished_length'];w=report['body_half_width'];s=report['sleeve_length_from_body_edge']
        scale=min(1.,145/(2*(w+s)),125/length)
        group=ET.SubElement(svg,tag('g'),{'transform':f'translate(90,29) scale({scale})'})
        for side in ['right','left']:
            curve=raw_curve(pattern,component+'_front_'+side)
            if report.get('open_front'):curve=curve.translated(complex(1.3 if side=='left' else -1.3,0))
            ET.SubElement(group,tag('path'),{'d':curve.d(),'fill':'#d8d5df',
                'stroke':'#57515e','stroke-width':'.35'})
        for curve in whole_neck_projection(pattern,component,report):
            ET.SubElement(group,tag('path'),{'d':curve.d(),'fill':'#b8b1c1','stroke':'#57515e','stroke-width':'.35'})
        defs=ET.SubElement(group,tag('defs'))
        for side,sign in [('left',1),('right',-1)]:
            if report.get('sleeveless'):break
            a=report['armhole_depth'];c=report['sleeve_opening_circumference']/2
            curve=raw_curve(pattern,component+'_sleeve_'+side)
            if sign<0:curve=curve.scaled(-1,1,origin=0)
            gap=1.3 if report.get('open_front') else 0.
            curve=curve.translated(complex(sign*(w+gap),-a))
            clip=ET.SubElement(defs,tag('clipPath'),{'id':'sleeve-'+side})
            ET.SubElement(clip,tag('rect'),{'x':'-300','y':'0','width':'600','height':'250'})
            ET.SubElement(group,tag('path'),{'d':curve.d(),'fill':'#d8d5df','stroke':'#57515e',
                'stroke-width':'.35','clip-path':'url(#sleeve-'+side+')'})
            band=report.get('cuff_band_finished_height',0.)
            if band:
                x=w+report['sleeve_body_length']+gap;end=x+band
                ET.SubElement(group,tag('path'),{'d':f'M {sign*x},0 L {sign*end},0 L {sign*end},{c} L {sign*x},{c} Z',
                    'fill':'#b8b1c1','stroke':'#57515e','stroke-width':'.35'})
        text(7,163,'完整无袖衣身；袖窿包边及领襟按实长配长。' if report.get('sleeveless') else '完整衣身及两袖；领襟按实际开口配长，系结闭合。',3)
        text(7,170,'基础净样，无缝份；不复原特殊文物裁法。',3)
    elif component in {'beizi','banbi'}:
        w=report['body_half_width'];n=report['neck_half_width'];d=report['front_neck_depth']
        a=report['armhole_depth'];s=report['sleeve_length_from_body_edge']
        c=report['sleeve_opening_circumference']/2;length=report['finished_length']
        scale=min(1.,155/(2*(w+s)),125/length)
        group=ET.SubElement(svg,tag('g'),{'transform':f'translate(90,29) scale({scale})'})
        for sign in [-1,1]:
            body=(f'M {sign*n},0 L {sign*w},0 L {sign*(w+s)},0 '
                f'L {sign*(w+s)},{c} L {sign*w},{a} L {sign*w},{length} '
                f'L 0,{length} L 0,{d} Q {sign*n*.3},{d*.4} {sign*n},0 Z')
            node=outline(body)
            svg.remove(node);group.append(node)
            # Sleeve attachment / front edge are construction cues only.
            ET.SubElement(group,tag('path'),{'d':f'M {sign*w},0 L {sign*w},{a}',
                'fill':'none','stroke':'#9993a0','stroke-width':'.22'})
            ET.SubElement(group,tag('path'),{'d':f'M {sign*n},0 Q {sign*n*.3},{d*.4} 0,{d} L 0,{length}',
                'fill':'none','stroke':'#8e849a','stroke-width':'2.2'})
            if report['slit_length']:
                y=length-report['slit_length']
                ET.SubElement(group,tag('path'),{'d':f'M {sign*w},{y} L {sign*w},{length}',
                    'fill':'none','stroke':'white','stroke-width':'.85','stroke-dasharray':'1 .8'})
        text(7,163,'独立左右前襟；领缘连续；袖底缝合。',3)
        if component=='beizi':text(7,170,'两侧虚线段为开衩，保持不缝合。',3)
        else:text(7,170,'当前为对襟短袖款，交领半臂需不同前襟。',3)
    elif component=='ruqun-skirt':
        top=report['wearing_circumference_estimate']/2
        hem=report['hem_arc_each']*3
        length=report['finished_length']
        scale=min(1.2,145/hem,120/length)
        group=ET.SubElement(svg,tag('g'),{'transform':f'translate(90,30) scale({scale})'})
        node=outline(f'M {-top/2},0 L {top/2},0 L {hem/2},{length} Q 0,{length+4} {-hem/2},{length} Z')
        svg.remove(node);group.append(node)
        for fraction in [-1/6,1/6]:
            ET.SubElement(group,tag('line'),{'x1':str(top*fraction),'y1':'0',
                'x2':str(hem*fraction),'y2':str(length+1.8),'stroke':'#aaa3b1','stroke-width':'.35'})
        ET.SubElement(group,tag('rect'),{'x':str(-top/2),'y':'-3.5','width':str(top),
            'height':'3.5','fill':'#9c93a7','stroke':'#57515e','stroke-width':'.3'})
        ET.SubElement(group,tag('path'),{'d':f'M {top*.27},0 L {hem*.38},{length}',
            'fill':'none','stroke':'#82768c','stroke-width':'.5','stroke-dasharray':'1 .7'})
        text(7,163,'六幅放摆、腰头系带；虚线提示围裹搭接。',3)
        text(7,170,'示意前侧轮廓，不包含上襦、披帛或马面裙门。',3)
    elif component in {'round-collar','cross-collar','duijin-collar'}:
        selected=[]
        for name,panel in pattern.pattern['panels'].items():
            if component!='round-collar' and name.endswith('_back'):
                continue
            ox=min(v[0] for v in panel['vertices']);oy=min(-v[1] for v in panel['vertices'])
            selected.append(curve_for(pattern,name).translated(complex(ox,oy)))
        boxes=[curve.bbox() for curve in selected]
        x0,x1=min(b[0] for b in boxes),max(b[1] for b in boxes)
        y0,y1=min(b[2] for b in boxes),max(b[3] for b in boxes)
        scale=min(3.,130/(x1-x0),120/(y1-y0))
        group=ET.SubElement(svg,tag('g'),{'transform':f'translate({90-scale*(x0+x1)/2},{30-scale*y0}) scale({scale})'})
        for curve in selected:
            ET.SubElement(group,tag('path'),{'d':curve.d(),'fill':'#d8d5df',
                'stroke':'#57515e','stroke-width':'.2'})
        text(7,163,'领口内侧留空；两前领保持自由；示意不包含衣身。',3)
        text(7,170,'仅为领襟贴，需与目标衣身领口另行试配。',3)
    else:
        cloud_names=[n for n in pattern.pattern['panels'] if n.startswith('cloud_layer_')]
        bounds=[]
        for name in cloud_names:
            vertices=pattern.pattern['panels'][name]['vertices']
            curve=curve_for(pattern,name)
            ox=min(v[0] for v in vertices);oy=min(-v[1] for v in vertices)
            bounds.append((name,curve,ox,oy))
        extent=max(max(abs(v[0]),abs(v[1])) for n in cloud_names for v in pattern.pattern['panels'][n]['vertices'])
        scale=min(2.,57/extent)
        group=ET.SubElement(svg,tag('g'),{'transform':f'translate(90,88) scale({scale})'})
        for i,(name,curve,ox,oy) in enumerate(bounds):
            ET.SubElement(group,tag('path'),{'d':curve.d(),'transform':f'translate({ox},{oy})',
                'fill':['#b7aebf','#d2cbd9','#e8e2ed'][i],
                'stroke':'#6b5d75','stroke-width':'.25'})
        for tassel in report['tassels']:
            x,y=tassel['position_cm'];y=-y
            radius=math.hypot(x,y);length=tassel['length_cm']
            ET.SubElement(group,tag('line'),{'x1':str(x),'x2':str(x+length*x/radius),'y1':str(y),
                'y2':str(y+length*y/radius),'stroke':'#82718e','stroke-width':'.35'})
        text(7,163,'各层同领口；前中开口保留；外缘分层。',3)
        text(7,170,'绳须为成品配件；未模拟肩部贴合与垂坠。',3)
    ET.ElementTree(svg).write(path,encoding='utf-8',xml_declaration=True)
