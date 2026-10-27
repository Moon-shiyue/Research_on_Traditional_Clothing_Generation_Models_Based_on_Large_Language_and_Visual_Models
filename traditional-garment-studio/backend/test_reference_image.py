"""Reference pictures follow confirmed designs, never unrelated subsequent text."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from zipfile import ZipFile

from fastapi.testclient import TestClient
from PIL import Image

from .app import create_app
from .engine import PaperEngine


class ImageModel:
    def text(self, *_):
        raise AssertionError('Explicit parameters must not load model weights')

    def image(self, path, *_):
        return {'component':'mamian-skirt','reason':'Controlled test observation',
                'features':{'length':'full','hem_shape':'wide'}}

    def image_outfit(self, path, *_):
        from .vision_fixtures import accounted_scene
        return accounted_scene([
            {'component':'banbi','reason':'Controlled short open-front upper',
             'features':{'length':'short','sleeve_length':'short','upper_front':'open'}},
            {'component':'ruqun-skirt','reason':'Controlled continuous soft-pleated lower',
             'features':{'length':'full','hem_shape':'wide'}}])


class ReferenceImageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.headers={'X-Session-Id':str(uuid.uuid4())}
        self.open()

    def open(self):
        self.app=create_app(PaperEngine(model=ImageModel()),self.root)
        self.client=TestClient(self.app)
        self.addCleanup(self.client.close)

    def request(self, **payload):
        payload.setdefault('scope','component')
        response=self.client.post('/api/v1/parse',headers=self.headers,json=payload)
        self.assertEqual(response.status_code,202,response.text)
        task=self.client.get('/api/v1/tasks/'+response.json()['task_id'],headers=self.headers).json()
        self.assertEqual(task['status'],'done',task)
        return task['result']

    def pictured_design(self, scope='component'):
        raw=io.BytesIO()
        Image.new('RGB',(80,120),(155,60,45)).save(raw,format='PNG')
        upload=self.client.post('/api/v1/upload/image',headers=self.headers,
            files={'file':('reference.png',raw.getvalue(),'image/png')}).json()
        suggestion=self.request(image=upload['image_id'],scope=scope)
        self.assertEqual(suggestion['status'],'needs_input',suggestion)
        result=self.request(text=suggestion['suggested_text'],
            image_proposal_id=suggestion['image_proposal_id'],scope=scope)
        self.assertEqual(result['status'],'generated',result)
        return result['pattern'],upload

    def test_confirmed_reference_survives_body_edit_restart_and_upload_loss(self):
        before,upload=self.pictured_design()
        original=self.client.get(upload['url']).content
        self.assertEqual(self.client.get(before['reference_image_url']).content,original)
        self.assertEqual(before['reference_image_sha256'],hashlib.sha256(original).hexdigest())
        upload_path=self.root/upload['url'].removeprefix('/static/')
        upload_path.unlink()  # Test-owned temporary data, simulating expired upload storage.
        changed=self.client.put('/api/v1/body/params',headers=self.headers,
            json={'path':['waist'],'value':88})
        self.assertEqual(changed.status_code,200,changed.text)
        after=changed.json()
        self.assertNotEqual(after['reference_image_url'],before['reference_image_url'])
        self.assertEqual(self.client.get(after['reference_image_url']).content,original)
        self.open()
        restored=self.client.get('/api/v1/pattern',headers=self.headers).json()
        self.assertEqual(restored,after)
        with ZipFile(io.BytesIO(self.client.get('/api/v1/download',headers=self.headers).content)) as archive:
            self.assertNotIn('reference.jpg',archive.namelist())
            self.assertIn('参考图片不包含在此包',archive.read('README.txt').decode('utf-8'))

    def test_outfit_reference_is_root_only_and_survives_one_member_edit(self):
        before,_=self.pictured_design('outfit')
        self.assertEqual(before['panel_count'],17)
        self.assertTrue(before['reference_image_url'])
        self.assertTrue(all('reference_image_url' not in g for g in before['garments']))
        response=self.client.put('/api/v1/design/params',headers=self.headers,
            json={'path':['ruqun-skirt','length'],'value':90,'unit':'cm'})
        self.assertEqual(response.status_code,200,response.text)
        after=response.json()
        self.assertEqual(after['reference_image_sha256'],before['reference_image_sha256'])
        self.open()
        self.assertEqual(self.client.get('/api/v1/pattern',headers=self.headers).json(),after)

    def test_explicit_skirt_only_request_overrides_default_full_image_scope(self):
        raw=io.BytesIO();Image.new('RGB',(80,120),(155,60,45)).save(raw,format='PNG')
        upload=self.client.post('/api/v1/upload/image',headers=self.headers,
            files={'file':('test.png',raw.getvalue(),'image/png')}).json()
        # Full-scene mock returns a different upper/skirt pair. This explicit
        # selection must use the requested-item classifier instead.
        result=self.request(image=upload['image_id'],scope='outfit',text='只制作马面裙，裙长95cm')
        self.assertEqual(result['status'],'generated',result)
        self.assertEqual(result['pattern']['component'],'mamian-skirt')
        self.assertNotIn('garments',result['pattern'])
        from .text_scope import requested_local_kinds
        self.assertEqual(requested_local_kinds('只做襦裙下裳'),{'skirt'})
        self.assertEqual(requested_local_kinds('交领上衣；马面裙'),set())

    def test_unconfirmed_image_never_replaces_committed_reference_and_text_clears_it(self):
        before,_=self.pictured_design()
        raw=io.BytesIO();Image.new('RGB',(40,50),(20,80,180)).save(raw,format='PNG')
        upload=self.client.post('/api/v1/upload/image',headers=self.headers,
            files={'file':('next.png',raw.getvalue(),'image/png')}).json()
        pending=self.request(image=upload['image_id'])
        self.assertEqual(pending['pattern']['reference_image_url'],before['reference_image_url'])
        plain=self.request(text='宋代褙子，衣长110cm，常服')
        self.assertEqual(plain['status'],'generated')
        self.assertNotIn('reference_image_url',plain['pattern'])

    def test_missing_optional_picture_keeps_valid_saved_pattern(self):
        before,_=self.pictured_design()
        path=self.root/before['reference_image_url'].removeprefix('/static/')
        path.unlink()
        self.open()
        restored=self.client.get('/api/v1/pattern',headers=self.headers).json()
        self.assertEqual(restored['svg_url'],before['svg_url'])
        self.assertNotIn('reference_image_url',restored)

    def test_reference_lost_before_confirmation_preserves_previous_valid_design(self):
        before=self.request(text='宋代褙子，衣长110cm，常服')['pattern']
        raw=io.BytesIO();Image.new('RGB',(40,50)).save(raw,format='PNG')
        upload=self.client.post('/api/v1/upload/image',headers=self.headers,
            files={'file':('new.png',raw.getvalue(),'image/png')}).json()
        suggestion=self.request(image=upload['image_id'])
        (self.root/upload['url'].removeprefix('/static/')).unlink()
        rejected=self.request(text=suggestion['suggested_text'],image_proposal_id=suggestion['image_proposal_id'])
        self.assertEqual(rejected['status'],'needs_input')
        self.assertEqual(rejected['pattern'],before)
        state=self.app.state.sessions[self.headers['X-Session-Id']]
        self.assertEqual(len([p for p in state['folder'].parent.iterdir() if p.is_dir()]),1)

    def test_changed_optional_picture_is_not_presented_as_original_after_restart(self):
        before,_=self.pictured_design()
        path=self.root/before['reference_image_url'].removeprefix('/static/')
        Image.new('RGB',(32,32),(0,0,255)).save(path,format='JPEG')
        self.open()
        restored=self.client.get('/api/v1/pattern',headers=self.headers).json()
        self.assertEqual(restored['svg_url'],before['svg_url'])
        self.assertNotIn('reference_image_url',restored)


if __name__=='__main__':
    unittest.main()
