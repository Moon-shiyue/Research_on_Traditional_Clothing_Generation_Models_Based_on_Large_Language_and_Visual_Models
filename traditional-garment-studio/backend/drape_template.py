"""Application-only straight pibo. A hemmed strip, not a cape or xiapei."""
import copy
from .mamian_v2 import rectangle
from .traditional_templates import new_pattern,validate_template

COMPONENT='pibo'
NAME='直幅披帛'
VERSION='straight-pibo-2026-10-26-v3'


def extend_drape_catalog(engine):
    fields={'strip_length':(300.,[150.,500.],[200.,300.,400.]),
            'strip_width':(30.,[10.,70.],[20.,30.,45.])}
    engine.schema['components'][COMPONENT]={'fields':{
        key:{'type':'float','bounds':bounds,'training_values':[value],'random_values':variants,'labels':{}}
        for key,(value,bounds,variants) in fields.items()},
        'contexts':copy.deepcopy(engine.schema['components']['cross-upper']['contexts'])}
    engine.template[COMPONENT]={key:{'v':value} for key,(value,_,_) in fields.items()}
    engine.names[COMPONENT]=NAME
    engine.vocab['PHRASE'][COMPONENT]={}


def build_pibo(body,design):
    length=float(design[COMPONENT]['strip_length']['v']);width=float(design[COMPONENT]['strip_width']['v'])
    if length<2.5*width:
        raise ValueError('直幅披帛须为长条，请增加长度或减小幅宽；宽幅披肩不能套用此款。')
    pattern=new_pattern(COMPONENT)
    pattern.pattern['panels']['pibo_strip']=rectangle(length,width)
    pattern.pattern['template_version']=VERSION
    report={'version':VERSION,'component':COMPONENT,'variant':'straight-long-strip',
        'variant_label':'直幅披帛基础净样','units':'cm','strip_length':length,'strip_width':width,
        'whole_garment':False,'accessory':True,'simulation_supported':False,
        'free_edges':[{'panel':'pibo_strip','edge':i,'reason':'separately hemmed free edge'} for i in range(4)],
        'notes':['一整幅长条披帛，四边分别收净，不与上衣或下裙缝在一起。',
            f'净长{length:g}cm、净幅宽{width:g}cm；四边另按工艺添加折边余量，净样未含缝份。',
            '300×30cm仅为可调整应用默认值，不是照片测量或文物实测。',
            '左图为肩后连接、前方长向松折的二维披搭示意，显示幅宽约为净幅宽的一半；不模拟布料下垂，右图仍是一整幅真实平铺净样。',
            '本款不替代扇形披肩、披领、霞帔、圆弧/拼接披帛及多幅相缝结构。'],
        'sources':[{'url':'https://www.dpm.org.cn/lemmas/239590.html','scope':'Defines pibo as a long textile wrapped around the body; not a measured cutting pattern.'},
                   {'url':'https://www.hcsartmuseum.com/exhibition/39140/','scope':'Describes shoulder/arm draping and long forms over two metres; application sizes remain editable defaults.'}],
        'cut_list':[{'panel':'pibo_strip','quantity':1,'net_pattern':True,'allowance_cm':None,'grain':'lengthwise grain'}],
        'assembly_steps':['核对所需净长和幅宽，先用试布检查披搭位置。',
                          '四边按面料选择卷边或折边工艺，另加相应余量；不可把净样尺寸误当含余量裁剪线。',
                          '沿长向裁一整幅，四边收净；肩臂间的披搭为穿用方式，不是衣物间缝合。']}
    report['validation']=validate_template(pattern,report)
    return pattern,report
