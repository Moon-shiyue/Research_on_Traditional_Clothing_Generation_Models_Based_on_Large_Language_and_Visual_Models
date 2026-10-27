"""Body placement must not rescale, replace or lose cutting geometry."""
import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from .engine import PaperEngine
from .patterns import generate_pattern
from .body_layout import tag
from .body_layout import mamian_front_dimensions


class BodyLayoutTests(unittest.TestCase):
    def setUp(self):
        self.engine=PaperEngine(model=object())
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def build(self,component,body=None,suffix=''):
        folder=Path(self.directory.name)/(component+suffix)
        generate_pattern(self.engine.defaults(component),self.engine.template,body,folder)
        return folder

    def test_all_components_keep_exact_net_paths_and_one_shared_scale(self):
        for component in self.engine.names:
            with self.subTest(component=component):
                folder=self.build(component)
                root=ET.parse(folder/'body-layout.svg').getroot()
                original=ET.parse(folder/'preview.svg').getroot()
                left=root.find(tag('g')+'[@id="body-placement"]')
                right=root.find(tag('g')+'[@id="net-layout"]')
                self.assertIsNotNone(left.find(tag('g')+'[@class="body-outline"]'))
                self.assertIsNone(right.find('.//'+tag('g')+'[@class="body-outline"]'))
                self.assertEqual([p.attrib['d'] for p in original.iter(tag('path'))],
                                 [p.attrib['d'] for p in right.iter(tag('path'))])
                self.assertEqual([g.attrib['transform'] for g in original if g.tag==tag('g')],
                                 [g.attrib['transform'] for g in right if g.tag==tag('g')])
                self.assertNotIn('scale',right.attrib['transform'])
                dimension=ET.parse(folder/'body-layout-dimensions.svg').getroot()
                self.assertEqual(root.attrib['viewBox'],dimension.attrib['viewBox'])
                captions=dimension.findall('.//'+tag('text')+'[@class="panel-size-label"]')
                self.assertEqual(len(captions),len(list(right)))
                for caption,panel in zip(captions,original.findall(tag('g'))):
                    from svgpathtools import parse_path
                    x0,x1,y0,y1=parse_path(panel.find(tag('path')).attrib['d']).bbox()
                    self.assertAlmostEqual(float(caption.attrib['data-width-cm']),x1-x0,places=6)
                    self.assertAlmostEqual(float(caption.attrib['data-height-cm']),y1-y0,places=6)
                panels=json.loads((folder/'pattern.json').read_text(encoding='utf-8'))['panels']
                self.assertEqual(sorted(panels),sorted(g.attrib['data-panel'] for g in right if g.tag==tag('g')))

    def test_body_changes_update_anatomical_landmarks_and_placement(self):
        first=self.build('beizi',{'height':166},'-first')
        second=self.build('beizi',{'height':180,'waist_line':42},'-second')
        a=json.loads((first/'body-layout.json').read_text(encoding='utf-8'))
        b=json.loads((second/'body-layout.json').read_text(encoding='utf-8'))
        self.assertEqual(b['body_landmarks']['height'],180)
        self.assertNotEqual(a['body_landmarks']['waist_y'],b['body_landmarks']['waist_y'])
        for folder in [first,second]:
            root=ET.parse(folder/'body-layout.svg').getroot()
            self.assertEqual(len(root.findall('.//'+tag('g')+'[@data-mode="folded-at-centre"]')),2)

    def test_skirts_show_folded_front_and_keep_all_cutting_pieces(self):
        for component,count,mode in [('mamian-skirt',3,'folded-front-projection'),
                                     ('ruqun-skirt',9,'front-three-gores')]:
            folder=self.build(component)
            report=json.loads((folder/'body-layout.json').read_text(encoding='utf-8'))
            self.assertEqual(len(report['right']['panels']),count)
            self.assertTrue(any(p['mode']==mode for p in report['left']['pieces']))
            self.assertFalse(report['right']['contains_body'])
            self.assertEqual(report['units'],'cm')
            self.assertEqual(report['shared_scale'],1)

    def test_mamian_releases_only_available_pleat_intake_at_hem(self):
        from .mamian_v2 import build_mamian
        from .patterns import body_from
        from training.schema import merge_defaults
        widths=[]
        for ratio in [1.4,1.8,3.0]:
            patch=self.engine.defaults('mamian-skirt')
            patch['mamian-skirt']['pleat_ruffle']['v']=ratio
            _,c=build_mamian(body_from(),merge_defaults(patch,self.engine.template))
            front=mamian_front_dimensions(c)
            self.assertAlmostEqual(front['hem_width']-front['waist_width'],c['side_flat_width']-c['side_folded_width'])
            self.assertEqual(front['door_width'],c['door_width'])
            self.assertGreater(front['hem_width'],front['waist_width'])
            widths.append(front['hem_width'])
        self.assertEqual(widths,sorted(widths))

    def test_standalone_sleeves_show_folded_half_on_body_without_changing_cutting_paths(self):
        for component in ['wide-sleeve','narrow-sleeve','pipa-sleeve']:
            with self.subTest(component=component):
                folder=self.build(component)
                report=json.loads((folder/'body-layout.json').read_text(encoding='utf-8'))
                shoulder=report['body_landmarks']['shoulder_y']
                svg=ET.parse(folder/'body-layout.svg').getroot()
                left=svg.find(tag('g')+'[@id="body-placement"]')
                pieces=left.findall(tag('g')+'[@data-mode="folded-arm-placement"]')
                self.assertEqual(len(pieces),2)
                for piece in pieces:
                    self.assertIn('clip-path',piece.attrib)
                    clip=piece.find(tag('clipPath')+'/'+tag('rect'))
                    self.assertAlmostEqual(float(clip.attrib['y']),shoulder)
                right=svg.find(tag('g')+'[@id="net-layout"]')
                original=ET.parse(folder/'preview.svg').getroot()
                self.assertEqual([p.attrib['d'] for p in right.iter(tag('path'))],
                                 [p.attrib['d'] for p in original.iter(tag('path'))])

