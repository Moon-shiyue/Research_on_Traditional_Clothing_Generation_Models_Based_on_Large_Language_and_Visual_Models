"""Style observations must change actual exported pieces, with user overrides intact."""
import io
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from fastapi.testclient import TestClient
from PIL import Image

from .app import create_app
from .engine import PaperEngine
from .patterns import body_from
from .style_features import visual_parameters
from training.common import read_jsonl
from .settings import GARMENT_ROOT


class NoInference:
    def image(self, *args):
        raise AssertionError('Each observation must be explicitly mocked')

    def text(self, *args):
        raise AssertionError('Explicit supported styles need no native model')


class StyleFeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = PaperEngine(NoInference())
        self.client = TestClient(create_app(self.engine, Path(self.temp.name)))
        self.addCleanup(self.client.close)
        self.headers = {'X-Session-Id': str(uuid.uuid4())}

    def parse(self, text='', image=None, proposal=None):
        response = self.client.post('/api/v1/parse', headers=self.headers,
            json={'text': text, 'image': image, 'image_proposal_id': proposal,'scope':'component'})
        self.assertEqual(response.status_code, 202, response.text)
        task = self.client.get('/api/v1/tasks/' + response.json()['task_id'], headers=self.headers).json()
        self.assertEqual(task['status'], 'done', task)
        return task['result']

    def image_request(self, component, features, text=''):
        buffer = io.BytesIO()
        Image.new('RGB', (32, 48)).save(buffer, format='PNG')
        upload = self.client.post('/api/v1/upload/image', headers=self.headers,
            files={'file': ('anonymous.png', buffer.getvalue(), 'image/png')}).json()['image_id']
        with patch.object(self.engine.model, 'image', return_value={
                'component': component, 'reason': 'Mock visible structure', 'features': features}):
            return self.parse(text, upload)

    def confirm(self, component, features, extra=''):
        suggested = self.image_request(component, features)
        self.assertEqual(suggested['status'], 'needs_input', suggested)
        return self.parse(suggested['suggested_text'] + extra,
            proposal=suggested['image_proposal_id'])

    def test_image_connection_failure_can_retry_the_same_uploaded_reference(self):
        buffer=io.BytesIO()
        Image.new('RGB',(32,48)).save(buffer,format='PNG')
        image=self.client.post('/api/v1/upload/image',headers=self.headers,
            files={'file':('anonymous.png',buffer.getvalue(),'image/png')}).json()['image_id']
        with patch.object(self.engine.model,'image',side_effect=RuntimeError('Temporary connection failure')):
            first=self.parse('衣长100cm',image)
        self.assertTrue(first['image_retry_available'])
        self.assertIsNone(first['pattern'])
        with patch.object(self.engine.model,'image',return_value={
                'component':'beizi','reason':'Mock visible structure','features':{'sleeve_shape':'wide'}}):
            second=self.parse('衣长100cm',image)
        self.assertNotIn('image_retry_available',second)
        ready=self.parse(second['suggested_text'],proposal=second['image_proposal_id'])
        self.assertEqual(ready['status'],'generated',ready)
        self.assertEqual(ready['pattern']['absolute_lengths_cm'],{'beizi.length':100})

    def test_image_text_mismatch_or_uncertain_structure_never_generates_text_defaults(self):
        previous=self.parse('云肩，无垂须')['pattern']
        for component in ['ruqun-skirt',None]:
            with self.subTest(component=component):
                result=self.image_request(component,{},text='马面裙，裙长95cm，腰围88cm')
                self.assertEqual(result['status'],'needs_input',result)
                self.assertEqual(result['pattern'],previous)
                self.assertNotIn('image_proposal_id',result)
                body=self.client.get('/api/v1/body/params',headers=self.headers).json()['params']
                self.assertNotEqual(body['waist'],88)

    def test_named_component_does_not_hide_failed_image_recognition(self):
        previous=self.parse('云肩，无垂须')['pattern']
        buffer=io.BytesIO();Image.new('RGB',(32,48)).save(buffer,format='PNG')
        image=self.client.post('/api/v1/upload/image',headers=self.headers,
            files={'file':('anonymous.png',buffer.getvalue(),'image/png')}).json()['image_id']
        with patch.object(self.engine.model,'image',side_effect=RuntimeError('Temporary test outage')):
            failed=self.parse('马面裙，裙长95cm，腰围88cm',image)
        self.assertEqual(failed['status'],'needs_input',failed)
        self.assertTrue(failed['image_retry_available'])
        self.assertEqual(failed['pattern'],previous)

    def test_matching_named_image_keeps_explicit_dimensions_and_visible_style(self):
        result=self.image_request('beizi',{'sleeve_shape':'wide','upper_front':'open'},
            text='褙子，衣长一百一十厘米，袖口整围四十八厘米')
        self.assertEqual(result['status'],'generated',result)
        self.assertEqual(result['pattern']['absolute_lengths_cm'],{'beizi.length':110})
        self.assertEqual(result['design_params']['beizi']['sleeve_cuff_width']['v'],48)
        self.assertIn('reference_image_url',result['pattern'])

    def test_named_component_focus_is_sent_to_visual_model_without_other_candidates(self):
        buffer=io.BytesIO();Image.new('RGB',(32,48)).save(buffer,format='PNG')
        image=self.client.post('/api/v1/upload/image',headers=self.headers,
            files={'file':('outfit.png',buffer.getvalue(),'image/png')}).json()['image_id']
        with patch.object(self.engine.model,'image',return_value={
                'component':'banbi','reason':'Controlled visible open half-sleeve upper',
                'features':{'upper_front':'open'}}) as infer:
            result=self.parse('只做半臂，衣长50cm',image)
        self.assertEqual(result['status'],'generated',result)
        self.assertEqual(infer.call_args.args[1],{'banbi':'半臂'})

    def bundle(self):
        response = self.client.get('/api/v1/download', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        with ZipFile(io.BytesIO(response.content)) as archive:
            self.assertIsNone(archive.testzip())
            return {name: json.loads(archive.read(name)) for name in
                    ['pattern.json', 'design.json', 'assembly.json', 'metadata.json', 'body.json']}

    def test_beizi_image_width_changes_sleeves_without_changing_body_or_seams(self):
        exported = []
        for shape, width in [('narrow', 22), ('wide', 60)]:
            result = self.confirm('beizi', {'sleeve_shape': shape, 'upper_front': 'open'})
            self.assertEqual(result['status'], 'generated', result)
            self.assertEqual(result['design_params']['beizi']['sleeve_cuff_width']['v'], width)
            self.assertEqual(result['pattern']['parameter_sources']['beizi.sleeve_cuff_width'], 'image_style_default')
            data = self.bundle()
            self.assertEqual(data['assembly.json']['sleeve_opening_circumference'], width)
            self.assertLess(data['assembly.json']['validation']['max_seam_length_difference_cm'], 1e-8)
            exported.append(data['pattern.json']['panels'])
        self.assertEqual(exported[0]['beizi_back'], exported[1]['beizi_back'])
        self.assertEqual(exported[0]['beizi_front_left'], exported[1]['beizi_front_left'])
        self.assertNotEqual(exported[0]['beizi_sleeve_left'], exported[1]['beizi_sleeve_left'])

    def test_cloud_visible_layers_and_tassels_reach_actual_cut_list(self):
        for layers in (1, 2, 3):
            with self.subTest(layers=layers):
                result = self.confirm('cloud-shoulder', {'cloud_layers': layers, 'tassels': 'absent'})
                self.assertEqual(result['status'], 'generated', result)
                data = self.bundle()
                self.assertEqual(len(data['pattern.json']['panels']), layers + 1)
                self.assertEqual(data['assembly.json']['layers'], layers)
                self.assertEqual(data['assembly.json']['tassels'], [])
                self.assertEqual(data['metadata.json']['parameter_sources']['cloud-shoulder.layers'], 'image_observation')

    def test_unknown_features_keep_disclosed_defaults(self):
        for component, field, value in [('beizi', 'sleeve_cuff_width', 22),
                ('cloud-shoulder', 'layers', 2)]:
            result = self.confirm(component, {'sleeve_shape': 'unclear', 'cloud_layers': None, 'tassels': 'unclear'})
            self.assertEqual(result['design_params'][component][field]['v'], value)
            self.assertIn(component + '.' + field, result['pattern']['default_fields'])

    def test_explicit_dimensions_override_visible_style_including_image_plus_text(self):
        result = self.confirm('beizi', {'sleeve_shape': 'wide'}, '，袖口整围32cm')
        self.assertEqual(result['design_params']['beizi']['sleeve_cuff_width']['v'], 32)
        self.assertEqual(result['pattern']['parameter_sources']['beizi.sleeve_cuff_width'], 'text')
        result = self.image_request('beizi', {'sleeve_shape': 'wide', 'upper_front': 'open'}, '褙子，衣长100cm')
        self.assertEqual(result['status'], 'generated', result)
        self.assertEqual(result['pattern']['assembly']['sleeve_opening_circumference'], 60)
        self.assertAlmostEqual(result['pattern']['assembly']['finished_length'], 100, places=5)
        result = self.confirm('cloud-shoulder', {'cloud_layers': 3, 'tassels': 'absent'}, '，层数1，垂须6cm')
        self.assertEqual(result['design_params']['cloud-shoulder']['layers']['v'], 1)
        self.assertEqual(result['design_params']['cloud-shoulder']['tassel_length']['v'], 6)

    def test_body_and_manual_updates_preserve_confirmed_style_and_export_sources(self):
        self.confirm('beizi', {'sleeve_shape': 'wide'})
        before = self.bundle()
        response = self.client.put('/api/v1/body/params', headers=self.headers, json={'path': ['bust'], 'value': 100})
        self.assertEqual(response.status_code, 200, response.text)
        after = self.bundle()
        self.assertEqual(after['assembly.json']['sleeve_opening_circumference'], 60)
        self.assertNotEqual(before['pattern.json']['panels']['beizi_back'], after['pattern.json']['panels']['beizi_back'])
        self.assertEqual(after['metadata.json']['parameter_sources']['beizi.sleeve_cuff_width'], 'image_style_default')
        response = self.client.put('/api/v1/design/params', headers=self.headers,
            json={'path': ['beizi', 'sleeve_cuff_width'], 'value': 40})
        self.assertEqual(response.status_code, 200, response.text)
        final = self.bundle()
        self.assertEqual(final['assembly.json']['sleeve_opening_circumference'], 40)
        self.assertEqual(final['metadata.json']['parameter_sources']['beizi.sleeve_cuff_width'], 'manual')

    def test_text_styles_are_deterministic_and_numerical_values_take_priority(self):
        for text, field, value in [('对襟宽袖褙子', 'sleeve_cuff_width', 60),
                ('窄袖褙子', 'sleeve_cuff_width', 22), ('宽袖褙子，袖口整围36cm', 'sleeve_cuff_width', 36)]:
            result = self.parse(text)
            self.assertEqual(result['status'], 'generated', result)
            self.assertEqual(result['design_params']['beizi'][field]['v'], value)
        result = self.parse('单层云肩，无流苏')
        self.assertEqual(result['pattern']['assembly']['layers'], 1)
        self.assertEqual(result['pattern']['assembly']['tassels'], [])

    def test_excluded_sleeve_and_cloud_layer_are_not_positive_style_requests(self):
        for text,section,field,value in [
                ('褙子，不要窄袖，采用广袖','beizi','sleeve_cuff_width',60),
                ('褙子，不要广袖，采用窄袖','beizi','sleeve_cuff_width',22),
                ('褙子，不是窄袖而是广袖','beizi','sleeve_cuff_width',60),
                ('褙子，不要琵琶袖，采用窄袖','beizi','sleeve_cuff_width',22),
                ('褙子，不用窄袖，采用广袖','beizi','sleeve_cuff_width',60),
                ('褙子，不采用窄袖，采用广袖','beizi','sleeve_cuff_width',60),
                ('云肩，不要双层，三层，无垂须','cloud-shoulder','layers',3)]:
            with self.subTest(text=text):
                result=self.parse(text)
                self.assertEqual(result['status'],'generated',result)
                self.assertEqual(result['design_params'][section][field]['v'],value)
        for text in ['褙子，不要窄袖','半臂，不要宽袖，不要窄袖','褙子，不要宋代']:
            self.assertEqual(self.parse(text)['status'],'needs_input')

    def test_unsupported_upper_variants_never_silently_become_open_front_straight_sleeves(self):
        for features in [{'upper_front': 'crossed'}, {'upper_front': 'closed'},
                         {'upper_front':'unclear'}, {'sleeve_shape': 'pipa'}]:
            result = self.image_request('beizi', features)
            self.assertEqual(result['status'], 'needs_input')
            self.assertNotIn('suggested_component', result)
            self.assertIsNone(result['pattern'])
        result = self.parse('琵琶袖褙子')
        self.assertEqual(result['status'], 'needs_input')

    def test_broad_cape_never_creates_a_cloud_or_round_band_proposal(self):
        before=self.parse('三层云肩，六云头，无垂须')['pattern']
        for component in ['cloud-shoulder','round-collar']:
            result=self.image_request(component,{'neckwear_shape':'broad-cape','cloud_layers':1})
            self.assertEqual(result['status'],'needs_input')
            self.assertEqual(result['pattern'],before)
            self.assertNotIn('image_proposal_id',result)
            self.assertIn('宽幅披领',result['reply'])

    def test_visible_unsupported_cloud_layer_count_does_not_become_two_layer_default(self):
        previous=self.parse('云肩，层数一，无穗须')['pattern']
        for layers in [4,5,8]:
            result=self.image_request('cloud-shoulder',{'cloud_layers':layers,'tassels':'absent'})
            self.assertEqual(result['status'],'needs_input',result)
            self.assertNotIn('image_proposal_id',result)
            self.assertEqual(result['pattern'],previous)

    def test_banbi_and_ruqun_observations_change_real_dimensions(self):
        result = self.confirm('banbi', {'sleeve_shape': 'wide', 'upper_front': 'open'})
        self.assertEqual(result['pattern']['assembly']['sleeve_opening_circumference'], 48)
        result = self.confirm('ruqun-skirt', {'hem_shape': 'wide'})
        self.assertEqual(result['design_params']['ruqun-skirt']['hem_ratio']['v'], 3.5)
        data = self.bundle()
        self.assertAlmostEqual(data['assembly.json']['hem_arc_each'] * 6 /
            data['assembly.json']['wearing_circumference_estimate'], 3.5, places=5)

    def test_native_v1_beizi_patch_still_valid_with_additional_application_field(self):
        target = next(row['target'] for row in read_jsonl(GARMENT_ROOT/'data/training_v1/val.jsonl')
            if row['component'] == 'beizi')
        with patch.object(self.engine.model, 'text', return_value=target):
            intent = self.engine.interpret('褙子，请参考常服外衣设计', None, None)
        self.assertEqual(intent['status'], 'ready', intent)
        self.assertEqual(intent['patch']['beizi']['length'], target['beizi']['length'])
        self.assertEqual(intent['patch']['beizi']['sleeve_cuff_width']['v'], 22)
        self.assertNotIn('sleeve_cuff_width', self.engine.model_schema['components']['beizi']['fields'])

    def test_explicit_cm_length_survives_height_change_while_relative_length_scales(self):
        self.parse('褙子，衣长100cm，袖长48cm，袖口整围60cm')
        response = self.client.put('/api/v1/body/params', headers=self.headers,
            json={'path': ['height'], 'value': 180})
        self.assertEqual(response.status_code, 200, response.text)
        data = self.bundle()
        self.assertAlmostEqual(data['assembly.json']['finished_length'], 100, places=5)
        self.assertEqual(data['metadata.json']['absolute_lengths_cm'], {'beizi.length':100, 'beizi.sleeve_length':48})
        self.assertAlmostEqual(data['design.json']['beizi']['sleeve_length']['v'] * data['body.json']['arm_length'], 48, places=5)
        self.parse('褙子，length=1，sleeve_length=0.9')
        before = self.bundle()['assembly.json']['finished_length']
        response = self.client.put('/api/v1/body/params', headers=self.headers,
            json={'path': ['height'], 'value': 175})
        self.assertEqual(response.status_code, 200, response.text)
        after = self.bundle()
        self.assertNotEqual(before, after['assembly.json']['finished_length'])
        self.assertEqual(after['metadata.json']['absolute_lengths_cm'], {})

    def test_cm_edit_is_validated_atomic_and_native_edit_clears_absolute_constraint(self):
        self.parse('褙子，衣长95cm')
        response = self.client.put('/api/v1/design/params', headers=self.headers,
            json={'path': ['beizi','length'], 'value':100, 'unit':'cm'})
        self.assertEqual(response.status_code, 200, response.text)
        before = self.bundle()
        self.assertAlmostEqual(before['assembly.json']['finished_length'],100,places=5)
        for payload in [
            {'path':['beizi','length'],'value':500,'unit':'cm'},
            {'path':['beizi','length'],'value':True,'unit':'cm'},
            {'path':['beizi','slit_height'],'value':30,'unit':'cm'},
            {'path':['beizi','length'],'value':10,'unit':'inches'}]:
            response = self.client.put('/api/v1/design/params', headers=self.headers, json=payload)
            self.assertEqual(response.status_code,422,response.text)
            self.assertEqual(self.bundle(), before)
        response = self.client.put('/api/v1/design/params', headers=self.headers,
            json={'path':['beizi','length'],'value':1,'unit':'native'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertNotIn('beizi.length',self.bundle()['metadata.json']['absolute_lengths_cm'])

    def test_image_suggested_95cm_is_disclosed_default_and_explicit_override_stays_text(self):
        for text,cm,source in [(None,95,'image_style_default'),('襦裙，裙长100cm',100,'text')]:
            suggested=self.image_request('ruqun-skirt',{'length':'full','hem_shape':'moderate'})
            result=self.parse(text or suggested['suggested_text'],proposal=suggested['image_proposal_id'])
            self.assertEqual(result['status'],'generated',result)
            metadata=self.bundle()['metadata.json']
            self.assertEqual(metadata['absolute_lengths_cm']['ruqun-skirt.length'],cm)
            self.assertEqual(metadata['parameter_sources']['ruqun-skirt.length'],source)

    def test_long_beizi_centimetres_are_not_limited_by_frozen_training_vocabulary(self):
        result=self.parse('褙子，衣长110.5cm，袖长48cm')
        self.assertEqual(result['status'],'generated',result)
        self.assertGreater(result['design_params']['beizi']['length']['v'],1.25)
        response=self.client.put('/api/v1/body/params',headers=self.headers,
            json={'path':['height'],'value':170})
        self.assertEqual(response.status_code,200,response.text)
        exported=self.bundle()
        self.assertAlmostEqual(exported['assembly.json']['finished_length'],110.5,places=5)
        self.assertEqual(exported['metadata.json']['absolute_lengths_cm']['beizi.length'],110.5)
        self.assertEqual(self.engine.model_schema['components']['beizi']['fields']['length']['bounds'],[.75,1.25])


if __name__ == '__main__':
    unittest.main()
