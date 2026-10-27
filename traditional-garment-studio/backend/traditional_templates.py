"""Evidence-informed basic flat patterns, application version 2026-10-18.

These are adjustable teaching templates, not measured museum reproductions.
Research sources and the distinction between observations and design choices
are recorded in docs/research-2026-10-18. Frozen training data stay unchanged.
"""
import math
from collections import Counter

import numpy as np
import pygarment as pyg
from pygarment.pattern.wrappers import VisPattern

from .mamian_v2 import rectangle
from .collar_facings import cross_collar,duijin_collar


SUPPORTED = {'beizi', 'banbi', 'ruqun-skirt', 'cloud-shoulder', 'round-collar', 'cross-collar', 'duijin-collar'}
VERSION = 'traditional-basics-2026-10-18'
CLOUD_VERSION = 'cloud-basics-2026-10-27-v2'
SOURCE_URLS = {
    'CSM-SONG-2023':'https://www.chinasilkmuseum.com/ngcxg/info_11.aspx?itemid=31128',
    'CSM-COLLAR-2023':'https://www.chinasilkmuseum.com/ngcxg/info_11.aspx?itemid=31157',
    'CSM-TANG-BANBI':'https://www.chinasilkmuseum.com/yz/info_18.aspx?itemid=28162',
    'HBUST-BANBI':'https://jgy.hbust.edu.cn/info/1001/2943.htm',
    'CNM-CLOUD':'https://www.cnmuseum.com/cn/album/2511/0080-1.htm',
    'MET-671791':'https://www.metmuseum.org/art/collection/search/70458',
    'MAKER-RUQUN-2015':'https://www.aihanfu.com/wen/1176/',
}


def piece(points, curves=None):
    """Serialize absolute control points without moving the drafting origin."""
    points = [[float(x), float(y)] for x, y in points]
    edges = []
    for i, start in enumerate(points):
        end = points[(i+1) % len(points)]
        controls = (curves or {}).get(i)
        edge = (pyg.CurveEdge(start, end, control_points=controls, relative=False)
                if controls else pyg.Edge(start, end))
        _, serialized = edge.assembly()
        serialized['endpoints'] = [i, (i+1) % len(points)]
        edges.append(serialized)
    return {'vertices': points, 'edges': edges,
            'translation': [0., 0., 0.], 'rotation': [0., 0., 0.]}


def new_pattern(component):
    result = VisPattern()
    result.name = component + '-basic-v2'
    return result


def curve_for(pattern, name):
    return pattern._draw_a_panel(name, apply_transform=False, fill=False)[0]


def edge_length(pattern, name, edge):
    return float(curve_for(pattern, name)[edge].length())


def seam(pattern, first, second):
    pattern.pattern['stitches'].append([
        {'panel': first[0], 'edge': first[1]},
        {'panel': second[0], 'edge': second[1]}])


def fold_mark(panel, start, end):
    return {'panel': panel, 'kind': 'fold', 'start': start, 'end': end}


def arc(center, radius, start, end):
    """Cubic circular arc, angles measured from the positive y axis."""
    def point(a):
        return [center[0]+radius*math.sin(a), center[1]+radius*math.cos(a)]
    k = 4/3*math.tan((end-start)/4)
    a, b = point(start), point(end)
    controls = [[a[0]+k*radius*math.cos(start), a[1]-k*radius*math.sin(start)],
                [b[0]-k*radius*math.cos(end), b[1]+k*radius*math.sin(end)]]
    return a, b, controls


def build_upper(body, design, component):
    """Open-front, dropped-shoulder basic beizi / short-sleeved banbi."""
    d = design[component]
    is_beizi = component == 'beizi'
    length = float(d['length']['v'])*body['_leg_length']
    half = float(d['chest_ease']['v'])*body['bust']/4
    neck = min(body['neck_w']/2, half*.55)
    front_depth = float(d['neck_depth_front']['v'])
    back_depth = float(d['neck_depth_back']['v'])
    cuff_half = float(d['sleeve_cuff_width']['v'])/2 if is_beizi else float(d['sleeve_width']['v'])
    # The root controls the body armhole. A wide/flared cuff must not enlarge
    # the body or move the slit: root and cuff are independent sleeve ends.
    arm_depth = float(d['sleeve_root_width']['v'])/2 if is_beizi else 18.
    sleeve_from_shoulder = float(d['sleeve_length']['v'])*body['arm_length']
    dropped_shoulder = max(0., half-body['shoulder_w']/2)
    sleeve_length = sleeve_from_shoulder-dropped_shoulder
    slit = float(d['slit_height']['v'])*length if is_beizi else 0.
    if min(length-front_depth, length-arm_depth-slit, sleeve_length, half-neck) <= 1:
        raise ValueError('衣长、开衩或袖长不足以组成当前上衣，请降低开衩或增加长度。')
    pattern = new_pattern(component)
    panels = pattern.pattern['panels']
    prefix = component+'_'
    # Side slits are deliberately separate free edges, never silently clamped.
    stop = length-slit
    back_points = [[-neck,0],[-half,0],[-half,-arm_depth],[-half,-stop],
                   [-half,-length],[half,-length],[half,-stop],[half,-arm_depth],
                   [half,0],[neck,0]]
    # Banbi has no side slit: avoid zero-length edges at the hem.
    if not is_beizi:
        back_points = [[-neck,0],[-half,0],[-half,-arm_depth],[-half,-length],
                       [half,-length],[half,-arm_depth],[half,0],[neck,0]]
    back_name = prefix+'back'
    panels[back_name] = piece(back_points, {len(back_points)-1:[[0,-2*back_depth]]})
    back_refs = {'left': {'shoulder':0, 'root':1, 'side':2},
                 'right': {'shoulder':8 if is_beizi else 6,
                           'root':7 if is_beizi else 5, 'side':6 if is_beizi else 4}}
    free_edges, marks = [], []
    front_paths = []
    for side, sign in [('left',-1),('right',1)]:
        points = [[neck,0],[half,0],[half,-arm_depth],[half,-stop],
                  [half,-length],[0,-length],[0,-front_depth]] if is_beizi else [
                  [neck,0],[half,0],[half,-arm_depth],[half,-length],[0,-length],[0,-front_depth]]
        points = [[sign*x,y] for x,y in points]
        f = prefix+'front_'+side
        neckline = len(points)-1
        opening = len(points)-2
        panels[f] = piece(points, {neckline:[[sign*neck*.30,-front_depth*.40]]})
        seam(pattern, (f,0), (back_name,back_refs[side]['shoulder']))
        seam(pattern, (f,2), (back_name,back_refs[side]['side']))
        free_edges.append({'panel':f,'edge':opening,'reason':'front opening; facing attached, fronts remain separate'})
        if is_beizi:
            free_edges += [{'panel':f,'edge':3,'reason':'unsewn side slit'},
                           {'panel':back_name,'edge':3 if side=='left' else 5,'reason':'unsewn side slit'}]
        sleeve = prefix+'sleeve_'+side
        # Root is split into two halves, each exactly equal to one body armhole.
        # Flat tapered sleeve, no unsupported Western sleeve-cap approximation.
        panels[sleeve] = piece([[0,0],[0,-arm_depth],[0,-2*arm_depth],
            [sleeve_length,-arm_depth-cuff_half],[sleeve_length,-arm_depth+cuff_half]])
        seam(pattern, (sleeve,0), (f,1))
        seam(pattern, (sleeve,1), (back_name,back_refs[side]['root']))
        seam(pattern, (sleeve,2), (sleeve,4))
        front_paths.append([(f,opening),(f,neckline)])
        marks.append(fold_mark(sleeve,[0,-arm_depth],[sleeve_length,-arm_depth]))
    # One measured facing follows the two front edges and the back neckline.
    # Segment lengths are actual Bezier arc lengths, not endpoint chords.
    facing_targets = front_paths[0]+[(back_name,len(back_points)-1)]+list(reversed(front_paths[1]))
    facing_lengths = [edge_length(pattern,*ref) for ref in facing_targets]
    breaks = list(np.cumsum(facing_lengths))
    facing = prefix+'neck_front_facing'
    panels[facing] = rectangle(sum(facing_lengths),6.,breaks[:-1])
    for i, ref in enumerate(facing_targets):
        seam(pattern,(facing,i),ref)
    marks.append(fold_mark(facing,[0,-3],[sum(facing_lengths),-3]))
    for side in ['left','right']:
        tie = prefix+'tie_'+side
        panels[tie] = rectangle(35.,3.)
        marks.append(fold_mark(tie,[0,-1.5],[35,-1.5]))
    notes = [
        '采用直领对襟基础款：左右前身独立，前襟从领口一直开至下摆；不是交领右衽款。',
        '领襟贴边按实际领口弧长分段配长；袖片有对折线、袖底缝，袖根与前后衣身逐段等长。',
        '领襟包边使用斜裁条，成品宽3cm、系带各35cm为模板默认值；系带在前襟胸线附近手缝固定。',
        '这里是无里基础净样，不复原出土夹衣的里布、印金镶边或纽襻工艺。',
        f'袖长{sleeve_from_shoulder:.1f}cm从人体肩点沿臂部方向计，含落肩{dropped_shoulder:.1f}cm；独立袖片从衣身边缘至袖口为{sleeve_length:.1f}cm。',
    ]
    if is_beizi:
        notes.append(f'两侧各开衩{slit:.1f}cm；开衩纵边保持自由，不能与侧缝一起缝死。')
    else:
        notes.append('半臂有对襟、交领等多种历史形态；当前默认对襟短袖款，袖口宽参数为平铺半围。')
    report = {'version':'upper-sleeve-2026-10-21','component':component,'variant':'straight-collar-open-front',
        'variant_label':'直领对襟褙子基础款' if is_beizi else '对襟短袖半臂基础款',
        'source_ids':['CSM-SONG-2023','CSM-COLLAR-2023'] if is_beizi else ['CSM-TANG-BANBI','HBUST-BANBI'],
        'units':'cm','finished_length':length,'garment_bust':4*half,
        'body_half_width':half,'neck_half_width':neck,'front_neck_depth':front_depth,
        'armhole_depth':arm_depth,
        'sleeve_length_from_shoulder':sleeve_from_shoulder,'dropped_shoulder_length':dropped_shoulder,
        'sleeve_length_from_body_edge':sleeve_length,'sleeve_opening_circumference':2*cuff_half,
        'slit_length':slit,'facing_length':sum(facing_lengths),'facing_finished_width':3.,
        'tie_length_each':35.,'free_edges':free_edges,'notes':notes,'simulation_supported':False}
    pattern.pattern['drafting_marks'] = marks
    return pattern,report


def build_ruqun(body, design):
    """Six-gore open wrap lower skirt; an explicit modern basic variant."""
    d = design['ruqun-skirt']
    length = float(d['length']['v'])*body['_leg_length']
    position = float(d['waist_position']['v'])
    # Waist, high/underbust and chest positions use available body measures.
    # Upper-chest placement still needs an actual wearing-position measurement.
    if position<=.85:
        fraction=max(0.,min(1.,(position-.7)/.15))
        reference=body['waist']+(body['underbust']-body['waist'])*fraction
    else:
        fraction=max(0.,min(1.,(position-.85)/.10))
        reference=body['underbust']+(body['bust']-body['underbust'])*fraction
    wearing=reference*float(d['waist_ratio']['v'])
    overlap = max(18.,min(30.,wearing*.25))
    top = wearing+overlap
    hem = wearing*float(d['hem_ratio']['v'])
    if hem <= top or min(length,wearing) <= 0:
        raise ValueError('裙摆展宽不足以组成围裹裙，请增加展宽或检查围度。')
    count = 6
    inner = length/(hem/top-1)
    angle = top/count/inner
    if not 0 < angle < math.pi/2:
        raise ValueError('裙长与放摆比例不适合当前六幅基础款，请增加裙长或降低展宽。')
    pattern = new_pattern('ruqun-skirt')
    panels = pattern.pattern['panels']
    # x=R*sin(theta), y=inner-R*cos(theta).
    a,b,ct = arc([0,0],inner,-angle/2,angle/2)
    a,b = [a[0],inner-a[1]],[b[0],inner-b[1]]
    ct = [[x,inner-y] for x,y in ct]
    br,bl,ch = arc([0,0],inner+length,angle/2,-angle/2)
    br,bl = [br[0],inner-br[1]],[bl[0],inner-bl[1]]
    ch = [[x,inner-y] for x,y in ch]
    for i in range(count):
        name = f'ruqun_gore_{i+1:02d}'
        panels[name] = piece([a,b,br,bl],{0:ct,2:ch})
        if i:
            seam(pattern,(f'ruqun_gore_{i:02d}',1),(name,3))
    # Use the measured arc length in the waistband to avoid arc/chord mismatch.
    top_each = edge_length(pattern,'ruqun_gore_01',0)
    actual_top = top_each*count
    tie = float(d['tie_length']['v'])
    band_height = float(d['waistband_width']['v'])*body['hips_line']
    breaks = [top_each*i for i in range(1,count)]
    panels['ruqun_waistband'] = rectangle(actual_top,2*band_height,breaks)
    for i in range(count):
        seam(pattern,('ruqun_waistband',i),(f'ruqun_gore_{i+1:02d}',0))
    marks=[fold_mark('ruqun_waistband',[0,-band_height],[actual_top,-band_height])]
    # Separate ties make the cut list explicit and avoid a misleading 2.7 m
    # uninterrupted waistband dominating the preview. Join before folding.
    for side in ['left','right']:
        name='ruqun_tie_'+side
        panels[name]=rectangle(tie,2*band_height)
        seam(pattern,('ruqun_waistband',count+2 if side=='left' else count),
             (name,1 if side=='left' else 3))
        marks.append(fold_mark(name,[0,-band_height],[tie,-band_height]))
    pattern.pattern['drafting_marks'] = marks
    notes = [
        '默认采用六幅放摆围裹下裙：各幅沿径向拼接，只缝五道纵缝，首尾保留整条自由边用于搭接。',
        f'上缘围合长度{actual_top:.1f}cm，按穿着围度{wearing:.1f}cm加搭接{overlap:.1f}cm；独立系带只接腰头短边，不接裙身。',
        '裙腰与裙摆为同心圆弧，腰头按弧长配长；这是一种现代参数化基础款，并非所有朝代襦裙的通用裁法。',
        '齐腰参考腰围，高腰参考下胸围，齐胸暂参考胸围；中间位置插值。做实物前按实际穿着位置复量，照片不提供绝对尺寸。',
        '当前仅输出下裙；上襦、披帛、里裙和装饰不包含在这些裁片中。',
    ]
    return pattern, {'version':VERSION,'component':'ruqun-skirt','variant':'six-gore-wrap-lower-skirt',
        'variant_label':'六幅放摆围裹下裙',
        'units':'cm','source_ids':['CSM-SONG-2023','MAKER-RUQUN-2015'],
        'finished_length':length,'wearing_circumference_estimate':wearing,
        'waist_position':position,'overlap':overlap,'gore_count':count,
        'top_arc_each':top_each,'hem_arc_each':edge_length(pattern,'ruqun_gore_01',2),
        'waistband_attachment_length':actual_top,'tie_length_each':tie,
        'separate_ties':True,'waistband_finished_height':band_height,
        'free_edges':[{'panel':'ruqun_gore_01','edge':3,'reason':'wrap opening'},
                      {'panel':'ruqun_gore_06','edge':1,'reason':'wrap opening'}],
        'notes':notes,'simulation_supported':False}


def build_cloud(body, design):
    """Layered, front-opening cloud lobes sharing one neckline."""
    d = design['cloud-shoulder']
    count,layers = int(d['petal_count']['v']),int(d['layers']['v'])
    neck = body['neck_w']*.55
    petal = float(d['petal_length']['v'])*body['shoulder_w']
    extension=float(d.get('front_extension',{'v':0.})['v'])
    tassel = float(d['tassel_length']['v'])
    gap = math.radians(12.)
    start,end = gap/2,2*math.pi-gap/2
    steps = count*12
    pattern = new_pattern('cloud-shoulder')
    panels = pattern.pattern['panels']
    binding_targets,marks,tassels = [],[],[]
    # Each layered C-piece has the same neckline; the front opening stays free.
    for layer in range(layers):
        name = f'cloud_layer_{layer+1:02d}'
        offset = (layers-1-layer)*petal*.32
        def radius(a):
            phase = count*a
            return neck+1.8+offset+petal*(.52+.28*math.cos(phase)-.25*math.cos(2*phase))+extension*max(0.,math.cos(a))**2
        def point(a):
            r=radius(a)
            return [r*math.sin(a),-r*math.cos(a)]
        angles = np.linspace(start,end,steps+1)
        points = [point(float(a)) for a in angles]
        controls = {}
        # Cubic Hermite interpolation of a smooth radial cloud-head outline.
        def derivative(a):
            r=radius(a)
            dr=petal*count*(-.28*math.sin(count*a)+.50*math.sin(2*count*a))
            dr-=2*extension*max(0.,math.cos(a))*math.sin(a)
            return [dr*math.sin(a)+r*math.cos(a),-dr*math.cos(a)+r*math.sin(a)]
        for i in range(steps):
            h=float(angles[i+1]-angles[i])/3
            da,db=derivative(float(angles[i])),derivative(float(angles[i+1]))
            controls[i]=[[points[i][j]+h*da[j] for j in range(2)],
                         [points[i+1][j]-h*db[j] for j in range(2)]]
        # Opening edge to neckline, then a smooth, segmented inner circle.
        inner_steps = count*2
        inner_angles = np.linspace(end,start,inner_steps+1)
        for i in range(inner_steps+1):
            a=float(inner_angles[i])
            points.append([neck*math.sin(a),-neck*math.cos(a)])
        for i in range(inner_steps):
            index=steps+1+i
            aa,bb,cc=arc([0,0],neck,float(inner_angles[i]),float(inner_angles[i+1]))
            controls[index]=[[x,-y] for x,y in cc]
            binding_targets.append((name,index))
        panels[name]=piece(points,controls)
        if layer==0 and tassel>0:
            for i in range(count):
                # Two mirrored cloud-head tips; their count is a disclosed
                # template choice, never inferred from a partly hidden photo.
                for direction in [-1,1]:
                    a=(i*2*math.pi+direction*math.acos(.28))/count
                    a=a%(2*math.pi)
                    pos=point(a)
                    tassels.append({'position_cm':pos,'length_cm':tassel,'kind':'purchased cord tassel'})
                    marks.append({'panel':name,'kind':'tassel-position','point':pos})
    # Neck binding joins all layers simultaneously, like a layered seam.
    inner_refs=binding_targets[:count*2]
    lens=[edge_length(pattern,*ref) for ref in inner_refs]
    band=sum(lens)
    panels['cloud_neck_binding']=rectangle(band,3.,list(np.cumsum(lens))[:-1])
    for layer in range(layers):
        for i in range(count*2):
            seam(pattern,('cloud_neck_binding',i),binding_targets[layer*count*2+i])
    marks.append(fold_mark('cloud_neck_binding',[0,-1.5],[band,-1.5]))
    pattern.pattern['drafting_marks']=marks
    pattern.pattern['template_version']=CLOUD_VERSION
    notes = [
        '默认采用云头层叠基础轮廓；各层共用同一领口，前中保留穿脱开口，不把开口缝死。',
        '领口包边同时夹住各层；外缘不相互缝合。四云头时参考四合式构成，六/八云头为参数化变化。',
        '领口半径、层间距与云头曲线为可调整的工程默认值，不是馆藏实物的逐点描摹。',
        ('垂须采用成品绳须配件，每云头两个安装点为模板默认值；不输出环绕全周的长方形布须。'
         if tassel>0 else '当前采用无垂须款，不增加穗须安装点或成品穗须配件。'),
        '当前是平面装饰云肩净样；肩部省量、衬里、刺绣和垂坠需另行试样。',
    ]
    notes.append(f'云头曲线大小基准{petal:.1f}cm，前摆延伸参数{extension:.1f}cm；这两个值不是整件宽高，实际总尺寸以净样标注为准，图片建议值不是照片测量或馆藏实测。')
    return pattern, {'version':CLOUD_VERSION,'component':'cloud-shoulder','variant':'layered-front-opening-cloud-lobes',
        'variant_label':'四合云头平面基础款' if count==4 else f'{count}云头平面变化款',
        'source_ids':['CNM-CLOUD','MET-671791'],'units':'cm','layers':layers,'petal_count':count,
        'neck_radius':neck,'opening_angle_degrees':12.,'neck_binding_length':band,
        'petal_length_cm':petal,'petal_length_ratio':float(d['petal_length']['v']),'front_extension_cm':extension,
        'tassel_length':tassel,'tassels_per_lobe_default':2,'tassels':tassels,'notes':notes,
        'layered_seams':[{'panel':'cloud_neck_binding','edge':i,'layers':layers} for i in range(count*2)],
        'free_edges':[{'panel':f'cloud_layer_{i+1:02d}','edge':edge,'reason':'front opening'}
                      for i in range(layers) for edge in [steps,steps+count*2+1]],
        'simulation_supported':False}


def build_round_collar(body, design):
    """Two open half-neck facings; the neckline is empty, never a filled insert."""
    d=design['round-collar']
    front=float(d['front_depth']['v'])
    back=float(d['back_depth']['v'])
    border=float(d['border_width']['v'])
    radius=float(body['neck_w'])/2+front*.1
    if min(front,back,border,radius)<=0 or front<=back:
        raise ValueError('圆领需要正的领深、缘边宽，且前领深应大于后领深。')
    k=4/3*math.tan(math.pi/8)
    pattern=new_pattern('round-collar')
    free=[]
    for side,sign in [('left',-1),('right',1)]:
        points=[[0,-front],[radius,0],[0,back],[0,back+border],
                [radius+border,0],[0,-front-border]]
        curves={0:[[k*radius,-front],[radius,-k*front]],
                1:[[radius,k*back],[k*radius,back]],
                3:[[k*(radius+border),back+border],[radius+border,k*(back+border)]],
                4:[[radius+border,-k*(front+border)],[k*(radius+border),-front-border]]}
        name='round_collar_'+side
        pattern.pattern['panels'][name]=piece([[sign*x,y] for x,y in points],
            {i:[[sign*x,y] for x,y in controls] for i,controls in curves.items()})
        free += [{'panel':name,'edge':i,'reason':'front opening' if i==5 else 'free facing boundary'}
                 for i in [0,1,3,4,5]]
    seam(pattern,('round_collar_left',2),('round_collar_right',2))
    report={'version':'round-neck-facing-2026-10-20','component':'round-collar',
        'variant':'open-round-neck-facing','variant_label':'前中开口圆领贴基础款',
        'source_ids':[],'units':'cm','neck_half_width':radius,'front_depth':front,
        'back_depth':back,'border_width':border,'free_edges':free,'marks':[],
        'notes':['左右领贴在后中拼接，内侧为真实颈口边界；颈口区域不应填成布片。',
                 '前中保持开口，纽襻或系结另做；当前仅生成圆领贴，不包含衣身。',
                 '缘边宽用于外扩领贴；这是一款可调整的几何基础款，未复原某件馆藏服饰。'],
        'simulation_supported':False}
    return pattern,report


def build_traditional(body, design, component):
    if component in {'beizi','banbi'}:
        pattern,report=build_upper(body,design,component)
    elif component=='ruqun-skirt':
        pattern,report=build_ruqun(body,design)
    elif component=='cloud-shoulder':
        pattern,report=build_cloud(body,design)
    elif component=='round-collar':
        pattern,report=build_round_collar(body,design)
    elif component=='cross-collar':
        pattern,report=cross_collar(body,design,piece,new_pattern,seam)
    elif component=='duijin-collar':
        pattern,report=duijin_collar(body,design,piece,new_pattern)
    else:
        raise ValueError('Unsupported application template')
    pattern.pattern['template_version']=report.get('version',VERSION)
    report['sources']=[{'id':key,'url':SOURCE_URLS[key]} for key in report['source_ids']]
    report['cut_list']=[{'panel':name,'quantity':1,'net_pattern':True,
        'grain':'bias strip; test before cutting' if name.endswith(('neck_front_facing','neck_binding'))
                else 'lengthwise grain through panel centre',
        'allowance_cm':None} for name in pattern.pattern['panels']]
    report['assembly_steps']={
        'beizi':['合肩缝，后领与两前领保持连贯。','袖根中点对肩缝，两半袖根分别接前后袖窿。',
                 '合袖底和侧缝，开衩段保持自由。','斜裁领襟包边先试样，沿领襟连续包缝；系带另行固定。'],
        'banbi':['合肩缝；袖根中点对肩缝。','前后各半袖根接衣身，合袖底和侧缝。',
                 '领襟用斜裁包边，左右前襟不得相互缝死。','系带另行固定，试样确认短袖与衣长。'],
        'ruqun-skirt':['六幅裙片按顺序接成一排，只缝五道纵缝。','两根系带先接腰头两端短边，再沿中线折腰头。',
                        '按六段弧长把裙腰接入腰头，首尾围裹边保持自由。','按实际穿着高度复核围度与搭接，试样后再定折边。'],
        'cloud-shoulder':['各层领口和前中开口对齐，外层置下、较小层置上。',
                          '领口以斜裁包边同时夹住各层，外缘分层保持自由。',
                          '前中开口不得缝死，试样后另配纽襻或系结。','成品绳须按标点固定；肩部省量、衬里及刺绣需另做试样。'],
        'round-collar':['左右领贴后中短边等长拼接，前中短边保持开口。',
                        '内侧弧线与衣身领口配合，外侧领贴边缘另作包缝。',
                        '先试样核对颈口与衣身，另配纽襻或系结；当前净样未加缝份。'],
        'cross-collar':['左右前领贴短边分别与后领贴短边拼合，核对领缘宽。',
                        '以左右长短前领贴定位右衽交叉关系；领圈边与目标衣身另行试配。',
                        '领口内侧及两前领末端保持自由，不将左右前领相互缝死。'],
        'duijin-collar':['左右前领襟贴保持独立，先与目标前衣身领口试配。',
                        '按前中开口位置分别固定领襟，不连接两片前中自由边。',
                        '当前不含后领与衣身，完成整件前需补充相应裁片。'],
    }[component]
    report['validation']=validate_template(pattern,report)
    return pattern,report


def valid_outline(points):
    """Area and non-adjacent segment intersection on a sampled closed curve."""
    a=np.asarray(points,dtype=float)
    if len(a)<3 or not np.isfinite(a).all():
        return False
    b=np.roll(a,-1,axis=0)
    if abs(np.sum(a[:,0]*b[:,1]-b[:,0]*a[:,1]))<1e-6:
        return False
    n=len(a)
    delta=b-a
    # Only non-adjacent pairs; shared endpoints of adjacent edges are expected.
    i,j=np.triu_indices(n,k=2)
    keep=~((i==0)&(j==n-1))
    i,j=i[keep],j[keep]
    cross=lambda u,v:u[:,0]*v[:,1]-u[:,1]*v[:,0]
    p,q=delta[i],delta[j]
    offset=a[j]-a[i]
    den=cross(p,q)
    nonparallel=np.abs(den)>1e-10
    t=np.zeros_like(den);u=np.zeros_like(den)
    t[nonparallel]=cross(offset,q)[nonparallel]/den[nonparallel]
    u[nonparallel]=cross(offset,p)[nonparallel]/den[nonparallel]
    if np.any(nonparallel&(t>=-1e-8)&(t<=1+1e-8)&(u>=-1e-8)&(u<=1+1e-8)):
        return False
    collinear=(~nonparallel)&(np.abs(cross(offset,p))<1e-10)
    if np.any(collinear):
        pi,pj=i[collinear],j[collinear]
        lo=np.maximum(np.minimum(a[pi],b[pi]),np.minimum(a[pj],b[pj]))
        hi=np.minimum(np.maximum(a[pi],b[pi]),np.maximum(a[pj],b[pj]))
        if np.any(np.all(hi>=lo-1e-8,axis=1)):
            return False
    return True


def validate_template(pattern,report):
    """Check actual curves, arc lengths and sewing references before export."""
    paths={name:curve_for(pattern,name) for name in pattern.pattern['panels']}
    invalid=[]
    for name,path in paths.items():
        points=[]
        for segment in path:
            n=max(2,min(80,int(segment.length()/1.5)+2))
            points += [(segment.point(t).real,segment.point(t).imag) for t in np.linspace(0,1,n)[:-1]]
        if not valid_outline(points):
            invalid.append(name)
    if invalid:
        raise ValueError('裁片轮廓退化或自交：'+','.join(invalid))
    refs=Counter()
    max_error=0.
    for pair in pattern.pattern['stitches']:
        a,b=pair[:2]
        la=float(paths[a['panel']][a['edge']].length())
        lb=float(paths[b['panel']][b['edge']].length())
        max_error=max(max_error,abs(la-lb))
        refs.update((r['panel'],r['edge']) for r in pair[:2])
    if max_error>.02:
        raise ValueError(f'缝合边长不匹配（最大差{max_error:.3f}cm）')
    allowed={(r['panel'],r['edge']):r['layers'] for r in report.get('layered_seams',[])}
    duplicates={ref:n for ref,n in refs.items() if n>1}
    if any(allowed.get(ref)!=n for ref,n in duplicates.items()):
        raise ValueError('检测到未经声明的重复缝合边')
    # Front openings may have facings but must never join the two fronts.
    for opening in report.get('free_edges',[]):
        ref=(opening['panel'],opening['edge'])
        if refs.get(ref,0) and opening['reason']!='front opening; facing attached, fronts remain separate':
            raise ValueError('开口或开衩被错误缝合')
        if opening['reason']=='front opening; facing attached, fronts remain separate':
            for pair in pattern.pattern['stitches']:
                if any((r['panel'],r['edge'])==ref for r in pair[:2]):
                    other=next(r for r in pair[:2] if (r['panel'],r['edge'])!=ref)
                    if not other['panel'].endswith('neck_front_facing'):
                        raise ValueError('前襟开口只能接贴边，不能与另一前身缝合')
    return {'sampled_outline_valid':True,'checked_panels':len(paths),
            'max_seam_length_difference_cm':max_error,'declared_layered_seams':len(duplicates),
            'opening_checks_passed':True,'scope':'flat geometry; no physical sewing or fit guarantee'}
