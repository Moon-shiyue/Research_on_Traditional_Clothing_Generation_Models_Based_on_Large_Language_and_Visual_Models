"""A pibo stays one measured strip and a distinct complete-outfit member."""
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from fastapi.testclient import TestClient
from .app import create_app
from .engine import PaperEngine
from .patterns import build_geometry,generate_pattern
from .body_layout import tag,pibo_projections,landmarks
from .outfits import BASE_GROUPS,GROUPS,interpret_outfit,interpret_outfit_scene
from .session_restore import restore_saved_design
from .design_integrity import verify_design
from .vision_fixtures import accounted_scene
from .traditional_templates import valid_outline


class DrapeTests(unittest.TestCase):
    def setUp(self):self.engine=PaperEngine(object())

    def test_straight_strip_dimensions_and_all_original_catalog_entries_remain(self):
        self.assertGreaterEqual(len(self.engine.names),20)
        self.assertEqual(len(self.engine.model_schema['components']),12)
        self.assertGreaterEqual(len(BASE_GROUPS),63)
        self.assertGreaterEqual(len(GROUPS),135)
        for text in ['披帛，披帛长3米，幅宽30cm','直幅披帛，长度300cm，宽度300毫米','披帛，净长三米，净幅宽三十厘米']:
            intent=self.engine.interpret(text,None,{})
            self.assertEqual(intent['status'],'ready',intent)
            p,b,c,a,n,v=build_geometry(intent['patch'],self.engine.template,{})
            self.assertEqual(len(p.pattern['panels']),1);self.assertEqual(len(p.pattern['stitches']),0)
            self.assertEqual((a['strip_length'],a['strip_width']),(300.,30.))
            self.assertTrue(v['sampled_outline_valid'])
            self.assertEqual(len(a['free_edges']),4)
            self.assertEqual(a['cut_list'][0]['quantity'],1)
            paths,projection=pibo_projections(b,a,landmarks(b)['shoulder_y'])
            self.assertEqual(len(paths),2)
            self.assertAlmostEqual(projection['visible_centerline_length_each_cm']*2+
                                   projection['hidden_shoulder_length_cm'],300.)
            self.assertEqual(projection['visible_folded_width_cm'],15.)
            self.assertTrue(all(path.bbox()[2]>=landmarks(b)['shoulder_y']-1e-7 for path in paths))

    def test_broad_and_joined_shapes_are_not_relabelled_as_straight_strip(self):
        for text in ['扇形披帛','圆弧披帛','拼接披帛','交领上衣；襦裙；霞帔']:
            intent=interpret_outfit(self.engine,text,{}) or self.engine.interpret(text,None,{})
            self.assertEqual(intent['status'],'needs_input',intent)
        intent=self.engine.interpret('不要圆弧披帛，只做直幅披帛，披帛长300cm',None,{})
        self.assertEqual(intent['status'],'ready',intent)
        patch=self.engine.defaults('pibo');patch['pibo']['strip_length']['v']=150.;patch['pibo']['strip_width']['v']=70.
        with self.assertRaises(ValueError):build_geometry(patch,self.engine.template,{})

    def test_five_members_survive_zip_integrity_restoration_and_parameter_changes(self):
        text='交领上衣，衣长55cm；圆领对襟比甲，衣长80cm；襦裙，裙长95cm；双层云肩；披帛，披帛长320cm，幅宽35cm'
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);sid=str(uuid.uuid4());headers={'X-Session-Id':sid};app=create_app(self.engine,root)
            with TestClient(app) as client:
                req=client.post('/api/v1/parse',headers=headers,json={'text':text}).json()
                result=client.get('/api/v1/tasks/'+req['task_id'],headers=headers).json()['result']
                self.assertEqual(result['status'],'generated',result)
                pattern=result['pattern'];self.assertEqual([g['id'] for g in pattern['garments']],['upper','outer','lower','accessory','drape'])
                self.assertEqual(pattern['body_layout']['placement_order'][-1],'drape')
                folder=root/'patterns'/sid/pattern['svg_url'].split('/')[-2]
                verify_design(folder,pattern['integrity_version'])
                self.assertEqual(len(restore_saved_design(self.engine,root,sid,folder.name)['outfit']),5)
                with ZipFile(io.BytesIO(client.get('/api/v1/download',headers=headers).content)) as archive:
                    self.assertIsNone(archive.testzip());self.assertIn('drape/pattern.svg',archive.namelist())
                    strip=json.loads(archive.read('drape/assembly.json'))
                    self.assertEqual((strip['strip_length'],strip['strip_width']),(320.,35.))
                    self.assertIn('披帛',archive.read('drape/README.txt').decode('utf8'))
                plan=client.get('/api/v1/print/plan',headers=headers)
                self.assertEqual(plan.status_code,200,plan.text)
                self.assertTrue(any(row['panel_id']=='drape__pibo_strip' for row in plan.json()['panels']))
                response=client.put('/api/v1/design/params',headers=headers,json={'path':['pibo','strip_length'],'value':350.})
                self.assertEqual(response.status_code,200,response.text)
                response=client.put('/api/v1/body/params',headers=headers,json={'path':['height'],'value':180.})
                self.assertEqual(response.status_code,200,response.text)
                saved=app.state.sessions[sid]['folder']
                strip=json.loads((saved/'drape/assembly.json').read_text(encoding='utf8'))
                self.assertEqual((strip['strip_length'],strip['strip_width']),(350.,35.))
                # Adding or corrupting the drape cannot escape the receipt.
                (saved/'drape/pattern.svg').write_text('broken',encoding='utf8')
                with self.assertRaises(ValueError):verify_design(saved,pattern['integrity_version'])

    def test_photo_scene_keeps_drape_and_never_invents_it_from_a_cape(self):
        rows=[{'component':'cross-upper','reason':'交领上衣','features':{'upper_front':'crossed'}},
              {'component':'ruqun-skirt','reason':'下裙','features':{}},
              {'component':'pibo','reason':'连续长幅肩臂披搭','features':{'neckwear_shape':'long-drape'}}]
        scene=accounted_scene(rows)
        result=interpret_outfit_scene(self.engine,'',scene,{})
        self.assertTrue(result['suggested_outfit'],result)
        self.assertIn('pibo',[r['component'] for r in result['outfit_observations']])
        scene['observations'][2]['features']['neckwear_shape']='broad-cape'
        self.assertNotIn('suggested_outfit',interpret_outfit_scene(self.engine,'',scene,{}))

    def test_preview_contains_one_person_and_all_strip_dimensions(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'draft'
            generate_pattern(self.engine.defaults('pibo'),self.engine.template,{},folder)
            svg=ET.parse(folder/'body-layout-dimensions.svg').getroot()
            self.assertIsNotNone(svg.find('.//'+tag('g')+'[@class="body-outline"]'))
            net=svg.find(tag('g')+'[@id="net-layout"]')
            self.assertIsNone(net.find('.//'+tag('g')+'[@class="body-outline"]'))
            dims=ET.parse(folder/'pattern-dimensions.svg').getroot()
            self.assertEqual(len(dims.findall(tag('g'))),1)
            self.assertTrue(any('300.0' in (node.text or '') for node in dims.iter(tag('text'))))

    def test_folded_projection_never_crosses_itself_or_covers_the_head(self):
        for length,width in [(150.,10.),(175.,70.),(300.,30.),(500.,70.)]:
            patch=self.engine.defaults('pibo');patch['pibo']['strip_length']['v']=length;patch['pibo']['strip_width']['v']=width
            _,body,_,report,_,_=build_geometry(patch,self.engine.template,{})
            sy=landmarks(body)['shoulder_y'];paths,projection=pibo_projections(body,report,sy)
            for path in paths:
                points=[(segment.point(t).real,segment.point(t).imag) for segment in path for t in [i/30 for i in range(30)]]
                self.assertTrue(valid_outline(points),(length,width))
                self.assertGreaterEqual(path.bbox()[2],sy-1e-8)
            self.assertAlmostEqual(projection['visible_centerline_length_each_cm']*2+
                                   projection['hidden_shoulder_length_cm'],length)


if __name__=='__main__':unittest.main()
