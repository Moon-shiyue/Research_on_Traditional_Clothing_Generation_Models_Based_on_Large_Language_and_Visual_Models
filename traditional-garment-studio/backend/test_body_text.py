import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch
from zipfile import ZipFile

from fastapi.testclient import TestClient

from .app import create_app
from .body_text import body_measurements
from .engine import PaperEngine


class BodyTextTests(unittest.TestCase):
    def test_body_preparation_keeps_empty_canvas_and_survives_restart_before_first_design(self):
        for key,value in [('height',170),('waist',80)]:
            response=self.client.put('/api/v1/body/params',headers=self.headers,json={'path':[key],'value':value})
            self.assertEqual(response.status_code,200,response.text)
        self.assertIsNone(self.client.get('/api/v1/pattern',headers=self.headers).json()['svg_url'])
        self.assertEqual(self.client.get('/api/v1/design/history',headers=self.headers).json()['items'],[])
        self.client=TestClient(create_app(self.engine,Path(self.temp.name)))
        self.addCleanup(self.client.close)
        body=self.client.get('/api/v1/body/params',headers=self.headers).json()
        self.assertEqual(body['params']['height'],170)
        self.assertEqual(body['params']['waist'],80)
        self.assertEqual(body['parameter_sources'],{'height':'manual','waist':'manual'})
        self.assertIsNone(self.client.get('/api/v1/pattern',headers=self.headers).json()['svg_url'])
        result=self.parse('唐代半臂，衣长50cm，常服')
        self.assertEqual(result['status'],'generated',result)
        self.assertEqual(result['pattern']['panel_count'],8)
        self.assertEqual(result['body_params']['params']['height'],170)
        self.assertEqual(len(self.client.get('/api/v1/design/history',headers=self.headers).json()['items']),1)
        self.client.put('/api/v1/body/params',headers=self.headers,json={'path':['height'],'value':175})
        self.client=TestClient(create_app(self.engine,Path(self.temp.name)))
        self.addCleanup(self.client.close)
        self.assertEqual(self.client.get('/api/v1/body/params',headers=self.headers).json()['params']['height'],175)

    def test_invalid_body_draft_falls_back_without_creating_a_garment(self):
        self.client.put('/api/v1/body/params',headers=self.headers,json={'path':['height'],'value':170})
        parent=Path(self.temp.name)/'patterns'/self.headers['X-Session-Id']
        draft=parent/'body-draft.json'
        self.assertTrue(draft.is_file())
        data=json.loads(draft.read_text(encoding='utf-8'))
        data['body']['height']=-1
        draft.write_text(json.dumps(data),encoding='utf-8')
        self.client=TestClient(create_app(self.engine,Path(self.temp.name)))
        self.addCleanup(self.client.close)
        self.assertGreater(self.client.get('/api/v1/body/params',headers=self.headers).json()['params']['height'],100)
        self.assertIsNone(self.client.get('/api/v1/pattern',headers=self.headers).json()['svg_url'])

    def test_explicit_body_units_duplicates_and_reference_ratios(self):
        self.assertEqual(body_measurements('身高1.70m，胸围900mm，腰围70cm，臀围95，肩宽36，臂长54厘米'),
            {'height':170,'bust':90,'waist':70,'hips':95,'shoulder_w':36,'arm_length':54})
        self.assertEqual(body_measurements('腰围80cm，腰围800mm'),{'waist':80})
        self.assertEqual(body_measurements('袖长为臂长的0.9倍，衣长为腿长1倍'),{})
        self.assertEqual(body_measurements('袖长为臂长0.9倍'),{})
        for text in ['腰围80cm，腰围85cm','腰围30英寸','身高1米7','身高一米七',
                     '成衣胸围100cm','服装腰围90cm','上臂长30cm']:
            with self.subTest(text=text),self.assertRaises(ValueError):
                body_measurements(text)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine=PaperEngine(model=object())
        self.client=TestClient(create_app(self.engine,Path(self.temp.name)))
        self.addCleanup(self.client.close)
        self.headers={'X-Session-Id':str(uuid.uuid4())}

    def parse(self,text):
        response=self.client.post('/api/v1/parse',headers=self.headers,json={'text':text})
        self.assertEqual(response.status_code,202,response.text)
        return self.client.get('/api/v1/tasks/'+response.json()['task_id'],headers=self.headers).json()['result']

    def exported(self):
        response=self.client.get('/api/v1/download',headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        with ZipFile(io.BytesIO(response.content)) as archive:
            return {name:json.loads(archive.read(name+'.json')) for name in ['body','design','metadata']}

    def test_body_text_applies_before_ratio_conversion_and_is_exported_with_provenance(self):
        result=self.parse('马面裙，身高170cm，腰围80cm，臀围95cm，裙长95cm')
        self.assertEqual(result['status'],'generated',result)
        self.assertIn('腰围80cm',result['reply'])
        data=self.exported()
        self.assertEqual(data['body']['height'],170)
        self.assertEqual(data['body']['waist'],80)
        self.assertEqual(data['body']['hips'],95)
        self.assertAlmostEqual(data['design']['mamian-skirt']['length']['v']*data['body']['_leg_length'],95,places=5)
        self.assertEqual(data['metadata']['body_parameter_sources'],{'height':'text','waist':'text','hips':'text'})
        self.assertEqual(result['body_params']['parameter_sources'],data['metadata']['body_parameter_sources'])
        response=self.client.put('/api/v1/body/params',headers=self.headers,json={'path':['waist'],'value':82})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.exported()['metadata']['body_parameter_sources']['waist'],'manual')
        self.client.post('/api/v1/design/default',headers=self.headers)
        self.assertEqual(self.exported()['body']['waist'],82)

    def test_invalid_body_text_cannot_mutate_previous_body(self):
        self.parse('褙子，身高170cm，腰围80cm，衣长100cm')
        before=self.client.get('/api/v1/body/params',headers=self.headers).json()
        for text in ['褙子，身高10cm','褙子，腰围80cm，腰围90cm','褙子，腰围30英寸']:
            with self.subTest(text=text):
                result=self.parse(text)
                self.assertEqual(result['status'],'needs_input',result)
                self.assertEqual(self.client.get('/api/v1/body/params',headers=self.headers).json(),before)

    def test_fixed_coat_lengths_across_short_and_tall_bodies(self):
        cases=[('褙子','beizi',110,150,170),('半臂','banbi',50,185,180)]
        for label,component,length,height,next_height in cases:
            with self.subTest(component=component):
                result=self.parse(f'{label}，衣长{length}cm，身高{height}cm，常服')
                self.assertEqual(result['status'],'generated',result)
                data=self.exported()
                self.assertAlmostEqual(data['design'][component]['length']['v']*data['body']['_leg_length'],length,places=5)
                response=self.client.put('/api/v1/body/params',headers=self.headers,
                    json={'path':['height'],'value':next_height})
                self.assertEqual(response.status_code,200,response.text)
                data=self.exported()
                self.assertAlmostEqual(data['design'][component]['length']['v']*data['body']['_leg_length'],length,places=5)
                self.assertTrue(data['metadata']['geometry_finite'])

    def test_rejected_context_and_collar_edits_explain_supported_choices(self):
        valid=self.parse('明代立领，领高3.5cm，常服')
        self.assertEqual(valid['status'],'generated')
        previous=self.client.get('/api/v1/pattern',headers=self.headers).json()
        invalid=self.parse('清代立领，领高4.5cm，礼服')
        self.assertEqual(invalid['status'],'needs_input')
        self.assertIn('常服、朝服',invalid['reply'])
        self.assertNotIn('dataset',invalid['reply'])
        response=self.client.put('/api/v1/design/params',headers=self.headers,
            json={'path':['stand-collar','collar_height'],'value':5})
        self.assertEqual(response.status_code,422)
        self.assertIn('不超过4cm',response.json()['error']['message'])
        self.assertEqual(previous,self.client.get('/api/v1/pattern',headers=self.headers).json())

    def test_length_limit_message_uses_current_body_centimetres(self):
        invalid=self.parse('褙子，衣长300cm，身高170cm，常服')
        self.assertEqual(invalid['status'],'needs_input')
        self.assertIn('衣长',invalid['reply'])
        self.assertIn('172.1cm',invalid['reply'])
        self.assertNotIn('schema',invalid['reply'])
        self.assertEqual(self.parse('褙子，衣长172.1cm，身高170cm，常服')['status'],'generated')
        self.assertEqual(self.parse('褙子，衣长172.2cm，身高170cm，常服')['status'],'needs_input')

    def test_confirmed_visual_uses_body_text_and_retains_visible_style(self):
        class Model:
            def image(self,*args):
                return {'component':'beizi','reason':'clear open front','features':{'sleeve_shape':'wide'}}
        engine=PaperEngine(Model())
        suggestion=engine.interpret('身高170cm，胸围100cm，衣长110cm','test-only',{})
        self.assertEqual(suggestion['suggested_component'],'beizi')
        proposal={'component':'beizi','features':suggestion['visible_features']}
        self.assertIn('身高170cm',suggestion['suggested_text'])
        self.assertIn('衣长110cm',suggestion['suggested_text'])
        ready=engine.interpret(suggestion['suggested_text'],None,{},proposal)
        self.assertEqual(ready['status'],'ready',ready)
        self.assertEqual(ready['body_values']['bust'],100)
        self.assertEqual(ready['patch']['beizi']['sleeve_cuff_width']['v'],60)


if __name__=='__main__':
    unittest.main()
