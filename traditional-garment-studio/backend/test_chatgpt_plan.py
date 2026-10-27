"""Local protocol/security tests. All OpenAI traffic is mocked; no plan spent."""
import base64
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from urllib.parse import parse_qs, urlsplit
import uuid

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import httpx
import jwt
from PIL import Image

from .app import create_app
from .chatgpt_plan import PlanSession, ISSUER, RESOURCE, SCOPE
from .cloud_vision import CloudVision, VisionError
from .engine import PaperEngine
from .model import NativeModel


class ChatGPTPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.key.public_key()))
        cls.jwk.update(kid='unit-test-key', alg='RS256', use='sig')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.calls = []
        self.overrides = {}
        self.revoke_status = 200
        self.granted_scope = SCOPE
        self.bad_signature = False
        self.session = PlanSession(Path(self.temp.name)/'private', httpx.MockTransport(self.handle))
        self.addCleanup(self.session.cancel)

    def test_only_pre_delivery_connect_failure_is_retried_once(self):
        for method in ['GET','POST']:
            for failure in [httpx.ConnectError,httpx.ConnectTimeout]:
                calls=[]
                def handle(request):
                    calls.append(request)
                    if len(calls)==1:raise failure('test-secret-in-internal-error',request=request)
                    return httpx.Response(200,json={'ok':True})
                plan=PlanSession(Path(self.temp.name)/('connect-'+method),httpx.MockTransport(handle))
                self.assertEqual(plan._json(method,ISSUER+'/test',data={'token':'test-only-secret'}),{'ok':True})
                self.assertEqual(len(calls),2)
                self.assertEqual(calls[0].content,calls[1].content)

    def test_read_write_status_and_invalid_json_are_never_retried_or_leaked(self):
        for failure in [httpx.ReadTimeout,httpx.ReadError,httpx.WriteError,httpx.RemoteProtocolError]:
            calls=[]
            def handle(request):
                calls.append(request);raise failure('test-secret-in-internal-error',request=request)
            plan=PlanSession(Path(self.temp.name)/'no-resubmit',httpx.MockTransport(handle))
            with self.assertRaises(VisionError) as caught:plan._json('POST',ISSUER+'/test',data={'token':'test-only-secret'})
            self.assertEqual(len(calls),1)
            self.assertNotIn('test-secret',str(caught.exception))
        for status in [200,401,403,429,500]:
            calls=[]
            def handle(request):
                calls.append(request);return httpx.Response(status,text='test-secret-provider-response')
            plan=PlanSession(Path(self.temp.name)/'bad-response',httpx.MockTransport(handle))
            with self.assertRaises(VisionError) as caught:plan._json('POST',ISSUER+'/test')
            self.assertEqual(len(calls),1)
            self.assertNotIn('test-secret',str(caught.exception))

    def test_connection_retry_is_bounded_and_redacts_internal_error(self):
        calls=[]
        def handle(request):
            calls.append(request);raise httpx.ConnectError('test-secret-in-internal-error',request=request)
        plan=PlanSession(Path(self.temp.name)/'twice',httpx.MockTransport(handle))
        with self.assertRaises(VisionError) as caught:plan._json('GET',ISSUER+'/test')
        self.assertEqual(len(calls),2)
        self.assertNotIn('test-secret',str(caught.exception))

    def handle(self, request):
        self.calls.append(request)
        path = request.url.path
        if path == '/.well-known/openid-configuration':
            return httpx.Response(200,json={'issuer':ISSUER,
                'authorization_endpoint':ISSUER+'/api/accounts/authorize',
                'token_endpoint':ISSUER+'/api/accounts/oauth/token',
                'jwks_uri':ISSUER+'/.well-known/jwks.json',
                'revocation_endpoint':ISSUER+'/oauth/revoke'})
        if path == '/.well-known/jwks.json':
            return httpx.Response(200,json={'keys':[self.jwk]})
        if path == '/api/accounts/oauth/token':
            values = parse_qs(request.content.decode())
            if values['grant_type'] == ['refresh_token']:
                self.assertNotIn('scope',values)
                return httpx.Response(200,json={'access_token':'rotated-access','refresh_token':'rotated-refresh',
                    'token_type':'Bearer','expires_in':3600})
            pending = self.session.pending
            self.assertEqual(values['client_id'], ['oaiapp_test'])
            self.assertEqual(values['resource'], [RESOURCE])
            self.assertEqual(values['redirect_uri'], [pending['redirect_uri']])
            self.assertEqual(values['code_verifier'], [pending['verifier']])
            claims = {'iss':ISSUER,'sub':'unit-sub','aud':'oaiapp_test','iat':int(time.time()),
                      'exp':int(time.time()+3600),'nonce':pending['nonce'],'email':'test@example.invalid'}
            claims.update(self.overrides)
            token = jwt.encode(claims,self.key,algorithm='RS256',headers={'kid':'unit-test-key'})
            if self.bad_signature:
                pieces = token.split('.')
                pieces[2] = ('A' if pieces[2][0] != 'A' else 'B') + pieces[2][1:]
                token = '.'.join(pieces)
            return httpx.Response(200,json={'id_token':token,'access_token':'unit-access-secret',
                'refresh_token':'unit-refresh-secret','token_type':'Bearer','expires_in':3600,'scope':self.granted_scope})
        if path == '/v1/models':
            return httpx.Response(200,json={'models':[{'slug':'gpt-6.1-sol','display_name':'GPT Sol','visibility':'list'},
                {'slug':'hidden-model','visibility':'hidden'}]})
        if path == '/oauth/revoke':
            return httpx.Response(self.revoke_status)
        raise AssertionError('Unexpected provider request: '+path)

    def login(self):
        self.session.start()
        p = self.session.pending
        self.session.complete({'state':[p['state']], 'code':['unit-code'], 'client_id':['oaiapp_test']},p)

    def test_registration_pkce_state_and_callback_listener(self):
        started = self.session.start()
        query = parse_qs(urlsplit(started['authorization_url']).query)
        pending = self.session.pending
        expected = base64.urlsafe_b64encode(hashlib.sha256(pending['verifier'].encode()).digest()).rstrip(b'=').decode()
        self.assertEqual(query['code_challenge'],[expected])
        self.assertEqual(query['client_id'],['dynamic_agent_client'])
        self.assertEqual(query['agent_name_hint'],['Traditional Garment Studio'])
        self.assertEqual(query['scope'],[SCOPE])
        self.assertEqual(PlanSession(self.session.directory).data['host_id'],self.session.data['host_id'])
        with httpx.Client(trust_env=False) as client:
            rejected = client.get(pending['redirect_uri'],params={'state':'wrong','code':'never-exchange'})
            self.assertEqual(rejected.status_code,400)
            self.assertEqual(rejected.headers['referrer-policy'],'no-referrer')
            self.assertIs(self.session.pending,pending)
            good = client.get(pending['redirect_uri'],params={'state':pending['state'],'code':'test','client_id':'oaiapp_test'})
            self.assertEqual(good.status_code,200)
        self.assertTrue(self.session.status()['connected'])
        self.assertNotIn('unit-access-secret',good.text)
        with self.assertRaises(VisionError):
            self.session.complete({'state':[pending['state']], 'code':['replay']},pending)

    def test_id_token_identity_and_scope_fail_closed(self):
        for fields in [{'nonce':'wrong'}, {'aud':'other-app'}, {'iss':'https://wrong.invalid'},
                       {'exp':int(time.time()-60)}, {'sub':''}]:
            with self.subTest(fields=fields):
                self.overrides = fields
                self.session.start()
                p = self.session.pending
                with self.assertRaises(VisionError):
                    self.session.complete({'state':[p['state']],'code':['test'],'client_id':['oaiapp_test']},p)
                self.assertFalse(self.session.status()['connected'])
        self.overrides = {}
        self.bad_signature = True
        with self.assertRaises(VisionError):
            self.login()
        self.bad_signature = False
        self.granted_scope = 'openid profile email'
        with self.assertRaises(VisionError):
            self.login()
        self.assertFalse(self.session.status()['connected'])

    def test_missing_or_changed_client_id_and_denial_never_exchange(self):
        for extra in [{}, {'error':['access_denied']}]:
            self.session.start()
            p = self.session.pending
            count = len(self.calls)
            with self.assertRaises(VisionError):
                self.session.complete({'state':[p['state']],'code':['test'],**extra},p)
            self.assertEqual(len(self.calls),count)
        self.login()
        active = self.session.status()['active_account']
        self.session.start(active)
        p = self.session.pending
        count = len(self.calls)
        with self.assertRaises(VisionError):
            self.session.complete({'state':[p['state']],'code':['test'],'client_id':['oaiapp_other']},p)
        self.assertEqual(len(self.calls),count)
        self.assertEqual(self.session.status()['active_account'],active)

    def test_protected_storage_refresh_returning_account_and_signout(self):
        self.login()
        public = json.dumps(self.session.status())
        self.assertNotIn('unit-access-secret',public)
        self.assertNotIn('unit-refresh-secret',public)
        import os
        if os.name == 'nt':
            self.assertNotIn(b'unit-access-secret',self.session.file.read_bytes())
        restored = PlanSession(self.session.directory,self.session.transport)
        self.assertEqual(restored.bearer(),'unit-access-secret')
        active = self.session.data['active']
        self.session.data['accounts'][active]['expires_at'] = 0
        self.assertEqual(self.session.bearer(),'rotated-access')
        self.assertEqual(PlanSession(self.session.directory).data['accounts'][active]['refresh_token'],'rotated-refresh')
        started = self.session.start(active)
        q = parse_qs(urlsplit(started['authorization_url']).query)
        self.assertNotIn('agent_name_hint',q)
        self.assertEqual(q['client_id'],['oaiapp_test'])
        self.assertEqual(q['login_hint'],['test@example.invalid'])
        self.assertIn('id_token_hint',q)
        p = self.session.pending
        self.assertEqual(p['client_id'],'oaiapp_test')
        self.session.cancel()
        self.session.select_model('gpt-6.1-sol')
        self.assertEqual(self.session.credentials()[1],'gpt-6.1-sol')
        with self.assertRaises(VisionError):
            self.session.select_model('hidden-model')
        self.revoke_status = 503
        state = self.session.sign_out()
        self.assertFalse(state['connected'])
        self.assertIn('未确认远端撤销',state['message'])
        saved = PlanSession(self.session.directory).data['accounts'][active]
        self.assertEqual(saved['client_id'],'oaiapp_test')
        self.assertNotIn('refresh_token',saved)

    def test_api_endpoints_require_session_and_do_not_expose_credentials(self):
        model = NativeModel()
        model.cloud_vision = CloudVision(plan=self.session)
        application = create_app(PaperEngine(model),Path(self.temp.name)/'public')
        async def local_app(scope,receive,send):
            await application(dict(scope,client=('127.0.0.1',50000)),receive,send)
        with TestClient(local_app) as client:
            self.assertEqual(client.post('/api/v1/vision/chatgpt/login',json={}).status_code,400)
            headers = {'X-Session-Id':str(uuid.uuid4())}
            self.login()
            response = client.get('/api/v1/vision/chatgpt',headers=headers)
            self.assertEqual(response.status_code,200,response.text)
            self.assertTrue(response.json()['connected'])
            self.assertNotIn('unit-access-secret',response.text)
            self.assertEqual(client.get('/static/.private/chatgpt/credentials.dpapi').status_code,404)
            self.assertEqual(client.get('/api/v1/vision/chatgpt/models',headers=headers).json()['models'][0]['slug'],'gpt-6.1-sol')
            self.assertEqual(client.put('/api/v1/vision/chatgpt/model',headers=headers,json={'model':'hidden-model'}).status_code,400)
        with self.assertRaisesRegex(RuntimeError,'静态文件'):
            create_app(PaperEngine(model),Path(self.temp.name))

    def test_plan_sse_image_and_late_limit_never_fall_back_to_api_key(self):
        self.login()
        self.session.select_model('gpt-6.1-sol')
        observation = {'component':'mamian-skirt','evidence':'裙门与两侧褶', 'visible_garments':['马面裙'],
            'flat_front':True,'side_pleats':True,'length':'full','hem_shape':'wide','tassels':'unclear','uncertain':False,
            'sleeve_shape':'unclear','upper_front':'unclear','neckwear_shape':'unclear','cloud_layers':None,'waist_level':'unclear','cuff_finish':'unclear','front_opening':'unclear','sleeve_extent':'unclear','side_slits':'unclear','waist_belt':'unclear'}
        terminal = {'type':'response.completed','response':{'status':'completed'}}
        calls = []
        def stream(request):
            calls.append(request)
            self.assertEqual(str(request.url),RESOURCE+'/responses')
            self.assertEqual(request.headers['Authorization'],'Bearer unit-access-secret')
            payload = json.loads(request.content)
            self.assertTrue(payload['stream'])
            self.assertFalse(payload['store'])
            self.assertNotIn('max_output_tokens',payload)
            self.assertEqual(payload['input'][0]['content'][1]['type'],'input_image')
            events = [{'type':'response.output_text.delta','delta':json.dumps(observation)}, terminal]
            body = ''.join('data: '+json.dumps(v)+'\n\n' for v in events if v)
            return httpx.Response(200,headers={'Content-Type':'text/event-stream'},content=body.encode())
        cloud = CloudVision(plan=self.session,transport=httpx.MockTransport(stream))
        cloud.configure('https://example.invalid/v1','any-model','api-key-must-not-be-used')
        cloud.select_source('chatgpt_plan')
        path = Path(self.temp.name)/'photo.png'
        Image.new('RGB',(20,20)).save(path)
        self.assertEqual(cloud.image(path,{'mamian-skirt':'马面裙'})['component'],'mamian-skirt')
        terminal = {'type':'response.failed','response':{'error':{'code':'subscription_sharing_usage_limit_exceeded','message':'sensitive-provider-message'}}}
        with self.assertRaisesRegex(VisionError,'限额'):
            cloud.image(path,{'mamian-skirt':'马面裙'})
        terminal = None
        with self.assertRaisesRegex(VisionError,'连接中断'):
            cloud.image(path,{'mamian-skirt':'马面裙'})
        self.assertEqual(len(calls),3)
