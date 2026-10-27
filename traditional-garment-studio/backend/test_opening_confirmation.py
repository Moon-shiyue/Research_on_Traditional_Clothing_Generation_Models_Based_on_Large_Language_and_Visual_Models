"""An occluded opening can be selected explicitly, never silently guessed."""
import io
from pathlib import Path
import tempfile
import unittest
import uuid

from fastapi.testclient import TestClient
from PIL import Image
from .app import create_app
from .engine import PaperEngine


class Vision:
    def __init__(self,ensemble):self.calls=0;self.ensemble=ensemble
    def image_outfit(self,path,names):
        self.calls+=1
        upper={'component':'stand-upper' if self.ensemble else 'stand-robe',
               'reason':'领型和衣身可见，前襟被挡。','features':{'upper_front':'unclear','front_opening':'unclear',
                'sleeve_shape':'pipa','cuff_finish':'band','sleeve_extent':'wrist'}}
        from .vision_fixtures import accounted_scene
        return accounted_scene([upper]+([
            {'component':'mamian-skirt','reason':'有裙门和侧褶','features':{'length':'full','hem_shape':'moderate'}},
            {'component':'cloud-shoulder','reason':'两层云头肩饰','features':{'neckwear_shape':'cloud-lobes','cloud_layers':2}}]
            if self.ensemble else []))


class OpeningConfirmationTests(unittest.TestCase):
    def test_default_full_scope_requires_a_bound_choice_and_reuses_the_same_photo_observation(self):
        for ensemble in [False,True]:
            for choice in ['center','right']:
                with self.subTest(ensemble=ensemble,choice=choice),tempfile.TemporaryDirectory() as temp:
                    model=Vision(ensemble);app=create_app(PaperEngine(model),Path(temp));headers={'X-Session-Id':str(uuid.uuid4())}
                    with TestClient(app) as client:
                        content=io.BytesIO();Image.new('RGB',(32,64),'white').save(content,format='PNG')
                        image=client.post('/api/v1/upload/image',headers=headers,files={'file':('test.png',content.getvalue(),'image/png')}).json()['image_id']
                        def parse(payload):
                            response=client.post('/api/v1/parse',headers=headers,json=payload)
                            self.assertEqual(response.status_code,202,response.text)
                            task=client.get('/api/v1/tasks/'+response.json()['task_id'],headers=headers).json()
                            self.assertEqual(task['status'],'done',task);return task['result']
                        proposal=parse({'image':image})  # Default API scope must be whole clothes.
                        self.assertEqual(proposal['status'],'needs_input',proposal)
                        self.assertEqual({c['id'] for c in proposal['opening_choices']},{'center','right'})
                        payload={'text':proposal['suggested_text'],'image_proposal_id':proposal['image_proposal_id']}
                        self.assertEqual(client.post('/api/v1/parse',headers=headers,json=payload).status_code,422)
                        outsider={'X-Session-Id':str(uuid.uuid4())}
                        self.assertEqual(client.post('/api/v1/parse',headers=outsider,json=dict(payload,opening_choice=choice)).status_code,422)
                        result=parse(dict(payload,opening_choice=choice))
                        self.assertEqual(result['status'],'generated',result)
                        self.assertEqual(result['pattern']['panel_count'],18 if ensemble else 13)
                        component='stand-upper' if ensemble else 'stand-robe'
                        self.assertEqual(result['design_params'][component]['opening_type']['v'],int(choice=='center'))
                        self.assertEqual(result['pattern']['parameter_sources'][component+'.opening_type'],'user_confirmation')
                        self.assertIn('未由图片确认',result['reply'] if ensemble else result['reply'].replace('未从图片确认','未由图片确认'))
                        self.assertEqual(model.calls,1)
                        self.assertIn('reference_image_url',result['pattern'])
                        self.assertEqual(client.post('/api/v1/parse',headers=headers,json=dict(payload,opening_choice=choice)).status_code,422)
                        if ensemble:
                            reset=client.post('/api/v1/design/default',headers=headers)
                            self.assertEqual(reset.status_code,200,reset.text)
                            current=client.get('/api/v1/pattern',headers=headers).json()
                            self.assertNotIn('user_confirmation',current['parameter_sources'].values())
                            self.assertFalse(any('开襟位置由用户选择' in note for note in current['warnings']))


if __name__=='__main__':unittest.main()
