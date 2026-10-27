import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid

import httpx
from fastapi.testclient import TestClient
from PIL import Image

from .app import create_app
from .cloud_vision import CloudVision, VisionError
from .engine import PaperEngine
from .model import NativeModel
from .chatgpt_plan import PlanSession


class CloudVisionTests(unittest.TestCase):
    def test_cloud_coverage_is_checked_and_missing_legacy_values_are_unclear(self):
        row={'component':'cloud-shoulder','evidence':'A separate cloud-lobed piece extends over the chest',
             'visible_garments':['cloud collar'],'flat_front':None,'side_pleats':None,'length':'short',
             'hem_shape':'unclear','tassels':'present','uncertain':False,'sleeve_shape':'unclear',
             'upper_front':'unclear','neckwear_shape':'cloud-lobes','cloud_layers':1,'waist_level':'unclear',
             'cuff_finish':'unclear','front_opening':'unclear','sleeve_extent':'unclear','side_slits':'unclear',
             'waist_belt':'unclear','cloud_coverage':'chest'}
        def handle(request):
            payload=json.loads(request.content)
            self.assertIn('cloud_coverage',payload['text']['format']['schema']['required'])
            return httpx.Response(200,json={'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(row)}]}]})
        client=self.client(httpx.MockTransport(handle));client.configure('https://api.openai.com/v1','test-model','test-key')
        with tempfile.TemporaryDirectory() as temp:
            photo=Path(temp)/'p.png';Image.new('RGB',(32,64)).save(photo)
            self.assertEqual(client.image(photo,{'cloud-shoulder':'云肩'})['features']['cloud_coverage'],'chest')
            row.pop('cloud_coverage')
            self.assertEqual(client.image(photo,{'cloud-shoulder':'云肩'})['features']['cloud_coverage'],'unclear')
            for bad in [None,'large',2,[]]:
                row['cloud_coverage']=bad
                with self.assertRaises(VisionError):client.image(photo,{'cloud-shoulder':'云肩'})

    def setUp(self):
        self.private = tempfile.TemporaryDirectory()
        self.addCleanup(self.private.cleanup)

    def client(self, transport):
        return CloudVision(transport=transport,plan=PlanSession(Path(self.private.name)/'login',transport=transport))

    def test_outfit_contract_checks_each_observation_and_never_trusts_outer_list_alone(self):
        upper={'component':'beizi','evidence':'Open coat with long sleeves',
            'visible_garments':['coat'],'flat_front':None,'side_pleats':None,
            'length':'full','hem_shape':'unclear','tassels':'unclear','uncertain':False,
            'sleeve_shape':'wide','upper_front':'open','neckwear_shape':'unclear','cloud_layers':None,'waist_level':'unclear','cuff_finish':'unclear','front_opening':'unclear','sleeve_extent':'unclear','side_slits':'unclear','waist_belt':'unclear'}
        lower=dict(upper,component='mamian-skirt',flat_front=True,side_pleats=True,upper_front='unclear',hem_shape='wide')
        upper['garment_index']=0;lower['garment_index']=1
        upper['skirt_candidates']=[];lower['skirt_candidates']=[]
        answer={'observations':[upper,lower],'visible_garments':['coat','skirt'],
                'single_outfit':True,'all_garments_accounted':True}
        def handle(request):
            payload=json.loads(request.content)
            self.assertEqual(set(payload['text']['format']['schema']['required']),
                {'observations','visible_garments','single_outfit','all_garments_accounted'})
            prompt=payload['input'][0]['content'][0]['text']
            self.assertNotIn('例如交领清楚而下裙不明时选cross-collar',prompt)
            self.assertIn('不同人物的不同款式',prompt)
            self.assertEqual(payload['input'][0]['content'][1]['type'],'input_image')
            return httpx.Response(200,json={'output':[{'type':'message','content':[
                {'type':'output_text','text':json.dumps(answer)}]}]})
        client=self.client(httpx.MockTransport(handle))
        client.configure('https://api.openai.com/v1','gpt-6.1-sol','test-only-secret')
        with tempfile.TemporaryDirectory() as folder:
            photo=Path(folder)/'p.png'
            Image.new('RGB',(32,64)).save(photo)
            components={'beizi':'褙子','mamian-skirt':'马面裙'}
            result=client.image(photo,components,outfit=True)
            self.assertEqual([o['component'] for o in result['observations']],['beizi','mamian-skirt'])
            self.assertEqual([o['garment_index'] for o in result['observations']],[0,1])
            self.assertEqual(result['visible_garments'],['coat','skirt'])
            answer['single_outfit']='true'
            with self.assertRaises(VisionError):client.image(photo,components,outfit=True)
            answer['single_outfit']=True
            saved=answer.pop('all_garments_accounted')
            with self.assertRaises(VisionError):client.image(photo,components,outfit=True)
            answer['all_garments_accounted']=saved
            ambiguous=dict(lower,component=None,flat_front=None,side_pleats=None,sleeve_shape='unclear',
                           skirt_candidates=['mamian-skirt','ruqun-skirt'])
            answer['observations']=[upper,ambiguous]
            self.assertEqual(client.image(photo,components,outfit=True)['observations'][1]['skirt_candidates'],
                             ['mamian-skirt','ruqun-skirt'])
            for bad in [['mamian-skirt','mamian-skirt'],['modern-skirt'],None,'ruqun-skirt']:
                ambiguous['skirt_candidates']=bad
                with self.assertRaises(VisionError):client.image(photo,components,outfit=True)
            answer['observations']=[upper,lower]
            lower['flat_front']=None
            self.assertIsNone(client.image(photo,components,outfit=True)['observations'][1]['component'])
            lower['flat_front']=True
            # Observing more than the generation limit must be allowed, so
            # unsupported extra layers cannot vanish merely to fit a schema.
            extra=dict(upper,component=None,visible_garments=['披帛'],upper_front='unclear',garment_index=2)
            answer['observations']=[upper,lower,extra,dict(extra,visible_garments=['中衣'],garment_index=3)]
            answer['visible_garments']=['coat','skirt','scarf','inner']
            self.assertEqual(len(client.image(photo,components,outfit=True)['observations']),4)
            answer['observations']=[upper,upper]
            answer['single_outfit']=False
            self.assertFalse(client.image(photo,components,outfit=True)['single_outfit'])
            answer['single_outfit']=True
            with self.assertRaises(VisionError):
                client.image(photo,components,outfit=True)
            answer['observations']=[upper,lower,upper]
            with self.assertRaises(VisionError):
                client.image(photo,components,outfit=True)
            answer['observations']=[{'component':'beizi'}]
            with self.assertRaises(VisionError):
                client.image(photo,components,outfit=True)
            answer['observations']=[dict(upper,sleeve_extent='sleeveless')]
            refused=client.image(photo,components,outfit=True)['observations'][0]
            self.assertIsNone(refused['component'])
            self.assertIn('无袖',refused['reason'])

    def test_responses_image_contract_and_secret_redaction(self):
        observed={'component':'mamian-skirt','evidence':'平整裙门、两侧褶裥',
            'visible_garments':['上衣','马面裙'],'flat_front':True,'side_pleats':True,
            'length':'full','hem_shape':'wide','tassels':'unclear','uncertain':False,
            'sleeve_shape':'unclear','upper_front':'unclear','neckwear_shape':'unclear','cloud_layers':None,'waist_level':'unclear','cuff_finish':'unclear','front_opening':'unclear','sleeve_extent':'unclear','side_slits':'unclear','waist_belt':'unclear'}
        def handle(request):
            self.assertEqual(str(request.url),'https://api.openai.com/v1/responses')
            payload=json.loads(request.content)
            self.assertFalse(payload['store'])
            self.assertEqual(payload['input'][0]['content'][1]['type'],'input_image')
            self.assertTrue(payload['input'][0]['content'][1]['image_url'].startswith('data:image/jpeg;base64,'))
            self.assertTrue(payload['text']['format']['strict'])
            return httpx.Response(200,json={'output':[{'type':'message','content':[
                {'type':'output_text','text':json.dumps(observed)}]}]})
        client=self.client(httpx.MockTransport(handle))
        client.configure('https://api.openai.com/v1','gpt-6.1-sol','test-only-secret')
        self.assertNotIn('test-only-secret',json.dumps(client.status()))
        with tempfile.TemporaryDirectory() as folder:
            photo=Path(folder)/'photo.png'
            Image.new('RGB',(80,120)).save(photo)
            result=client.image(photo,{'mamian-skirt':'马面裙','ruqun-skirt':'襦裙'})
            self.assertEqual(result['component'],'mamian-skirt')
            self.assertEqual(result['features']['hem_shape'],'wide')
            observed['component']='ruqun-skirt'
            self.assertIsNone(client.image(photo,{'mamian-skirt':'马面裙','ruqun-skirt':'襦裙'})['component'])

    def test_no_configuration_or_provider_error_has_no_local_fallback(self):
        client=self.client(httpx.MockTransport(lambda r:httpx.Response(401,json={'error':'test-secret'})))
        client.clear()
        with self.assertRaisesRegex(VisionError,'云端视觉设置'):
            client.image(Path('unused'),{'mamian-skirt':'马面裙'})
        client.configure('https://api.openai.com/v1','gpt-6.1-sol','test-secret')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'p.png'
            Image.new('RGB',(10,10)).save(path)
            with self.assertRaises(VisionError) as caught:
                client.image(path,{'mamian-skirt':'马面裙'})
            self.assertNotIn('test-secret',str(caught.exception))

    def test_unknown_skirt_structure_cannot_be_accepted_as_ruqun(self):
        observed={'component':'ruqun-skirt','evidence':'The waist is hidden by the upper garment.',
            'visible_garments':['skirt'],'flat_front':False,'side_pleats':None,
            'length':'full','hem_shape':'wide','tassels':'unclear','uncertain':False,
            'sleeve_shape':'unclear','upper_front':'unclear','neckwear_shape':'unclear','cloud_layers':None,'waist_level':'unclear','cuff_finish':'unclear','front_opening':'unclear','sleeve_extent':'unclear','side_slits':'unclear','waist_belt':'unclear'}
        def handle(request):
            return httpx.Response(200,json={'output':[{'type':'message','content':[
                {'type':'output_text','text':json.dumps(observed)}]}]})
        client=self.client(httpx.MockTransport(handle))
        client.configure('https://api.openai.com/v1','gpt-6.1-sol','test-only-secret')
        with tempfile.TemporaryDirectory() as folder:
            photo=Path(folder)/'photo.png'
            Image.new('RGB',(80,120)).save(photo)
            for front,pleats,expected in [(False,None,None),(None,False,None),
                    (True,False,None),(True,True,None),(False,False,'ruqun-skirt')]:
                with self.subTest(front=front,pleats=pleats):
                    observed.update(flat_front=front,side_pleats=pleats)
                    self.assertEqual(client.image(photo,{'ruqun-skirt':'skirt'})['component'],expected)

    def test_configuration_api_does_not_return_or_export_key(self):
        model=NativeModel()
        model.cloud_vision=self.client(httpx.MockTransport(lambda r:httpx.Response(401)))
        model.cloud_vision.clear()
        with tempfile.TemporaryDirectory() as folder, TestClient(create_app(PaperEngine(model),Path(folder))) as c:
            headers={'X-Session-Id':str(uuid.uuid4())}
            response=c.put('/api/v1/vision/config',headers=headers,json={
                'base_url':'https://api.openai.com/v1','model':'gpt-6.1-sol','api_key':'test-secret'})
            self.assertEqual(response.status_code,200)
            self.assertTrue(response.json()['configured'])
            self.assertNotIn('test-secret',c.get('/api/v1/vision/config').text)
            invalid=c.put('/api/v1/vision/config',headers=headers,json={
                'base_url':'http://example.com','model':'x','api_key':'test-secret'})
            self.assertEqual(invalid.status_code,422)
            self.assertNotIn('test-secret',invalid.text)
            c.delete('/api/v1/vision/config',headers=headers)
            self.assertFalse(c.get('/api/v1/vision/config').json()['configured'])

    def test_connect_failure_retries_once_but_read_failure_or_http_error_does_not(self):
        observed={'component':'cloud-shoulder','evidence':'One clearly visible layer',
            'visible_garments':['cloud shoulder'],'flat_front':None,'side_pleats':None,
            'length':'short','hem_shape':'unclear','tassels':'absent','uncertain':False,
            'sleeve_shape':'unclear','upper_front':'unclear','neckwear_shape':'cloud-lobes','cloud_layers':1,'waist_level':'unclear','cuff_finish':'unclear','front_opening':'unclear','sleeve_extent':'unclear','side_slits':'unclear','waist_belt':'unclear'}
        with tempfile.TemporaryDirectory() as folder:
            photo=Path(folder)/'photo.png'
            Image.new('RGB',(32,32)).save(photo)
            for failure,expected_calls in [('connect',2),('read',1),('rate',1)]:
                with self.subTest(failure=failure):
                    calls=[]
                    def handle(request):
                        calls.append(request)
                        if len(calls)==1:
                            if failure=='connect':
                                raise httpx.ConnectError('test-only',request=request)
                            if failure=='read':
                                raise httpx.ReadTimeout('test-only',request=request)
                            return httpx.Response(429)
                        return httpx.Response(200,json={'output':[{'type':'message','content':[
                            {'type':'output_text','text':json.dumps(observed)}]}]})
                    client=self.client(httpx.MockTransport(handle))
                    client.configure('https://api.openai.com/v1','gpt-6.1-sol','test-only-secret')
                    if failure=='connect':
                        self.assertEqual(client.image(photo,{'cloud-shoulder':'cloud'})['features']['cloud_layers'],1)
                    else:
                        with self.assertRaises(VisionError):
                            client.image(photo,{'cloud-shoulder':'cloud'})
                    self.assertEqual(len(calls),expected_calls)

    def test_cloud_layer_contract_rejects_boolean_fraction_and_unsupported_counts(self):
        observed={'component':'cloud-shoulder','evidence':'Test observation',
            'visible_garments':['cloud'],'flat_front':None,'side_pleats':None,
            'length':'short','hem_shape':'unclear','tassels':'absent','uncertain':False,
            'sleeve_shape':'unclear','upper_front':'unclear','neckwear_shape':'cloud-lobes','cloud_layers':None,'waist_level':'unclear','cuff_finish':'unclear','front_opening':'unclear','sleeve_extent':'unclear','side_slits':'unclear','waist_belt':'unclear'}
        transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'output':[
            {'type':'message','content':[{'type':'output_text','text':json.dumps(observed)}]}]}))
        client=self.client(transport)
        client.configure('https://api.openai.com/v1','gpt-6.1-sol','test-only-secret')
        with tempfile.TemporaryDirectory() as folder:
            photo=Path(folder)/'photo.png'
            Image.new('RGB',(32,32)).save(photo)
            for bad in [True,False,1.5,0,9,'2']:
                observed['cloud_layers']=bad
                with self.subTest(value=bad),self.assertRaises(VisionError):
                    client.image(photo,{'cloud-shoulder':'cloud'})
            for layers in [4,5,8]:
                observed['cloud_layers']=layers
                result=client.image(photo,{'cloud-shoulder':'cloud'})
                self.assertIsNone(result['component'])
                self.assertEqual(result['features']['cloud_layers'],layers)
                self.assertIn('1–3',result['reason'])

    def test_broad_pi_ling_cannot_become_cloud_lobes_or_a_narrow_round_band(self):
        observed={'component':'cloud-shoulder','evidence':'Broad fan-shaped cloth with one rounded opening',
            'visible_garments':['cape collar'],'flat_front':None,'side_pleats':None,
            'length':'short','hem_shape':'unclear','tassels':'absent','uncertain':False,
            'sleeve_shape':'unclear','upper_front':'unclear','neckwear_shape':'broad-cape','cloud_layers':1,'waist_level':'unclear','cuff_finish':'unclear','front_opening':'unclear','sleeve_extent':'unclear','side_slits':'unclear','waist_belt':'unclear'}
        transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'output':[
            {'type':'message','content':[{'type':'output_text','text':json.dumps(observed)}]}]}))
        client=self.client(transport)
        client.configure('https://api.openai.com/v1','gpt-6.1-sol','test-only-key')
        components={'cloud-shoulder':'cloud','round-collar':'round'}
        with tempfile.TemporaryDirectory() as folder:
            photo=Path(folder)/'cape.png';Image.new('RGB',(32,32)).save(photo)
            for component in [None,'cloud-shoulder','round-collar']:
                observed['component']=component
                result=client.image(photo,components)
                self.assertIsNone(result['component'])
                self.assertEqual(result['features']['neckwear_shape'],'broad-cape')
                self.assertIn('宽幅披领',result['reason'])
            for component,accepted in [('cloud-shoulder','cloud-lobes'),('round-collar','round-band')]:
                observed['component']=component
                for shape in ['cloud-lobes','round-band','unclear']:
                    observed['neckwear_shape']=shape
                    self.assertEqual(client.image(photo,components)['component'],component if shape==accepted else None)

    def test_standalone_sleeve_requires_consistent_visible_shape(self):
        observed={'component':'narrow-sleeve','evidence':'Detached sleeve direction is unclear',
            'visible_garments':['sleeve'],'flat_front':None,'side_pleats':None,
            'length':'unclear','hem_shape':'unclear','tassels':'unclear','uncertain':False,
            'sleeve_shape':'unclear','upper_front':'unclear','neckwear_shape':'unclear','cloud_layers':None,'waist_level':'unclear','cuff_finish':'unclear','front_opening':'unclear','sleeve_extent':'unclear','side_slits':'unclear','waist_belt':'unclear'}
        transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'output':[
            {'type':'message','content':[{'type':'output_text','text':json.dumps(observed)}]}]}))
        client=self.client(transport)
        client.configure('https://api.openai.com/v1','gpt-6.1-sol','test-only-secret')
        components={'narrow-sleeve':'narrow','wide-sleeve':'wide','pipa-sleeve':'pipa'}
        with tempfile.TemporaryDirectory() as folder:
            photo=Path(folder)/'photo.png'
            Image.new('RGB',(32,32)).save(photo)
            for component,expected in components.items():
                observed['component']=component
                for shape in ['unclear',*components.values()]:
                    observed['sleeve_shape']=shape
                    with self.subTest(component=component,shape=shape):
                        self.assertEqual(client.image(photo,components)['component'],
                                         component if shape==expected else None)
                observed.update(sleeve_shape=expected,uncertain=True)
                self.assertIsNone(client.image(photo,components)['component'])
                observed['uncertain']=False
