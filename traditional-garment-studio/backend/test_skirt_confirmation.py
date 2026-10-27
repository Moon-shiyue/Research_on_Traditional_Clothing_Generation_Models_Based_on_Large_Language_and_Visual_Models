"""Occluded skirts can be selected without losing the rest of the outfit."""
import copy
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
from .outfits import interpret_outfit_scene
from .session_restore import restore_saved_design
from .vision_fixtures import accounted_scene


class Vision:
    def __init__(self,occluded_opening=False):
        self.calls=0
        self.scene=accounted_scene([
            {'component':'stand-upper' if occluded_opening else 'cross-upper','reason':'整件上衣',
             'features':{'upper_front':'unclear' if occluded_opening else 'crossed',
                         'front_opening':'unclear','sleeve_shape':'regular'}},
            {'component':None,'reason':'裙门和侧褶区域被上衣挡住','features':{
                'flat_front':None,'side_pleats':None,'length':'full','hem_shape':'moderate'},
             'skirt_candidates':['mamian-skirt','ruqun-skirt']}])
    def image_outfit(self,*_):self.calls+=1;return copy.deepcopy(self.scene)


class SkirtConfirmationTests(unittest.TestCase):
    def test_bound_choice_generates_all_members_and_survives_export_edit_and_restore(self):
        for opening in [False,True]:
            for skirt in ['mamian-skirt','ruqun-skirt']:
                with self.subTest(opening=opening,skirt=skirt),tempfile.TemporaryDirectory() as temp:
                    model=Vision(opening);engine=PaperEngine(model);root=Path(temp)
                    sid=str(uuid.uuid4());headers={'X-Session-Id':sid}
                    app=create_app(engine,root)
                    with TestClient(app) as client:
                        def parse(payload):
                            response=client.post('/api/v1/parse',headers=headers,json=payload)
                            self.assertEqual(response.status_code,202,response.text)
                            task=client.get('/api/v1/tasks/'+response.json()['task_id'],headers=headers).json()
                            self.assertEqual(task['status'],'done',task);return task['result']
                        previous=parse({'text':'交领长袍，衣长130cm'})['pattern']
                        buffer=io.BytesIO();Image.new('RGB',(32,64),'white').save(buffer,format='PNG')
                        image=client.post('/api/v1/upload/image',headers=headers,
                            files={'file':('test.png',buffer.getvalue(),'image/png')}).json()['image_id']
                        proposal=parse({'image':image,'text':'衣长60cm，裙长100cm'})
                        self.assertEqual({c['id'] for c in proposal['skirt_choices']},{'mamian-skirt','ruqun-skirt'})
                        self.assertEqual(proposal['pattern'],previous)
                        payload={'text':proposal['suggested_text'],'image_proposal_id':proposal['image_proposal_id']}
                        self.assertEqual(client.post('/api/v1/parse',headers=headers,json=payload).status_code,422)
                        outsider={'X-Session-Id':str(uuid.uuid4())}
                        selected=dict(payload,skirt_choice=skirt)
                        self.assertEqual(client.post('/api/v1/parse',headers=outsider,json=selected).status_code,422)
                        result=parse(selected)
                        if opening:
                            self.assertEqual(result['status'],'needs_input',result)
                            self.assertIn('opening_choices',result)
                            self.assertEqual(result['pattern'],previous)
                            result=parse({'text':result['suggested_text'],'image_proposal_id':result['image_proposal_id'],
                                          'opening_choice':'center'})
                        self.assertEqual(result['status'],'generated',result)
                        members=result['pattern']['garments']
                        self.assertEqual([g['component'] for g in members],['stand-upper' if opening else 'cross-upper',skirt])
                        self.assertEqual(members[1]['component_source'],'user_confirmation')
                        self.assertIn('下裙款式已按你的选择',result['reply'])
                        self.assertEqual(model.calls,1)
                        self.assertEqual(result['pattern']['absolute_lengths_cm'][skirt+'.length'],100)
                        self.assertIn('reference_image_url',result['pattern'])
                        folder=root/'patterns'/sid/result['pattern']['svg_url'].split('/')[-2]
                        lower=json.loads((folder/'lower/metadata.json').read_text(encoding='utf8'))
                        self.assertEqual(lower['component_source'],'user_confirmation')
                        exported=client.get('/api/v1/download',headers=headers)
                        self.assertEqual(exported.status_code,200,exported.text[:200] if exported.status_code!=200 else '')
                        with ZipFile(io.BytesIO(exported.content)) as archive:
                            self.assertIsNone(archive.testzip())
                            receipt=json.loads(archive.read('lower/metadata.json'))
                            self.assertEqual(receipt['component_source'],'user_confirmation')
                            self.assertIn('未从图片确认',receipt['selection_note'])
                            self.assertNotIn('reference.jpg',archive.namelist())
                        restored=restore_saved_design(engine,root,sid,folder.name)
                        self.assertEqual(restored['outfit'][1]['component_source'],'user_confirmation')
                        response=client.put('/api/v1/body/params',headers=headers,json={'path':['height'],'value':175})
                        self.assertEqual(response.status_code,200,response.text)
                        current=client.get('/api/v1/pattern',headers=headers).json()
                        self.assertEqual(current['garments'][1]['component_source'],'user_confirmation')
                        self.assertTrue(any('下裙款式由用户选择' in note for note in current['warnings']))
                        self.assertEqual(client.post('/api/v1/parse',headers=headers,json=selected).status_code,422)
                        if not opening and skirt=='ruqun-skirt':
                            for action in ['default','random']:
                                response=client.post('/api/v1/design/'+action,headers=headers)
                                self.assertEqual(response.status_code,200,response.text)
                                current=client.get('/api/v1/pattern',headers=headers).json()
                                self.assertEqual(current['garments'][1]['component_source'],'user_confirmation')
                                self.assertTrue(any('下裙款式由用户选择' in note for note in current['warnings']))

    def test_exclusions_and_explicit_skirt_request_limit_choices(self):
        engine=PaperEngine(object());scene=Vision().scene
        for text,expected in [('不要马面裙',{'ruqun-skirt'}),('襦裙，裙长95cm',{'ruqun-skirt'})]:
            result=interpret_outfit_scene(engine,text,scene,{})
            self.assertEqual({c['id'] for c in result['skirt_choices']},expected,result)
        result=interpret_outfit_scene(engine,'不要马面裙，也不要襦裙',scene,{})
        self.assertNotIn('skirt_choices',result)

    def test_unknown_extra_garment_never_becomes_a_skirt_choice(self):
        engine=PaperEngine(object());scene=Vision().scene
        scene['observations'][1]['skirt_candidates']=[]
        self.assertNotIn('skirt_choices',interpret_outfit_scene(engine,'',scene,{}))
        scene=Vision().scene
        scene['visible_garments'].append('额外披帛')
        self.assertNotIn('skirt_choices',interpret_outfit_scene(engine,'',scene,{}))
        for feature,value in [('neckwear_shape','broad-cape'),('sleeve_extent','sleeveless'),
                              ('hem_shape','unclear'),('upper_front','open')]:
            scene=Vision().scene;scene['observations'][1]['features'][feature]=value
            self.assertNotIn('skirt_choices',interpret_outfit_scene(engine,'',scene,{}))


if __name__=='__main__':unittest.main()
