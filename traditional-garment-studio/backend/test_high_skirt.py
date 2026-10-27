"""Long high skirts must reach the same hem level when waist/body changes."""
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree as ET

from .engine import PaperEngine
from .patterns import body_from,build_geometry
from .body_layout import ruqun_wearing_y,tag
from .outfits import interpret_outfit,generate_outfit


class HighSkirtTests(unittest.TestCase):
    def test_high_and_chest_image_length_follows_body_and_keeps_explicit_cm(self):
        engine=PaperEngine(model=object())
        for level,position in [('high',.85),('chest',.95)]:
            visual={'component':'ruqun-skirt','features':{'length':'full','waist_level':level,'hem_shape':'wide'}}
            result=engine.interpret('襦裙',None,{'height':150},visual)
            self.assertEqual(result['status'],'ready',result)
            self.assertNotIn('ruqun-skirt.length',result['absolute_lengths_cm'])
            for height in [150,180]:
                body=body_from({'height':height})
                patch=engine.preserve_absolute_lengths(result['patch'],{'height':height},result['absolute_lengths_cm'],result['sources'])
                length=patch['ruqun-skirt']['length']['v']*body['_leg_length']
                self.assertAlmostEqual(ruqun_wearing_y(body,position)+length,height-5,places=5)
                self.assertTrue(build_geometry(patch,engine.template,{'height':height})[-1]['sampled_outline_valid'])
            fixed=engine.interpret('襦裙，裙长95cm',None,{'height':150},visual)
            self.assertEqual(fixed['absolute_lengths_cm']['ruqun-skirt.length'],95.)
            patch=engine.preserve_absolute_lengths(fixed['patch'],{'height':180},fixed['absolute_lengths_cm'],fixed['sources'])
            self.assertAlmostEqual(patch['ruqun-skirt']['length']['v']*body_from({'height':180})['_leg_length'],95.,places=5)

    def test_chest_skirt_wraps_over_closed_blouse_and_keeps_every_net(self):
        engine=PaperEngine(model=object())
        intent=interpret_outfit(engine,'交领上衣，短袖；齐胸襦裙',{})
        self.assertEqual(intent['status'],'ready',intent)
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'design';meta=generate_outfit(intent['garments'],engine.template,{},folder)
            self.assertEqual(meta['body_layout']['placement_order'],['upper','lower'])
            root=ET.parse(folder/'body-layout.svg').getroot()
            left=root.find(tag('g')+'[@id="body-placement"]')
            self.assertEqual([n.attrib['data-garment'] for n in left if 'data-garment' in n.attrib],['upper','lower'])
            self.assertEqual(meta['panel_count'],19)
            self.assertEqual(len(meta['panel_measurements']),19)


if __name__=='__main__':unittest.main()
