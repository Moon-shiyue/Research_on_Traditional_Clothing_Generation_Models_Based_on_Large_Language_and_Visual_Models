"""Readable, dimensioned cut sheets derived from the basic overlap geometry.

Net panels stay unchanged. Added cut outlines are explicit rectangular allowances,
not an offset of arbitrary curves. Style view is a schematic, not draping output.
"""
import copy
import json
from xml.etree import ElementTree as ET

NS = 'http://www.w3.org/2000/svg'
INK = '#263d48'
MUTED = '#62747c'
RED = '#aa514a'
BLUE = '#397c94'
GOLD = '#b98638'


def tag(name):
    return '{' + NS + '}' + name


def node(parent, name, **attrs):
    return ET.SubElement(parent, tag(name), {k.replace('_', '-'): str(v) for k, v in attrs.items()})


def text(parent, x, y, value, size=2.1, color=INK, **attrs):
    n = node(parent, 'text', x=x, y=y, font_size=size, fill=color, **attrs)
    n.text = value
    return n


def line(parent, x1, y1, x2, y2, color=INK, width=.13, **attrs):
    return node(parent, 'line', x1=x1, y1=y1, x2=x2, y2=y2, stroke=color, stroke_width=width, **attrs)


def dimension(parent, x1, y1, x2, y2, label):
    line(parent,x1,y1,x2,y2,MUTED,.10)
    label_width=sum(1.75 if ord(ch)>255 else .95 for ch in label)+1
    if abs(y1-y2) < .001:
        for x in [x1,x2]: line(parent,x,y1-.7,x,y1+.7,MUTED,.10)
        mid=(x1+x2)/2
        node(parent,'rect',x=mid-label_width/2,y=y1-2.8,width=label_width,height=2.3,fill='white')
        text(parent,mid,y1-.9,label,1.75,MUTED,text_anchor='middle')
    else:
        for y in [y1,y2]: line(parent,x1-.7,y,x1+.7,y,MUTED,.10)
        g=node(parent,'g',transform=f'translate({x1-1.2},{(y1+y2)/2}) rotate(-90)')
        node(g,'rect',x=-label_width/2,y=-1.8,width=label_width,height=2.8,fill='white')
        text(g,0,.3,label,1.75,MUTED,text_anchor='middle')


def arrow(parent, x1, y1, x2, y2, color=INK, both=False):
    import math
    line(parent,x1,y1,x2,y2,color,.18)
    angle=math.atan2(y2-y1,x2-x1)
    for x,y,a in [(x2,y2,angle)] + ([(x1,y1,angle+math.pi)] if both else []):
        for delta in [-.5,.5]:
            line(parent,x,y,x-1.0*math.cos(a+delta),y-1.0*math.sin(a+delta),color,.18)


def sheet(width,height):
    ET.register_namespace('',NS)
    root=ET.Element(tag('svg'),{'viewBox':f'0 0 {width:.5f} {height:.5f}',
        'width':f'{width:.5f}cm','height':f'{height:.5f}cm','role':'img',
        'font-family':"'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif"})
    node(root,'rect',x=0,y=0,width=width,height=height,fill='white')
    return root


def save(root,path):
    ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)


def cut_data(c):
    pieces=[]
    for code, suffix in [('A','a'),('B','b'),('C','waistband')]:
        skirt = code != 'C'
        w = c['flat_width_each'] if skirt else c['waistband_attachment_length']+2*c['tie_length_each']
        h = c['skirt_length'] if skirt else 2*c['waistband_finished_height']
        allowance={'top':1.,'right':1.,'bottom':3. if skirt else 1.,'left':1.}
        a=allowance
        pieces.append({'id':code,'panel':'mamian_width_'+suffix if skirt else 'mamian_waistband',
            'name':{'A':'裙幅 A','B':'裙幅 B','C':'腰头连系带'}[code], 'cut_quantity':1,
            'net_width_cm':w,'net_height_cm':h,'allowance_cm':a,
            'cut_width_cm':w+a['left']+a['right'],'cut_height_cm':h+a['top']+a['bottom'],
            'cut_outline':[[-a['left'],-a['top']],[w+a['right'],-a['top']],
                           [w+a['right'],h+a['bottom']],[-a['left'],h+a['bottom']]],
            'grain':'parallel-to-skirt-length' if skirt else 'parallel-to-band-length',
            'waist_match_x_cm': [0,c['door_width'],w-c['door_width'],w] if skirt else [
                c['tie_length_each'],c['tie_length_each']+c['door_width'],
                c['tie_length_each']+c['door_width']+c['side_folded_width'],
                c['tie_length_each']+2*c['door_width']+c['side_folded_width'],
                c['tie_length_each']+2*c['door_width']+2*c['side_folded_width'],
                c['tie_length_each']+c['waistband_attachment_length']],
            'folds':copy.deepcopy(c['fold_lines']) if skirt else []})
    return {'version':'mamian-drafting-v3','units':'cm','coordinate_system':'net-origin, x right and y down',
        'geometry_source':c['version'],'pieces':pieces,
        'allowance_source':'application construction defaults, not inferred from image',
        'notes':['黑实线为裁剪边界；绿虚线为净样/折边基准；彩色褶线只标记、不剪开。',
                 '裙幅顶边1cm接腰余量，两侧各1cm折边，底边3cm折边；腰头四边各1cm。',
                 'A、B各裁1片，不对折裁；C裁1片。腰头连带较长，需核对布长或另行设计接缝。',
                 '对位点采用线钉/可消笔，不要求剪开裙身；褶裥整理后再接腰头。',
                 '样式示意是结构说明，未经过试缝、布料仿真或合体性验证。']}


def draw_skirt(parent,x,y,p,c):
    g=node(parent,'g',transform=f'translate({x},{y})',id='piece-'+p['id'].lower())
    w,h,door=c['flat_width_each'],c['skirt_length'],c['door_width']
    # Entire physical cut piece, then net-area fills and net reference contour.
    node(g,'rect',x=-1,y=-1,width=w+2,height=h+4,fill='#fbf7ef',stroke=INK,stroke_width='.24',**{'class':'cut-outline'})
    node(g,'rect',x=0,y=0,width=w,height=h,fill='#f5f9fb')
    labels = [('M1','前裙门 · 外层'),('M2','后裙门 · 内层')] if p['id']=='A' else [('M3','后裙门 · 外层'),('M4','前裙门 · 内层')]
    for start,(code,label) in zip([0,w-door],labels):
        node(g,'rect',x=start,y=0,width=door,height=h,fill='#f4e5df',**{'class':'door-zone'})
        text(g,start+door/2,6,code,3.4,RED,text_anchor='middle',font_weight=600)
        text(g,start+door/2,10,label,1.8,RED,text_anchor='middle')
        text(g,start+door/2,14,'保持平整',1.8,MUTED,text_anchor='middle')
        # A suggested trim placement guide, not an extra seam or cut line.
        if door >= 12 and h >= 30:
            node(g,'rect',x=start+2,y=h-15,width=door-4,height=11,fill='none',stroke=GOLD,
                 stroke_width='.13',stroke_dasharray='.5 .6',**{'class':'optional-trim-guide'})
            text(g,start+door/2,h-8,'纹样定位参考',1.6,GOLD,text_anchor='middle')
            text(g,start+door/2,h-5,'不剪开',1.4,GOLD,text_anchor='middle')
    node(g,'rect',x=0,y=0,width=w,height=h,fill='none',stroke='#4d8877',stroke_width='.14',
         stroke_dasharray='1.2 .65',**{'class':'net-outline'})
    for i,mark in enumerate(c['fold_lines']):
        px=mark['x']; mountain=mark['kind']=='mountain'
        color=RED if mountain else BLUE
        line(g,px,0,px,h,color,.15,stroke_dasharray='1.4 .6' if mountain else '.3 .6',**{'class':'fold-mark'})
        node(g,'circle',cx=px,cy=0,r='.30',fill='white',stroke=color,stroke_width='.12')
        text(g,px,-2.1,f'{i+1}',1.6,color,text_anchor='middle')
    for i in range(c['pleat_count_each']):
        pair=c['fold_lines'][2*i:2*i+2]
        mid=sum(v['x'] for v in pair)/2
        # Pair number is well inside the pleat block; avoid collision with door labels.
        text(g,mid,h*.32,f'P{i+1}',1.9,BLUE,text_anchor='middle')
        direction=-1 if pair[0]['direction']=='left' else 1
        arrow(g,mid-direction*1.3,h*.38,mid+direction*1.3,h*.38,BLUE)
    # Prominent grain arrow lives in the flat door to avoid marking congestion.
    arrow(g,door/2,h*.38,door/2,h*.66,INK,both=True)
    text(g,door/2+1.3,h*.53,'经向',1.8,MUTED)
    for px,label in zip(p['waist_match_x_cm'],['a','b','c','d']):
        node(g,'circle',cx=px,cy=0,r='.45',fill=INK)
        text(g,px,3.2,p['id']+label,1.6,INK,text_anchor='middle')
    line(g,0,h+1.5,w,h+1.5,GOLD,.12,stroke_dasharray='1 .6')
    text(g,w/2,h+2.7,'下摆余量 3 cm · 双折参考线',1.6,GOLD,text_anchor='middle')
    text(parent,x-1,y-13,f'{p["id"]}  /  {p["name"]} · 裁 1 片 · 不对折裁',2.6,INK,font_weight=600)
    text(parent,x-1,y-9,f'净样 {w:.1f} × {h:.1f}   |   裁剪 {w+2:.1f} × {h+4:.1f} cm',1.9,MUTED)
    dimension(parent,x,y-5,x+door,y-5,f'裙门 {door:g}')
    dimension(parent,x+door,y-5,x+w-door,y-5,f'展开褶区 {c["side_flat_width"]:.1f}')
    dimension(parent,x+w-door,y-5,x+w,y-5,f'裙门 {door:g}')
    dimension(parent,x-5,y,x-5,y+h,f'净裙长 {h:.1f} cm')
    dimension(parent,x,y+h+7,x+w,y+h+7,f'展开净宽 {w:.1f} → 折后 {c["folded_width_each"]:.1f} cm')
    text(parent,x,y+h+12,'侧边各留 1 cm；顶边接腰 1 cm。褶线不剪开。',1.8,MUTED)


def draw_belt(parent,x,y,p,c):
    g=node(parent,'g',transform=f'translate({x},{y})',id='piece-c')
    w,h=p['net_width_cm'],p['net_height_cm']; tie=c['tie_length_each']
    node(g,'rect',x=-1,y=-1,width=w+2,height=h+2,fill='#fbf7ef',stroke=INK,stroke_width='.24',**{'class':'cut-outline'})
    node(g,'rect',x=0,y=0,width=w,height=h,fill='#edf3f5',stroke='#4d8877',stroke_width='.14',stroke_dasharray='1 .6')
    line(g,0,h/2,w,h/2,BLUE,.15,stroke_dasharray='1.4 .6')
    text(parent,x,y-11,f'C  /  腰头连系带 · 裁 1 片 · 四边各留 1 cm',2.6,INK,font_weight=600)
    text(parent,x,y-7,f'净样 {w:.1f} × {h:.1f} cm；对折后腰头高 {h/2:.1f} cm；沿布长排料',1.9,MUTED)
    for center in [tie/2,w-tie/2]:
        arrow(g,center-8,h*.75,center+8,h*.75,MUTED,both=True)
        text(g,center,h*.4,'自由系带 45 cm',1.8,MUTED,text_anchor='middle')
    points=p['waist_match_x_cm']
    for start,end,label in zip(points,points[1:],['Aa–Ab','Ab–Ac（折后）','Ac–Ad + Ba–Bb','Bb–Bc（折后）','Bc–Bd']):
        line(g,start,0,start,h,BLUE,.1,stroke_dasharray='.5 .5')
        text(g,(start+end)/2,-1.8,label,1.55,INK,text_anchor='middle')
    line(g,points[-1],0,points[-1],h,BLUE,.1,stroke_dasharray='.5 .5')
    text(g,w/2,h*.78,'腰头中线对折；后裙门叠合段夹入双层裙门',1.7,BLUE,text_anchor='middle')
    dimension(parent,x,y+h+5,x+w,y+h+5,f'含两端系带净长 {w:.1f} cm · 对位使用折后长度')


def render_cutting(folder,c,data):
    width=max(230,2*c['flat_width_each']+37,c['waistband_attachment_length']+2*c['tie_length_each']+24)
    band_y=34; skirt_y=74; bottom=skirt_y+c['skirt_length']+23
    root=sheet(width,bottom+28)
    text(root,10,8,'马面裙  /  精细裁片与对位',4.2,INK,font_weight=600)
    text(root,10,13,f'基础两幅交叠款 · 净裙长 {c["skirt_length"]:.1f} cm · 穿着围度 {c["wearing_circumference"]:.1f} cm · 每幅 {c["pleat_count_each"]} 褶',2.1,MUTED)
    for x,color,dash,label in [(10,INK,None,'裁剪线'),(48,'#4d8877','1 .6','净样 / 折边基准'),(110,RED,'1.4 .6','山折'),(144,BLUE,'.3 .6','谷折'),(175,GOLD,'.5 .6','可选纹样定位')]:
        attrs={'stroke_dasharray':dash} if dash else {}
        line(root,x,19,x+7,19,color,.22,**attrs)
        text(root,x+9,19.7,label,1.9,color)
    draw_belt(root,12,band_y,data['pieces'][2],c)
    start_b=12+c['flat_width_each']+15
    draw_skirt(root,12,skirt_y,data['pieces'][0],c)
    draw_skirt(root,start_b,skirt_y,data['pieces'][1],c)
    line(root,10,bottom,width-10,bottom,'#d7e1e5',.15)
    text(root,10,bottom+5,'操作顺序  01 标记褶位与对位点 → 02 熨折 P1–P4 → 03 整理前后裙门 → 04 对位接腰头 → 05 处理开口边与下摆',2.05)
    text(root,10,bottom+10,'M1 与 M4 在前中心搭接；M2 与 M3 在后中心搭接。裙幅竖边保持开口，不连接成裙筒。',2.05)
    text(root,10,bottom+15,'余量为本模板默认：顶 1 / 侧 1 / 下摆 3 / 腰头 1 cm。纹样框仅辅助定位，不表示刺绣复原。',1.9,MUTED)
    text(root,10,bottom+20,'基础纸样未试缝。以 100% 打印并核对标尺；款式示意不能代替裁剪图。',1.9,MUTED)
    line(root,width-34,bottom+24,width-24,bottom+24,INK,.2)
    for x in [width-34,width-24]: line(root,x,bottom+23.4,x,bottom+24.6,INK,.15)
    text(root,width-22,bottom+24.6,'10 cm',1.8)
    save(root,folder/'cutting.svg')
    # Each detail is a complete standalone SVG: readable without browser-specific fragments.
    regions={'a':(3,skirt_y-18,c['flat_width_each']+15,c['skirt_length']+37),
             'b':(start_b-9,skirt_y-18,c['flat_width_each']+15,c['skirt_length']+37),
             'waistband':(4,band_y-16,width-8,data['pieces'][2]['net_height_cm']+26)}
    for name,(x,y,w,h) in regions.items():
        detail=copy.deepcopy(root)
        detail.set('viewBox',f'{x} {y} {w} {h}')
        detail.set('width',f'{w}cm'); detail.set('height',f'{h}cm')
        save(detail,folder/f'cutting-{name}.svg')


def render_style(path,c):
    root=sheet(200,133)
    text(root,9,9,'马面裙  /  款式结构示意',4.1,INK,font_weight=600)
    text(root,9,15,'平整裙门 + 两侧褶裥 + 前后搭接 + 腰头系带',2.6,MUTED)
    # A schematic projection: vertical extent follows net length, not a draping simulation.
    scale=min(76/c['skirt_length'],.9)
    h=c['skirt_length']*scale
    door=min(c['door_width']*scale,24)
    for center,label,ids in [(47,'正面',('M1','M4')),(140,'背面',('M3','M2'))]:
        y=35; top=max(door+15,37); hem=top+20
        outline=f'M {center-top/2},{y} L {center+top/2},{y} L {center+hem/2},{y+h} Q {center},{y+h+3} {center-hem/2},{y+h} Z'
        node(root,'path',d=outline,fill='#ead9d4',stroke=INK,stroke_width='.3')
        for side in [-1,1]:
            for j in range(c['pleat_count_each']//2+1):
                tx=center+side*(door/2+2+j*3)
                bx=center+side*(door/2+4+j*6.5)
                node(root,'path',d=f'M {tx},{y} L {bx},{y+h}',fill='none',stroke=RED,stroke_width='.26')
        node(root,'path',d=f'M {center-door/2},{y} H {center+door/2} V {y+h+1} H {center-door/2} Z',
             fill='#f5e9e0',stroke=RED,stroke_width='.22',**{'class':'style-door'})
        # Flat skirt door and hem accent express construction without invented embroidery.
        node(root,'rect',x=center-door/2+1,y=y+h-14,width=max(door-2,1),height=10,
             fill='none',stroke=GOLD,stroke_width='.2',stroke_dasharray='.6 .7')
        line(root,center-hem/2+1,y+h-4,center+hem/2-1,y+h-4,GOLD,.5)
        node(root,'rect',x=center-top/2-1,y=y-4,width=top+2,height=4,fill='#9c4c46',stroke=INK,stroke_width='.22')
        if label=='正面':
            knot=center-top/2+2
            for side in [-1,1]:
                node(root,'path',d=f'M {knot},{y-2} q {side*8},-7 {side*9},-1 q 0,5 {-side*9},1',
                     fill='#b3655a',stroke=INK,stroke_width='.2')
            for dx in [-4,1]:
                node(root,'path',d=f'M {knot+dx},{y-1} l -2,20 l 3,1 l 3,-21 Z',fill='#b3655a',stroke=INK,stroke_width='.2')
            node(root,'circle',cx=knot,cy=y-2,r=1.3,fill='#9c4c46',stroke=INK,stroke_width='.15')
        text(root,center,27,label,2.8,INK,text_anchor='middle')
        text(root,center,y+h+8,f'平整裙门 {ids[0]} / {ids[1]} 搭接',2.1,RED,text_anchor='middle')
        text(root,center,y+h+12,'两侧褶裥向裙门侧整理',2,MUTED,text_anchor='middle')
    text(root,9,129,'示意图不按 1:1 比例；外展轮廓为绘图表达，非布料仿真。纹样框为定位参考，不属于裁片边界。',1.85,MUTED)
    save(root,path)


def render_pleat_detail(path,c):
    root=sheet(200,116)
    text(root,8,9,'折褶详解  /  从展开布幅到腰头对位',3.8,INK,font_weight=600)
    text(root,8,15,f'每幅 4 个褶 · 展开褶区 {c["side_flat_width"]:.1f} → 折后 {c["side_folded_width"]:.1f} cm · 褶深 {c["pleat_depth"]:.2f} cm',2.2,MUTED)
    # Enlarged material cross section, computed directly from the piecewise fold map.
    points=c['fold_map']; start=points[0][0]; end=points[-1][0]
    sx=170/(end-start)
    text(root,8,24,'01  腰口展开：按编号标线，红为山折、蓝为谷折（不剪开）',2.4)
    node(root,'rect',x=14,y=29,width=170,height=18,fill='#f3f7f9',stroke=INK,stroke_width='.16')
    for i,m in enumerate(c['fold_lines']):
        x=14+(m['x']-start)*sx
        line(root,x,29,x,47,RED if m['kind']=='mountain' else BLUE,.2,stroke_dasharray='1 .6')
        text(root,x,27.5,str(i+1),2.0,RED if m['kind']=='mountain' else BLUE,text_anchor='middle')
    for i in range(4):
        text(root,14+(i+.5)*170/4,43,f'P{i+1}',2.5,BLUE,text_anchor='middle')
    text(root,8,57,'02  褶裥横截面放大：折回段保留布量，不能把褶区直接裁窄',2.4)
    # Diagram separates overlapping layers vertically; x uses the true folded map.
    folded=c['side_folded_width']; factor=145/folded
    trace=[]
    for i,(u,v) in enumerate(points):
        sign=1 if max(0,(i-1)//3)<c['pleat_count_each']//2 else -1
        z=0 if i==0 or i%3==0 else sign*(3 if i%3==1 else -3)
        trace.append([23+(v-start)*factor,71+z])
    node(root,'polyline',points=' '.join(f'{x:.4f},{y:.4f}' for x,y in trace),
         fill='none',stroke=BLUE,stroke_width='.55',**{'class':'fold-cross-section'})
    dimension(root,23,82,168,82,f'折后侧褶区 {folded:.1f} cm')
    text(root,8,94,'03  接腰：Aa–Ab / Ab–Ac / Ac–Ad 与腰头 A 区对位；B 幅同理。',2.25)
    text(root,8,100,'后裙门 Ac–Ad 与 Ba–Bb 先叠合，再共同夹入腰头；前裙门由系带围合。',2.25)
    text(root,8,107,'褶深是单个折回量；一褶吃量 = 2 × 褶深。示意的层间高度被放大，不是缝份。',2.0,MUTED)
    save(root,path)


def render_drafting(folder,c):
    data=cut_data(c)
    (folder/'cutting.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    render_cutting(folder,c,data)
    render_style(folder/'style.svg',c)
    render_pleat_detail(folder/'pleat-detail.svg',c)
    return data
