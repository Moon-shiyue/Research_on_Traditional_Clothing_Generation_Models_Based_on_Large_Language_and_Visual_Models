"""Side openings stay free in all wrap layers and leave neck bindings matched."""
from collections import Counter
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree as ET

from .engine import PaperEngine
from .patterns import build_geometry,generate_pattern
from .whole_catalog import NAMES
from .body_layout import tag


class WholeSlitTests(unittest.TestCase):
    def test_all_whole_openings_have_free_lower_edges_and_equal_upper_side_seams(self):
        engine=PaperEngine(model=object())
        for component,name in NAMES.items():
            for opening in ['', '，对襟'] if component.startswith(('round','stand')) else ['']:
                with self.subTest(component=component,opening=opening):
                    text=name+opening+'，衣长'+('130' if component.endswith('robe') else '60')+'cm，侧衩高15cm'
                    result=engine.interpret(text,None,{})
                    self.assertEqual(result['status'],'ready',result)
                    self.assertEqual(result['patch'][component]['side_slit']['v'],15.)
                    pattern,_,_,assembly,_,validation=build_geometry(result['patch'],engine.template,{})
                    refs=Counter((r['panel'],r['edge']) for pair in pattern.pattern['stitches'] for r in pair[:2])
                    loose=[r for r in assembly['free_edges'] if r['reason']=='unsewn side slit']
                    self.assertEqual(len(loose),5 if component.startswith(('round','stand')) and not opening else 4)
                    self.assertTrue(all(not refs[(r['panel'],r['edge'])] for r in loose))
                    self.assertLess(validation['max_seam_length_difference_cm'],.02)
                    with tempfile.TemporaryDirectory() as temp:
                        folder=Path(temp)/'draft'
                        generate_pattern(result['patch'],engine.template,{},folder)
                        root=ET.parse(folder/'pattern-dimensions.svg').getroot()
                        self.assertEqual(len(root.findall('.//'+tag('line')+'[@class="side-slit-open"]')),len(loose))

    def test_slit_cannot_reach_or_cross_the_armhole(self):
        engine=PaperEngine(model=object())
        result=engine.interpret('交领上衣，衣长45cm，侧衩高40cm',None,{})
        self.assertEqual(result['status'],'ready',result)
        with self.assertRaisesRegex(ValueError,'侧衩上端'):
            build_geometry(result['patch'],engine.template,{})


if __name__=='__main__':unittest.main()
