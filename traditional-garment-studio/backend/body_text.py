"""Parse explicitly named body measurements without asking a model to guess."""
import re
from .text_numbers import validate_number_tail, normalize_numeric_text, ASSIGNMENT
from .text_scope import NEGATION

FIELDS={'身高':'height','人体身高':'height','胸围':'bust','腰围':'waist','臀围':'hips',
        '肩宽':'shoulder_w','臂长':'arm_length','颈宽':'neck_w'}
LABELS={value:key for key,value in FIELDS.items()}
PATTERN=re.compile(r'(?P<label>人体身高|身高|胸围|腰围|臀围|肩宽|臂长|颈宽)'
    +ASSIGNMENT+r'(?P<value>[+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*'
    r'(?P<unit>厘米|毫米|cm|mm|米|m)?',re.I)


def body_measurements(text):
    text=normalize_numeric_text(text,FIELDS)
    result={}
    for match in PATTERN.finditer(text):
        label=match['label']
        prefix=text[max(0,match.start()-5):match.start()].rstrip()
        suffix=text[match.end():]
        if NEGATION.search(text[max(0,match.start()-8):match.start()]):
            raise ValueError('人体尺寸含有排除条件，请只填写本次采用的数值，例如腰围80cm。')
        # A reference ratio is a garment parameter, not a 0.9cm arm.
        if not match['unit'] and suffix.startswith(('倍','%','％')):
            continue
        validate_number_tail(suffix,label)
        if label=='臂长' and prefix.endswith(('上','下','前','后')):
            raise ValueError('当前臂长参数是完整臂长，不能用上臂或前臂分段长度代替。请在人体尺寸中填写完整臂长。')
        if any(prefix.endswith(word) for word in ('成衣','服装','衣服','成品','衣身','裙子')):
            raise ValueError('成衣围度与人体尺寸不同。请在人体尺寸中填写人体参考，并用设计参数调整款式；当前不从文字直接设置成衣围度。')
        if not match['unit'] and (re.match('[A-Za-z]',suffix) or suffix.startswith(('英寸','寸','码'))):
            raise ValueError(label+'请使用厘米cm、毫米mm或米m；不识别的单位不会自动当作厘米。')
        if match['unit'] and suffix[:1].isdigit():
            raise ValueError(label+'请写成一个完整数值，例如身高1.70m。')
        value=float(match['value'])
        unit=(match['unit'] or 'cm').lower()
        value*=.1 if unit in ('毫米','mm') else 100. if unit in ('米','m') else 1.
        value=round(value,8)
        field=FIELDS[label]
        if field in result and result[field]!=value:
            raise ValueError(label+'出现不同数值，请明确本次要使用的一个值。')
        result[field]=value
    if re.search(r'(?:身高|胸围|腰围|臀围|肩宽|臂长|颈宽)\s*(?:是|为|约)?\s*[一二三四五六七八九十百两]+(?:米|厘|毫|寸)',text):
        raise ValueError('人体尺寸请用数字和单位填写，例如身高170cm、腰围70cm。')
    return result


def measurement_note(measurements):
    if not measurements:
        return ''
    values='、'.join(f'{LABELS[field]}{value:g}cm' for field,value in measurements.items())
    return '按文字采用人体参考：'+values+'；尺寸统一换算为厘米，未注明单位时按厘米处理，可在人体尺寸中核对。'
