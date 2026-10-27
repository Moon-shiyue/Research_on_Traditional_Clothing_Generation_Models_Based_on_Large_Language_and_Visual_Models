"""Visible categories select disclosed, editable drafting defaults, never measurements."""
from .text_scope import positive_occurrences
from .whole_catalog import WHOLE,SLEEVED


def visual_parameters(component, features):
    """Return supported field values and their provenance for one selected component."""
    result = {}

    def add(field, value, note, source='image_style_default'):
        result[field] = {'value': value, 'source': source, 'note': note}

    sleeve = features.get('sleeve_shape')
    if component in SLEEVED and component.endswith('robe') and features.get('waist_belt') in {'present','absent'}:
        belt=int(features['waist_belt']=='present')
        add('belt',belt,'按腰部清晰可见的独立腰带附上腰带净样。' if belt else '腰部完整可见且无独立腰带，不附加腰带净样。','image_observation')
    if component=='bijia' and features.get('length') in {'short','mid','full'}:
        ratio={'short':.6,'mid':.8,'full':1.25}[features['length']]
        add('length',ratio,f'按可见比甲衣长类别采用腿长{ratio:g}倍的基础衣长，可调整，并非照片测量。')
    if component in WHOLE:
        if features.get('side_slits')=='present':
            add('side_slit',15.,'可见左右侧衩，采用垂直高15cm的基础开口；具体高度可调整，并非照片测量。')
        elif features.get('side_slits')=='absent':
            add('side_slit',0.,'侧边下摆清晰且未见侧衩，采用闭合侧缝。','image_observation')
        extent={'short':.45,'elbow':.6,'wrist':.95,'extra-long':1.25}.get(features.get('sleeve_extent'))
        if extent:
            add('sleeve_length',extent,f'按可见袖长类别采用臂长{extent:g}倍的袖长默认值，含袖口条；可调整，非照片测量。')
    if component in SLEEVED and component.startswith(('round','stand')) and features.get('front_opening') in {'right','center'}:
        add('opening_type',int(features['front_opening']=='center'),'按可见前襟位置选择右侧斜襟或对襟衣身，使用不同前身裁片。','image_observation')
    if component in SLEEVED and features.get('cuff_finish')=='band':
        add('cuff_band_height',4.,'按可见独立袖口圈增加成品宽4cm的袖口条，已计入袖长；可调整，非照片测量。')
    elif component in SLEEVED and features.get('cuff_finish')=='plain':
        add('cuff_band_height',0.,'按可见直接收净的袖口，不附加独立袖口条。','image_observation')
    if component in SLEEVED and sleeve=='pipa':
        add('sleeve_type',1,'按可见收口膨袖采用整件连接琵琶袖基础款。','image_observation')
        add('sleeve_cuff_width',22.,'琵琶袖先采用袖口整围22cm，可调整，非照片测量。')
    if component in SLEEVED and sleeve in {'narrow','regular','wide'}:
        value={'narrow':24.,'regular':36.,'wide':76.}[sleeve]
        add('sleeve_cuff_width',value,f'按可见袖型采用袖口整围{value:g}cm的完整基础款，可调整，非照片测量。')
    if component in WHOLE and features.get('length')=='full' and component.endswith('robe'):
        add('length',1.6,'长袍先用腿长1.6倍的衣长默认值；不是照片测量。')
    if component in WHOLE and component.endswith('upper') and features.get('length')=='short':
        add('length',.5,'按短上衣采用腿长0.5倍的衣长默认值，可调整，非照片测量。')
    if component == 'beizi' and sleeve in {'narrow', 'regular','wide'}:
        value = {'narrow': 22., 'regular':32.,'wide': 60.}[sleeve]
        add('sleeve_cuff_width', value,
            f'按可见袖型采用袖口整围{value:g}cm的基础袖片；这是可调整的模板选值，并非照片测量。')
    if component == 'banbi' and sleeve in {'narrow', 'regular','wide'}:
        value = {'narrow': 14., 'regular':18.,'wide': 24.}[sleeve]
        add('sleeve_width', value,
            f'按可见袖型采用袖口平铺半围{value:g}cm的半臂基础袖片；这是模板选值，并非照片测量。')
    if component == 'cloud-shoulder':
        coverage=features.get('cloud_coverage')
        if coverage in {'neck','shoulders','chest'}:
            size={'neck':.22,'shoulders':.38,'chest':.38}[coverage]
            add('petal_length',size,'按可见云肩覆盖范围选择云头外伸默认值，可按厘米调整；不是照片测量。')
            add('front_extension',10. if coverage=='chest' else 0.,
                '按可见胸前覆盖采用前摆加长10cm的基础选值；可调整，非照片测量。' if coverage=='chest' else '本款不额外加长前摆，可在参数中调整。')
        layers = features.get('cloud_layers')
        if type(layers) is int and layers in (1, 2, 3):
            add('layers', layers, f'按图片中可分辨的独立云肩层片采用{layers}层；刺绣边框不计为层片。',
                'image_observation')
        if features.get('tassels') == 'absent':
            add('tassel_length', 0., '云肩下缘清晰且未见穗须，采用无垂须款。', 'image_observation')
        elif features.get('tassels') == 'present':
            add('tassel_length', 6., '图片可见穗须，先采用6cm成品穗须默认值；不是照片测量。')
    if component == 'mamian-skirt':
        if features.get('waist_level')=='waist':
            add('rise',1.,'按图片可见自然腰位置选择腰线；尺寸取当前人体腰围，不由照片测量。','image_observation')
        value = {'straight': 1.8, 'moderate': 2.4, 'wide': 3.}.get(features.get('hem_shape'))
        if value:
            add('pleat_ruffle', value,
                f'按可见裙摆外形采用褶量比{value:g}的基础模板；外形不等于实际布量，可调整。')
    if component == 'ruqun-skirt':
        position={'waist':.7,'high':.85,'chest':.95}.get(features.get('waist_level'))
        if position:
            add('waist_position',position,'按图片可见腰头高度选择穿着腰位；具体围度仍以人体尺寸及试样为准。','image_observation')
        value = {'straight': 1.8, 'moderate': 2.5, 'wide': 3.5}.get(features.get('hem_shape'))
        if value:
            add('hem_ratio', value,
                f'按可见裙摆外形采用展宽比{value:g}的六幅围裹下裙；外形不等于实际布量，可调整。')
    return result


def text_style_parameters(text, component):
    """Qualitative text only fills fields not explicitly supplied as numbers."""
    result = {}
    if component in {'beizi', 'banbi'}|WHOLE:
        if component in SLEEVED and component.startswith(('round','stand')):
            if any(positive_occurrences(text,t) for t in ['对襟','前中开襟','前中扣']):result['opening_type']=1
            elif any(positive_occurrences(text,t) for t in ['右斜襟','斜开襟','右侧开襟']):result['opening_type']=0
        if component in WHOLE and any(positive_occurrences(text,t) for t in ['琵琶袖','pipa-sleeve']):
            result.update(sleeve_type=1,sleeve_cuff_width=22.)
        if component in WHOLE:
            if any(t in text for t in ['无侧衩','无侧开衩','不开侧衩','不留侧衩']):result['side_slit']=0.
            extents={value for value,terms in [(.45,['短袖']),(.6,['中袖','七分袖']),(.95,['长袖']),
                                               (1.25,['超长袖'])] if any(positive_occurrences(text,t) for t in terms)}
            # 超长袖 contains 长袖; keep the more specific requested extent.
            if 1.25 in extents:extents.discard(.95)
            if len(extents)>1:raise ValueError('出现不同袖长类别，请明确短袖、中袖或长袖。')
            if extents:result['sleeve_length']=next(iter(extents))
        if component.endswith('robe'):
            if any(t in text for t in ['无腰带','不含腰带','不带腰带','不要腰带']):result['belt']=0
            elif any(positive_occurrences(text,t) for t in ['腰带','束带']):result['belt']=1
        wide = any(positive_occurrences(text, word) for word in ('宽袖', '宽口袖', '广袖'))
        narrow = any(positive_occurrences(text, word) for word in ('窄袖', '窄口袖'))
        if not wide and not narrow and any(word in text for word in ('宽袖','宽口袖','广袖','窄袖','窄口袖')):
            raise ValueError('你只提供了排除的袖型，请明确本次采用宽袖还是窄袖，避免默认值与排除条件冲突。')
        if wide and narrow:
            raise ValueError('宽袖和窄袖同时出现，请明确本次采用的袖型。')
        if wide or narrow:
            field = 'sleeve_width' if component=='banbi' else 'sleeve_cuff_width'
            result[field] = (76. if wide else 26.) if component in WHOLE else (60. if wide else 22.) if component == 'beizi' else (24. if wide else 14.)
    if component == 'cloud-shoulder':
        sizes={kind for kind,terms in [('neck',['小云肩','小型云肩']),('shoulders',['覆肩云肩']),
                                      ('chest',['大云肩','覆胸云肩'])] if any(positive_occurrences(text,t) for t in terms)}
        if len(sizes)>1:raise ValueError('出现不同云肩覆盖范围，请明确小云肩、覆肩或覆胸基础款。')
        if sizes:
            size=next(iter(sizes));result.update(petal_length=.22 if size=='neck' else .38,front_extension=10. if size=='chest' else 0.)
        matches = {number for words, number in [
            (('单层', '一层'), 1), (('双层', '两层', '二层'), 2), (('三层',), 3)]
            if any(positive_occurrences(text, word) for word in words)}
        if len(matches) > 1:
            raise ValueError('云肩出现不同层数，请明确本次采用的层数。')
        if matches:
            result['layers'] = matches.pop()
        if any(positive_occurrences(text, word) for word in ('无穗须', '无垂须', '没有穗须', '不带穗须', '不带流苏', '无流苏')):
            result['tassel_length'] = 0.
    return result


def unsupported_visual_variant(component, features):
    from .chest_wrap import chest_wrap_front
    if component=='chest-wrap' and features and not (chest_wrap_front(features) and features.get('innerwear_closure')=='tie-back'):
        return '仅看见胸前一片不能确认完整内搭；直幅后背系带基础款需要明确选款，不能代替吊带或闭背结构。'
    if component=='duijin-upper' and features.get('length')=='full':
        return '图片为长身衣物，不能缩成直领对襟短上衣；请确认长褙子或补充完整衣长与结构。'
    if component=='duijin-upper' and features and (features.get('upper_front')!='open' or features.get('neckwear_shape','unclear')!='unclear'):
        return '直领对襟长袖上衣需要明确开敞的两前襟；不能代替交领、闭合立领或右侧斜襟。'
    if component=='pibo' and features and features.get('neckwear_shape')!='long-drape':
        return '当前披帛仅支持明确长条幅形；宽幅披肩、扇形披领或霞帔不能用直幅披帛代替。'
    if component=='bijia' and features and (features.get('sleeve_extent')!='sleeveless' or features.get('front_opening')!='center'):
        return '当前比甲只支持明确圆领、前中对襟的无袖基础款，不能用它替代斜襟、立领或带袖衣物；请补充清楚的领襟与袖窿图。'
    if component in SLEEVED|{'beizi','banbi'} and features.get('sleeve_extent')=='sleeveless':
        return '图片是无袖衣物，当前没有对应完整模板，不能补成长袖或短袖衣身。'
    if component in WHOLE and features:
        front=features.get('upper_front')
        if component.startswith('cross') and front!='crossed':
            return '未确认交领搭襟，不能替换成整件交领基础款。请补充清楚的领襟图。'
        if component.startswith(('round','stand')) and front not in {'crossed','closed'}:
            return '未确认闭合领口及右侧开襟，不能用圆领/立领整件模板替代。'
        if component.startswith(('round','stand')) and features.get('front_opening') not in {'right','center'}:
            return '圆领/立领衣身的开襟被遮挡，暂不能区分右斜襟与前中对襟。请补充清楚的前襟图，不会用错误衣身代替。'
    if component in {'cloud-shoulder','round-collar'} and features.get('neckwear_shape')=='broad-cape':
        return '图片为宽幅披领或披肩，不能用带云头的云肩或窄圆领贴代替；当前尚无对应基础模板。'
    if component=='cloud-shoulder' and type(features.get('cloud_layers')) is int and features['cloud_layers']>3:
        return f'图片可见{features["cloud_layers"]}层独立云肩层片；当前基础模板只支持1–3层，不能自动减为两层。请另选支持的款式，或用文字明确制作1–3层变化款。'
    if component in {'beizi', 'banbi'}:
        if features.get('upper_front')=='unclear':
            return '图片前襟关系尚未看清，不能确认开敞对襟基础款。请补充无遮挡的正面照片；不能把遮挡部分自动补成对襟。'
        if features.get('upper_front') in {'crossed', 'closed'}:
            return '图片上衣不是当前支持的直领对襟开敞基础款，不能用对襟裁片替代。请明确要制作的领型局部或另选对襟款。'
        if features.get('sleeve_shape') == 'pipa':
            return '图片上衣带收口琵琶袖；当前整件对襟上衣只支持直线收放的宽袖或窄袖。可单独制作琵琶袖，暂不能按此图生成整件上衣。'
    return ''
