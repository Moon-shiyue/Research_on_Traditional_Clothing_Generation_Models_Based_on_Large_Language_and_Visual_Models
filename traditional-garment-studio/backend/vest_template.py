"""Round-neck centre-opening sleeveless basic vest; no imaginary sleeves."""
import numpy as np
from .traditional_templates import piece,new_pattern,seam,edge_length,fold_mark,validate_template
from .mamian_v2 import rectangle
from .whole_templates import open_side_slits

VERSION='round-centre-bijia-2026-10-25-v1'


def build_bijia(body,design):
    d={k:float(node['v']) for k,node in design['bijia'].items()}
    length=d['length']*body['_leg_length'];w=body['bust']*d['chest_ease']/4
    n=min(body['neck_w']/2,w*.4);shoulder=min(body['shoulder_w']/2,w-2.)
    a=max(16.,min(27.,body['armscye_depth']+2.));depth=d['neck_depth_front']
    h=w+d['hem_expand'];slit=d['side_slit'];width=d['collar_width']
    if min(shoulder-n,length-a,length-depth)<3.:
        raise ValueError('比甲的肩宽、领口或衣长不相容，请检查人体尺寸、增加衣长或减小领深。')
    if slit and length-slit-a<3.:
        raise ValueError('比甲侧衩上端须低于袖窿至少3cm，请减小侧衩高度或增加衣长。')
    p=new_pattern('bijia');panels=p.pattern['panels'];marks=[];free=[];layered=[]
    panels['bijia_back']=piece([[-n,0],[-shoulder,0],[-w,-a],[-h,-length],
        [h,-length],[w,-a],[shoulder,0],[n,0]],{
        1:[[-shoulder*.9,-a*.55],[-w*.85,-a*.95]],
        5:[[w*.85,-a*.95],[shoulder*.9,-a*.55]],7:[[0,-4.]]})
    def bind(name,targets,finished_width):
        lengths=[edge_length(p,*ref) for ref in targets];total=sum(lengths)
        panels[name]=rectangle(total,2*finished_width,list(np.cumsum(lengths))[:-1])
        for index,ref in enumerate(targets):seam(p,(name,index),ref)
        marks.append(fold_mark(name,[0,-finished_width],[total,-finished_width]))
    neck=[]
    for side,sign in [('left',1),('right',-1)]:
        name='bijia_front_'+side
        panels[name]=piece([[sign*x,y] for x,y in [[n,0],[shoulder,0],[w,-a],
            [h,-length],[-2.,-length],[-2.,-depth],[0,-depth]]],{
            1:[[sign*shoulder*.72,-a*.55],[sign*w*.85,-a*.95]],6:[[sign*n*.9,-depth]]})
        seam(p,(name,0),('bijia_back',6 if sign>0 else 0))
        seam(p,(name,2),('bijia_back',4 if sign>0 else 2))
        bind('bijia_placket_'+side,[(name,4)],3.)
        bind('bijia_armhole_binding_'+side,[(name,1),('bijia_back',5 if sign>0 else 1)],1.5)
        neck.append((name,6))
        free.append({'panel':name,'edge':5,'reason':'free placket top; centre button overlap'})
    bind('bijia_neck_binding',[neck[0],('bijia_back',7),neck[1]],width)
    for index in range(2):
        name='bijia_tie_'+str(index+1);panels[name]=rectangle(30.,3.)
        marks.append(fold_mark(name,[0,-1.5],[30.,-1.5]))
    necks=[[{'panel':name,'edge':edge}] for name,edge in neck]
    if slit:marks.extend(open_side_slits(p,'bijia',length,slit,free,layered,necks))
    p.pattern.update(drafting_marks=marks,template_version=VERSION)
    report={'version':VERSION,'component':'bijia','variant':'round-centre-sleeveless-vest',
        'variant_label':'圆领对襟比甲基础净样','units':'cm','whole_garment':True,'sleeveless':True,
        'finished_length':length,'body_half_width':w,'neck_half_width':n,'front_neck_depth':depth,
        'armhole_depth':a,'shoulder_half_width':shoulder,'garment_bust':4*w,'hem_half_width':h,
        'side_slit_height':slit,'collar_finished_width':width,'front_opening':'center',
        'sleeve_length_from_body_edge':0.,'neckline_projection_edges':necks,
        'free_edges':free,'layered_seams':[],'simulation_supported':False,
        'notes':['圆领、前中对襟、无袖基础款：包含后身、两前身、门襟贴、领贴、两条配长袖窿包边及系带。',
            '袖窿按前后弧线实长配包边，不能改用有袖上衣后仅隐藏袖片。',
            '只覆盖本应用圆领对襟变化款；不替代立领、大襟、琵琶襟、前后不等长或文物原裁法。',
            f'侧衩垂直高{slit:g}cm，下段不缝；净样不含缝份，图像不提供绝对尺寸，做实物前需试样。'],
        'sources':[{'id':'TAIWAN-HISTORICA-19800010086',
            'url':'https://collections.culture.tw/th_collectionsweb/collection.aspx?GID=MNMEM6M7MD',
            'scope':'Source documents sleeveless vest family and several opening types; this is an application centre-front basic, not its measured pattern.'}],
        'cut_list':[{'panel':name,'quantity':1,'net_pattern':True,'allowance_cm':None,
                     'grain':'bias strip' if 'binding' in name else 'lengthwise grain'} for name in panels],
        'assembly_steps':['先核对领口、袖窿与胸围松量，裁试样；后身与两前身合肩。',
            '左右袖窿包边各按前后弧线配长，对折收净，保留完整无袖开口。',
            '左右侧缝缝至侧衩上端，下段不缝；侧衩和下摆分别折净边。',
            '前领弧线和后领弧线接连续领贴，前中竖边接独立门襟贴；两前身不相互缝死。',
            '系带或另配纽襻在试穿确认位置固定，再核加缝份与工艺。']}
    report['validation']=validate_template(p,report)
    return p,report
