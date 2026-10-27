"""Multiple bounded occlusions must retain every garment and require each choice."""
import copy
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
from .outfits import interpret_outfit_scene
from .vision_fixtures import accounted_scene


def scene(outer='duijin-upper', extras=False):
    rows=[{'component':outer,'reason':'Separate outer garment',
           'features':{'upper_front':'open','length':'short' if outer in {'banbi','duijin-upper'} else 'mid'}},
          {'component':None,'reason':'Skirt waist hidden','skirt_candidates':['mamian-skirt','ruqun-skirt'],
           'features':{'flat_front':None,'side_pleats':None,'length':'full','hem_shape':'moderate'}},
          {'component':None,'reason':'Straight inner front; back hidden','innerwear_candidates':['chest-wrap'],
           'features':{'innerwear_front':'straight-top','innerwear_closure':'unclear'}}]
    if outer=='bijia':rows[0]['features'].update(upper_front='closed',sleeve_extent='sleeveless',front_opening='center')
    if extras:rows += [
        {'component':'cloud-shoulder','reason':'Cloud lobes','features':{'neckwear_shape':'cloud-lobes','cloud_layers':2}},
        {'component':'pibo','reason':'Separate long strip','features':{'neckwear_shape':'long-drape'}}]
    return accounted_scene(rows)


class Vision:
    def __init__(self,value):self.value=value;self.calls=0
    def image_outfit(self,*_):self.calls+=1;return copy.deepcopy(self.value)


class SequentialChoiceTests(unittest.TestCase):
    def test_each_supported_outer_keeps_both_occlusions_and_original_indices(self):
        engine=PaperEngine(object())
        for outer in ['beizi','banbi','bijia','duijin-upper']:
            for extras in [False,True]:
                for reverse in [False,True]:
                    s=scene(outer,extras)
                    if reverse:s['observations'].reverse()
                    r=interpret_outfit_scene(engine,'',s,{})
                    self.assertEqual(r['innerwear_choices'][0]['id'],'chest-wrap',r)
                    self.assertEqual(r['innerwear_choice_index'],2)
                    self.assertNotIn('skirt_choices',r)
                    self.assertIn('所有项目确认完毕',r['reply'])
                    row=next(o for o in s['observations'] if o['garment_index']==2)
                    row.update(component='chest-wrap',component_source='user_confirmation',innerwear_candidates=[])
                    row['features']['innerwear_closure']='tie-back'
                    r=interpret_outfit_scene(engine,'直幅系带抹胸',s,{})
                    self.assertEqual({c['id'] for c in r['skirt_choices']},{'mamian-skirt','ruqun-skirt'},r)
                    self.assertEqual(r['skirt_choice_index'],1)

    def test_unbounded_unsupported_omitted_and_conflicting_members_never_get_partial_choices(self):
        engine=PaperEngine(object())
        cases=[]
        s=scene();s['observations'][1]['skirt_candidates']=[];cases.append(s)
        s=scene();s['observations'][2]['features']['innerwear_closure']='straps';cases.append(s)
        s=scene();s['observations'][2]['features']['innerwear_closure']='closed-back';cases.append(s)
        s=scene();s['observations'][0]['features']['upper_front']='crossed';cases.append(s)
        s=scene();s['observations'][0]['features']['sleeve_extent']='sleeveless';cases.append(s)
        s=scene();s['visible_garments'].append('unsupported extra garment');cases.append(s)
        s=scene();s['observations'][2]['garment_index']=1;cases.append(s)
        s=scene();s['single_outfit']=False;cases.append(s)
        s=scene();s['observations'][2]=copy.deepcopy(s['observations'][1]);s['observations'][2]['garment_index']=2;cases.append(s)
        for s in cases:
            r=interpret_outfit_scene(engine,'',s,{})
            self.assertNotIn('innerwear_choices',r,r)
            self.assertNotIn('skirt_choices',r,r)
            self.assertNotIn('opening_choices',r,r)
        for text in ['不要直幅系带抹胸','不要马面裙，也不要襦裙','交领长袍','马面裙和襦裙']:
            r=interpret_outfit_scene(engine,text,scene(),{})
            self.assertNotIn('innerwear_choices',r,r)
        s=scene();s['observations'][0].update(component='stand-upper',features={'upper_front':'unclear','sleeve_extent':'sleeveless'})
        s['observations']=[s['observations'][0]];s['visible_garments']=['stand-upper']
        self.assertNotIn('opening_choices',interpret_outfit_scene(engine,'',s,{}))

    def test_two_bound_choices_reuse_photo_keep_old_design_until_complete_and_survive_restart(self):
        for skirt in ['mamian-skirt','ruqun-skirt']:
            with self.subTest(skirt=skirt),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);model=Vision(scene(extras=True));engine=PaperEngine(model)
                headers={'X-Session-Id':str(uuid.uuid4())};app=create_app(engine,root)
                with TestClient(app) as c:
                    def parse(payload):
                        response=c.post('/api/v1/parse',headers=headers,json=payload)
                        self.assertEqual(response.status_code,202,response.text)
                        task=c.get('/api/v1/tasks/'+response.json()['task_id'],headers=headers).json()
                        self.assertEqual(task['status'],'done',task);return task['result']
                    old=parse({'text':'圆领长袍，衣长130cm'})['pattern']
                    buf=io.BytesIO();Image.new('RGB',(40,80),'white').save(buf,format='PNG')
                    image=c.post('/api/v1/upload/image',headers=headers,files={'file':('ref.png',buf.getvalue(),'image/png')}).json()['image_id']
                    first=parse({'image':image,'text':'身高170cm，裙长100cm'})
                    payload={'text':first['suggested_text'],'image_proposal_id':first['image_proposal_id'],'innerwear_choice':'chest-wrap'}
                    mixed=c.post('/api/v1/parse',headers=headers,json=dict(payload,skirt_choice=skirt))
                    self.assertEqual(mixed.status_code,422)
                    second=parse(payload)
                    self.assertEqual(second['pattern']['svg_url'],old['svg_url'])
                    self.assertNotEqual(second['image_proposal_id'],first['image_proposal_id'])
                    self.assertEqual(c.post('/api/v1/parse',headers=headers,json=payload).status_code,422)
                    selected={'text':second['suggested_text'],'image_proposal_id':second['image_proposal_id'],'skirt_choice':skirt}
                    missing=dict(selected);missing.pop('skirt_choice')
                    self.assertEqual(c.post('/api/v1/parse',headers=headers,json=missing).status_code,422)
                    self.assertEqual(c.post('/api/v1/parse',headers={'X-Session-Id':str(uuid.uuid4())},json=selected).status_code,422)
                    result=parse(selected);self.assertEqual(result['status'],'generated',result)
                    pattern=result['pattern'];members=pattern['garments']
                    self.assertEqual([g['component'] for g in members],['chest-wrap','duijin-upper',skirt,'cloud-shoulder','pibo'])
                    self.assertEqual(len(members),5);self.assertEqual(pattern['absolute_lengths_cm'][skirt+'.length'],100.)
                    self.assertEqual([g.get('component_source') for g in [members[0],members[2]]],['user_confirmation']*2)
                    self.assertEqual(model.calls,1)
                    response=c.put('/api/v1/body/params',headers=headers,json={'path':['height'],'value':180.})
                    self.assertEqual(response.status_code,200,response.text)
                    pattern=response.json();self.assertEqual(len(pattern['garments']),5)
                    archive=c.get('/api/v1/download',headers=headers)
                    with ZipFile(io.BytesIO(archive.content)) as z:
                        self.assertIsNone(z.testzip())
                        manifest=json.loads(z.read('export-manifest.json'))
                        for name,entry in manifest['files'].items():self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(),entry['sha256'])
                        for role in ['upper','lower']:
                            meta=json.loads(z.read(role+'/metadata.json'))
                            self.assertEqual(meta['component_source'],'user_confirmation')
                            self.assertIn(meta['selection_note'],z.read('README.txt').decode('utf-8'))
                            self.assertIn(meta['selection_note'],z.read(role+'/README.txt').decode('utf-8'))
                    self.assertEqual(c.get('/api/v1/print/plan',headers=headers).status_code,200)
                with TestClient(create_app(PaperEngine(object()),root)) as c:
                    restored=c.get('/api/v1/pattern',headers=headers).json()
                    self.assertEqual(restored['svg_url'],pattern['svg_url'])
                    self.assertEqual(len(restored['garments']),5)
                    self.assertEqual(restored['garments'][0]['component_source'],'user_confirmation')
                    self.assertEqual(restored['garments'][2]['component_source'],'user_confirmation')


if __name__=='__main__':unittest.main()
