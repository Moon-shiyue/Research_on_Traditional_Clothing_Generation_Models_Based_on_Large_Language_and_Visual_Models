"""Structural regressions: openings, measured seam lengths and real dimensions."""
import copy
import tempfile
import unittest
from pathlib import Path
from collections import Counter
from xml.etree import ElementTree as ET

import numpy as np

from .engine import PaperEngine
from .patterns import body_from,generate_pattern
from .traditional_templates import (build_traditional,curve_for,valid_outline,
                                    validate_template,SUPPORTED)
from training.schema import merge_defaults


class TraditionalTemplateTests(unittest.TestCase):
    def setUp(self):
        self.engine=PaperEngine(model=object())
        self.body=body_from()

    def build(self,component,values=None,body=None):
        patch=self.engine.defaults(component)
        for field,value in (values or {}).items():
            patch[component][field]['v']=value
        return build_traditional(body or self.body,merge_defaults(patch,self.engine.template),component)

    def test_open_front_upper_panels_have_no_hem_bridge_and_matched_sleeves(self):
        for component in ['beizi','banbi']:
            with self.subTest(component=component):
                pattern,report=self.build(component)
                panels=pattern.pattern['panels']
                self.assertEqual(len(panels),8)
                left=curve_for(pattern,component+'_front_left')
                right=curve_for(pattern,component+'_front_right')
                self.assertAlmostEqual(left.length(),right.length())
                self.assertAlmostEqual(max(v[1] for v in panels[component+'_front_left']['vertices'])-
                    min(v[1] for v in panels[component+'_front_left']['vertices']),report['finished_length'])
                self.assertLessEqual(max(v[0] for v in panels[component+'_front_left']['vertices']),0)
                self.assertGreaterEqual(min(v[0] for v in panels[component+'_front_right']['vertices']),0)
                # An opening edge on each front runs exactly to the hem.
                for opening in report['free_edges']:
                    if 'facing attached' in opening['reason']:
                        p=panels[opening['panel']]
                        ys=[p['vertices'][i][1] for i in p['edges'][opening['edge']]['endpoints']]
                        self.assertAlmostEqual(min(ys),-report['finished_length'])
                self.assertLess(report['validation']['max_seam_length_difference_cm'],1e-8)
                seams=pattern.pattern['stitches']
                for side in ['left','right']:
                    name=component+'_sleeve_'+side
                    self.assertTrue(any({r['panel'] for r in pair}=={name} for pair in seams))

    def test_beizi_slit_is_requested_length_and_is_never_sewn_closed(self):
        pattern,report=self.build('beizi',{'slit_height':.6,'length':.75})
        self.assertAlmostEqual(report['slit_length'],.6*.75*self.body['_leg_length'])
        used={(r['panel'],r['edge']) for pair in pattern.pattern['stitches'] for r in pair}
        for item in report['free_edges']:
            if 'slit' in item['reason']:
                self.assertNotIn((item['panel'],item['edge']),used)
        with self.assertRaises(ValueError):
            self.build('beizi',{'slit_height':.9,'length':.75})

    def test_upper_sleeve_length_includes_disclosed_dropped_shoulder(self):
        for component in ['beizi','banbi']:
            for bust in [80,100,120]:
                body=body_from({'bust':bust})
                _,report=self.build(component,body=body)
                expected=self.engine.defaults(component)[component]['sleeve_length']['v']*body['arm_length']
                self.assertAlmostEqual(report['sleeve_length_from_shoulder'],expected)
                self.assertAlmostEqual(report['sleeve_length_from_body_edge']+report['dropped_shoulder_length'],expected)
                self.assertTrue(any('从人体肩点' in note for note in report['notes']))

    def test_six_gore_skirt_wraps_without_sealing_the_opening_or_ties(self):
        pattern,report=self.build('ruqun-skirt',{'hem_ratio':2.5,'waist_position':.7},body_from({'waist':80,'bust':96}))
        self.assertAlmostEqual(report['wearing_circumference_estimate'],80)
        self.assertAlmostEqual(report['overlap'],20)
        self.assertAlmostEqual(report['waistband_attachment_length'],100,places=4)
        self.assertAlmostEqual(6*report['hem_arc_each'],200,places=4)
        self.assertEqual(sum(1 for pair in pattern.pattern['stitches'] if all('gore' in r['panel'] for r in pair)),5)
        used={(r['panel'],r['edge']) for pair in pattern.pattern['stitches'] for r in pair}
        self.assertNotIn(('ruqun_gore_01',3),used)
        self.assertNotIn(('ruqun_gore_06',1),used)
        band=pattern.pattern['panels']['ruqun_waistband']
        self.assertAlmostEqual(max(v[0] for v in band['vertices']),100,places=4)
        self.assertEqual(len(pattern.pattern['panels']),9)
        for side in ['left','right']:
            tie=pattern.pattern['panels']['ruqun_tie_'+side]
            self.assertEqual(max(v[0] for v in tie['vertices']),80)
            self.assertFalse(any('gore' in r['panel'] for pair in pattern.pattern['stitches']
                if any(r['panel']=='ruqun_tie_'+side for r in pair) for r in pair))

    def test_waist_position_changes_the_disclosed_estimated_circumference(self):
        _,low=self.build('ruqun-skirt',{'waist_position':.7})
        _,middle=self.build('ruqun-skirt',{'waist_position':.85})
        _,high=self.build('ruqun-skirt',{'waist_position':.95})
        self.assertAlmostEqual(low['wearing_circumference_estimate'],self.body['waist'])
        self.assertAlmostEqual(high['wearing_circumference_estimate'],self.body['bust'])
        self.assertAlmostEqual(middle['wearing_circumference_estimate'],self.body['underbust'])
        _,changed=self.build('ruqun-skirt',{'waist_position':.85},body_from({'underbust':88}))
        self.assertAlmostEqual(changed['wearing_circumference_estimate'],88)
        self.assertNotEqual(low['waistband_attachment_length'],high['waistband_attachment_length'])

    def test_cloud_layers_share_neckline_keep_open_and_have_no_fabric_fringe(self):
        for layers in [1,2,3]:
            pattern,report=self.build('cloud-shoulder',{'layers':layers,'petal_count':4,'tassel_length':6})
            self.assertEqual(len(pattern.pattern['panels']),layers+1)
            self.assertEqual(len(report['tassels']),8)
            self.assertFalse(any('tassel' in name for name in pattern.pattern['panels']))
            for item in report['free_edges']:
                p=curve_for(pattern,item['panel'])
                self.assertGreater(p[item['edge']].length(),1)
            for layer in range(1,layers):
                a=curve_for(pattern,'cloud_layer_01')
                b=curve_for(pattern,f'cloud_layer_{layer+1:02d}')
                for index in range(49,57):
                    self.assertAlmostEqual(a[index].length(),b[index].length())
        _,no_tassel=self.build('cloud-shoulder',{'tassel_length':0})
        self.assertEqual(no_tassel['tassels'],[])

    def test_bad_geometry_and_unexpected_closed_front_are_rejected(self):
        self.assertTrue(valid_outline([[0,0],[5,0],[5,5],[0,5]]))
        self.assertFalse(valid_outline([[0,0],[5,5],[0,5],[5,0]]))
        self.assertFalse(valid_outline([[0,0],[5,0],[2,0]]))
        pattern,report=self.build('beizi')
        opens=[r for r in report['free_edges'] if 'facing attached' in r['reason']]
        refs={(r['panel'],r['edge']) for r in opens}
        pattern.pattern['stitches']=[pair for pair in pattern.pattern['stitches']
            if not any((r['panel'],r['edge']) in refs for r in pair)]
        pattern.pattern['stitches'].append([{'panel':r['panel'],'edge':r['edge']} for r in opens])
        with self.assertRaisesRegex(ValueError,'前襟'):
            validate_template(pattern,report)

    def test_round_collar_keeps_neck_empty_and_border_changes_facing_only(self):
        from matplotlib.path import Path as Polygon
        for width in [1.2,2.5,4.5]:
            pattern,report=self.build('round-collar',{'border_width':width})
            self.assertEqual(len(pattern.pattern['panels']),2)
            self.assertEqual(len(pattern.pattern['stitches']),1)
            self.assertLess(report['validation']['max_seam_length_difference_cm'],1e-8)
            for name in pattern.pattern['panels']:
                curve=curve_for(pattern,name)
                points=[(p.real,p.imag) for segment in curve for p in
                        [segment.point(t) for t in np.linspace(0,1,50,endpoint=False)]]
                self.assertFalse(Polygon(points).contains_point((0,0)))
                vertices=pattern.pattern['panels'][name]['vertices']
                self.assertAlmostEqual(abs(vertices[4][0])-abs(vertices[1][0]),width)
                self.assertAlmostEqual(vertices[3][1]-vertices[2][1],width)
                self.assertAlmostEqual(vertices[0][1]-vertices[5][1],width)
            used={(r['panel'],r['edge']) for pair in pattern.pattern['stitches'] for r in pair}
            for item in report['free_edges']:
                self.assertNotIn((item['panel'],item['edge']),used)

    def test_crossed_and_open_front_facings_have_no_overlapping_shoulder_edges(self):
        from matplotlib.path import Path as Polygon
        for component in ['cross-collar','duijin-collar']:
            for width in [1.5,3.,5.]:
                with self.subTest(component=component,width=width):
                    key='border_width' if component=='cross-collar' else 'placket_width'
                    pattern,report=self.build(component,{key:width})
                    self.assertTrue(report['validation']['sampled_outline_valid'])
                    self.assertLess(report['validation']['max_seam_length_difference_cm'],1e-8)
                    for name in pattern.pattern['panels']:
                        curve=curve_for(pattern,name)
                        # A repeated shoulder edge or filled neckline must not
                        # turn the upper central neckline into cloth.
                        points=[(p.real,p.imag) for segment in curve for p in
                            [segment.point(t) for t in np.linspace(0,1,50,endpoint=False)]]
                        if not name.endswith('_back'):
                            self.assertFalse(Polygon(points).contains_point((0.,1.)))
                        self.assertTrue(all(segment.length()>1e-6 for segment in curve))
                    if component=='cross-collar':
                        self.assertEqual(len(pattern.pattern['stitches']),2)
                    else:
                        self.assertEqual(pattern.pattern['stitches'],[])

    def test_export_records_version_and_simple_preview_keeps_all_real_pieces(self):
        with tempfile.TemporaryDirectory() as temp:
            for component in SUPPORTED:
                folder=Path(temp)/component
                result=generate_pattern(self.engine.defaults(component),self.engine.template,None,folder)
                self.assertTrue((folder/'assembly.json').is_file())
                svg=ET.parse(folder/'preview.svg')
                ns='{http://www.w3.org/2000/svg}'
                self.assertEqual(len(svg.findall('.//'+ns+'g')),result['panel_count'])
                self.assertEqual(svg.findall('.//'+ns+'text'),[])
                self.assertFalse(result['is_self_intersecting'])


if __name__=='__main__':
    unittest.main()
