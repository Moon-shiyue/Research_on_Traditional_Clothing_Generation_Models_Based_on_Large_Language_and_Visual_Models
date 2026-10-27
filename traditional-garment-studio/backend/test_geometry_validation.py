import copy
import unittest

from .engine import PaperEngine
from .patterns import build_geometry
from .geometry_validation import validate_geometry


class GeometryValidationTests(unittest.TestCase):
    def setUp(self):
        self.engine=PaperEngine(model=object())

    def geometry(self,component):
        return build_geometry(self.engine.defaults(component),self.engine.template,{})

    def test_mamian_attachment_is_compared_after_validated_isometric_folding(self):
        pattern,_,construction,assembly,_,validation=self.geometry('mamian-skirt')
        self.assertEqual(validation['folded_seams_checked'],2)
        self.assertLess(validation['max_seam_length_difference_cm'],1e-6)
        broken=copy.deepcopy(construction)
        broken['fold_map'][1][1]+=1
        with self.assertRaisesRegex(ValueError,'褶位收量'):
            validate_geometry(pattern,broken,assembly)

    def test_bad_seam_reference_and_length_fail_before_export(self):
        pattern,_,construction,assembly,_,_=self.geometry('beizi')
        pattern.pattern['stitches'][0][0]['edge']=999
        with self.assertRaisesRegex(ValueError,'引用无效'):
            validate_geometry(pattern,construction,assembly)
        pattern,_,construction,assembly,_,_=self.geometry('beizi')
        pair=pattern.pattern['stitches'][0]
        pair[0]={'panel':'beizi_back','edge':2}
        with self.assertRaisesRegex(ValueError,'边长不匹配'):
            validate_geometry(pattern,construction,assembly)

    def test_zero_length_and_crossed_contours_fail_before_export(self):
        for vertices in [ [[0,0],[0,0],[20,-20],[0,-20]],
                          [[0,0],[20,-20],[20,0],[0,-20]] ]:
            pattern,_,construction,assembly,_,_=self.geometry('mamian-skirt')
            name='mamian_width_a'
            pattern.pattern['panels'][name]['vertices']=vertices
            pattern.pattern['panels'][name]['edges']=[{'endpoints':[i,(i+1)%4]} for i in range(4)]
            with self.assertRaises(ValueError):
                validate_geometry(pattern,construction,assembly)

    def test_unexpected_duplicate_seam_is_rejected_even_when_lengths_match(self):
        pattern,_,construction,assembly,_,_=self.geometry('round-collar')
        pattern.pattern['stitches'].append(copy.deepcopy(pattern.pattern['stitches'][0]))
        with self.assertRaisesRegex(ValueError,'未经声明'):
            validate_geometry(pattern,construction,assembly)

    def test_standalone_sleeves_close_only_matching_underarm_edges_and_leave_openings_free(self):
        for component in ['wide-sleeve','narrow-sleeve','pipa-sleeve']:
            with self.subTest(component=component):
                pattern,_,_,_,notes,validation=self.geometry(component)
                self.assertEqual(len(pattern.pattern['stitches']),4)
                self.assertLess(validation['max_seam_length_difference_cm'],1e-6)
                for pair in pattern.pattern['stitches']:
                    self.assertEqual(pair[0]['panel'],pair[1]['panel'])
                    for ref in pair:
                        edge=pattern.pattern['panels'][ref['panel']]['edges'][ref['edge']]
                        self.assertNotIn(edge['label'],['armhole','cuff'])
                marks=pattern.pattern['drafting_marks']
                self.assertEqual(len(marks),2)
                for mark in marks:
                    self.assertEqual(mark['kind'],'fold')
                    panel=pattern.pattern['panels'][mark['panel']]
                    for label,key in [('armhole','start'),('cuff','end')]:
                        edge=next(e for e in panel['edges'] if e['label']==label)
                        vertices=[panel['vertices'][i] for i in edge['endpoints']]
                        self.assertEqual(mark[key],[(vertices[0][i]+vertices[1][i])/2 for i in range(2)])
                self.assertTrue(any('袖根' in note for note in notes))


if __name__=='__main__':
    unittest.main()
