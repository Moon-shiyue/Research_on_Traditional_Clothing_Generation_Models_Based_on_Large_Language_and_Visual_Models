"""Complete unlined basic garments with explicit sewing graphs, cm units.

Modern parametric templates, not measured archaeological reproductions.
Crossed fronts close wearer-left over wearer-right. Round/standing variants
use a right diagonal opening and full underlap, not a centre-open beizi.
"""
import numpy as np

from .traditional_templates import (piece, new_pattern, seam, edge_length,
                                   fold_mark, validate_template)
from .mamian_v2 import rectangle
from .whole_catalog import NAMES

VERSION='whole-garments-2026-10-25-v4'


def open_side_slits(pattern, component, length, height, free, layered, necks):
    """Split real side seams; lower segments stay unsewn on every layer."""
    panels=pattern.pattern['panels'];prefix=component+'_'
    targets={prefix+'back':{2,4},prefix+'front_left':{2},prefix+'front_right':{2}}
    if not component.startswith('cross') and len(panels[prefix+'front_left']['edges'])==8:
        targets[prefix+'front_left'].add(4)  # full outer lap has both side seams
    mapping={};marks=[]
    for name,indices in targets.items():
        panel=panels[name];edges=[]
        for old,edge in enumerate(panel['edges']):
            index=len(edges)
            if old not in indices:
                edges.append(edge);mapping[(name,old)]=index;continue
            start,end=(panel['vertices'][i] for i in edge['endpoints'])
            top=-length+height
            t=(top-start[1])/(end[1]-start[1])
            if not 0<t<1:raise ValueError('侧衩须止于袖窿以下，请减小侧衩高度。')
            point=[start[0]+t*(end[0]-start[0]),top]
            vertex=len(panel['vertices']);panel['vertices'].append(point)
            a,b=edge['endpoints']
            edges.extend([{'endpoints':[a,vertex]},{'endpoints':[vertex,b]}])
            sewn=index if start[1]>end[1] else index+1
            loose=index+1 if sewn==index else index
            mapping[(name,old)]=sewn
            free.append({'panel':name,'edge':loose,'reason':'unsewn side slit'})
            bottom=start if start[1]<end[1] else end
            marks.append({'panel':name,'kind':'side-slit','start':point,'end':bottom,'height_cm':height})
        panel['edges']=edges
    for pair in pattern.pattern['stitches']:
        for ref in pair[:2]:ref['edge']=mapping.get((ref['panel'],ref['edge']),ref['edge'])
    # Existing free openings and multi-layer seams use original indices;
    # the newly added slit entries already use the split indices.
    for ref in [row for row in free if row['reason']!='unsewn side slit']+layered:
        ref['edge']=mapping.get((ref['panel'],ref['edge']),ref['edge'])
    for group in necks:
        for ref in group:ref['edge']=mapping.get((ref['panel'],ref['edge']),ref['edge'])
    return marks


def build_whole(body, design, component):
    d={key:float(node['v']) for key,node in design[component].items()}
    length=d['length']*body['_leg_length']
    w=max(body['bust']*d['chest_ease']/4,body['hips']/4+1. if component.endswith('robe') else 0.)
    n=min(body['neck_w']/2,w*.45)
    a=max(16.,min(25.,body['armscye_depth']))
    dropped=max(0.,w-body['shoulder_w']/2)
    band=d['cuff_band_height']
    sl=d['sleeve_length']*body['arm_length']-dropped-band
    cuff=d['sleeve_cuff_width']/2
    opened=component=='duijin-upper'
    h=w+d['hem_expand'];depth=d['neck_depth_front'];over=0. if opened else d.get('overlap',12.)
    if min(length-a,length-depth,sl,w-n) <= 2. or over>=w:
        raise ValueError('整件版型的衣长、袖长、领深或搭襟不相容，请增加长度或减小领深/搭襟。')
    slit=d['side_slit']
    if slit and length-slit-a<3.:
        raise ValueError('侧衩上端须低于袖窿至少3cm，请减小侧衩高度或增加衣长。')
    pattern=new_pattern(component); panels=pattern.pattern['panels'];prefix=component+'_'
    back=prefix+'back'
    panels[back]=piece([[-n,0],[-w,0],[-w,-a],[-h,-length],[h,-length],
                       [w,-a],[w,0],[n,0]],{7:[[0,-4.]]})
    marks=[];free=[];layered=[]
    neck_targets=[]
    def binding(name, targets, width, fold=True):
        lengths=[edge_length(pattern,*ref) for ref in targets]
        total=sum(lengths)
        panels[name]=rectangle(total,2*width,list(np.cumsum(lengths))[:-1])
        for index,ref in enumerate(targets):
            seam(pattern,(name,index),ref)
        if fold:
            marks.append(fold_mark(name,[0,-width],[total,-width]))
        return total
    if opened:
        root_front={};fronts=[]
        for side,sign in [('left',1),('right',-1)]:
            front=prefix+'front_'+side
            panels[front]=piece([[sign*x,y] for x,y in [
                [n,0],[w,0],[w,-a],[h,-length],[0,-length],[0,-depth]]],
                {5:[[sign*n*.3,-depth*.4]]})
            seam(pattern,(front,0),(back,6 if sign>0 else 0))
            seam(pattern,(front,2),(back,4 if sign>0 else 2))
            root_front[sign]=(front,1);fronts.append([(front,4),(front,5)])
            free.append({'panel':front,'edge':4,'reason':'front opening; facing attached, fronts remain separate'})
        binding(prefix+'neck_front_facing',fronts[0]+[(back,7)]+list(reversed(fronts[1])),d['collar_width'])
        variant='straight-collar-open-short-upper'
        facing_note='直领对襟长袖上衣：两前身从前领至下摆保持开敞，连续领襟按前中边及前后领弧实长配长；不是短袖半臂，也不是闭合立领或右斜襟衣身。'
    elif component.startswith('cross'):
        for side,sign in [('left',1),('right',-1)]:
            front=prefix+'front_'+side
            panels[front]=piece([[sign*x,y] for x,y in [
                [n,0],[w,0],[w,-a],[h,-length],[-over,-length],[-over,-depth]]])
            seam(pattern,(front,0),(back,6 if sign>0 else 0))
            seam(pattern,(front,2),(back,4 if sign>0 else 2))
            neck_targets.append((front,5))
            free.append({'panel':front,'edge':4,'reason':'free wrap front; closes with ties, never sewn to opposite front'})
        # One continuous cross-collar binding, broken exactly at shoulders.
        binding(prefix+'neck_binding',[neck_targets[0],(back,7),neck_targets[1]],d['collar_width'])
        root_front={1:(prefix+'front_left',1),-1:(prefix+'front_right',1)}
        variant='crossed-right-wrap';facing_note='左前襟（穿着者左侧）盖右襟，以两组内外系带固定；领贴按前领斜线与后领弧线实长配长。'
    elif d.get('opening_type')==1:
        # Buttoned centre fronts are a distinct whole body, not a right-lap
        # front with its labels changed. Each body extends 2cm past centre.
        fronts=[];root_front={}
        for side,sign in [('left',1),('right',-1)]:
            front=prefix+'front_'+side
            panels[front]=piece([[sign*x,y] for x,y in [
                [n,0],[w,0],[w,-a],[h,-length],[-2.,-length],[-2.,-depth],[0,-depth]]],
                {6:[[sign*n*.9,-depth]]})
            seam(pattern,(front,0),(back,6 if sign>0 else 0))
            seam(pattern,(front,2),(back,4 if sign>0 else 2))
            root_front[sign]=(front,1);fronts.append((front,6))
            binding(prefix+'placket_'+side,[(front,4)],3.)
            free.append({'panel':front,'edge':5,'reason':'free placket top; centre button overlap'})
        standing=component.startswith('stand')
        binding(prefix+'neck_binding',[fronts[0],(back,7),fronts[1]],
                d['collar_width']/(2 if standing else 1),not standing)
        variant='standing-centre-front' if standing else 'round-centre-front'
        facing_note='对襟闭合基础款：左右前身各有2cm搭门、独立门襟贴，领口连续；前襟另配纽襻，不相互缝死。'
    else:
        main=prefix+'front_left';under=prefix+'front_right'
        # A full front, cut open diagonally to the wearer-right neck point.
        # The underlap provides the right shoulder/armhole and continues to hem.
        # Mirror the drafted lap to viewer-left = wearer-right. Mirror the
        # absolute control points before serializing, not just the SVG preview.
        panels[main]=piece([[n,0],[w,0],[w,-a],[h,-length],[-h,-length],
                           [-w,-a],[-n,0],[0,-depth]],
                          {6:[[-n*.9,-depth]],7:[[n*.9,-depth]]})
        panels[under]=piece([[-n,0],[-w,0],[-w,-a],[-h,-length],[0,-length],[0,-depth]],
                           {5:[[-n*.9,-depth]]})
        seam(pattern,(main,0),(back,6));seam(pattern,(under,0),(back,0))
        seam(pattern,(main,2),(back,4))
        seam(pattern,(main,4),(back,2));seam(pattern,(under,2),(back,2))
        layered=[{'panel':back,'edge':2,'layers':2}]
        standing=component.startswith('stand')
        binding(prefix+'neck_binding',[(main,6),(main,7),(back,7)],d['collar_width']/(2 if standing else 1),not standing)
        binding(prefix+'under_neck_binding',[(under,5)],d['collar_width']/(2 if standing else 1),not standing)
        binding(prefix+'opening_facing',[(main,5)],3.)
        free=[{'panel':under,'edge':4,'reason':'free inner underlap opening'}]
        root_front={1:(main,1),-1:(under,1)}
        variant='round-right-diagonal' if component.startswith('round') else 'standing-right-diagonal'
        facing_note=('圆领右侧斜开襟，整片外前身覆盖内搭襟；右侧缝夹住两层前身，斜开襟用系结或另配纽襻，不能缝死。'
                     if component.startswith('round') else
                     '立领右侧斜开襟，领片不对折为平领：沿标记折净边后立起；领端及斜开襟另配系结或纽襻。')
    for side,sign in [('left',1),('right',-1)]:
        sleeve=prefix+'sleeve_'+side
        curves={}
        if d['sleeve_type']==1:
            if cuff>=a:
                raise ValueError(f'琵琶袖的袖口整围须小于袖根整围{2*a:.1f}cm，请减小袖口。')
            bulge=max(28.,a*1.65)
            curves={2:[[sl*.2,-a-bulge],[sl*.72,-a-bulge]],
                    4:[[sl*.72,-a+bulge],[sl*.2,-a+bulge]]}
        panels[sleeve]=piece([[0,0],[0,-a],[0,-2*a],[sl,-a-cuff],[sl,-a+cuff]],curves)
        seam(pattern,(sleeve,0),root_front[sign])
        seam(pattern,(sleeve,1),(back,5 if sign>0 else 1))
        seam(pattern,(sleeve,2),(sleeve,4))
        marks.append(fold_mark(sleeve,[0,-a],[sl,-a]))
        if band:
            cuff_name=prefix+'cuff_'+side
            panels[cuff_name]=rectangle(2*cuff,2*band)
            seam(pattern,(cuff_name,0),(sleeve,3))
            seam(pattern,(cuff_name,1),(cuff_name,3))
            marks.append(fold_mark(cuff_name,[0,-band],[2*cuff,-band]))
    tie_count=4 if component.startswith('cross') else 2
    for index in range(tie_count):
        name=prefix+'tie_'+str(index+1)
        panels[name]=rectangle(35.,3.)
        marks.append(fold_mark(name,[0,-1.5],[35,-1.5]))
    if d.get('belt')==1:
        name=prefix+'belt';belt_length=float(body['waist'])*1.8+40.
        panels[name]=rectangle(belt_length,8.)
        marks.append(fold_mark(name,[0,-4.],[belt_length,-4.]))
    necks=([[{'panel':prefix+'front_'+side,'edge':i} for i in [4,5]] for side in ['right','left']] if opened else
           [[{'panel':prefix+'front_'+side,'edge':5 if component.startswith('cross') else 6}]
            for side in ['right','left']] if component.startswith('cross') or d.get('opening_type')==1 else
           [[{'panel':prefix+'front_left','edge':i} for i in [6,7]]])
    if slit:marks.extend(open_side_slits(pattern,component,length,slit,free,layered,necks))
    pattern.pattern['drafting_marks']=marks
    version='open-upper-2026-10-26-v1' if opened else VERSION
    pattern.pattern['template_version']=version
    report={'version':version,'component':component,'variant':variant,'open_front':opened,
            'variant_label':NAMES[component]+'基础净样','units':'cm','whole_garment':True,
            'finished_length':length,'body_half_width':w,'neck_half_width':n,
            'front_neck_depth':depth,'armhole_depth':a,'garment_bust':4*w,
            'side_slit_height':slit,'neckline_projection_edges':necks,
            'sleeve_length_from_shoulder':sl+dropped+band,'dropped_shoulder_length':dropped,
            'sleeve_length_from_body_edge':sl+band,'sleeve_body_length':sl,
            'cuff_band_finished_height':band,'sleeve_opening_circumference':2*cuff,
            'hem_half_width':h,'collar_finished_width':d['collar_width'],
            'sleeve_type':'pipa' if d['sleeve_type']==1 else 'straight',
            'front_opening':'open' if opened else 'crossed' if component.startswith('cross') else 'center' if d['opening_type']==1 else 'right',
            'belt_length':belt_length if d.get('belt')==1 else None,
            'free_edges':free,'layered_seams':layered,'simulation_supported':False,
            'notes':[facing_note,'包含前后衣身、左右袖、领襟和系带，非独立领片或袖片。',
                     '现代参数化无里基础款；不复原曲裾、内外摆、贴里腰褶、马蹄袖或文物原裁法。',
                     '袖长从人体肩点计，含落肩；净样无缝份，照片不提供绝对尺寸，实物前需试样。'],
            'sources':[{'id':'CSM-CROSS-1833','url':'https://www.chinasilkmuseum.com/zggd/info_21.aspx?itemid=1833'},
                       {'id':'DPM-ROUND-230670','url':'https://www.dpm.org.cn/collection/embroider/230670.html'}],
            'cut_list':[{'panel':name,'quantity':1,'net_pattern':True,'allowance_cm':None,
                         'grain':'bias strip' if 'binding' in name or 'facing' in name else 'lengthwise grain'}
                        for name in panels],
            'assembly_steps':['核对衣长、袖长、胸围松量及开襟方向；先裁试样。',
                              '合肩缝，袖根两半分别对接前后袖窿，合袖底。',
                              '合侧缝；右斜襟基础款的右侧缝夹住内外两层前身。' if not opened and not component.startswith('cross') and d['opening_type']==0 else '合左右侧缝，两前襟保持独立。',
                              facing_note,'系带在领襟闭合点及内搭襟手缝固定，试穿后再加缝份、折边与纽襻。']}
    if opened:
        report['sources']=[{'url':'https://www.chinasilkmuseum.com/ngcxg/info_11.aspx?itemid=31128',
            'scope':'Open-front garment family reference. This short long-sleeve version is an application basic, not a measured museum reconstruction.'}]
    if band:
        report['notes'].append(f'两只袖口各含成品宽{band:g}cm的对折袖口条；袖长已包含袖口条，不额外加长。')
        report['assembly_steps'].insert(3,'袖口条短边合缝成圈，对折后按等长边接入袖口；试样后收净内侧。')
    if slit:
        report['notes'].append(f'左右侧衩垂直高{slit:g}cm；净样标记下段为开口，不纳入侧缝缝合。')
        report['assembly_steps'].insert(3,f'侧缝只缝到侧衩上端标记，距下摆垂直{slit:g}cm的下段保留开口；各层分别折净边。')
    if d.get('belt')==1:
        report['notes'].append(f'附独立腰带净样，展开长{belt_length:.1f}cm、对折后宽4cm；可在参数面板关闭腰带。')
    if component.startswith('stand'):
        report['sources']=[{'id':'CSM-STAND-2033','url':'https://www.chinasilkmuseum.com/zggd/info_21.aspx?itemid=2033'},
                           {'id':'CSM-STAND-2117','url':'https://www.chinasilkmuseum.com/zggd/info_21.aspx?itemid=2117'}]
        report['notes'].append('立领参考领型与开襟类别，尺寸及直条领为应用基础选值；使用直丝及适当领衬试样，不是文物原裁法。')
        for row in report['cut_list']:
            if row['panel'].endswith('neck_binding'):row['grain']='lengthwise grain; standing collar, test interfacing'
    report['validation']=validate_template(pattern,report)
    return pattern,report
