"""Supported separates share one body; each garment keeps its own sewing graph."""
import copy
import itertools
import json
import re
from xml.etree import ElementTree as ET

from svgpathtools import parse_path

from .body_layout import tag
from .body_text import body_measurements
from .patterns import body_from, generate_pattern
from .text_scope import WHOLE, NEGATION, positive_occurrences, component_references, unsupported_full_request_issue,garment_quantity_issue
from .style_features import unsupported_visual_variant
from .whole_catalog import WHOLE as WHOLE_COMPONENTS, NAMES as WHOLE_NAMES, UPPERS, ALIASES,OUTERS


PAIRS = [('beizi', 'mamian-skirt'), ('banbi', 'ruqun-skirt')]+[
    (upper,lower) for upper in sorted(UPPERS) for lower in ['mamian-skirt','ruqun-skirt']
    if (upper,lower) not in [('beizi','mamian-skirt'),('banbi','ruqun-skirt')]]
LABELS = {'beizi': '褙子', 'mamian-skirt': '马面裙', 'banbi': '半臂', 'ruqun-skirt': '襦裙下裳',**WHOLE_NAMES}
LABELS['cloud-shoulder']='云肩'
LABELS['pibo']='直幅披帛'
LABELS['chest-wrap']='直幅系带抹胸'
GROUPS=PAIRS+[pair+('cloud-shoulder',) for pair in PAIRS]+[
    (robe,'cloud-shoulder') for robe in sorted(WHOLE_COMPONENTS) if robe.endswith('robe')]
LAYERED=[(inner,outer,lower) for inner in ['cross-upper','round-upper','stand-upper','chest-wrap']
         for outer in sorted(OUTERS) for lower in ['mamian-skirt','ruqun-skirt']]
GROUPS+=LAYERED+[group+('cloud-shoulder',) for group in LAYERED]
BASE_GROUPS=tuple(GROUPS)
GROUPS += [group+('pibo',) for group in BASE_GROUPS]+[
    (c,'pibo') for c in sorted(UPPERS|{c for c in WHOLE_COMPONENTS if c.endswith('robe')})]
VERSION = 'traditional-ensembles-v2'
MEMBER_ORDER={'upper':0,'outer':1,'lower':2,'accessory':3,'drape':4}


def member_id(component, components=()):
    if component=='pibo':return 'drape'
    if component in OUTERS and any(c!=component and (c=='chest-wrap' or c in WHOLE_COMPONENTS and c.endswith('upper')) for c in components):
        return 'outer'
    return 'accessory' if component=='cloud-shoulder' else 'lower' if component.endswith('skirt') else 'upper'


def ordered_members(components):
    return sorted(components,key=lambda c:MEMBER_ORDER[member_id(c,components)])


def component_terms(engine,component):
    return sorted([engine.names[component],component]+ALIASES.get(component,[]),key=len,reverse=True)


def unknown_openings(observations):
    return [o['component'] for o in observations if o.get('component') in WHOLE_COMPONENTS
            and o['component'].startswith(('round','stand'))
            and o.get('features',{}).get('upper_front','unclear')!='open'
            and (o.get('features',{}).get('front_opening') not in {'right','center'}
                 or o.get('features',{}).get('upper_front')=='unclear')]


def opening_question(engine,observations,canonical,components):
    unknown=unknown_openings(observations)
    if not unknown:return None
    name='＋'.join(LABELS[c] for c in components)
    answer={'status':'needs_input','pattern':None,'suggested_name':name,'suggested_text':canonical,
            'opening_choice_component':unknown[0],
            'opening_choice_name':engine.names[unknown[0]],
            'opening_choices':[{'id':'center','label':'对襟闭合'},{'id':'right','label':'右侧斜开襟'}],
            'reply':'\n'.join(o.get('reason','') for o in observations)
                +'\n请确认'+engine.names[unknown[0]]+'的开襟：衣身可见，但前襟被遮挡。请选择一种基础版型；所有待选项目确认后生成整套，该细节会标为你的选择，不会按图片推断。'}
    if len(components)>1:
        answer.update(suggested_outfit=True,outfit_observations=observations)
    else:
        answer.update(suggested_component=components[0],visible_features=observations[0].get('features',{}))
    return answer


def pending_visual_issue(component, visual):
    """A hidden opening may be chosen, but other observed conflicts still block."""
    features=copy.deepcopy(visual.get('features',{}))
    if component in unknown_openings([visual]):
        features.update(upper_front='closed',front_opening='center')
    return unsupported_visual_variant(component,features)


def garment_choice_question(engine,text,observations,details):
    """Offer one bounded choice at a time, only if every member can be retained."""
    from .scene_inventory import ambiguous_skirt
    from .chest_wrap import ambiguous_chest_wrap
    unknown=[o for o in observations if not o.get('component')]
    if not unknown or len(observations)<2:return None
    known={o['component']:o for o in observations if o.get('component')}
    if len(known)!=len(observations)-len(unknown):return None
    if any(pending_visual_issue(c,o) for c,o in known.items()):return None
    slots=[]
    for row in unknown:
        if ambiguous_chest_wrap(row):slots.append(('innerwear',row,['chest-wrap']))
        elif ambiguous_skirt(row):slots.append(('skirt',row,['mamian-skirt','ruqun-skirt']))
        else:return None
    # Multiple unidentified clothes of the same role cannot be silently merged.
    if len({kind for kind,_,_ in slots})!=len(slots):return None
    named=set(engine.find_components(text));_,excluded=engine.references(text)
    available=set(known)|{c for _,_,choices in slots for c in choices}
    if not named<=available or set(excluded)&set(known):return None
    options=[]
    for _,_,choices in slots:
        selected=named&set(choices)
        options.append([c for c in choices if c not in excluded and (not selected or selected=={c})])
    supported={frozenset(g) for g in GROUPS}
    completions=[choice for choice in itertools.product(*options)
        if len(set(known)|set(choice))==len(observations)
        and frozenset(set(known)|set(choice)) in supported]
    if not completions:return None
    index=next((i for i,s in enumerate(slots) if s[0]=='innerwear'),0)
    kind,row,_=slots[index]
    candidates=list(dict.fromkeys(choice[index] for choice in completions))
    canonical=text.strip()
    for c in ordered_members(known):
        if c not in named:canonical+=('；' if canonical else '')+engine.names[c]
    if len(canonical)>4000:return engine.clarify('描述过长，请精简尺寸后重新识别。')
    reply=(details+'\n只看见直上缘胸前内搭，背面与肩带未确认。可明确选择本应用直幅后背系带基础款；此款会标为你的选款，不会声称图片已确认其背面。若实际为吊带或闭背款，请补图，不要选此基础款。'
        if kind=='innerwear' else details+'\n下裙已列入整套，但裙门或侧褶被遮挡，无法从本图区分款式。请选择本次采用的下裙基础款；会标为你的选择，不会只生成上衣。')
    remaining=len(unknown)-1+len(unknown_openings(observations))
    if remaining:reply+='\n本步选择后还需确认其它被遮挡的衣物或开襟；所有项目确认完毕后才生成整套。'
    return {'status':'needs_input','pattern':None,'suggested_outfit':True,
        'suggested_name':'完整服饰＋待选'+('内搭' if kind=='innerwear' else '下裙'),
        'suggested_text':canonical,'outfit_observations':observations,
        kind+'_choice_index':row['garment_index'],
        kind+'_choices':[{'id':c,'label':'采用直幅后背系带内搭基础款' if kind=='innerwear' else '制作'+LABELS[c]+'基础款'} for c in candidates],
        'reply':reply}


def common_contexts(engine, components):
    return {field: [v for v in engine.schema['components'][components[0]]['contexts'][field]
                   if all(v in engine.schema['components'][c]['contexts'][field] for c in components)]
            for field in ['dynasty', 'occasion']}


def interpret_outfit(engine, text, body_values, confirmed_visuals=None):
    """Return None for the existing single-component route, otherwise an intent."""
    quantity_issue=garment_quantity_issue(text,engine)
    if quantity_issue:return engine.clarify(quantity_issue)
    named, _ = engine.references(text)
    # Upper-garment sleeve qualifiers are supported, but an explicitly separate
    # third piece must not disappear when the single-item scope filters run.
    if any(set(pair) <= set(named) for pair in GROUPS):
        for component in named:
            if component.endswith(('sleeve', 'collar')) and any(re.search(
                    r'(?:另做|再做|单独|另外|额外|增加)[^，。；\n]{0,12}$', text[max(0, m.start()-18):m.start()])
                    for term in [engine.names[component], component] for m in positive_occurrences(text, term)):
                return engine.clarify('本次组合只包含上装和下裙；另做的领片或袖片请单独提交，不会自动忽略第三件。')
    components = engine.find_components(text)
    if len(components) < 2:
        return None
    scope_issue=unsupported_full_request_issue(text)
    if scope_issue:return engine.clarify(scope_issue)
    pair = next((p for p in GROUPS if set(p) == set(components)), None)
    if pair is None:
        return engine.clarify('当前整套支持完整上衣＋马面裙/襦裙，可外搭褙子或半臂、另配云肩；长袍也可配云肩。其他复杂叠穿请补充款式，不能用领片或袖片代替衣身。')
    if not set(pair)&WHOLE_COMPONENTS and any('套' not in m.group() and not NEGATION.search(text[max(0,m.start()-8):m.start()])
           for m in WHOLE.finditer(text)):
        return engine.clarify('这次还提到了尚未支持的整件衣物，请明确只制作褙子＋马面裙，或半臂＋襦裙下裳。')
    if any(positive_occurrences(text, term) for term in ['连体', '连衣', '缝在一起', '连接成', '一体式']):
        return engine.clarify('目前支持上装和裙装分别穿着的组合，暂不支持连体衣或把上下装缝成一件。')
    try:
        supplied_body = body_measurements(text)
        body_values = dict(body_values or {}, **supplied_body)
        body_from(body_values)
        contexts = common_contexts(engine, pair)
        if any(not values for values in contexts.values()):
            return engine.clarify('这组基础衣物暂没有共同的朝代/场合选项，请调整组合；不会忽略其中一件。')
        chosen = {}
        for field, mapping in [('dynasty', engine.vocab['DYN_CN']), ('occasion', engine.vocab['OCC_CN'])]:
            values = {k for k, label in mapping.items() if positive_occurrences(text, label)}
            if not values and any(label in text for label in mapping.values()):
                raise ValueError('你只提供了排除的朝代或场合，请明确本次采用的一个值。')
            if len(values) > 1:
                raise ValueError('一套设计当前使用统一的朝代与场合，请保留各一个值。')
            value = next(iter(values)) if values else contexts[field][0]
            if value not in contexts[field]:
                raise ValueError('所选朝代或场合不在这组基础款的共同支持范围内，请在参数面板选择兼容值。')
            chosen[field] = value
        # Scope measurements to the named item. The leading clause is shared
        # (e.g. body measurements); instructions after a name belong to it.
        occurrences = []
        for c in pair:
            matches = engine.positive_component_matches(text,c)
            occurrences.append((min(m.start() for m in matches), c))
        occurrences.sort()
        leading = text[:occurrences[0][0]]
        garments = []
        for index, (start, c) in enumerate(occurrences):
            end = occurrences[index+1][0] if index+1 < len(occurrences) else len(text)
            chunk = leading + text[start:end]
            # Physical role labels remain unambiguous in a shared closing clause.
            labels=(['裙长','裙摆','褶量','马面宽','腰位','pleat_ruffle','mamian_width','hem_ratio','rise','waist_position']
                    if c.endswith('skirt') else ['衣长','袖长','半袖长','袖口','开衩','窄袖','宽袖','广袖','琵琶袖',
                        'sleeve_length','sleeve_width','sleeve_cuff_width','slit_height'])
            # With two upper garments, measurements/styles belong to the
            # named item's clause. Copying every sleeve measurement globally
            # would overwrite the inner sleeve with the outer sleeve's size.
            if c=='cloud-shoulder' or c in UPPERS and sum(other in UPPERS for other in pair)>1:labels=[]
            for label in labels:
                for match in re.finditer(re.escape(label),text,re.I):
                    window=max(0,match.start()-8)
                    negated=NEGATION.search(text[window:match.start()])
                    phrase_start=window+negated.start() if negated else match.start()
                    # Preserve the negator when copying a role-specific phrase
                    # out of a shared clause. Dropping it reverses style intent
                    # and can silently replace excluded dimensions by defaults.
                    tail=re.split(r'[，,。；;\n]',text[phrase_start:],maxsplit=1)[0]
                    for other in pair:
                        for term in component_terms(engine,other):tail=tail.replace(term,'')
                    if tail not in chunk:
                        chunk+='，'+tail
            # The orchestration layer has already accepted this exact pair;
            # do not let its whole-outfit wording trigger the single-item guard.
            chunk=WHOLE.sub(lambda m:'' if '套' in m.group() else m.group(),chunk)
            for other in engine.names:
                if other!=c and (other in pair or c.endswith('skirt')):
                    if other=='duijin-upper':
                        spans=sorted({m.span() for m in engine.positive_component_matches(chunk,other)},reverse=True)
                        # Merge nested aliases to avoid offset changes while
                        # retaining a closed collar's longer garment name.
                        spans=[(a,b) for a,b in spans if not any(x<=a and b<=y and (a,b)!=(x,y) for x,y in spans)]
                        for a,b in spans:chunk=chunk[:a]+chunk[b:]
                        continue
                    for term in component_terms(engine,other):chunk=chunk.replace(term,'')
            visual=(confirmed_visuals or {}).get(c) or {'component':c,'features':{}}
            image_default=False
            if c.endswith('skirt') and visual.get('features',{}).get('length')=='full':
                supplied=engine.supplied_fields(chunk,c,body_from(body_values))
                if c+'.length' not in supplied:
                    high=engine.high_skirt_image_length(visual.get('features',{}),body_from(body_values),supplied) if c=='ruqun-skirt' else None
                    if high is None:
                        chunk+='，裙长95cm'
                        image_default=True
            intent = engine.interpret(chunk, None, body_values, visual)
            if intent['status'] != 'ready':
                return intent
            if image_default:
                intent['sources'][c+'.length']='image_style_default'
            for field, value in chosen.items():
                intent['patch']['traditional'][field]['v'] = value
                path = 'traditional.' + field
                intent['sources'][path] = 'text' if any(positive_occurrences(text,label) for label in
                    (engine.vocab['DYN_CN'] if field == 'dynasty' else engine.vocab['OCC_CN']).values()) else 'default'
            intent['default_fields'] = [k for k, v in intent['sources'].items() if v == 'default']
            intent['id'] = member_id(c,pair)
            if visual.get('opening_source')=='user_confirmation':
                intent['sources'][c+'.opening_type']='user_confirmation'
                intent['note']=(intent.get('note','')+' 开襟位置由用户选择；本图遮挡，未从图片确认。').strip()
            if visual.get('component_source')=='user_confirmation':
                intent['component_source']='user_confirmation'
                intent['selection_note']=('内搭基础款由用户选择；图片未确认背面、肩带及完整裁法，采用直幅后背系带款。'
                    if c=='chest-wrap' else '下裙款式由用户选择；本图裙门或侧褶被遮挡，未从图片确认。')
                intent['note']=(intent.get('note','')+' '+intent['selection_note']).strip()
            garments.append(intent)
        garments.sort(key=lambda g: MEMBER_ORDER[g['id']])
        return {'status': 'ready', 'garments': garments, 'body_values': body_values,
                'supplied_body_fields': list(supplied_body), 'component': 'outfit'}
    except ValueError as exc:
        return engine.clarify(str(exc))


def interpret_outfit_image(engine, text, image, body_values):
    try:
        result=engine.model.image_outfit(image,engine.names)
    except Exception as exc:
        answer=engine.clarify('整套图片识别暂不可用，请重试或用文字明确上装和下裙。'
                             + (' '+str(exc) if isinstance(exc,RuntimeError) else ''))
        answer['image_retry_available']=True
        return answer
    return interpret_outfit_scene(engine,text,result,body_values)


def interpret_outfit_scene(engine,text,result,body_values):
    """Reuse the checked scene during explicit choices, without re-sending a photo."""
    from .scene_inventory import coverage_issue, ambiguous_skirt
    issue=coverage_issue(result)
    if issue:
        return engine.clarify(issue)
    quantity_issue=garment_quantity_issue(text,engine)
    if quantity_issue:return engine.clarify(quantity_issue)
    observations=result['observations']
    inventory={'version':'scene-inventory-v1','visible_garments':result['visible_garments'],
               'single_outfit':True,'all_garments_accounted':True}
    def checked_proposal(answer):
        answer['image_inventory']=copy.deepcopy(inventory)
        if answer.get('suggested_outfit'):
            answer['outfit_scene']=copy.deepcopy(result)
        if not answer['reply'].startswith('本次整图衣物清单：'):
            answer['reply']='本次整图衣物清单：'+'、'.join(inventory['visible_garments'])+'。\n'+answer['reply']
        return answer
    by_component={o.get('component'):o for o in observations if o.get('component')}
    pair=next((p for p in GROUPS if set(p)==set(by_component)),None)
    details='本次整图衣物清单：'+'、'.join(result['visible_garments'])+'。\n'
    details+='\n'.join(o.get('reason','') for o in observations)
    question=garment_choice_question(engine,text,observations,details)
    if question:return checked_proposal(question)
    if len(observations)==1 and len(by_component)==1:
        component=next(iter(by_component))
        if component in WHOLE_COMPONENTS|UPPERS|{'mamian-skirt','ruqun-skirt','cloud-shoulder','pibo'}:
            visual=by_component[component]
            _,excluded=engine.references(text)
            if component in excluded:
                return engine.clarify(details+'\n你已排除这件衣物，本次不会按图生成；请明确本次需要的款式。')
            named=engine.find_components(text)
            if named and set(named)!={component}:
                return engine.clarify(details+'\n图片整件款式与文字指定不同，请核对后重试。')
            if not named:text=engine.names[component]+('，'+text if text else '')
            issue=pending_visual_issue(component,visual)
            if issue:return engine.clarify(details+'\n'+issue)
            question=opening_question(engine,observations,text,[component])
            if question:return checked_proposal(question)
            intent=engine.interpret(text,None,body_values,visual)
            if intent['status']!='ready':return intent
            return checked_proposal({'status':'needs_input','pattern':None,'suggested_component':component,
                'suggested_name':engine.names[component],'suggested_text':text,
                'visible_features':visual.get('features',{}),
                'reply':details+'\n建议制作'+engine.names[component]+'完整基础款。包含该件全部必要裁片；尺寸采用当前人体和可调整默认值，请确认生成。'})
    # Every observation must be accounted for. Never discard an unconfirmed item.
    if len(by_component)!=len(observations):
        return engine.clarify(details+'\n整套中仍有衣物未确认，不会只输出其它部分。请补充无遮挡正面图或明确完整款式。')
    if not pair:
        return engine.clarify(details+'\n未确认可用的完整衣物组合，不会改用领片或袖片。请补充正面全身图，或明确上衣＋下裙/整件长袍。')
    for component,visual in by_component.items():
        issue=pending_visual_issue(component,visual)
        if issue:
            return engine.clarify(details+'\n'+issue)
        if component in {'beizi','banbi'} and visual.get('features',{}).get('upper_front')!='open':
            return engine.clarify(details+'\n上装的开敞对襟尚未确认，不能用当前基础款补齐整套。请补充清楚的前襟照片或使用文字制版。')
    named=engine.find_components(text)
    _,excluded=engine.references(text)
    if set(excluded)&set(pair):
        return engine.clarify(details+'\n你已排除图片组合中的衣物，请明确本次要制作的款式。')
    if named and not set(named)<=set(pair):
        return engine.clarify(details+'\n文字指定的款式与图片组合不同，请明确本次要制作的衣物。')
    # Add only missing confirmed item names; keep supplied numeric instructions.
    canonical=text.strip()
    for component in pair:
        if component not in named:
            canonical+=('；' if canonical else '')+engine.names[component]
    if len(canonical)>4000:
        return engine.clarify('描述过长，请精简尺寸要求后重新识别。')
    question=opening_question(engine,observations,canonical,pair)
    if question:return checked_proposal(question)
    intent=interpret_outfit(engine,canonical,body_values,by_component)
    if not intent or intent['status']!='ready':
        return intent or engine.clarify('请明确上装与下裙。')
    name='＋'.join(LABELS[c] for c in pair)
    answer={'status':'needs_input','pattern':None,'suggested_name':name,
        'suggested_text':canonical,'suggested_outfit':True,'outfit_observations':observations,
        'reply':details+'\n建议制作'+name+f'，共{len(pair)}件基础款，请确认后生成。图片未提供精确人体尺寸；未指定参数使用明示默认值。'}
    if any(g['sources'].get(g['component']+'.length')=='image_style_default' for g in intent['garments']):
        if any(g['absolute_lengths_cm'].get(g['component']+'.length')==95. for g in intent['garments']):
            answer['reply']+='\n长裙先用95cm默认裙长，可在生成后调整；这不是照片测量。'
        else:
            answer['reply']+='\n高腰/齐胸长裙按当前体型和穿着腰位估算至近脚踝，默认长度可在参数面板调整；不是照片测量。'
    return checked_proposal(answer)


def parameter_response(engine, garments, body_values=None):
    components = [g['component'] for g in garments]
    params = {}
    for g in garments:
        params[g['component']] = engine.parameter_response(g['patch'],body_values)['params'][g['component']]
    params['traditional'] = {k: {'v': garments[0]['patch']['traditional'][k]['v'], 'type': 'select', 'range': values}
                             for k, values in common_contexts(engine, components).items()}
    return {'body_id': 'mean_female', 'is_sectioned': True, 'params': params,
            'garments': [{'id': g['id'], 'component': g['component'], 'name': LABELS[g['component']]} for g in garments]}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def namespaced(node, prefix):
    node = copy.deepcopy(node)
    ids = {item.attrib['id']: prefix + '__' + item.attrib['id'] for item in node.iter() if 'id' in item.attrib}
    for item in node.iter():
        for key, value in list(item.attrib.items()):
            if key == 'id':
                item.set(key, ids[value])
            elif key == 'data-panel':
                item.set(key, prefix + '__' + value)
            else:
                for old, new in ids.items():
                    value = value.replace('url(#' + old + ')', 'url(#' + new + ')')
                    if value == '#' + old:
                        value = '#' + new
                item.set(key, value)
    return node


def canvas(width, height, label):
    return ET.Element(tag('svg'), {'viewBox': f'0 0 {width:.8f} {height:.8f}',
        'width': f'{width:.8f}cm', 'height': f'{height:.8f}cm', 'role': 'img', 'aria-label': label})


def title(svg, x, y, value):
    node = ET.SubElement(svg, tag('text'), {'x': str(x), 'y': str(y), 'font-size': '3',
        'font-family': 'Microsoft YaHei, sans-serif', 'fill': '#65758a'})
    node.text = value


def combine_nets(folder, garments, source, target):
    roots = [ET.parse(folder / g['id'] / source).getroot() for g in garments]
    boxes = [[float(v) for v in node.attrib['viewBox'].split()] for node in roots]
    # Stack garment blocks instead of making a separate wide column for every
    # member. Curves retain the same cm scale and all pieces remain present.
    width = max(b[2] for b in boxes)
    height = sum(b[3] for b in boxes) + 20 * (len(boxes)-1) + 8
    svg = canvas(width, height, '整套服饰裁片净样，统一厘米比例')
    y = 0.
    for g, node, box in zip(garments, roots, boxes):
        title(svg, 3, y+4, LABELS[g['component']])
        group = ET.SubElement(svg, tag('g'), {'data-garment': g['id'], 'transform': f'translate(0,{y+8})'})
        geometry=json.loads((folder/g['id']/'pattern.json').read_text(encoding='utf-8'))
        panel_names=iter(sorted(geometry['panels']))
        for child in node:
            if child.tag == tag('g'):
                child=copy.deepcopy(child)
                child.set('data-panel',next(panel_names))
            group.append(namespaced(child, g['id']))
        y += box[3] + 20
    ET.ElementTree(svg).write(folder / target, encoding='utf-8', xml_declaration=True)
    return svg


def combine_body_layout(folder, garments):
    trees = {g['id']: ET.parse(folder/g['id']/'body-layout.svg').getroot() for g in garments}
    raw = {}
    bounds = []
    person = None
    chest_skirt=any(g['component']=='ruqun-skirt' and
        g['patch']['ruqun-skirt']['waist_position']['v']>=.85 for g in garments)
    closed_upper=any(g['component']=='chest-wrap' or g['component'] in WHOLE_COMPONENTS and g['component'].endswith('upper') and g['component'] not in OUTERS for g in garments)
    has_chest_wrap=any(g['component']=='chest-wrap' for g in garments)
    order=({'upper':0,'lower':1,'outer':2,'accessory':3,'drape':4} if has_chest_wrap or chest_skirt and closed_upper
           else {'lower':0,'upper':1,'outer':2,'accessory':3,'drape':4})
    tuck_y=None
    if has_chest_wrap:
        from .body_layout import landmarks,ruqun_wearing_y
        lower=next((g for g in garments if g['id']=='lower'),None)
        if lower:
            body=json.loads((folder/lower['id']/'body.json').read_text(encoding='utf-8'))
            tuck_y=(ruqun_wearing_y(body,lower['patch']['ruqun-skirt']['waist_position']['v'])
                if lower['component']=='ruqun-skirt' else landmarks(body)['waist_y']+(1-lower['patch']['mamian-skirt']['rise']['v'])*body['hips_line'])
    for g in garments:
        left = trees[g['id']].find(tag('g') + '[@id="body-placement"]')
        raw[g['id']] = [node for node in left if node.attrib.get('class') != 'body-outline']
        if person is None:
            person = left.find(tag('g') + '[@class="body-outline"]')
            bounds += [parse_path(p.attrib['d']).bbox() for p in person.iter(tag('path'))]
        for node in raw[g['id']]:
            clip = node.find('.//' + tag('clipPath') + '/' + tag('rect'))
            for path in node.iter(tag('path')):
                x0, x1, y0, y1 = parse_path(path.attrib['d']).bbox()
                if clip is not None:
                    y0 = max(y0, float(clip.attrib['y']))
                if y1 >= y0:
                    bounds.append((x0, x1, y0, y1))
    x0 = min(b[0] for b in bounds); x1 = max(b[1] for b in bounds)
    y0 = min(b[2] for b in bounds); y1 = max(b[3] for b in bounds)
    left_width = max(x1-x0+12, 80.)
    center = (left_width-x1-x0)/2
    net = ET.parse(folder/'preview.svg').getroot()
    box = [float(v) for v in net.attrib['viewBox'].split()]
    width = left_width + 12 + box[2]
    height = max(y1-y0, box[3]) + 16
    for source, target in [('preview.svg', 'body-layout.svg'), ('preview-dimensions.svg', 'body-layout-dimensions.svg')]:
        svg = canvas(width, height, '左侧整套人体定位，右侧全部无人体净样，统一厘米比例')
        title(svg, 6, 5, '整套人体定位 · 二维示意')
        left = ET.SubElement(svg, tag('g'), {'id': 'body-placement', 'transform': f'translate({center},{10-y0})'})
        left.append(copy.deepcopy(person))
        # Chest-height skirts wrap over the blouse; open coats stay outside.
        # There are no seams between these independent garments.
        for g in sorted(garments,key=lambda g:order[g['id']]):
            group = ET.SubElement(left, tag('g'), {'data-garment': g['id']})
            if g['component']=='chest-wrap' and tuck_y is not None:
                ident=g['id']+'__tucked-wrap-clip'
                defs=ET.SubElement(group,tag('defs'));clip=ET.SubElement(defs,tag('clipPath'),{'id':ident})
                ET.SubElement(clip,tag('rect'),{'x':'-500','y':'-500','width':'1000','height':str(tuck_y+500)})
                group.set('clip-path','url(#'+ident+')')
            for child in raw[g['id']]:
                group.append(namespaced(child, g['id']))
        right = ET.SubElement(svg, tag('g'), {'id': 'net-layout', 'transform': f'translate({left_width+12},8)'})
        for child in ET.parse(folder/source).getroot():
            child=copy.deepcopy(child)
            for path in child.iter(tag('path')):
                path.set('fill','#b5d5f6'); path.set('fill-opacity','.55')
                path.set('stroke','#397dcb'); path.set('stroke-width','.28')
            for mark in child.iter(tag('line')):
                mark.set('stroke','#7099c6')
            right.append(child)
        ET.ElementTree(svg).write(folder/target, encoding='utf-8', xml_declaration=True)
    report = {'version': VERSION, 'units': 'cm', 'shared_scale': 1., 'garments':
              [{'id': g['id'], 'component': g['component']} for g in garments],
              'body_count': 1, 'right_contains_body': False, 'view_box': [0,0,width,height],
              'placement_order':[g['id'] for g in sorted(garments,key=lambda g:order[g['id']])],
              'innerwear_tuck_y_cm':tuck_y,
              'scope': 'Separate garments on one 2D body; not cloth simulation or fit validation'}
    write_json(folder/'body-layout.json', report)
    return report


def generate_outfit(garments, template, body_values, folder):
    folder.mkdir(parents=True, exist_ok=False)
    combined = {'panels': {}, 'stitches': [], 'drafting_marks': [], 'template_version': VERSION}
    members = []
    measurements = []
    member_notes = []
    for g in garments:
        child = folder/g['id']
        meta = generate_pattern(g['patch'], template, body_values, child)
        meta.pop('body_values')
        meta.update(parameter_sources=g['sources'], default_fields=g['default_fields'],
                    absolute_lengths_cm=g['absolute_lengths_cm'])
        if g.get('component_source'):
            meta.update(component_source=g['component_source'],selection_note=g.get('selection_note',''))
        member_notes += [LABELS[g['component']]+'：'+note for note in meta.get('warnings',[])]
        if g.get('note'):member_notes.append(LABELS[g['component']]+'：'+g['note'])
        elif g.get('selection_note'):member_notes.append(LABELS[g['component']]+'：'+g['selection_note'])
        write_json(child/'metadata.json', meta)
        geometry = json.loads((child/'pattern.json').read_text(encoding='utf-8'))
        prefix = g['id'] + '__'
        combined['panels'].update({prefix+k: v for k,v in geometry['panels'].items()})
        for stitch in geometry.get('stitches', []):
            stitch = copy.deepcopy(stitch)
            for edge in stitch:
                if isinstance(edge, dict) and 'panel' in edge:
                    edge['panel'] = prefix+edge['panel']
            combined['stitches'].append(stitch)
        for mark in geometry.get('drafting_marks', []):
            combined['drafting_marks'].append(dict(mark, panel=prefix+mark['panel']))
        measurements += [dict(row, panel_id=prefix+row['panel_id'], garment_id=g['id'],
                              garment_name=LABELS[g['component']]) for row in meta['panel_measurements']]
        members.append({'id': g['id'], 'component': g['component'], 'name': LABELS[g['component']],
                        'panel_count': meta['panel_count'], 'geometry_validation': meta['geometry_validation']})
        if g.get('component_source'):
            members[-1]['component_source']=g['component_source']
    for source in ['pattern.svg','pattern-dimensions.svg','preview.svg','preview-dimensions.svg']:
        if source.startswith('preview'):continue
        combine_nets(folder, garments, source, source)
    from .preview_packing import compact_plan,render_compact_preview
    preview_plan=compact_plan(folder,garments)
    for source in ['preview.svg','preview-dimensions.svg']:
        render_compact_preview(folder,garments,source,source,preview_plan)
    write_json(folder/'preview-layout.json',preview_plan)
    layout = combine_body_layout(folder, garments)
    write_json(folder/'pattern.json', combined)
    write_json(folder/'design.json', {'version': VERSION, 'garments':
        [{'id': g['id'], 'component': g['component'], 'patch': g['patch']} for g in garments]})
    write_json(folder/'body.json', body_from(body_values).params)
    notes = [f'本次包含{len(garments)}件独立衣物；没有衣物之间的缝合边。',
             '左侧为二维定位示意，右侧为全部净样；未进行实体试缝。']
    notes += member_notes
    return {'component': 'outfit', 'outfit_version': VERSION, 'garments': members,
            'panel_count': len(combined['panels']), 'stitch_count': len(combined['stitches']),
            'geometry_finite': True, 'is_self_intersecting': False,
            'geometry_validation': {'garments': {g['id']: g['geometry_validation'] for g in members}},
            'panel_measurements': measurements, 'warnings': notes,
            'body_layout': dict(layout, scope='左侧为整套二维定位示意；右侧为各件全部净样，统一厘米比例。')}
