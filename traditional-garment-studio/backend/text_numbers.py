"""Reject incomplete numeric measurements instead of accepting their prefix."""
import re
import unicodedata


_DIGITS = dict(zip('一二三四五六七八九',range(1,10)),零=0,〇=0,两=2)
_UNITS = {'十':10,'百':100,'千':1000}
_CN = '零〇一二三四五六七八九十百千两点'
ASSIGNMENT = (r'\s*(?:改(?:为|成|用)?|修改为|调整(?:为|至)|设置为|设为|换成|变为|'
              r'约为|大约|是|为|取|约|在|=|：|:)?\s*')


def _chinese_number(value):
    parts=value.split('点')
    if len(parts)>2 or not parts[0] or (len(parts)==2 and not parts[1]):
        raise ValueError('中文小数写法不完整，请使用数字和单位，例如95.5cm。')
    whole=parts[0]
    if all(c in _DIGITS for c in whole):
        integer=int(''.join(str(_DIGITS[c]) for c in whole))
    else:
        total=0;current=None;last_unit=10000;zero=False;current_after_zero=False
        for char in whole:
            if char in _DIGITS:
                digit=_DIGITS[char]
                if current is not None:
                    raise ValueError('中文数值不明确，请使用数字和单位。')
                if digit==0:
                    zero=True
                else:
                    current=digit;current_after_zero=zero
            else:
                unit=_UNITS[char]
                if unit>=last_unit or (current is None and not (unit==10 and total==0 and not zero)):
                    raise ValueError('中文数值的位数不明确，请使用数字和单位。')
                total+=(current if current is not None else 1)*unit
                current=None;last_unit=unit;zero=False
        if current is not None:
            if last_unit>=100 and not current_after_zero:
                raise ValueError('中文数值有省略位数，请使用完整数字，例如110cm或101cm。')
            total+=current
        elif zero:
            raise ValueError('中文数值写法不完整，请使用数字和单位。')
        integer=total
    if len(parts)==1:
        return str(integer)
    if not all(c in _DIGITS for c in parts[1]):
        raise ValueError('中文小数部分请逐位填写，或直接使用数字。')
    return str(integer)+'.'+''.join(str(_DIGITS[c]) for c in parts[1])


def normalize_numeric_text(text,labels):
    """Normalize only explicit labelled numbers; never rewrite clothing names/prose."""
    text=text.replace('−','-')
    text=''.join(unicodedata.normalize('NFKC',c) if (
        '０'<=c<='９' or 'Ａ'<=c<='Ｚ' or 'ａ'<=c<='ｚ' or c in '．＋－％﹣﹢﹒＜＞') else c for c in text)
    names='|'.join(re.escape(v) for v in sorted(set(labels),key=len,reverse=True))
    constraint=re.search(r'(?P<label>'+names+r')\s*(?:=|：|:|为|是)?\s*'
        +r'(?:不少于|不多于|不低于|不高于|不小于|不大于|不超过|至少|至多|大于|小于|超过|低于|高于|'
        +r'不要|不用|不是|不取|不能为|不选|介于|>=|<=|>|<|≥|≤)\s*'
        +r'[+-]?(?:\d|\.\d|['+_CN+r'])',text)
    if constraint:
        raise ValueError(constraint['label']+'含有数值上下界或排除条件，请明确填写本次采用的一个数值，不自动猜选尺寸。')
    pattern=re.compile(r'(?P<label>'+names+r')(?P<gap>'+ASSIGNMENT+r')'
        +r'(?P<sign>负|正|[+-])?(?P<number>['+_CN+r']+)(?P<tail>\s*)')
    def replace(match):
        after=text[match.end():]
        # Qualitative prose such as 衣长一般 is not a one-centimetre instruction.
        if after and not re.match(r'(?:厘米|毫米|cm|mm|米|m|%|％|倍|度|°|层|个|云头|[，,。；;、\s\)）]|[-–—~～至到或/±]|$)',after,re.I):
            if after.startswith(('半','尺','寸','丈','公分','分米')):
                raise ValueError(match['label']+'请使用一个明确数字和cm/mm/m单位，不猜测省略尺寸。')
            return match.group()
        if after.startswith(('-', '–', '—', '~', '～', '至', '到', '或', '/', '±')):
            raise ValueError(match['label']+'请填写一个确定数值，不要填写范围或多个候选值。')
        number=_chinese_number(match['number'])
        sign='-' if match['sign'] in ('负','-') else '+' if match['sign'] in ('正','+') else ''
        return match['label']+match['gap']+sign+number+match['tail']
    return pattern.sub(replace,text)


def validate_number_tail(tail, label):
    tail=tail.lstrip()
    if re.match(r'(?:改(?:为|成|用)?|修改为|调整(?:为|至)|换成|变为)\s*[+-]?(?:\d|\.\d)',tail):
        raise ValueError(label+'出现未明确归属的修改数值，请只保留本次采用的一个值。')
    if re.match(r'(?:[-–—~～至到或/±]|\.\.?)[\s\d]',tail):
        raise ValueError(label+'请填写一个确定数值，不要填写范围或多个候选值。')
    if re.match(r'[,，]\s*[+-]?(?:\d+(?:\.\d+)?|['+_CN+r']+)\s*(?=(?:cm|mm|m|厘米|毫米|米)(?![A-Za-z])|[,，。；;、]|$)',tail,re.I):
        raise ValueError(label+'含有逗号分隔的多个数值；小数请用小数点，例如3.5cm。')
    extra_chinese=re.match(r'['+_CN+r']+(?=\s*(?:厘米|毫米|cm|mm|米|m|[，,。；;、]|$))',tail,re.I)
    if (tail[:1].isdigit() or (tail and unicodedata.category(tail[0]) in ('Nl','No'))
            or extra_chinese or re.match(r'[A-Za-z²³]',tail)
            or tail.startswith(('英寸','寸','尺','丈','码','公分','分米','平方','立方'))):
        raise ValueError(label+'的数值或单位未能完整识别，请检查后重试。')


def validate_unit(field, unit, label):
    physical={'mamian_width','cuff_width','root_width','bulge_width','collar_height',
        'top_curve','collar_depth','overlap_amount','border_width','front_depth',
        'back_depth','front_width','neck_depth','placket_width','elbow_width',
        'tassel_length','sleeve_width','sleeve_cuff_width','hem_expand','neck_depth_front','collar_width','overlap','cuff_band_height','side_slit','strip_length','strip_width','panel_height','tie_length','tie_width','front_extension'}
    if field in physical:
        allowed={'','mm','毫米','cm','厘米','m','米'}
    elif field in {'cross_angle','collar_flare'}:
        allowed={'','度','°'}
    elif field in {'layers','petal_count'}:
        allowed={''}
    elif field in {'length','sleeve_length','petal_length'}:
        allowed={'','mm','毫米','cm','厘米','m','米','%','％','倍'}
    else:
        allowed={'','%','％','倍'}
    if unit not in allowed:
        raise ValueError(label+'的单位与该参数不符；长度请用cm/mm/m，角度请用度，层数和云头数请填整数。')
