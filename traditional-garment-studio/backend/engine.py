import copy
import json
import math
import re
import yaml

from .settings import GARMENT_ROOT
from .model import NativeModel
from .patterns import body_from, generate_pattern
from training.common import generator_constants
from training.schema import validate_patch, form_errors, finite_number
from .style_features import visual_parameters, text_style_parameters, unsupported_visual_variant
from .body_text import body_measurements, measurement_note
from .text_numbers import validate_number_tail, validate_unit, normalize_numeric_text, ASSIGNMENT
from .text_scope import (component_references, whole_request_issue, requested_local_kinds,
    component_kind, explicit_components_outside_robe_names, positive_occurrences, NEGATION,garment_quantity_issue)
from .whole_catalog import NAMES as WHOLE_NAMES, ALIASES, WHOLE, UPPERS, extend_catalog
from .body_layout import ruqun_wearing_y


FIELD_NAMES = {
    'petal_length':['云头大小基准','云头基准长','云头外伸长','云头长度','云头长'], 'front_extension':['云肩前摆加长','前摆加长'],
    'panel_height':['抹胸净高','内搭净高','围前净高','衣长'], 'front_coverage':['围前覆盖比','胸围覆盖比'],
    'tie_length':['系带净长','系带长'], 'tie_width':['系带展开宽','系带宽'],
    'strip_length':['披帛净长','披帛长度','披帛长','帛长','净长','长度'],
    'strip_width':['披帛净幅宽','披帛幅宽','披帛净宽','披帛宽','帛宽','净幅宽','净宽','幅宽','宽度'],
    'length': ['长度'], 'sleeve_length': ['袖长', '半袖长'],
    'mamian_width': ['马面宽度', '马面宽'], 'pleat_ruffle': ['褶量比', '褶量'],
    'rise': ['腰位参数', '腰位'], 'cuff_width': ['袖口宽度', '袖口宽'],
    'root_width': ['袖根宽度', '袖根宽'], 'bulge_width': ['膨起宽度', '袖身膨起', '袖身宽'],
    'collar_height': ['领高', '领子高度'], 'collar_flare': ['外倾角', '外倾'],
    'top_curve': ['顶弧', '领顶弧起量'], 'collar_depth': ['领深', '领口深度'],
    'cross_angle': ['交叉角'], 'overlap_amount': ['重叠量', '重叠'],
    'border_width': ['领缘宽度', '领缘宽'], 'front_depth': ['前领深'], 'back_depth': ['后领深'],
    'front_width': ['前襟宽'], 'neck_depth': ['领深'], 'placket_width': ['门襟宽'],
    'elbow_width': ['肘部宽'], 'hem_ratio': ['裙摆展宽', '展宽比'],
    'hem_expand': ['下摆单侧放量', '下摆放量'], 'chest_ease':['胸围松量比'],
    'neck_depth_front':['前领深','领深'], 'collar_width':['领宽','领高','领缘宽度','领缘宽'], 'overlap':['搭襟宽','搭襟'],
    'cuff_band_height':['袖口条宽','袖口条成品宽'],
    'side_slit':['侧衩高度','侧衩高','侧开衩高'],
    'waist_position': ['腰位参数'], 'layers': ['层数'], 'petal_count': ['云头数量', '云头数'],
    'tassel_length': ['垂须长度', '垂须'], 'slit_height': ['开衩高度比例', '开衩比例', '开衩'],
    'sleeve_width': ['袖口平铺半围', '袖口半围', '袖口平铺宽度', '袖口平铺宽',
                     '袖口整围', '袖口围度', '袖口全围', '袖口宽度', '袖口宽'],
    'sleeve_cuff_width': ['袖口整围', '袖口围度', '袖口全围', '袖口平铺半围', '袖口半围',
                          '袖口平铺宽度', '袖口平铺宽', '袖口宽度', '袖口宽'],
}


class PaperEngine:
    def __init__(self, model=None):
        self.schema = json.loads((GARMENT_ROOT / 'data/training_v1/schema.json').read_text(encoding='utf-8'))
        self.model_schema = copy.deepcopy(self.schema)
        # The v1 model never learned this hidden drafting field. Application
        # controls extend a copy; native predictions retain their original contract.
        self.schema['components']['beizi']['fields']['sleeve_cuff_width'] = {
            'type': 'float', 'bounds': [16., 80.],
            'training_values': [22., 40., 60.], 'labels': {},
        }
        # Application-only bounds allow centimetre skirt lengths. Frozen v1
        # data/schema and trained weights are not rewritten.
        for name in ['mamian-skirt','ruqun-skirt']:
            self.schema['components'][name]['fields']['length']['bounds'] = [0.2,1.5]
        self.schema['components']['ruqun-skirt']['fields']['length']['bounds'][1]=1.9
        # Long open-front coats remain valid beyond the v1 vocabulary's
        # 1.25 leg-length ceiling (e.g. fixed 110cm after a height correction).
        self.schema['components']['beizi']['fields']['length']['bounds'] = [0.75,2.0]
        # A fixed 50cm half-sleeve jacket on a tall body can fall just below
        # the training vocabulary's 0.5 ratio. Geometry still checks the
        # neckline, armhole and side seam before any design is committed.
        self.schema['components']['banbi']['fields']['length']['bounds'] = [0.4,0.9]
        # The application overlap template supports a wider release than the
        # frozen training vocabulary; do not alter the archived training schema.
        self.schema['components']['mamian-skirt']['fields']['pleat_ruffle']['bounds'] = [1.4,3.0]
        self.schema['components']['mamian-skirt']['fields']['rise']['bounds'][1] = 1.0
        self.template = yaml.safe_load((GARMENT_ROOT / 'assets/design_params/traditional.yaml').read_text(encoding='utf-8'))['design']
        # Four joined cloud heads are the museum-documented basic form.
        # This application default does not rewrite frozen examples or weights.
        self.template['cloud-shoulder']['petal_count']['v'] = 4
        self.schema['components']['cloud-shoulder']['fields'].update(
            petal_length={'type':'float','bounds':[.15,.9],'training_values':[.28],
                          'random_values':[.22,.28,.38,.5],'labels':{}},
            front_extension={'type':'float','bounds':[0.,20.],'training_values':[0.],
                             'random_values':[0.,6.,10.],'labels':{}})
        self.template['cloud-shoulder']['front_extension']={'v':0.}
        self.vocab = generator_constants()
        self.names = {c: v[1] for c, v in self.vocab['COMPONENT_CLASS'].items()}
        extend_catalog(self)
        from .drape_template import extend_drape_catalog
        extend_drape_catalog(self)
        from .chest_wrap import extend_chest_catalog
        extend_chest_catalog(self)
        self.model = model or NativeModel()

    def positive_component_matches(self,text,component):
        own=[m for term in [self.names[component],component]+ALIASES.get(component,[])
            for m in positive_occurrences(text,term)]
        if component=='duijin-upper' or component.endswith(('collar','sleeve')):
            longer=[m for c in WHOLE-{component}
                for term in [self.names[c],c]+ALIASES.get(c,[])
                for m in re.finditer(re.escape(term),text,re.I)]
            # "圆领袍，只做领子" explicitly selects its source neckline.
            # A negated source garment cannot supply such a local part.
            if component_kind(component) in requested_local_kinds(text):
                longer=[m for m in longer if NEGATION.search(text[max(0,m.start()-8):m.start()])]
            specific=[m.span() for m in longer]
            own=[m for m in own if not any(a<=m.start() and m.end()<=b for a,b in specific)]
        return own

    def references(self,text):
        found,excluded=component_references(text,self.names)
        for component,terms in ALIASES.items():
            if any(positive_occurrences(text,term) for term in terms):
                if component not in found:found.append(component)
                if component in excluded:excluded.remove(component)
            elif component not in found and any(term in text for term in terms):
                if component not in excluded:excluded.append(component)
        # Generic "对襟上衣" is also inside the more specific standing/round
        # names. Count it only when at least one occurrence is independent;
        # otherwise a single closed-collar garment becomes two garments.
        found=[c for c in found if not (c=='duijin-upper' or c.endswith(('collar','sleeve')))
               or self.positive_component_matches(text,c)]
        return found,excluded

    def find_components(self, text):
        found,_ = self.references(text)
        if set(found)&WHOLE and not requested_local_kinds(text):
            found=[c for c in found if not c.endswith(('collar','sleeve'))]
        local_kinds=requested_local_kinds(text)
        if len(local_kinds)==1:
            found=[component for component in found if component_kind(component) in local_kinds]
            explicit=explicit_components_outside_robe_names(text,self.names,found)
            if explicit:
                found=explicit
        # A sleeve name qualifying one whole upper garment is a style, rather
        # than a second requested standalone component (e.g. 窄袖褙子).
        if len(set(found) & {'beizi', 'banbi'}) == 1:
            found = [c for c in found if c not in {'wide-sleeve', 'narrow-sleeve', 'pipa-sleeve', 'duijin-collar'}]
        return found

    def defaults(self, component):
        spec = self.schema['components'][component]
        patch = {component: {}, 'traditional': {}}
        for field, f in spec['fields'].items():
            value = self.template[component][field]['v']
            if not f['bounds'][0] <= value <= f['bounds'][1]:
                value = f['training_values'][0]
            patch[component][field] = {'v': value}
        for field, allowed in spec['contexts'].items():
            value = self.template['traditional'][field]['v']
            patch['traditional'][field] = {'v': value if value in allowed else allowed[0]}
        self.adapt_default_context(patch, set())
        return patch

    def adapt_default_context(self, patch, supplied):
        if 'stand-collar' in patch and 'stand-collar.collar_height' not in supplied:
            dynasty = patch['traditional']['dynasty']['v']
            values = self.schema['components']['stand-collar']['fields']['collar_height']['training_values']
            current = patch['stand-collar']['collar_height']['v']
            if dynasty == 'Qing' and current < 4:
                patch['stand-collar']['collar_height']['v'] = next(v for v in values if v >= 4)
            elif dynasty == 'Ming' and current > 4:
                patch['stand-collar']['collar_height']['v'] = next(v for v in values if v <= 4)

    def parse_fields(self, text, component, body, absolute_lengths=None):
        if component=='cloud-shoulder' and re.search(r'(?:云肩净?长|总宽|总高|直径)\s*[:=：]?\s*[\d一二三四五六七八九十]',text):
            raise ValueError('云肩总宽高由领口、云头外伸及前摆加长共同决定；请填写“云头外伸长12cm、前摆加长10cm”，并核对右侧总宽高，不会忽略你指定的整体尺寸。')
        if component=='chest-wrap' and re.search(r'(?:围前净?宽|内搭净?宽|抹胸净?宽)\s*[:=：]?\s*\d',text):
            raise ValueError('本款围前净宽按人体胸围乘覆盖比计算；请设置胸围和围前覆盖比，并核对右侧厘米尺寸，不能忽略你指定的净宽。')
        text=normalize_numeric_text(text,[alias for names in FIELD_NAMES.values() for alias in names]
            +list(FIELD_NAMES)+['衣长','裙长','袖长','腿长','臂长'])
        supplied = {}
        spec = self.schema['components'][component]
        for field, f in spec['fields'].items():
            phrases = self.vocab['PHRASE'][component].get(field, {})
            matched = [(label, phrase) for label, phrase in phrases.items() if positive_occurrences(text, phrase)]
            matched = [(label, phrase) for label, phrase in matched if not any(phrase != other and phrase in other for _, other in matched)]
            values = {f['labels'][label] for label, _ in matched}
            if field in {'layers','petal_count'}:
                count_label='层数' if field=='layers' else '云头数'
                suffix='层' if field=='layers' else r'(?:个\s*)?云头'
                for count in re.finditer(r'([+-]?(?:\d+(?:\.\d+)?|[零〇一二三四五六七八九十百千两点]+))\s*'+suffix,text):
                    if NEGATION.search(text[max(0,count.start()-8):count.start()]):
                        raise ValueError('层数或云头数含有排除条件，请明确本次采用的数量。')
                    token=normalize_numeric_text(count_label+count[1],[count_label])[len(count_label):]
                    values.add(float(token))
            aliases = FIELD_NAMES.get(field, []).copy()
            if field == 'length':
                aliases += ['裙长'] if component in {'mamian-skirt', 'ruqun-skirt'} else (['衣长'] if component in UPPERS|WHOLE else ['袖长'])
            names = [re.escape(a) for a in aliases] + [r'(?<![\w])' + re.escape(field) + r'(?![\w])']
            pattern = '(?:' + '|'.join(names) + ')' + ASSIGNMENT + r'([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*(mm|毫米|cm|厘米|m|米|%|％|倍|度|°)?'
            for m in re.finditer(pattern, text, flags=re.I):
                if NEGATION.search(text[max(0,m.start()-8):m.start()]):
                    raise ValueError('数值要求含有排除条件，请只保留本次采用的尺寸，例如衣长110cm、袖口整围40cm。')
                value, unit = float(m[1]), (m[2] or '').lower()
                validate_number_tail(text[m.end():],aliases[0] if aliases else field)
                validate_unit(field,unit,aliases[0] if aliases else field)
                if field in {'length','sleeve_length','petal_length'} and not unit and abs(value)>max(f['bounds']):
                    raise ValueError('长度未注明单位；厘米长度请写为衣长110cm、裙长95cm或袖长48cm，不猜测厘米与比例。')
                if unit in {'mm', '毫米'}:
                    value /= 10
                elif unit in {'m', '米'}:
                    value *= 100
                if unit in {'%', '％'}:
                    value /= 100
                # Half-circumference is the banbi field; beizi stores the full
                # circumference. Explicit wording must not be dropped or read
                # as twice/half the requested sleeve opening.
                if field == 'sleeve_width' and re.match(r'袖口(?:整围|围度|全围)', m[0]):
                    value /= 2
                elif field == 'sleeve_cuff_width' and re.match(r'袖口(?:平铺半围|半围|平铺宽)', m[0]):
                    value *= 2
                value = round(value, 8)
                if field in {'length', 'sleeve_length','petal_length'} and unit in {'mm', '毫米', 'cm', '厘米','m','米'}:
                    if absolute_lengths is not None:
                        absolute_lengths[component + '.' + field] = value
                    reference = 'shoulder_w' if field=='petal_length' else '_leg_length' if component in {'mamian-skirt', 'ruqun-skirt'}|UPPERS|WHOLE and field == 'length' else 'arm_length'
                    value /= body[reference]
                values.add(round(value, 8))
            # Ratio expressions where reference length separates name and number.
            if field in {'length', 'sleeve_length'}:
                label = '裙长' if component in {'mamian-skirt', 'ruqun-skirt'} else ('衣长' if component in UPPERS|WHOLE and field == 'length' else '袖长')
                for m in re.finditer(re.escape(label) + r'[^，。；\n]{0,16}?(?:腿长|臂长)的?\s*(\d+(?:\.\d+)?)\s*(倍|%|％)', text):
                    values.add(float(m[1]) / (100 if m[2] in {'%', '％'} else 1))
            if len(values) > 1:
                raise ValueError(f'{field} 出现不同数值，请明确本次要使用的一个值。')
            if values:
                supplied[f'{component}.{field}'] = next(iter(values))
        for field, mapping in [('dynasty', self.vocab['DYN_CN']), ('occasion', self.vocab['OCC_CN'])]:
            matches = {key for key, name in mapping.items() if positive_occurrences(text, name)}
            if not matches and any(name in text for name in mapping.values()):
                raise ValueError('你只提供了排除的朝代或场合，请明确本次采用的一个值。')
            if len(matches) > 1:
                raise ValueError('请明确本次使用的一个朝代和场合。')
            if matches:
                supplied['traditional.' + field] = next(iter(matches))
        return supplied

    def supplied_fields(self, text, component, body, absolute_lengths=None):
        supplied = self.parse_fields(text, component, body, absolute_lengths)
        for field, value in text_style_parameters(text, component).items():
            supplied.setdefault(component + '.' + field, value)
        return supplied

    @staticmethod
    def length_reference(component, field, body_values):
        """Only these wire fields are ratios of a physical body length."""
        if component=='cloud-shoulder' and field=='petal_length':
            return body_from(body_values)['shoulder_w']
        if field == 'length' and component in UPPERS|WHOLE|{'mamian-skirt','ruqun-skirt'}:
            return body_from(body_values)['_leg_length']
        if (field == 'sleeve_length' and component in UPPERS|WHOLE
                or field == 'length' and component in {'pipa-sleeve', 'wide-sleeve', 'narrow-sleeve'}):
            return body_from(body_values)['arm_length']
        raise ValueError('该参数不是可换算厘米的长度比例。')

    def preserve_absolute_lengths(self, patch, body_values, absolute_lengths, sources=None):
        patch = copy.deepcopy(patch)
        component=next(k for k in patch if k!='traditional')
        if (component=='ruqun-skirt' and (sources or {}).get(component+'.length') in {'image_style_default','style_default'}
                and component+'.length' not in absolute_lengths):
            body=body_from(body_values);position=patch[component]['waist_position']['v']
            patch[component]['length']['v']=round((body['height']-5.-ruqun_wearing_y(body,position))/body['_leg_length'],8)
        if (component in WHOLE and component.endswith('robe') and (sources or {}).get(component+'.length') in {'default','image_style_default'}
                and component+'.length' not in absolute_lengths):
            body=body_from(body_values)
            patch[component]['length']['v']=round((body['height']-body['head_l']-5.)/body['_leg_length'],8)
        for path, cm in absolute_lengths.items():
            section, field = path.split('.')
            patch[section][field]['v'] = round(cm / self.length_reference(section, field, body_values), 8)
        return patch

    @staticmethod
    def high_skirt_image_length(features,body,supplied):
        if features.get('length')!='full' or 'ruqun-skirt.length' in supplied:return None
        position=supplied.get('ruqun-skirt.waist_position',{'high':.85,'chest':.95}.get(features.get('waist_level')))
        if position is None or position<.85:return None
        return round(body['height']-5.-ruqun_wearing_y(body,position),4)

    def interpret(self, text, image, body_values, confirmed_visual=None):
        quantity_issue=garment_quantity_issue(text,self)
        if quantity_issue:return self.clarify(quantity_issue)
        try:
            supplied_body = body_measurements(text)
            if supplied_body:
                body_values = dict(body_values or {}, **supplied_body)
                body_from(body_values)
        except ValueError as exc:
            return self.clarify(str(exc))
        components = self.find_components(text)
        _,excluded_components = self.references(text)
        scope_issue = whole_request_issue(text,components)
        if scope_issue:
            return self.clarify(scope_issue)
        if not components and excluded_components and not image:
            return self.clarify('你已排除所提到的组件，请明确这次要制作的一个组件名称。')
        note = measurement_note(supplied_body)
        model_patch = None
        if len(components) > 1:
            return self.clarify('这次描述包含多个组件，请先指定要生成的一个组件：' + '、'.join(self.names[c] for c in components))
        if image:
            try:
                candidates={c:self.names[c] for c in components} if components else self.names
                visual = self.model.image(image, candidates)
            except Exception as exc:
                result = self.clarify('图像识别暂时不可用，尚未依据本图生成。请重试图片；如只按文字制作，请不附图片单独发送文字。'
                    + (' ' + str(exc) if isinstance(exc, RuntimeError) else ''))
                result['image_retry_available'] = True
                return result
            else:
                if components:
                    if visual['component'] and visual['component'] != components[0]:
                        return self.clarify(visual['reason']+'\n参考图可确认的款式与文字指定不同，本次未生成。请更换参考图或修正款式名称；如只按文字制作，请不附图片单独发送文字。')
                    elif visual['component'] == components[0]:
                        confirmed_visual = visual
                    else:
                        return self.clarify(visual['reason']+'\n图片尚未确认文字指定的结构，本次未生成。请补充清楚的参考图；如只按文字制作，请不附图片单独发送文字。')
                elif visual['component']:
                    component = visual['component']
                    if component in excluded_components:
                        return self.clarify('图片可确认的组件为'+self.names[component]+'，但你已明确排除它。请指定其它要制作的组件，或更换参考图。')
                    unsupported = unsupported_visual_variant(component, visual.get('features', {}))
                    if unsupported:
                        return self.clarify(visual['reason'] + '\n' + unsupported)
                    suggestion = self.names[component]
                    image_default_lengths = {}
                    length_note = ''
                    style_note = ''
                    style_note = ''.join('\n' + item['note'] for item in
                        visual_parameters(component, visual.get('features', {})).values())
                    if component in {'mamian-skirt','ruqun-skirt'} and visual.get('features',{}).get('length')=='full':
                        try:
                            supplied_image_text = self.supplied_fields(text,component,body_from(body_values))
                        except ValueError as exc:
                            return self.clarify(str(exc))
                        if component+'.length' not in supplied_image_text:
                            high=self.high_skirt_image_length(visual.get('features',{}),body_from(body_values),supplied_image_text) if component=='ruqun-skirt' else None
                            if high is not None:
                                length_note=f'\n图片为高腰/齐胸长裙，按当前体型与腰位先估算裙长{high:g}cm至近脚踝；可调整，并非照片测量。'
                            else:
                                suggestion += '，裙长95cm'
                                image_default_lengths[component+'.length'] = 95.
                                length_note = '\n图片显示长裙：先采用95cm默认裙长，可在生成后调整；这不是从照片测得的尺寸。'
                    return {'status':'needs_input','pattern':None,
                            'reply':visual['reason'] + '\n建议先制作' + self.names[component]
                                + '。本次只制作所选组件，不代表图中整套服装。请确认组件后生成纸样。'+length_note+style_note
                                + ('\n'+note if note else ''),
                            'suggested_component':component,
                            'suggested_name':self.names[component],
                            'suggested_text':suggestion+('，'+text if text else ''),
                            'image_default_lengths_cm':image_default_lengths,
                            'visible_features':visual.get('features',{})}
                else:
                    return self.clarify(visual['reason'])
        if not components and text:
            try:
                candidate = self.model.text(text)
            except Exception:
                candidate = None
            if candidate:
                components = [c for c in candidate if c in self.names]
                model_patch = candidate
            if len(components) != 1:
                return self.clarify('请补充要生成的传统组件，例如马面裙、襦裙、褙子、半臂、云肩、交领或袖型。')
        if not components:
            return self.clarify('请上传参考图，或输入要制作的组件和尺寸。')
        component = components[0]
        if component in {'beizi','banbi'} and any(positive_occurrences(text, term) for term in ['琵琶袖', 'pipa-sleeve']):
            return self.clarify('当前整件对襟上衣暂不支持琵琶袖连接版型。请单独输入“琵琶袖”制作袖片，或改用宽袖、窄袖基础款。')
        patch = self.defaults(component)
        body = body_from(body_values)
        if component in WHOLE and component.endswith('robe'):
            patch[component]['length']['v']=round((body['height']-body['head_l']-5.)/body['_leg_length'],8)
        absolute_lengths = {}
        try:
            supplied = self.supplied_fields(text, component, body, absolute_lengths)
        except ValueError as exc:
            return self.clarify(str(exc))
        sources = {f'{section}.{key}': 'default' for section, fields in patch.items() for key in fields}
        if (component=='ruqun-skirt' and component+'.length' not in supplied
                and positive_occurrences(text,'齐胸')):
            high=self.high_skirt_image_length({'length':'full','waist_level':'chest'},body,supplied)
            if high is not None:
                patch[component]['length']['v']=high/body['_leg_length']
                sources[component+'.length']='style_default'
                note+=f' 齐胸裙先按当前体型估算裙长{high:g}cm至近脚踝；可调整，非实测尺寸。'
        # A named component with an explicit geometry value is directly usable.
        # Leave omitted fields as disclosed defaults instead of loading a model
        # solely to guess dimensions the user never supplied.
        explicit_geometry = any(path.startswith(component + '.') for path in supplied)
        if (component not in WHOLE|{'pibo'} and text and not image and not confirmed_visual and not explicit_geometry and not supplied_body
                and len(supplied) < len(sources) and len(text) > len(self.names[component]) + 8):
            try:
                model_patch = model_patch or self.model.text(text)
            except Exception:
                note += ' 未解析的尺寸采用默认值，可在参数面板修改。'
        if model_patch and component in model_patch and not validate_patch(model_patch, self.model_schema):
            for section, fields in model_patch.items():
                for key, node in fields.items():
                    if section in patch and key in patch[section]:
                        patch[section][key] = copy.deepcopy(node)
                        sources[f'{section}.{key}'] = 'model'
        if confirmed_visual and confirmed_visual['component']==component:
            features = confirmed_visual.get('features', {})
            unsupported = unsupported_visual_variant(component, features)
            if unsupported:
                return self.clarify(unsupported)
            observed=visual_parameters(component, features)
            high=self.high_skirt_image_length(features,body,supplied) if component=='ruqun-skirt' else None
            if high is not None:
                observed['length']={'value':high/body['_leg_length'],'source':'image_style_default',
                    'note':f'按高腰/齐胸穿着位置与当前体型，先估算裙长{high:g}cm至近脚踝；可调整，并非照片测量。'}
            for field, item in observed.items():
                if component in WHOLE and component.endswith('robe') and field=='length':
                    item=dict(item,value=round((body['height']-body['head_l']-5.)/body['_leg_length'],8),
                        note='长袍先按当前身高与头长给出近脚踝的衣长默认值；可调整，非照片测量。')
                path = component + '.' + field
                if path not in supplied:
                    patch[component][field]['v'] = item['value']
                    sources[path] = item['source']
                    note += ' ' + item['note']
        for path, value in supplied.items():
            section, field = path.split('.')
            patch[section][field]['v'] = value
            sources[path] = 'text'
        if confirmed_visual:
            for path, cm in confirmed_visual.get('default_lengths_cm',{}).items():
                if path in absolute_lengths and abs(absolute_lengths[path]-cm) < 1e-7:
                    sources[path] = 'image_style_default'
        self.adapt_default_context(patch, set(supplied))
        errors = validate_patch(patch, self.schema)
        if not errors:
            errors = form_errors(patch, self.template)
        if errors:
            return self.clarify(self.parameter_error_message(errors,patch,body_values))
        defaults = [key for key, source in sources.items() if source == 'default']
        return {'status': 'ready', 'patch': patch, 'component': component, 'sources': sources,
                'default_fields': defaults, 'note': note.strip(), 'absolute_lengths_cm': absolute_lengths,
                'body_values':body_values, 'supplied_body_fields':list(supplied_body)}

    @staticmethod
    def clarify(reply):
        return {'status': 'needs_input', 'reply': reply, 'pattern': None}

    def parameter_error_message(self, errors, patch, body_values=None):
        """Describe an unchanged validation decision in terms a maker can adjust."""
        component=next((k for k in patch if k!='traditional'),None)
        spec=self.schema['components'].get(component,{})
        messages=[]
        form_notes={
            'stand-collar: Ming height exceeds the project 4cm limit':'当前明代立领基础模板要求领高不超过4cm。',
            'stand-collar: Qing height below the project 4cm limit':'当前清代立领基础模板要求领高至少4cm。',
            'stand-collar: height exceeds 8cm':'当前立领模板的领高不能超过8cm。',
            'pipa-sleeve: cuff < root < bulge is required':'琵琶袖须满足：袖口宽小于袖根宽，袖根宽小于膨起宽。',
            'wide-sleeve: cuff must exceed root width':'广袖的袖口宽须大于袖根宽。',
            'mamian-skirt: width below 15cm':'马面宽度不能小于15cm。',
            'mamian-skirt: ruffle below 1':'马面裙褶量比不能小于1。',
        }
        for error in errors:
            if error in form_notes:
                messages.append(form_notes[error]);continue
            context=re.fullmatch(r'traditional\.(dynasty|occasion): unsupported value for this dataset component',error)
            if context:
                key=context.group(1)
                labels=self.vocab['DYN_CN' if key=='dynasty' else 'OCC_CN']
                choices='、'.join(labels.get(v,v) for v in spec.get('contexts',{}).get(key,[]))
                messages.append(f'当前{self.names.get(component,"服饰")}基础模板的'+('朝代' if key=='dynasty' else '场合')+f'可选：{choices}。')
                continue
            bounds=re.fullmatch(r'([^.:]+)\.([^.:]+): value outside schema bounds',error)
            if bounds and bounds.group(1)==component and bounds.group(2) in spec.get('fields',{}):
                field=bounds.group(2)
                low,high=spec['fields'][field]['bounds']
                label=FIELD_NAMES.get(field,[field])[0]
                unit=''
                try:
                    factor=self.length_reference(component,field,body_values or {})
                    # Match the one-decimal UI endpoints: never suggest a
                    # rounded-up maximum that the same validator would reject.
                    low=math.ceil((low*factor-1e-8)*10)/10
                    high=math.floor((high*factor+1e-8)*10)/10
                    unit='cm'
                    label='云头大小基准' if field=='petal_length' else '袖长' if field=='sleeve_length' or component.endswith('sleeve') else '裙长' if component.endswith('skirt') else '衣长'
                except ValueError:
                    pass
                messages.append(f'{label}超出当前模板范围，请在参数面板的{low:.1f}–{high:.1f}{unit}内调整。')
                continue
            messages.append('这组参数不符合当前基础模板，请恢复默认后逐项调整。')
        return '；'.join(dict.fromkeys(messages))

    def parameter_response(self, patch, body_values=None):
        component = next(k for k in patch if k != 'traditional')
        spec = self.schema['components'][component]
        params = {component: {}, 'traditional': {}}
        for key, f in spec['fields'].items():
            params[component][key] = {'v': patch[component][key]['v'], 'type': f['type'], 'range': list(f['bounds'])}
        if component=='cloud-shoulder':
            params[component]['petal_length']['constraint_note']='调整云头曲线大小的基准值，不是整件宽高；实际净样总宽高见右侧标注。'
            params[component]['front_extension']['constraint_note']='只延伸前侧云头，领口与后侧保持；以右侧净样尺寸核对实际轮廓。'
        if component=='stand-collar':
            height=params[component]['collar_height']
            dynasty=patch['traditional']['dynasty']['v']
            if dynasty=='Ming':
                height['range'][1]=min(height['range'][1],4.)
                height['constraint_note']='当前明代基础模板的领高范围为2.5–4cm。'
            elif dynasty=='Qing':
                height['range'][0]=max(height['range'][0],4.)
                height['constraint_note']='当前清代基础模板的领高范围为4–5cm。'
        for key, choices in spec['contexts'].items():
            params['traditional'][key] = {'v': patch['traditional'][key]['v'], 'type': 'select', 'range': choices}
        if component in WHOLE|{'pibo','chest-wrap'}:
            for key,labels in [('sleeve_type',{0:'直线袖',1:'琵琶袖'}),('belt',{0:'不含腰带',1:'含腰带'}),
                               ('opening_type',{0:'右侧斜开襟',1:'对襟闭合'})]:
                if key in params[component]:
                    params[component][key].update(type='select',range=list(labels),option_labels=labels)
            from .design_constraints import constrain_controls
            constrain_controls(component,patch[component],params[component],body_from(body_values))
        return {'body_id': 'mean_female', 'is_sectioned': True, 'params': params}
