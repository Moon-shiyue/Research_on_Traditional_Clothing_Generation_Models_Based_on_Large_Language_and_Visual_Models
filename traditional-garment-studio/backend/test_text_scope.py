import unittest
from .engine import PaperEngine


class Model:
    def __init__(self):
        self.calls=0
    def text(self,*args):
        self.calls+=1
        raise AssertionError('Explicit scope must not require a native prediction')
    def image(self,*args):
        self.calls+=1
        return {'component':'mamian-skirt','reason':'Mock observation','features':{}}


class TextScopeTests(unittest.TestCase):
    def test_multiple_copies_or_identical_inner_outer_layers_are_not_collapsed(self):
        from .outfits import interpret_outfit
        model=Model();engine=PaperEngine(model)
        for text in ['两件褙子，衣长100cm；马面裙，裙长95cm',
            '褙子2件；马面裙','半臂×２；襦裙','交领上衣和马面裙，要两套',
            '内层交领上衣，衣长55cm；外层交领上衣，衣长55cm；襦裙',
            '褙子，衣长100cm；褙子，衣长100cm；马面裙',
            '明代褙子，衣长100cm；明代褙子，衣长100cm；马面裙',
            '两条马面裙，裙长95cm','披帛3幅','云肩2件','半臂0件']:
            with self.subTest(text=text):
                r=interpret_outfit(engine,text,{}) or engine.interpret(text,None,{})
                self.assertEqual(r['status'],'needs_input',r)
                self.assertIn('多件同款',r['reply'])
        self.assertEqual(model.calls,0)

    def test_garment_quantity_check_preserves_layers_cloth_counts_and_parameter_restatements(self):
        from .outfits import interpret_outfit
        engine=PaperEngine(Model())
        for text in ['褙子，衣长100cm；马面裙，裙长95cm',
            '一件褙子，衣长100cm；一条马面裙，裙长95cm',
            '交领上衣；褙子；襦裙；两层云肩',
            '褙子，衣长100cm；褙子袖长50cm；马面裙，裙长95cm',
            '一套交领上衣和马面裙','不要两套，只做一套交领上衣和马面裙',
            '只做交领上衣和马面裙','只做马面裙和交领上衣','只制作褙子加马面裙',
            '只做一套圆领对襟上衣和马面裙','只做立领短衫和马面裙',
            '内层交领上衣；外层褙子；马面裙']:
            with self.subTest(text=text):
                r=interpret_outfit(engine,text,{}) or engine.interpret(text,None,{})
                self.assertEqual(r['status'],'ready',r)

    def test_unsupported_extra_garment_is_never_silently_dropped_from_an_outfit(self):
        from .outfits import interpret_outfit
        engine=PaperEngine(Model())
        for text in ['交领上衣；襦裙；抹胸','立领上衣；马面裙；云肩；霞帔','褙子；马面裙；中衣']:
            with self.subTest(text=text):
                result=interpret_outfit(engine,text,{})
                self.assertEqual(result['status'],'needs_input',result)
                self.assertIn('不能在整套中省略',result['reply'])
        for text in ['交领上衣；襦裙；不要做披帛','褙子；马面裙；不含中衣',
                     '立领上衣；马面裙；云肩；无需制作霞帔','整套褙子＋马面裙']:
            with self.subTest(text=text):
                result=interpret_outfit(engine,text,{})
                self.assertEqual(result['status'],'ready',result)

    def test_whole_unsupported_requests_never_become_local_parts_or_model_guesses(self):
        model=Model()
        engine=PaperEngine(model)
        for text in ['圆领长袍，马蹄袖',
                     '旗袍，身高170cm','制作深衣','对襟长衫','比甲','旗袍，先做褙子的领子',
                     '制作全套汉服，身高170cm','汉服套装','交领长袍的袖子，袖长48cm',
                     '褙子的领子','圆领袍的袖片']:
            with self.subTest(text=text):
                result=engine.interpret(text,None,{})
                self.assertEqual(result['status'],'needs_input',result)
                self.assertIsNone(result['pattern'])
        self.assertEqual(model.calls,0)

    def test_explicit_local_requests_and_negated_alternatives_select_the_requested_piece(self):
        engine=PaperEngine(Model())
        for text,expected in [('只制作圆领袍的圆领，领缘宽3cm','round-collar'),
            ('圆领袍，只做领子，领缘宽3cm','round-collar'),('旗袍的立领，领高3cm','stand-collar'),
            ('不要圆领袍，做褙子，衣长100cm','beizi'),('不要马面裙，做襦裙，裙长90cm','ruqun-skirt'),
            ('不是半臂而是褙子，衣长100cm','beizi'),('交领衣领，领深18cm','cross-collar'),
            ('整套汉服，只做马面裙，裙长95cm','mamian-skirt'),
            ('交领长袍的琵琶袖，袖长48cm','pipa-sleeve'),
            ('圆领袍的立领，领高3cm','stand-collar'),
            ('对襟褙子的领子，前襟宽12cm','duijin-collar')]:
            with self.subTest(text=text):
                result=engine.interpret(text,None,{})
                self.assertEqual(result['status'],'ready',result)
                self.assertEqual(result['component'],expected)

    def test_only_excluded_component_does_not_return_through_model_or_image(self):
        model=Model()
        engine=PaperEngine(model)
        result=engine.interpret('不要马面裙',None,{})
        self.assertEqual(result['status'],'needs_input')
        self.assertEqual(model.calls,0)
        result=engine.interpret('不要马面裙','mock-image',{})
        self.assertEqual(result['status'],'needs_input')
        self.assertNotIn('suggested_component',result)
        self.assertEqual(model.calls,1)

