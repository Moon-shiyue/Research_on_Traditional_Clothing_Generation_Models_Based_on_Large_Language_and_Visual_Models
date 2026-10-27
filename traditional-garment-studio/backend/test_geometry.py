"""Regression checks for real normals and skirt waistband connections."""
import unittest
import warnings
import numpy as np
from scipy.spatial.transform import Rotation
from .engine import PaperEngine
import pygarment as pyg
from .patterns import body_from
from training.schema import merge_defaults
from traditional_ext.mamian_skirt import MamianPanel
from .mamian_v2 import build_mamian
from collections import Counter
from traditional_ext.skirts_extra import RuqunSkirt


class GeometryTests(unittest.TestCase):
    def test_rotated_rectangles_have_finite_unit_normals(self):
        panel = MamianPanel('rectangle', 28, 70)
        with warnings.catch_warnings():
            warnings.simplefilter('error', RuntimeWarning)
            first = panel.norm()
            self.assertTrue(np.isfinite(first).all())
            self.assertAlmostEqual(np.linalg.norm(first), 1)
            panel.rotation = Rotation.from_euler('xyz', [23, 51, 17], degrees=True)
            np.testing.assert_allclose(panel.norm(), panel.rotation.apply(first), atol=1e-12)

    def test_degenerate_rectangle_is_rejected(self):
        panel = pyg.Panel('flat_line')
        panel.edges.append(pyg.Edge([0, 0], [28, 0]))
        panel.edges.append(pyg.Edge([28, 0], [14, 0]))
        panel.edges.close_loop()
        with self.assertRaises(ValueError):
            panel.norm()

    def test_mamian_overlap_and_fold_geometry(self):
        engine = PaperEngine()
        for ruffle in [1.4, 1.8, 2.4]:
            patch = engine.defaults('mamian-skirt')
            patch['mamian-skirt']['pleat_ruffle']['v'] = ruffle
            pattern,c = build_mamian(body_from(),merge_defaults(patch,engine.template))
            # Two folded skirt widths overlap at both doors to cover the circumference.
            self.assertAlmostEqual(2*c['folded_width_each']-2*c['door_width'],c['wearing_circumference'])
            self.assertAlmostEqual(2*c['folded_width_each']-c['door_width'],c['waistband_attachment_length'])
            points=c['fold_map']
            self.assertAlmostEqual(points[-1][0]-points[0][0],c['side_flat_width'])
            self.assertAlmostEqual(points[-1][1]-points[0][1],c['side_folded_width'])
            for a,b in zip(points,points[1:]):
                self.assertAlmostEqual(b[0]-a[0],abs(b[1]-a[1]))
                self.assertGreater(b[0],a[0])
            refs=Counter()
            for seam in pattern.pattern['stitches']:
                self.assertEqual(seam[0]['panel'],'mamian_waistband')
                self.assertIn(seam[1]['edge'],[0,1,2], 'Long skirt-opening edges must remain free')
                refs.update([(r['panel'],r['edge']) for r in seam])
            self.assertEqual({k:v for k,v in refs.items() if v>1},{('mamian_waistband',3):2})

    def test_mamian_known_dimensions_and_impossible_doors(self):
        engine=PaperEngine()
        design=merge_defaults(engine.defaults('mamian-skirt'),engine.template)
        design['mamian-skirt']['mamian_width']['v']=20
        design['mamian-skirt']['pleat_ruffle']['v']=2
        _,c=build_mamian(body_from({'waist':80,'hips':80}),design)
        self.assertEqual(c['flat_width_each'],80)
        self.assertEqual(c['folded_width_each'],60)
        self.assertEqual(c['waistband_attachment_length'],100)
        design['mamian-skirt']['mamian_width']['v']=41
        with self.assertRaises(ValueError):
            build_mamian(body_from({'waist':80,'hips':80}),design)

    def test_ruqun_waist_seam_leaves_ties_free(self):
        engine = PaperEngine()
        skirt = RuqunSkirt(body_from(), merge_defaults(engine.defaults('ruqun-skirt'), engine.template))
        rule = skirt.stitching_rules[0]
        self.assertAlmostEqual(sum(rule.int1.projecting_lengths()), skirt.waist_circ)
        self.assertAlmostEqual(sum(rule.int2.projecting_lengths()), skirt.waist_circ)
        self.assertEqual({p.name for p in rule.int2.panel}, {'ruqun_front','ruqun_back'})
        self.assertTrue(all(e.start[0] >= 0 and e.end[0] <= skirt.waist_circ for e in rule.int1.edges))
        refs = [(r['panel'], r['edge']) for stitch in skirt.assembly().pattern['stitches'] for r in stitch[:2]]
        self.assertEqual(len(refs),len(set(refs)))


if __name__ == '__main__':
    unittest.main()
