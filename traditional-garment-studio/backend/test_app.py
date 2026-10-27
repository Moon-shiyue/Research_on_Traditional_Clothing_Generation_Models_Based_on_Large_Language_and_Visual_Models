import io
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from fastapi.testclient import TestClient
from PIL import Image
from .app import create_app
from .engine import PaperEngine
from .patterns import body_from, generate_pattern
from training.common import read_jsonl
from .settings import GARMENT_ROOT


class NoModel:
    def text(self, text):
        raise RuntimeError('No model in this HTTP/geometry test')

    def image(self, path, components):
        assert path.is_file()
        with Image.open(path) as image:
            assert image.mode == 'RGB'
        return {'component':'mamian-skirt','reason':'Test-only classifier; real inference verified separately.'}


class AppTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.engine = PaperEngine(model=NoModel())
        self.app = create_app(self.engine,Path(self.directory.name))
        self.client = TestClient(self.app)
        self.headers = {'X-Session-Id':str(uuid.uuid4())}

    def tearDown(self):
        self.client.close()
        self.directory.cleanup()

    def generate(self,text='',image=None,proposal=None):
        response = self.client.post('/api/v1/parse',headers=self.headers,json={'text':text,'image':image,'image_proposal_id':proposal,'scope':'component'})
        self.assertEqual(response.status_code,202,response.text)
        status = self.client.get('/api/v1/tasks/'+response.json()['task_id'],headers=self.headers).json()
        self.assertEqual(status['status'],'done',status)
        return status['result']

    def test_text_builds_real_panels_svg_and_download(self):
        result = self.generate('明代马面裙，裙长及小腿，马面宽约28cm，褶量适中（褶量比1.8），高腰位，常服。')
        self.assertEqual(result['status'],'generated')
        self.assertEqual(result['pattern']['panel_count'],3)
        self.assertEqual(result['design_params']['mamian-skirt']['mamian_width']['v'],28)
        svg = self.client.get(result['pattern']['svg_url'])
        self.assertEqual(svg.status_code,200)
        element = ET.fromstring(svg.content)
        self.assertTrue(element.attrib['width'].endswith('cm'))
        self.assertEqual(len(element.findall('.//{http://www.w3.org/2000/svg}g')),3)
        self.assertEqual(len(element.findall('.//{http://www.w3.org/2000/svg}line[@class="fold-mountain"]')),8)
        self.assertEqual(len(element.findall('.//{http://www.w3.org/2000/svg}rect[@class="skirt-door"]')),4)
        self.assertEqual(self.client.get(result['pattern']['structure_svg_url']).status_code,200)
        dimension_svg = self.client.get(result['pattern']['dimension_svg_url'])
        self.assertEqual(dimension_svg.status_code,200)
        dimension_root = ET.fromstring(dimension_svg.content)
        ns = '{http://www.w3.org/2000/svg}'
        self.assertEqual(element.attrib,dimension_root.attrib)
        self.assertEqual([v.attrib['d'] for v in element.iter(ns+'path')],
                         [v.attrib['d'] for v in dimension_root.iter(ns+'path')])
        labels = [v for v in dimension_root.iter(ns+'text') if v.attrib.get('class')=='edge-dimension']
        self.assertTrue(labels)
        self.assertTrue(any(abs(float(v.attrib['data-length-cm'])-28)<1e-6 for v in labels))
        archive = self.client.get('/api/v1/download',headers=self.headers)
        self.assertEqual(archive.status_code,200)
        with ZipFile(io.BytesIO(archive.content)) as z:
            self.assertIsNone(z.testzip())
            self.assertIn('pattern-dimensions.svg',z.namelist())
            self.assertEqual(len(json.loads(z.read('pattern.json'))['panels']),3)
            self.assertIn('construction.json',z.namelist())
            self.assertIn('structure.svg',z.namelist())
        link = self.client.post('/api/v1/download/link',headers=self.headers)
        self.assertEqual(link.status_code,200)
        bundle = self.client.get(link.json()['url'])
        self.assertEqual(bundle.status_code,200)
        with ZipFile(io.BytesIO(bundle.content)) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(len(json.loads(z.read('pattern.json'))['panels']),3)

    def test_bad_values_do_not_change_saved_design(self):
        self.generate('宋代褙子，衣长及小腿，开衩较高（0.6），袖长超过臂长，常服。')
        before = self.client.get('/api/v1/design/params',headers=self.headers).json()
        self.assertEqual(before['params']['beizi']['length']['v'],1)
        bad = self.client.put('/api/v1/design/params',headers=self.headers,json={'path':['beizi','length'],'value':0.7})
        self.assertEqual(bad.status_code,422)
        after = self.client.get('/api/v1/design/params',headers=self.headers).json()
        self.assertEqual(before,after)

    def test_partial_explicit_geometry_uses_disclosed_defaults_without_model(self):
        with patch.object(self.engine.model, 'text', side_effect=AssertionError('Unexpected model load')) as infer:
            result = self.generate('明代马面裙，裙长及小腿，马面宽28cm，常服。')
        infer.assert_not_called()
        self.assertEqual(result['status'], 'generated')
        self.assertEqual(result['pattern']['panel_count'], 3)
        self.assertEqual(result['design_params']['mamian-skirt']['mamian_width']['v'], 28)
        self.assertIn('mamian-skirt.pleat_ruffle', result['pattern']['default_fields'])
        self.assertIn('mamian-skirt.rise', result['pattern']['default_fields'])

    def test_body_updates_and_actual_geometry_changes(self):
        self.generate('明代马面裙，常服')
        before = self.client.get('/api/v1/download',headers=self.headers).content
        response = self.client.put('/api/v1/body/params',headers=self.headers,json={'path':['waist'],'value':90})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.get('/api/v1/body/params',headers=self.headers).json()['params']['waist'],90)
        with ZipFile(io.BytesIO(before)) as first, ZipFile(io.BytesIO(self.client.get('/api/v1/download',headers=self.headers).content)) as second:
            self.assertNotEqual(json.loads(first.read('pattern.json')),json.loads(second.read('pattern.json')))

    def test_image_upload_owned_reference_and_task_isolation(self):
        photo = io.BytesIO()
        Image.new('RGB',(64,64),(40,100,160)).save(photo,format='PNG')
        upload = self.client.post('/api/v1/upload/image',headers=self.headers,files={'file':('test.png',photo.getvalue(),'image/png')})
        self.assertEqual(upload.status_code,200)
        result = self.generate(image=upload.json()['image_id'])
        self.assertEqual(result['status'],'needs_input')
        self.assertIsNone(result['pattern'])
        self.assertEqual(result['suggested_component'],'mamian-skirt')
        confirmed = self.generate('马面裙')
        self.assertEqual(confirmed['status'],'generated')
        self.assertTrue(confirmed['pattern']['default_fields'])
        outsider = {'X-Session-Id':str(uuid.uuid4())}
        response = self.client.post('/api/v1/parse',headers=outsider,json={'image':upload.json()['image_id']})
        self.assertEqual(response.status_code,400)
        blob = self.client.post('/api/v1/parse',headers=self.headers,json={'image':'blob:http://localhost/not-a-file'})
        self.assertEqual(blob.status_code,400)
        invalid = self.client.post('/api/v1/upload/image',headers=self.headers,files={'file':('x.jpg',b'not image','image/jpeg')})
        self.assertEqual(invalid.status_code,400)

    def test_missing_component_and_conflicting_values_clarify(self):
        result = self.generate('做一件我喜欢的衣服')
        self.assertEqual(result['status'],'needs_input')
        self.assertIsNone(result['pattern'])
        result = self.generate('明代马面裙，马面宽20cm，马面宽35cm，常服')
        self.assertEqual(result['status'],'needs_input')
        result = self.generate('明代立领，领高9cm，常服')
        self.assertEqual(result['status'],'needs_input')

    def test_unit_conversion_and_qing_default_height(self):
        result = self.generate('明代马面裙，mamian_width=280毫米，pleat_ruffle=1.8，rise=95%，length=70%，常服')
        self.assertEqual(result['status'],'generated',result)
        self.assertEqual(result['design_params']['mamian-skirt']['mamian_width']['v'],28)
        result = self.generate('清代立领，常服')
        self.assertEqual(result['status'],'generated',result)
        self.assertGreaterEqual(result['design_params']['stand-collar']['collar_height']['v'],4)

    def test_full_length_image_proposal_keeps_length_on_confirmation(self):
        with patch.object(self.engine.model,'image',return_value={
                'component':'mamian-skirt','reason':'Test observation', 'features':{'length':'full'}}):
            body=self.client.get('/api/v1/body/params',headers=self.headers).json()['params']
            intent=self.engine.interpret('',Path('test-only'),{k:v for k,v in body.items() if not k.startswith('_')})
        self.assertEqual(intent['suggested_text'],'马面裙，裙长95cm')
        result=self.generate(intent['suggested_text'])
        self.assertEqual(result['status'],'generated')
        self.assertAlmostEqual(result['pattern']['construction']['skirt_length'],95,places=5)

    def test_visual_fullness_proposal_is_session_bound_and_applied_once(self):
        photo=io.BytesIO()
        Image.new('RGB',(64,96)).save(photo,format='PNG')
        uploaded=self.client.post('/api/v1/upload/image',headers=self.headers,
            files={'file':('test.png',photo.getvalue(),'image/png')}).json()['image_id']
        with patch.object(self.engine.model,'image',return_value={'component':'mamian-skirt',
                'reason':'Test: broad skirt with door and side pleats',
                'features':{'length':'full','hem_shape':'wide'}}):
            suggestion=self.generate(image=uploaded)
        token=suggestion['image_proposal_id']
        outsider={'X-Session-Id':str(uuid.uuid4())}
        self.assertEqual(self.client.post('/api/v1/parse',headers=outsider,json={
            'text':suggestion['suggested_text'],'image_proposal_id':token}).status_code,422)
        result=self.generate(suggestion['suggested_text'],proposal=token)
        self.assertEqual(result['design_params']['mamian-skirt']['pleat_ruffle']['v'],3)
        self.assertEqual(result['pattern']['parameter_sources']['mamian-skirt.pleat_ruffle'],'image_style_default')
        self.assertAlmostEqual(result['pattern']['construction']['skirt_length'],95,places=5)
        self.assertEqual(self.client.post('/api/v1/parse',headers=self.headers,json={
            'text':suggestion['suggested_text'],'image_proposal_id':token}).status_code,422)
        # A later direct text request must not inherit the last image's fullness.
        plain=self.generate('马面裙')
        self.assertEqual(plain['design_params']['mamian-skirt']['pleat_ruffle']['v'],1.8)

    def test_explicit_pleat_ratio_overrides_image_style_default(self):
        body={k:v for k,v in body_from().params.items() if not k.startswith('_')}
        intent=self.engine.interpret('马面裙，裙长95cm，褶量比2.4',None,body,
            {'component':'mamian-skirt','features':{'hem_shape':'wide'}})
        self.assertEqual(intent['patch']['mamian-skirt']['pleat_ruffle']['v'],2.4)
        self.assertEqual(intent['sources']['mamian-skirt.pleat_ruffle'],'text')

    def test_clear_absence_of_cloud_tassels_survives_confirmation_and_manual_override(self):
        body={k:v for k,v in body_from().params.items() if not k.startswith('_')}
        proposal={'component':'cloud-shoulder','features':{'tassels':'absent'}}
        intent=self.engine.interpret('云肩',None,body,proposal)
        self.assertEqual(intent['patch']['cloud-shoulder']['tassel_length']['v'],0)
        self.assertEqual(intent['sources']['cloud-shoulder.tassel_length'],'image_observation')
        intent=self.engine.interpret('云肩，垂须长度6cm',None,body,proposal)
        self.assertEqual(intent['patch']['cloud-shoulder']['tassel_length']['v'],6)
        self.assertEqual(intent['sources']['cloud-shoulder.tassel_length'],'text')

    def test_all_twelve_components_render(self):
        body = {k:v for k,v in body_from().params.items() if not k.startswith('_')}
        seen = set()
        for row in read_jsonl(GARMENT_ROOT/'data/training_v1/val.jsonl'):
            if row['component'] in seen:
                continue
            seen.add(row['component'])
            with self.subTest(component=row['component']):
                intent = self.engine.interpret(row['prompt'],None,body)
                self.assertEqual(intent['status'],'ready',intent)
                # Application-only sleeve controls supplement frozen v1 fields.
                expected = self.engine.defaults(row['component'])
                for section, fields in row['target'].items():
                    expected[section].update(fields)
                self.assertEqual(intent['patch'],expected)
                generated = generate_pattern(intent['patch'],self.engine.template,body,Path(self.directory.name)/row['component'])
                self.assertTrue(generated['geometry_finite'])
        self.assertEqual(len(seen),12)

    def test_random_skips_body_incompatible_first_draw_and_records_source(self):
        self.generate('马面裙')
        for key,value in [('waist',60),('hips',82)]:
            response=self.client.put('/api/v1/body/params',headers=self.headers,
                json={'path':[key],'value':value})
            self.assertEqual(response.status_code,200,response.text)
        # Individually in range, but the first 35cm door leaves no pleat zone
        # at this wearing circumference. The second draw must still succeed.
        with patch('backend.app.random.choice',side_effect=[.85,35,1.8,.85,.85,20,1.8,.85]) as choose:
            response=self.client.post('/api/v1/design/random',headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(choose.call_count,8)
        self.assertEqual(response.json()['params']['mamian-skirt']['mamian_width']['v'],20)
        metadata=self.client.get('/api/v1/pattern',headers=self.headers).json()
        self.assertEqual(metadata['parameter_sources']['mamian-skirt.mamian_width'],'random')
        self.assertEqual(metadata['parameter_sources']['traditional.dynasty'],'default')
        self.assertEqual(metadata['absolute_lengths_cm'],{})

    def test_exports_have_specific_guidance_complete_hashes_and_only_allowed_files(self):
        for text,expected_count in [('褙子，衣长95cm',13),('马面裙，裙长95cm',20),('立领，领高3cm',11)]:
            with self.subTest(text=text):
                result=self.generate(text)
                folder=Path(self.directory.name)/result['pattern']['svg_url'].removeprefix('/static/').rsplit('/',1)[0]
                (folder/'unrelated-private-test.txt').write_text('not part of any export',encoding='utf-8')
                response=self.client.post('/api/v1/download/link',headers=self.headers)
                self.assertEqual(response.status_code,200,response.text)
                exported=self.client.get(response.json()['url'])
                with ZipFile(io.BytesIO(exported.content)) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertEqual(len(archive.namelist()),expected_count)
                    self.assertNotIn('unrelated-private-test.txt',archive.namelist())
                    manifest=json.loads(archive.read('export-manifest.json'))
                    self.assertEqual(set(manifest['files']),set(archive.namelist())-{'export-manifest.json'})
                    for name,record in manifest['files'].items():
                        content=archive.read(name)
                        self.assertEqual(record['bytes'],len(content))
                        self.assertEqual(record['sha256'],hashlib.sha256(content).hexdigest())
                    instructions=archive.read('README.txt').decode('utf-8')
                    self.assertIn('100%',instructions)
                    self.assertIn('不能沿其轮廓裁布',instructions)
                    self.assertEqual('不要再次重复添加' in instructions,'马面裙' in text)
                    self.assertEqual('95cm' in instructions,'95cm' in text)

    def test_researched_templates_export_source_and_assembly_with_the_same_geometry(self):
        seen=set()
        for row in read_jsonl(GARMENT_ROOT/'data/training_v1/val.jsonl'):
            component=row['component']
            if component not in {'beizi','banbi','ruqun-skirt','cloud-shoulder'} or component in seen:
                continue
            seen.add(component)
            with self.subTest(component=component):
                result=self.generate(row['prompt'])
                p=result['pattern']
                self.assertTrue(p['assembly']['validation']['opening_checks_passed'])
                self.assertEqual(self.client.get(p['style_svg_url']).status_code,200)
                with ZipFile(io.BytesIO(self.client.get('/api/v1/download',headers=self.headers).content)) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertEqual(len(archive.namelist()),13)
                    assembly=json.loads(archive.read('assembly.json'))
                    geometry=json.loads(archive.read('pattern.json'))
                    self.assertEqual(assembly['version'],geometry['template_version'])
                    self.assertEqual(len(assembly['cut_list']),len(geometry['panels']))
                    self.assertTrue(assembly['sources'])
                    self.assertIn('style.svg',archive.namelist())
        self.assertEqual(len(seen),4)


if __name__ == '__main__':
    unittest.main()
