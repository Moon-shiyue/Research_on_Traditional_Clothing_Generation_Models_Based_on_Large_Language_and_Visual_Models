"""Physical dimensions must never silently accept a partial or wrong unit."""
import unittest

from .body_text import body_measurements
from .engine import PaperEngine


class TextNumberTests(unittest.TestCase):
    def test_numeric_bounds_and_infix_exclusions_require_one_explicit_value(self):
        engine=PaperEngine(model=object())
        for text in ['褙子，衣长至少110cm','立领，领高>4cm','半臂，衣长不要50cm',
                     '褙子，身高不低于175cm','马面裙，裙长介于80和90cm',
                     '马面裙，裙长在80到90cm']:
            with self.subTest(text=text):
                self.assertEqual(engine.interpret(text,None,{})['status'],'needs_input')
        self.assertEqual(body_measurements('身高在170cm'),{'height':170})
        missing=engine.interpret('半臂，衣长50',None,{})
        self.assertEqual(missing['status'],'needs_input')
        self.assertIn('单位',missing['reply'])
        self.assertEqual(engine.interpret('褙子，衣长在110cm，袖长超过臂长',None,{})['status'],'ready')
        for phrase in ['衣长约为110cm','衣长大约一百一十厘米','衣长是110cm','衣长修改为110cm','衣长改110cm']:
            result=engine.interpret('褙子，'+phrase,None,{})
            self.assertEqual(result['status'],'ready',result)
            self.assertEqual(result['absolute_lengths_cm'],{'beizi.length':110})
        canonical=engine.interpret('汉代窄袖，袖长超过臂长1.4倍，袖口宽14cm，袖根宽17cm，肘部宽20cm，常服',None,{})
        self.assertEqual(canonical['status'],'ready',canonical)
        self.assertEqual(canonical['patch']['narrow-sleeve']['length']['v'],1.4)

    def test_copied_minus_fraction_and_comma_numbers_cannot_silently_use_defaults(self):
        engine=PaperEngine(model=object())
        for text in ['立领，领高−3cm','立领，领高3½cm','立领，领高3,5cm',
                     '云肩，垂须6，8厘米','褙子，袖口整围24，26']:
            with self.subTest(text=text):
                self.assertEqual(engine.interpret(text,None,{})['status'],'needs_input')
        self.assertEqual(engine.interpret('马面裙，裙长95cm，100%棉',None,{})['status'],'ready')

    def test_chinese_and_fullwidth_dimensions_are_explicit_values(self):
        engine=PaperEngine(model=object())
        for text,expected in [
                ('明代马面裙，裙长九十五厘米，褶量比二点四，常服',{'mamian-skirt.length':95}),
                ('宋代褙子，衣长一百一十厘米，袖长四十八厘米，常服',{'beizi.length':110,'beizi.sleeve_length':48}),
                ('唐代半臂，衣长５０．０ｃｍ，常服',{'banbi.length':50}),
                ('马面裙，裙长+九十五厘米',{'mamian-skirt.length':95})]:
            with self.subTest(text=text):
                result=engine.interpret(text,None,{})
                self.assertEqual(result['status'],'ready',result)
                self.assertEqual(result['absolute_lengths_cm'],expected)
                self.assertTrue(all(result['sources'][key]=='text' for key in expected))
                if '褶量' in text:
                    self.assertEqual(result['patch']['mamian-skirt']['pleat_ruffle']['v'],2.4)
        self.assertEqual(body_measurements('身高一百七十厘米，腰围八十厘米，臂长零点五米'),
            {'height':170,'waist':80,'arm_length':50})
        self.assertEqual(body_measurements('身高１７０ｃｍ，腰围８０．５厘米'),{'height':170,'waist':80.5})
        result=engine.interpret('云肩，层数三，垂须五点五厘米',None,{})
        self.assertEqual(result['status'],'ready',result)
        self.assertEqual(result['patch']['cloud-shoulder']['layers']['v'],3)
        self.assertEqual(result['patch']['cloud-shoulder']['tassel_length']['v'],5.5)
        for text in ['三层云肩，六云头，无穗须','云肩3层，6个云头，无穗须']:
            result=engine.interpret(text,None,{})
            self.assertEqual(result['status'],'ready',result)
            self.assertEqual(result['patch']['cloud-shoulder']['layers']['v'],3)
            self.assertEqual(result['patch']['cloud-shoulder']['petal_count']['v'],6)

    def test_ambiguous_chinese_values_wrong_units_and_exclusions_never_become_defaults(self):
        engine=PaperEngine(model=object())
        for text in ['褙子，衣长一百一厘米','褙子，衣长九十到一百厘米','马面裙，裙长九十五或九十厘米',
                     '褙子，不要衣长一百一十厘米','半臂，衣长负五十厘米','立领，领高三尺',
                     '立领，领高３ｉｎ','云肩，垂须三点厘米','马面裙，褶量比二点四点五',
                     '半臂，衣长一半','褙子，衣长一米七','马面裙，裙长-九十五厘米',
                     '四层云肩','云肩三层，层数二','云肩，不要六云头']:
            with self.subTest(text=text):
                self.assertEqual(engine.interpret(text,None,{})['status'],'needs_input')
        for text in ['身高一百七厘米','腰围八十到八十五厘米','身高一米七','腰围负八十厘米']:
            with self.subTest(text=text):
                if '负' in text:
                    self.assertLess(body_measurements(text)['waist'],0)
                else:
                    with self.assertRaises(ValueError):body_measurements(text)

    def test_chinese_number_normalization_preserves_existing_qualitative_phrases(self):
        engine=PaperEngine(model=object())
        for text in ['宋代褙子，衣长及小腿，袖长超过臂长，常服',
                     '明代云肩，三层云肩，六云头，无垂须，礼服',
                     '宋代半臂，衣长一般，常服','马面裙，裙长95cm一共三片','立领，领高3cm点缀刺绣']:
            with self.subTest(text=text):
                self.assertEqual(engine.interpret(text,None,{})['status'],'ready')

    def test_collar_controls_follow_current_template_context_without_mutating_schema(self):
        engine=PaperEngine(model=object())
        original=list(engine.schema['components']['stand-collar']['fields']['collar_height']['bounds'])
        for dynasty,expected in [('Ming',[2.5,4.]),('Qing',[4.,5.]),('Ming',[2.5,4.])]:
            patch=engine.defaults('stand-collar')
            patch['traditional']['dynasty']['v']=dynasty
            response=engine.parameter_response(patch)
            field=response['params']['stand-collar']['collar_height']
            self.assertEqual(field['range'],expected)
            self.assertIn('模板',field['constraint_note'])
        self.assertEqual(engine.schema['components']['stand-collar']['fields']['collar_height']['bounds'],original)

    def test_body_ranges_and_partial_units_are_not_silently_truncated(self):
        for text in ['腰围80-85cm','腰围80至85厘米','腰围80或85cm','腰围80±5cm',
                     '身高170cms','身高170.5.4cm','腰围80cm²','成衣 腰围80cm']:
            with self.subTest(text=text),self.assertRaises(ValueError):
                body_measurements(text)

    def test_garment_wrong_units_and_ranges_require_clarification(self):
        engine=PaperEngine(model=object())
        for text in ['褙子，衣长100-110cm','褙子，袖口整围60in','褙子，袖口整围60cm²',
                     '褙子，衣长1米7','立领，外倾角5cm','云肩，层数2cm','马面裙，褶量比2cm',
                     '立领，领高3度','云肩，垂须6.5.2cm']:
            with self.subTest(text=text):
                result=engine.interpret(text,None,{})
                self.assertEqual(result['status'],'needs_input',result)

    def test_explicit_metre_lengths_and_existing_ratio_units_remain_usable(self):
        engine=PaperEngine(model=object())
        result=engine.interpret('褙子，衣长1.1米，袖长0.48m，袖口整围600毫米',None,{})
        self.assertEqual(result['status'],'ready',result)
        self.assertEqual(result['absolute_lengths_cm'],{'beizi.length':110.,'beizi.sleeve_length':48.})
        self.assertEqual(result['patch']['beizi']['sleeve_cuff_width']['v'],60)
        result=engine.interpret('马面裙，裙长95cm，褶量比240%，腰位95%',None,{})
        self.assertEqual(result['status'],'ready',result)
        self.assertEqual(result['patch']['mamian-skirt']['pleat_ruffle']['v'],2.4)
        self.assertEqual(result['patch']['mamian-skirt']['rise']['v'],.95)

    def test_explicit_sleeve_half_and_full_circumference_have_distinct_units(self):
        engine=PaperEngine(model=object())
        for component,field,expected in [('banbi','sleeve_width',24),('beizi','sleeve_cuff_width',48)]:
            for wording in ['袖口平铺半围24cm','袖口半围240毫米','袖口整围48cm',
                            '袖口围度0.48米','袖口平铺宽度24cm，袖口全围48cm']:
                with self.subTest(component=component,wording=wording):
                    result=engine.interpret(engine.names[component]+'，'+wording,None,{})
                    self.assertEqual(result['status'],'ready',result)
                    self.assertEqual(result['patch'][component][field]['v'],expected)
                    self.assertEqual(result['sources'][component+'.'+field],'text')
            result=engine.interpret(engine.names[component]+'，袖口半围24cm，袖口整围30cm',None,{})
            self.assertEqual(result['status'],'needs_input',result)

    def test_leading_decimal_and_plus_sign_never_fall_back_to_defaults(self):
        engine=PaperEngine(model=object())
        result=engine.interpret('褙子，衣长+1.1米，袖口整围+48cm',None,{})
        self.assertEqual(result['status'],'ready',result)
        self.assertEqual(result['absolute_lengths_cm']['beizi.length'],110)
        self.assertEqual(result['patch']['beizi']['sleeve_cuff_width']['v'],48)
        self.assertEqual(body_measurements('腰围.8米，身高+170cm'),{'waist':80,'height':170})
        self.assertEqual(body_measurements('腰围改为80cm，身高调整为170cm'),{'waist':80,'height':170})
        result=engine.interpret('褙子，衣长改为110cm，袖长调整为48cm，袖口整围改用40cm',None,{})
        self.assertEqual(result['status'],'ready',result)
        self.assertEqual(result['absolute_lengths_cm'],{'beizi.length':110,'beizi.sleeve_length':48})
        self.assertEqual(result['patch']['beizi']['sleeve_cuff_width']['v'],40)
        for text in ['半臂，袖口半围.5cm','褙子，衣长100厘米改110厘米',
                     '褙子，袖长48cm改成50cm','褙子，袖口整围60cm改用40cm']:
            with self.subTest(text=text):
                self.assertEqual(engine.interpret(text,None,{})['status'],'needs_input')

    def test_excluded_measurements_are_never_applied_as_positive_sizes(self):
        engine=PaperEngine(model=object())
        for text in ['褙子，不要衣长100cm','半臂，不用袖口半围24cm',
                     '褙子，不要腰围80cm','褙子，不要衣长100cm，衣长110cm']:
            with self.subTest(text=text):
                self.assertEqual(engine.interpret(text,None,{})['status'],'needs_input')


if __name__=='__main__':
    unittest.main()
