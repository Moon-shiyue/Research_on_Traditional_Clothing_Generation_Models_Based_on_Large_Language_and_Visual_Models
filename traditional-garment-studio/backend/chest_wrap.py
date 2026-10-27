"""A bounded application basic: straight front cloth and four back ties."""
import copy
from .mamian_v2 import rectangle
from .traditional_templates import new_pattern,validate_template,fold_mark

COMPONENT='chest-wrap'
NAME='直幅系带抹胸'
VERSION='straight-tie-chest-wrap-2026-10-26-v1'


def extend_chest_catalog(engine):
    fields={'panel_height':(30.,[18.,42.],[24.,30.,36.]),
            'front_coverage':(.65,[.55,.85],[.6,.65,.75]),
            'tie_length':(45.,[30.,90.],[40.,50.,65.]),
            'tie_width':(3.,[2.,5.],[2.,3.,4.])}
    engine.schema['components'][COMPONENT]={'fields':{
        k:{'type':'float','bounds':bounds,'training_values':[v],'random_values':choices,'labels':{}}
        for k,(v,bounds,choices) in fields.items()},
        'contexts':copy.deepcopy(engine.schema['components']['cross-upper']['contexts'])}
    engine.template[COMPONENT]={k:{'v':v} for k,(v,_,_) in fields.items()}
    engine.names[COMPONENT]=NAME;engine.vocab['PHRASE'][COMPONENT]={}


def build_chest_wrap(body,design):
    d={k:float(v['v']) for k,v in design[COMPONENT].items()}
    width=float(body['bust'])*d['front_coverage'];height=d['panel_height']
    needed=(float(body['bust'])-width)/2+15.
    if d['tie_length']+1e-8<needed:
        raise ValueError(f'当前胸围与覆盖比例需要每条系带至少{needed:.1f}cm，以留出后背系结长度；请加长系带或增加覆盖比例。')
    p=new_pattern(COMPONENT);panels=p.pattern['panels']
    panels['chest_wrap_front']=rectangle(width,height)
    marks=[]
    for i in range(1,5):
        name='chest_wrap_tie_'+str(i)
        panels[name]=rectangle(d['tie_length'],d['tie_width'])
        marks.append(fold_mark(name,[0,-d['tie_width']/2],[d['tie_length'],-d['tie_width']/2]))
    p.pattern['drafting_marks']=marks;p.pattern['template_version']=VERSION
    anchors=[{'panel':'chest_wrap_front','x_cm':x,'y_cm':y,'tie_panel':'chest_wrap_tie_'+str(i+1)}
        for i,(x,y) in enumerate([(1.,-2.),(width-1.,-2.),(1.,-height+2.),(width-1.,-height+2.)])]
    marks.extend({'panel':a['panel'],'kind':'tie-attachment','point':[a['x_cm'],a['y_cm']],'number':i+1}
                 for i,a in enumerate(anchors))
    report={'version':VERSION,'component':COMPONENT,'variant':'straight-front-open-back-four-ties',
        'variant_label':NAME+'基础净样','whole_garment':True,'units':'cm','simulation_supported':False,
        'panel_width':width,'panel_height':height,'front_coverage':d['front_coverage'],
        'tie_length':d['tie_length'],'tie_unfolded_width':d['tie_width'],
        'attachment_points':anchors,'free_edges':[{'panel':name,'edge':i,'reason':'hemmed free boundary; ties hand attached at marked points'}
            for name in panels for i in range(4)],
        'notes':['一幅直上缘围前布与四条独立系带，向身体两侧围裹、后背系结；无肩带、胸省、胸杯或闭合后背。',
                 '围前布展开宽为人体胸围乘覆盖比例，净高独立设置；系带在标记处手缝固定，不把两侧缝成闭合衣筒。',
                 '本款是可选择的应用基础版型，30cm净高及覆盖比例不是照片测量或文物实测；背面被挡时必须明确选款。',
                 '净样无缝份；先以试布核对围裹覆盖、上下缘和系带位置，再加工艺余量。'],
        'sources':[],
        'cut_list':[{'panel':name,'quantity':1,'net_pattern':True,'allowance_cm':None,'grain':'lengthwise grain'} for name in panels],
        'assembly_steps':['按实际胸围、所需净高和围前覆盖比例核对尺寸。','围前布四边另加折净余量，分别收净。',
            '四条系带沿标记对折收净，成品宽为展开宽的一半。',
            '上、下两对系带分别手缝固定在围前左右侧的标记位置；在背后分别系结，上缘与下缘可独立调整。']}
    report['validation']=validate_template(p,report)
    return p,report


def chest_wrap_front(features):
    return (features.get('innerwear_front')=='straight-top'
        and features.get('upper_front','unclear')=='unclear'
        and features.get('sleeve_extent','unclear') in {'unclear','sleeveless'}
        and features.get('sleeve_shape','unclear')=='unclear'
        and features.get('neckwear_shape','unclear')=='unclear'
        and features.get('hem_shape','unclear')=='unclear'
        and features.get('flat_front') is None and features.get('side_pleats') is None
        and features.get('cloud_layers') is None
        and features.get('cloud_coverage','unclear')=='unclear')


def ambiguous_chest_wrap(row):
    f=row.get('features',{})
    return (row.get('component') is None and row.get('innerwear_candidates')==[COMPONENT]
        and not row.get('skirt_candidates') and chest_wrap_front(f)
        and f.get('innerwear_closure')=='unclear')
