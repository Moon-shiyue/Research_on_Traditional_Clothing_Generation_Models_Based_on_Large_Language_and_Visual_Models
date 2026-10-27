"""Explicitly chosen innerwear must not be mistaken for observed back detail."""
import io,json,copy,tempfile,unittest,uuid
from pathlib import Path
from zipfile import ZipFile
from fastapi.testclient import TestClient
from PIL import Image
from .app import create_app
from .engine import PaperEngine
from .patterns import build_geometry,generate_pattern
from .outfits import interpret_outfit_scene,GROUPS
from .vision_fixtures import accounted_scene


def scene():
    return accounted_scene([
        {'component':'duijin-upper','reason':'open short outer','features':{'upper_front':'open'}},
        {'component':'ruqun-skirt','reason':'soft skirt','features':{'length':'full','flat_front':False,'side_pleats':False}},
        {'component':None,'reason':'only the straight chest front is visible','innerwear_candidates':['chest-wrap'],
         'features':{'innerwear_front':'straight-top','innerwear_closure':'unclear'}}])


class Vision:
    def __init__(self):self.calls=0
    def image_outfit(self,*args):self.calls+=1;return scene()
    def text(self,*args):raise AssertionError('No native model needed')


class ChestWrapTests(unittest.TestCase):
    def setUp(self):self.model=Vision();self.engine=PaperEngine(self.model)

    def test_actual_cm_geometry_body_width_and_four_attachment_marks(self):
        for bust in [82.,112.]:
            intent=self.engine.interpret('直幅系带抹胸，围前净高30cm，围前覆盖比0.65，系带净长45cm',None,{'bust':bust})
            self.assertEqual(intent['status'],'ready',intent)
            p,_,_,a,_,v=build_geometry(intent['patch'],self.engine.template,{'bust':bust})
            self.assertEqual(len(p.pattern['panels']),5);self.assertEqual(a['panel_height'],30.)
            self.assertAlmostEqual(a['panel_width'],bust*.65,places=5)
            self.assertEqual(len(a['attachment_points']),4);self.assertTrue(v['sampled_outline_valid'])
            with tempfile.TemporaryDirectory() as d:
                folder=Path(d)/'out';generate_pattern(intent['patch'],self.engine.template,{'bust':bust},folder)
                svg=(folder/'pattern-dimensions.svg').read_text(encoding='utf-8')
                self.assertEqual(svg.count('class="tie-attachment"'),4)

    def test_unknown_or_different_innerwear_never_gets_this_choice(self):
        candidate=interpret_outfit_scene(self.engine,'',scene(),{})
        self.assertEqual(candidate['innerwear_choices'][0]['id'],'chest-wrap')
        for changes in [{'innerwear_front':'other'},{'innerwear_closure':'straps'}, {'innerwear_closure':'closed-back'}]:
            s=scene();s['observations'][2]['features'].update(changes)
            self.assertNotIn('innerwear_choices',interpret_outfit_scene(self.engine,'',s,{}))
        for text in ['抹胸；襦裙','直幅系带抹胸，吊带','直幅系带抹胸；另做抹胸','直幅系带抹胸，围前净宽55cm']:
            from .outfits import interpret_outfit
            result=interpret_outfit(self.engine,text,{}) or self.engine.interpret(text,None,{})
            self.assertEqual(result['status'],'needs_input',result)

    def test_bound_choice_whole_outfit_edits_zip_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);sid=str(uuid.uuid4());headers={'X-Session-Id':sid}
            with TestClient(create_app(self.engine,root)) as c:
                image=io.BytesIO();Image.new('RGB',(80,120)).save(image,format='PNG')
                upload=c.post('/api/v1/upload/image',headers=headers,files={'file':('ref.png',image.getvalue(),'image/png')}).json()
                def parse(payload):
                    r=c.post('/api/v1/parse',headers=headers,json=payload)
                    if r.status_code!=202:return r
                    task=c.get('/api/v1/tasks/'+r.json()['task_id'],headers=headers).json()
                    self.assertEqual(task['status'],'done',task);return task['result']
                proposal=parse({'image':upload['image_id']})
                token=proposal['image_proposal_id'];text=proposal['suggested_text']
                missing=parse({'text':text,'image_proposal_id':token})
                self.assertEqual(missing.status_code,422)
                other=c.post('/api/v1/parse',headers={'X-Session-Id':str(uuid.uuid4())},json={'text':text,'image_proposal_id':token,'innerwear_choice':'chest-wrap'})
                self.assertEqual(other.status_code,422)
                result=parse({'text':text,'image_proposal_id':token,'innerwear_choice':'chest-wrap'})
                self.assertEqual(result['status'],'generated',result)
                self.assertEqual([g['component'] for g in result['pattern']['garments']],['chest-wrap','duijin-upper','ruqun-skirt'])
                layout=result['pattern']['body_layout'];self.assertIsNotNone(layout['innerwear_tuck_y_cm'])
                self.assertLess(layout['placement_order'].index('upper'),layout['placement_order'].index('lower'))
                self.assertEqual(self.model.calls,1)
                stale=parse({'text':text,'image_proposal_id':token,'innerwear_choice':'chest-wrap'});self.assertEqual(stale.status_code,422)
                changed=c.put('/api/v1/body/params',headers=headers,json={'path':['bust'],'value':108.})
                self.assertEqual(changed.status_code,200,changed.text)
                pattern=changed.json();self.assertEqual(pattern['garments'][0]['component_source'],'user_confirmation')
                archive=c.get('/api/v1/download',headers=headers)
                with ZipFile(io.BytesIO(archive.content)) as z:
                    self.assertIsNone(z.testzip())
                    meta=json.loads(z.read('upper/metadata.json'));self.assertIn('背面',meta['selection_note'])
                    self.assertIn(meta['selection_note'],z.read('upper/README.txt').decode('utf-8'))
                    self.assertIn(meta['selection_note'],z.read('README.txt').decode('utf-8'))
                    a=json.loads(z.read('upper/assembly.json'));self.assertAlmostEqual(a['panel_width'],108*.65,places=5)
                self.assertEqual(c.get('/api/v1/print/plan',headers=headers).status_code,200)
                self.assertEqual(c.get('/api/v1/design/history',headers=headers).status_code,200)
                for action in ['default','random']:
                    r=c.post('/api/v1/design/'+action,headers=headers);self.assertEqual(r.status_code,200,r.text)
                    pattern=c.get('/api/v1/pattern',headers=headers).json()
                    self.assertEqual(pattern['garments'][0]['component_source'],'user_confirmation')
            with TestClient(create_app(PaperEngine(Vision()),root)) as c:
                restored=c.get('/api/v1/pattern',headers=headers).json()
                self.assertEqual(restored['svg_url'],pattern['svg_url'])
                self.assertEqual(len(restored['garments']),3)
                self.assertEqual(restored['garments'][0]['component_source'],'user_confirmation')

    def test_provider_candidate_is_not_automatic_recognition_or_a_skirt(self):
        import httpx
        from .cloud_vision import CloudVision,VisionError
        from .chatgpt_plan import PlanSession
        row={'component':None,'evidence':'A separate straight chest front is visible; back hidden.',
             'visible_garments':['innerwear'],'flat_front':None,'side_pleats':None,'length':'unclear',
             'hem_shape':'unclear','tassels':'unclear','sleeve_shape':'unclear','upper_front':'unclear',
             'neckwear_shape':'unclear','cloud_layers':None,'waist_level':'unclear','cuff_finish':'unclear',
             'front_opening':'unclear','sleeve_extent':'unclear','side_slits':'unclear','waist_belt':'unclear',
             'uncertain':True,'garment_index':0,'skirt_candidates':[],
             'innerwear_front':'straight-top','innerwear_closure':'unclear','innerwear_candidates':['chest-wrap']}
        answer={'observations':[row],'visible_garments':['innerwear'],'single_outfit':True,'all_garments_accounted':True}
        def handle(request):
            payload=json.loads(request.content)
            required=payload['text']['format']['schema']['properties']['observations']['items']['required']
            self.assertIn('innerwear_candidates',required)
            return httpx.Response(200,json={'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(answer)}]}]})
        with tempfile.TemporaryDirectory() as d:
            transport=httpx.MockTransport(handle);client=CloudVision(transport=transport,plan=PlanSession(Path(d)/'login',transport=transport))
            client.configure('https://api.openai.com/v1','test-model','test-only-key')
            photo=Path(d)/'p.png';Image.new('RGB',(80,120)).save(photo)
            def observed():return client.image(photo,self.engine.names,outfit=True)['observations'][0]
            o=observed();self.assertIsNone(o['component']);self.assertEqual(o['innerwear_candidates'],['chest-wrap'])
            row.update(component='chest-wrap',uncertain=False)
            self.assertIsNone(observed()['component'])
            row['innerwear_closure']='tie-back';self.assertEqual(observed()['component'],'chest-wrap')
            row['sleeve_extent']='wrist';self.assertIsNone(observed()['component'])
            row['sleeve_extent']='unclear'
            row.update(component=None,uncertain=True,innerwear_closure='straps')
            self.assertEqual(observed()['innerwear_candidates'],[])
            row.update(innerwear_closure='unclear',skirt_candidates=['mamian-skirt','ruqun-skirt'])
            with self.assertRaises(VisionError):observed()


if __name__=='__main__':unittest.main()
