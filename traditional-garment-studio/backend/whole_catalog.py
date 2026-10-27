"""Application-only complete garments. Frozen training vocabulary is unchanged."""
import copy

NAMES = {'cross-robe':'交领长袍', 'cross-upper':'交领上衣',
         'round-robe':'圆领长袍', 'round-upper':'圆领上衣',
         'stand-robe':'立领长衫', 'stand-upper':'立领上衣', 'bijia':'圆领对襟比甲',
         'duijin-upper':'直领对襟上衣'}
ALIASES = {'cross-robe':['交领袍','交领长衫','直裾袍'], 'cross-upper':['交领衫','交领襦','上襦'],
           'stand-robe':['立领袍','立领长袍','立领对襟长衫'],
           'stand-upper':['立领衫','立领短衫','立领对襟上衣','立领对襟衫'],
           'round-upper':['圆领衫','圆领对襟上衣'],
           'round-robe':['圆领袍','圆领长衫','圆领对襟长袍'],
           'bijia':['对襟比甲','无袖对襟长衣','无袖对襟上衣'],
           'pibo':['披帛','长条披帛'],
           'duijin-upper':['对襟长袖上衣','直领对襟上衣','对襟短衫','对襟上衣'],
           'chest-wrap':['直幅系带内搭','直幅系带抹胸']}
UPPERS = {'beizi','banbi','cross-upper','round-upper','stand-upper','bijia','duijin-upper','chest-wrap'}
OUTERS = {'beizi','banbi','bijia','duijin-upper'}
WHOLE = set(NAMES)
SLEEVED = WHOLE-{'bijia'}


def extend_catalog(engine):
    # Keep contexts descriptive metadata, not a claim of historical accuracy.
    contexts={'dynasty':list(engine.vocab['DYN_CN']), 'occasion':list(engine.vocab['OCC_CN'])}
    # This basic short-sleeved jacket can be paired with the application's
    # Ming skirt. The archived dataset conventions remain in model_schema.
    for component in ['banbi','ruqun-skirt']:
        if 'Ming' not in engine.schema['components'][component]['contexts']['dynasty']:
            engine.schema['components'][component]['contexts']['dynasty'].append('Ming')
    for component in NAMES:
        robe=component.endswith('robe')
        values={'length':(1.6 if robe else .62, [.9,2.2] if robe else [.4,.95]),
                'sleeve_length':(.95,[.4,1.5]), 'sleeve_cuff_width':(30.,[16.,100.]),
                'chest_ease':(1.18,[1.08,1.6]), 'hem_expand':(12. if robe else 4.,[0.,35.]),
                'neck_depth_front':(14. if component.startswith(('cross','duijin')) else 8.,[5.,24.]),
                'collar_width':(3.,[1.5,6.]), 'overlap':(12.,[6.,22.])}
        values['sleeve_type']=(0,[0,1])
        values['cuff_band_height']=(0.,[0.,8.])
        values['side_slit']=(0.,[0.,60.])
        if robe:values['belt']=(1,[0,1])
        if not component.startswith('cross'):
            values.pop('overlap')
            if component!='duijin-upper':values['opening_type']=(0,[0,1])
        if component=='bijia':
            values={'length':(1.2,[.5,2.]),'chest_ease':(1.18,[1.08,1.6]),
                    'hem_expand':(4.,[0.,30.]),'neck_depth_front':(8.,[4.,18.]),
                    'collar_width':(3.,[1.5,5.]),'side_slit':(15.,[0.,60.])}
        engine.schema['components'][component]={'fields':{key:{'type':'float','bounds':bounds,
            'training_values':[value], 'labels':{}} for key,(value,bounds) in values.items()},
            'contexts':copy.deepcopy(contexts)}
        engine.template[component]={key:{'v':value} for key,(value,_) in values.items()}
        variants={'length':([.8,1.2,1.5] if component=='bijia' else [1.2,1.5,1.8] if robe else [.5,.65,.8]),
            'chest_ease':[1.12,1.18,1.28],'hem_expand':[0.,4.,12.],
            'neck_depth_front':([10.,14.,18.] if component.startswith('cross') else [6.,8.,10.]),
            'collar_width':[2.,3.,4.],'side_slit':[0.,10.,20.],
            'sleeve_length':[.65,.95,1.15],'sleeve_cuff_width':[22.,30.,40.,60.],
            'sleeve_type':[0,1],'cuff_band_height':[0.,3.,5.],
            'opening_type':[0,1],'overlap':[8.,12.,16.],'belt':[0,1]}
        for key,choices in variants.items():
            if key in values:engine.schema['components'][component]['fields'][key]['random_values']=choices
        for key in ['sleeve_type','belt','opening_type']:
            if key in values:engine.schema['components'][component]['fields'][key]['type']='int'
        engine.vocab['PHRASE'][component]={}
    engine.names.update(NAMES)


def label(component):
    if component=='chest-wrap':return '直幅系带抹胸'
    if component=='pibo':return '直幅披帛'
    if component in NAMES:
        return NAMES[component]
    from training.common import generator_constants
    return generator_constants()['COMPONENT_CLASS'][component][1]
