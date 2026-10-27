"""Conservative request scope: a named collar is not an entire robe."""
import re
import unicodedata


NEGATION=re.compile(r'(?:(?:不要|不用|不需要|不想要|无需|别)(?:再|额外)?(?:做|制作|生成|输出|添加|加入|配)?'
    r'|不是|不选用|不选|不采用|不使用|避免|不做|不生成|不制作|不含|不带|不配|取消|去掉|排除|非)\s*$')
UNSUPPORTED_FULL_ITEMS=['曲裾','深衣','贴里','道袍','直裰','曳撒','龙袍','蟒袍','旗袍','马蹄袖',
    '披风','斗篷','比甲','霞帔','抹胸','肚兜','中衣','亵衣','裤子','袄裙','大袖衫']
WHOLE=re.compile(r'(?:圆领|交领|对襟|立领)(?:长袍|袍|长衫|上衣|外衣|衫|衣(?!领))'
    r'|深衣|曲裾|直裰|道袍|旗袍|龙袍|蟒袍|褂裙|袄裙|披风|斗篷|比甲'
    r'|汉服套装|汉服全套|全套汉服|整套汉服|全套服装|整套服装'
    r'|(?:一整套|一套|整套|全套|完整的?|全身的?)(?:传统)?(?:服饰|服装|衣服|汉服)|传统服饰套装|全身纸样')
LOCAL_WORD=r'(领片|领子|衣领|领贴|领型|袖片|袖型|袖子|马面裙|襦裙下裳|襦裙|下裙|裙片|立领|圆领|交领|对襟领|广袖|窄袖|琵琶袖)(?!(?:对襟)?(?:袍|衣|衫|长袍|长衫|上衣|外衣|短衫))'


def component_kind(component):
    return 'collar' if component.endswith('collar') else ('sleeve' if component.endswith('sleeve') else (
        'skirt' if component.endswith('skirt') else 'whole'))


def requested_local_kinds(text):
    matches=[]
    for index,prefix in enumerate([r'(?:只|仅|单独|局部|先)(?:制作|做|生成|要|输出)?[^，。；\n]{0,16}?',r'(?:的|中的?)\s*']):
        for match in re.finditer(prefix+LOCAL_WORD,text):
            lead=text[match.start():match.start(1)]
            # "Only one outfit of upper + skirt" limits the outfit, not
            # its skirt. Source-specific "...的马面裙" remains local.
            if index==0 and re.search(r'(?:一|1|整|全)套',lead):continue
            if index==0 and '裙' in match[1]:
                from .whole_catalog import NAMES,ALIASES,UPPERS
                join=r'(?:和|与|及|加|、|＋|\+)'
                names=['褙子','半臂']+[name for c,name in NAMES.items() if c in UPPERS or c.endswith('robe')]
                names += [name for c,aliases in ALIASES.items() if c in UPPERS or c.endswith('robe') for name in aliases]
                upper=r'(?:'+WHOLE.pattern+'|'+'|'.join(re.escape(name) for name in sorted(names,key=len,reverse=True))+')'
                tail=re.split(r'[，,。；;\n]',text[match.end():],maxsplit=1)[0]
                if re.search(upper+r'.*'+join,lead) or re.search(join+r'\s*'+upper,tail):continue
            matches.append(match[1])
    return {('sleeve' if '袖' in word else ('skirt' if '裙' in word else 'collar')) for word in matches}


def explicit_components_outside_robe_names(text,names,components):
    spans=[match.span() for match in WHOLE.finditer(text)]
    return [component for component in components if any(
        not any(start<=match.start() and match.end()<=end for start,end in spans)
        for term in [names[component],component] for match in positive_occurrences(text,term))]


def positive_occurrences(text,term):
    return [match for match in re.finditer(re.escape(term),text,re.I)
        if not NEGATION.search(text[max(0,match.start()-8):match.start()])]


def component_references(text,names):
    positive=[]
    negative=[]
    for component,name in names.items():
        terms=[name,component]
        if any(positive_occurrences(text,term) for term in terms):
            positive.append(component)
        elif any(term.lower() in text.lower() for term in terms):
            negative.append(component)
    return positive,negative


def garment_quantity_issue(text,engine):
    """Do not collapse explicitly requested copies or identical inner/outer layers."""
    from .whole_catalog import UPPERS,WHOLE as COMPLETE
    from .text_numbers import _chinese_number
    normalized=unicodedata.normalize('NFKC',text)
    count=r'(?P<count>\d+|[零〇一二三四五六七八九十百千两]+)'
    def multiple(match):
        if NEGATION.search(normalized[max(0,match.start()-8):match.start()]):return False
        token=match['count']
        try:return int(token if token.isdecimal() else _chinese_number(token))!=1
        except ValueError:return True
    message=('当前一份设计只保存一套、每种衣物一件的基础版型，不能把多件同款或相同款式的内外两层合并成一件。'
             '同款多件可复用同一份纸样；请明确本次只制作一份版型。不同叠穿层请分别指定当前支持的款式。')
    for match in re.finditer(count+r'\s*(?:套|份)\s*(?:完整)?(?:服饰|服装|汉服|纸样|版型)?',normalized):
        if multiple(match):return message
    for c in engine.find_components(normalized):
        if c not in UPPERS|COMPLETE|{'mamian-skirt','ruqun-skirt','cloud-shoulder','pibo'}:continue
        matches=engine.positive_component_matches(normalized,c)
        # Drop nested aliases of this same garment, retaining independent names.
        spans={m.span() for m in matches}
        spans={s for s in spans if not any(a<=s[0] and s[1]<=b and s!=(a,b) for a,b in spans)}
        terms='(?:'+'|'.join(re.escape(normalized[a:b]) for a,b in sorted(spans))+')'
        if not spans:continue
        units=r'(?:件|条|幅'+('' if c=='cloud-shoulder' else '|层')+')'
        for pattern in [count+r'\s*'+units+r'\s*(?:的)?'+terms,terms+r'\s*(?:各|共|一共|要|做|制作)?\s*'+count+r'\s*'+units,
                        terms+r'\s*[×xX*]\s*'+count+r'(?=$|[\s，,。；;])']:
            if any(multiple(m) for m in re.finditer(pattern,normalized)):return message
        roles=set()
        for a,b in spans:
            prefix=normalized[max(0,a-9):a]
            for role in ['内层','外层','内搭','外搭','里面','外面']:
                if re.search(re.escape(role)+r'\s*(?:用|做|制作|采用|的|为|是|穿)?\s*$',prefix):roles.add(role)
        if roles&{'内层','内搭','里面'} and roles&{'外层','外搭','外面'}:return message
        # A repeated name may be a harmless parameter clarification. Only
        # separate named clauses that each specify an entire garment length
        # unambiguously request two entries with this same type.
        full_entries=set()
        for a,b in spans:
            start=max(normalized.rfind(sep,0,a) for sep in '；;\n')+1
            tail=re.split(r'[；;\n]',normalized[b:],maxsplit=1)[0]
            if re.search(r'(?:衣长|裙长|围前净高|披帛长|strip_length|panel_height|\blength)\s*[:=：]?\s*[\d一二三四五六七八九十百]',tail):full_entries.add(start)
        if len(full_entries)>1:return message
    return ''


def unsupported_full_request_issue(text):
    if any(not NEGATION.search(text[max(0,m.start()-8):m.start()]) for m in
           re.finditer(r'(?:圆弧|弧形|拼接|多幅|多片|扇形)[^，；。\n]{0,5}披帛',text)):
        return '当前披帛只支持一整幅长条净样，不支持圆弧、扇形或拼接披帛；不能用直幅替代。'
    if not requested_local_kinds(text):
        unsupported=[term for term in UNSUPPORTED_FULL_ITEMS if positive_occurrences(text,term)]
        bound=[m.span() for m in positive_occurrences(text,'直幅系带抹胸')]
        if bound and all(any(a<=m.start() and m.end()<=b for a,b in bound) for m in positive_occurrences(text,'抹胸')):
            unsupported=[term for term in unsupported if term!='抹胸']
        if any(positive_occurrences(text,term) for term in ['对襟比甲','无袖对襟长衣','无袖对襟上衣']):
            unsupported=[term for term in unsupported if term!='比甲']
        if re.search(r'(?:立领|交领|斜襟|大襟|琵琶襟)[^，；。\n]{0,6}比甲',text):
            return '当前比甲只支持圆领对襟无袖基础款，不能替换为立领、斜襟或琵琶襟比甲。请明确圆领对襟变化款，或另选已支持服饰。'
        if unsupported:
            return ('本次还要求“'+'、'.join(unsupported)+'”，当前没有对应的完整基础版型，不能在整套中省略或用其它衣物代替。'
                '请明确去除这些项目，或只提交当前支持的完整上衣/袍衫、马面裙/襦裙及云肩。')
    return ''


def whole_request_issue(text,components):
    from .whole_catalog import WHOLE as COMPLETE
    extra=unsupported_full_request_issue(text)
    if extra:return extra
    if components==['chest-wrap'] and any(positive_occurrences(text,t) for t in ['肩带','吊带','闭背','拉链','胸杯','胸省']):
        return '直幅系带抹胸只支持直上缘围前布和后背系带；吊带、闭背或有胸省/胸杯的内搭须另制对应版型。'
    if components==['duijin-upper'] and any(positive_occurrences(text,term) for term in
            ['立领','圆领','交领','右斜襟','右侧斜襟','大襟','无袖']):
        return '直领对襟上衣是开敞直领的有袖基础款，不能与立领、圆领、交领、右斜襟或无袖要求混用；请明确本次领襟和袖型。'
    if set(components)&COMPLETE and not requested_local_kinds(text):
        if 'bijia' in components and any(positive_occurrences(text,term) for term in ['袖长','长袖','短袖','宽袖','窄袖','琵琶袖']):
            return '比甲是完整无袖基础款，不接受袖长或带袖样式；请去除袖部要求，或改选带袖的完整上衣。'
        return ''
    local_kinds=requested_local_kinds(text)
    if local_kinds and not components:
        return '请明确要制作的局部组件名称：领片可选立领、圆领、交领、对襟领；袖片可选窄袖、广袖、琵琶袖；下裙可选马面裙或襦裙。不会用来源衣物的领型代替袖片。'
    robes=[match.group() for match in WHOLE.finditer(text)
        if not NEGATION.search(text[max(0,match.start()-8):match.start()])]
    if not robes:
        return ''
    selected={'beizi':'褙子','banbi':'半臂','mamian-skirt':'马面裙','ruqun-skirt':'襦裙',
        'cloud-shoulder':'云肩','stand-collar':'立领','round-collar':'圆领',
        'cross-collar':'交领','duijin-collar':'对襟领','wide-sleeve':'广袖',
        'narrow-sleeve':'窄袖','pipa-sleeve':'琵琶袖'}
    if len(components)==1:
        name=selected.get(components[0])
        if name and re.search(r'(?:只|仅|单独|先)(?:制作|做|生成|要|输出)?\s*'+name
                +r'(?:组件|领片|袖片)?(?=$|[，。；\s])',text):
            return ''
    # An explicit local request is valid even if it identifies its source robe.
    local=(re.search(r'(?:只|仅|单独|局部|先)(?:制作|做|生成|要|输出)?[^，。；\n]{0,16}'
        r'(?:领片|领子|领贴|袖片|袖型|袖子|下裙|裙片)',text)
        or re.search(r'(?:的|中的?)(?:立领|圆领|交领|对襟领|领片|领子|领贴|袖片|袖型|袖子|广袖|窄袖|琵琶袖)',text)
        or re.search(r'(?:只|仅|单独)(?:制作|做|生成|要|输出)?[^，。；\n]{0,12}'
            r'(?:立领|圆领|交领|对襟领|广袖|窄袖|琵琶袖)(?=$|[，。；\s])',text))
    local_components={'stand-collar','round-collar','cross-collar','duijin-collar',
        'wide-sleeve','narrow-sleeve','pipa-sleeve','mamian-skirt','ruqun-skirt'}
    if (local and len(components)==1 and components[0] in local_components
            and (not local_kinds or component_kind(components[0]) in local_kinds)):
        return ''
    if local:
        return '当前可以制作局部领片或袖片，请明确一个组件名称，例如立领、圆领、交领、广袖或窄袖。'
    if any('套' in name for name in robes):
        return '请明确整套款式，例如“交领上衣＋襦裙”“立领上衣＋马面裙”，也可配云肩；整件长袍可选交领、圆领或立领基础款。不会用局部领袖代替整套。'
    return ('当前没有“'+'、'.join(dict.fromkeys(robes))+'”的整件版型，不能用局部领片或其它基础款代替。'
        '如只需要领片或袖片，请明确写“只制作圆领”“只制作交领领片”等；也可改选完整交领、圆领、立领上衣/袍衫或上衣＋下裙组合。')
