"""A valid skirt must not conceal an omitted upper or a second outfit."""
import copy
from pathlib import Path
import unittest

from .engine import PaperEngine
from .outfits import interpret_outfit_image
from .scene_inventory import coverage_issue, valid_scene
from .vision_fixtures import accounted_scene


class SceneInventoryTests(unittest.TestCase):
    def setUp(self):
        self.scene = accounted_scene([
            {'component':'cross-upper','reason':'交领短上衣','features':{'upper_front':'crossed'}},
            {'component':'ruqun-skirt','reason':'连续软褶下裙','features':{}}])
        owner = self
        class Vision:
            def image_outfit(self, *_): return copy.deepcopy(owner.scene)
        self.engine = PaperEngine(Vision())

    def proposal(self):
        return interpret_outfit_image(self.engine, '', Path('unused'), {})

    def refused(self):
        result = self.proposal()
        self.assertEqual(result['status'], 'needs_input')
        self.assertNotIn('suggested_outfit', result)
        self.assertNotIn('suggested_component', result)
        self.assertNotIn('opening_choices', result)
        return result

    def test_same_outfit_multiple_views_and_single_garment_can_proceed(self):
        self.assertTrue(self.proposal()['suggested_outfit'])
        self.scene = accounted_scene([{'component':'cross-robe','reason':'整件交领袍',
                                      'features':{'upper_front':'crossed'}}])
        self.assertEqual(self.proposal()['suggested_component'], 'cross-robe')

    def test_omitted_upper_cannot_become_a_skirt_only_proposal(self):
        self.scene['observations'].pop(0)
        self.assertIn('cross-upper', self.refused()['reply'])

    def test_different_outfits_cannot_be_combined_even_when_types_form_a_supported_pair(self):
        self.scene['single_outfit'] = False
        self.assertIn('裁出一套', self.refused()['reply'])

    def test_unaccounted_scene_is_not_complete_even_with_equal_counts(self):
        self.scene['all_garments_accounted'] = False
        self.assertIn('清单', self.refused()['reply'])

    def test_duplicate_indices_cannot_hide_the_missing_member(self):
        self.scene['observations'][1]['garment_index'] = 0
        self.assertIn('ruqun-skirt', self.refused()['reply'])

    def test_additional_unsupported_cloth_is_not_dropped_to_fit_supported_ensemble(self):
        self.scene['visible_garments'].append('披帛')
        self.assertIn('披帛', self.refused()['reply'])
        self.scene['observations'].append({'component':None,'reason':'披帛无模板',
                                          'features':{},'garment_index':2})
        self.assertIn('不会只输出其它部分', self.refused()['reply'])

    def test_invalid_or_missing_metadata_never_defaults_to_complete(self):
        original=copy.deepcopy(self.scene)
        for key in ['visible_garments','single_outfit','all_garments_accounted']:
            self.scene=copy.deepcopy(original);self.scene.pop(key)
            self.assertFalse(valid_scene(self.scene));self.refused()
        for key,value in [('single_outfit','true'),('all_garments_accounted',1),
                          ('visible_garments',[]),('visible_garments',[' ']),
                          ('observations',[{'garment_index':True}]),
                          ('observations',[{'garment_index':8}]),('observations',[None])]:
            self.scene=dict(original,**{key:value})
            self.assertFalse(valid_scene(self.scene));self.refused()
        self.assertTrue(coverage_issue(None))


if __name__=='__main__': unittest.main()
