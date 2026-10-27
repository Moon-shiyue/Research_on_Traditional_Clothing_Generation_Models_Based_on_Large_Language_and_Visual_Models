"""A complete sleeveless vest has shaped armholes, matched bindings and no sleeve pieces."""
from collections import Counter
import unittest
from .engine import PaperEngine
from .patterns import build_geometry,body_from
from .outfits import interpret_outfit,interpret_outfit_image


class BijiaTests(unittest.TestCase):
    def test_visible_thigh_length_vest_does_not_keep_the_long_default(self):
        engine=PaperEngine(model=object());body=body_from({})
        visual={'component':'bijia','features':{'length':'mid','sleeve_extent':'sleeveless','front_opening':'center'}}
        result=engine.interpret('圆领对襟比甲',None,{},visual)
        self.assertEqual(result['status'],'ready',result)
        length=result['patch']['bijia']['length']['v']*body['_leg_length']
        self.assertLess(body['head_l']+length,body['height']*.68)
        self.assertEqual(result['sources']['bijia.length'],'image_style_default')
        self.assertNotIn('bijia.length',result['absolute_lengths_cm'])

    def test_real_armholes_and_free_slits_are_distinct_from_a_hidden_sleeved_shirt(self):
        engine=PaperEngine(model=object())
        for height in [150,182]:
            result=engine.interpret('圆领对襟比甲，衣长90cm，侧衩高20cm',None,{'height':height})
            self.assertEqual(result['status'],'ready',result)
            pattern,_,_,report,_,validation=build_geometry(result['patch'],engine.template,{'height':height})
            self.assertTrue(report['sleeveless'])
            self.assertEqual(len(pattern.pattern['panels']),10)
            self.assertFalse(any('sleeve_' in name for name in pattern.pattern['panels']))
            for side in ['left','right']:
                self.assertIn('bijia_armhole_binding_'+side,pattern.pattern['panels'])
            self.assertLess(validation['max_seam_length_difference_cm'],.02)
            refs=Counter((r['panel'],r['edge']) for pair in pattern.pattern['stitches'] for r in pair[:2])
            slits=[r for r in report['free_edges'] if r['reason']=='unsewn side slit']
            self.assertEqual(len(slits),4)
            self.assertTrue(all(not refs[(r['panel'],r['edge'])] for r in slits))

    def test_collar_and_sleeve_variants_cannot_silently_become_the_vest_basic(self):
        engine=PaperEngine(model=object())
        for text in ['立领对襟比甲','斜襟比甲','圆领对襟比甲，长袖','圆领对襟比甲，袖长50cm']:
            result=engine.interpret(text,None,{})
            self.assertEqual(result['status'],'needs_input',result)
        r=interpret_outfit(engine,'交领上衣，衣长55cm，袖长45cm；圆领对襟比甲，衣长90cm；马面裙，裙长95cm；单层云肩',{})
        self.assertEqual(r['status'],'ready',r)
        self.assertEqual([g['id'] for g in r['garments']],['upper','outer','lower','accessory'])
        self.assertEqual(r['garments'][1]['component'],'bijia')
        self.assertNotIn('sleeve_length',r['garments'][1]['patch']['bijia'])


if __name__=='__main__':unittest.main()
