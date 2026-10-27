import io
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient
from .app import create_app
from .engine import PaperEngine
from .outfits import interpret_outfit, interpret_outfit_image
from .patterns import build_geometry
from .whole_catalog import NAMES, WHOLE,SLEEVED
from .session_restore import restore_saved_design, restore_last_design
from .design_integrity import seal_design


class WholeGarmentTests(unittest.TestCase):
    def setUp(self):
        self.engine=PaperEngine(model=object())

    def test_all_complete_templates_have_bodies_sleeves_and_matched_seams_across_bodies(self):
        for component in NAMES:
            for body in [{'height':150,'bust':78,'hips':86},{'height':185,'bust':112,'hips':114},{}]:
                with self.subTest(component=component,body=body):
                    pattern,_,_,report,_,validation=build_geometry(self.engine.defaults(component),self.engine.template,body)
                    panels=pattern.pattern['panels']
                    self.assertEqual(len(panels),8 if component=='duijin-upper' else 11 if component.endswith('robe') else 10)
                    for part in ['back','front_left','front_right','neck_front_facing' if component=='duijin-upper' else 'neck_binding']+(
                            ['armhole_binding_left','armhole_binding_right'] if component=='bijia' else ['sleeve_left','sleeve_right']):
                        self.assertIn(component+'_'+part,panels)
                    if component=='bijia':self.assertFalse(any(name.startswith('bijia_sleeve_') for name in panels))
                    self.assertTrue(report['whole_garment'])
                    self.assertLess(validation['max_seam_length_difference_cm'],.02)
                    self.assertTrue(validation['sampled_outline_valid'])

    def test_text_scope_preserves_whole_or_explicit_local_and_cm_lengths(self):
        for name,component in [(n,c) for c,n in NAMES.items()]+[('交领袍','cross-robe'),('上襦','cross-upper')]:
            with self.subTest(name=name):
                result=self.engine.interpret(name+'，衣长'+('130' if component.endswith('robe') else '60')+'cm'+('' if component=='bijia' else '，袖长55cm'),None,{})
                self.assertEqual(result['status'],'ready',result)
                self.assertEqual(result['component'],component)
                if component!='bijia':self.assertEqual(result['absolute_lengths_cm'][component+'.sleeve_length'],55.)
        local=self.engine.interpret('只做交领袍的交领领片',None,{})
        self.assertEqual(local['component'],'cross-collar',local)
        unsupported=self.engine.interpret('交领长袍，曲裾结构',None,{})
        self.assertEqual(unsupported['status'],'needs_input')

    def test_new_upper_skirt_pairs_include_full_upper_not_collar(self):
        for component in ['cross-upper','round-upper','stand-upper']:
            for lower,name in [('mamian-skirt','马面裙'),('ruqun-skirt','襦裙')]:
                text=NAMES[component]+'，衣长60cm，袖长55cm；'+name+'，裙长95cm'
                result=interpret_outfit(self.engine,text,{})
                self.assertEqual(result['status'],'ready',result)
                self.assertEqual([g['component'] for g in result['garments']],[component,lower])
                self.assertEqual(result['garments'][0]['absolute_lengths_cm'][component+'.length'],60.)

    def test_pipa_sleeves_connect_to_body_and_remain_equal_length(self):
        for component in SLEEVED:
            intent=self.engine.interpret(NAMES[component]+'，琵琶袖，袖口整围22cm，袖长55cm',None,{})
            self.assertEqual(intent['status'],'ready',intent)
            pattern,_,_,report,_,validation=build_geometry(intent['patch'],self.engine.template,{})
            self.assertEqual(report['sleeve_type'],'pipa')
            self.assertLess(validation['max_seam_length_difference_cm'],.02)
            for side in ['left','right']:
                sleeve=component+'_sleeve_'+side
                self.assertEqual(sum(any(r['panel']==sleeve for r in pair) for pair in pattern.pattern['stitches']),3)

    def test_legacy_complete_design_migrates_from_geometry_and_never_falls_back_to_collar(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);sid=str(uuid.uuid4());headers={'X-Session-Id':sid}
            app=create_app(self.engine,root)
            with TestClient(app) as client:
                def generate(text):
                    response=client.post('/api/v1/parse',headers=headers,json={'text':text}).json()
                    return client.get('/api/v1/tasks/'+response['task_id'],headers=headers).json()['result']
                generate('只做圆领领片')
                original=generate('交领上衣；襦裙，裙长95cm')
                self.assertEqual(original['status'],'generated',original)
                folder=app.state.sessions[sid]['folder']
                # Produce exactly the additive-control-free first revision.
                child=folder/'upper';patch=json.loads((child/'design.json').read_text(encoding='utf-8'))
                patch['cross-upper'].pop('sleeve_type')
                patch['cross-upper'].pop('cuff_band_height')
                patch['cross-upper'].pop('side_slit')
                (child/'design.json').write_text(json.dumps(patch),encoding='utf-8')
                legacy_meta=json.loads((child/'metadata.json').read_text(encoding='utf-8'))
                legacy_meta['assembly']['version']='whole-garments-2026-10-25-v1'
                (child/'metadata.json').write_text(json.dumps(legacy_meta),encoding='utf-8')
                combined=json.loads((folder/'design.json').read_text(encoding='utf-8'))
                combined['garments'][0]['patch']=patch
                (folder/'design.json').write_text(json.dumps(combined),encoding='utf-8');seal_design(folder)
                before={p: p.read_bytes() for p in [folder/'design.json',child/'design.json']}
                restored=restore_saved_design(self.engine,root,sid,folder.name)
                self.assertEqual(restored['pattern']['panel_count'],19)
                self.assertEqual(restored['outfit'][0]['patch']['cross-upper']['sleeve_type']['v'],0)
                for path,data in before.items():self.assertEqual(path.read_bytes(),data)
                # A corrupt full outfit cannot revive the preceding collar.
                (folder/'pattern.svg').write_text('broken',encoding='utf-8')
                self.assertIsNone(restore_last_design(self.engine,root,sid))

    def test_complete_image_never_discards_uncertain_member_or_returns_local(self):
        class Vision:
            def image_outfit(self,path,names):
                from .vision_fixtures import accounted_scene
                return accounted_scene(self.observations)
        model=Vision();self.engine.model=model
        cases=[{'component':'cross-collar','reason':'领型清楚','features':{}},
               {'component':None,'reason':'下裙被挡','features':{}}]
        model.observations=cases
        self.assertEqual(interpret_outfit_image(self.engine,'',Path('unused'),{})['status'],'needs_input')
        self.assertNotIn('suggested_component',interpret_outfit_image(self.engine,'',Path('unused'),{}))
        model.observations=[{'component':'cross-robe','reason':'完整交领袍','features':{'upper_front':'crossed','sleeve_shape':'wide'}}]
        proposal=interpret_outfit_image(self.engine,'',Path('unused'),{})
        self.assertEqual(proposal['suggested_component'],'cross-robe',proposal)
        model.observations=[
            {'component':'cross-upper','reason':'完整上衣','features':{'upper_front':'crossed'}},
            {'component':'mamian-skirt','reason':'下裙','features':{}},
            {'component':'cloud-shoulder','reason':'云肩','features':{}},
            {'component':None,'reason':'另有披帛','features':{}}]
        refused=interpret_outfit_image(self.engine,'',Path('unused'),{})
        self.assertEqual(refused['status'],'needs_input')
        self.assertNotIn('suggested_outfit',refused)
        self.assertIn('不会只输出其它部分',refused['reply'])

    def test_actual_generation_zip_history_and_fixed_lengths_after_body_change(self):
        with tempfile.TemporaryDirectory() as temp:
            app=create_app(self.engine,Path(temp));headers={'X-Session-Id':str(uuid.uuid4())}
            with TestClient(app) as client:
                def generate(text):
                    task=client.post('/api/v1/parse',headers=headers,json={'text':text}).json()
                    result=client.get('/api/v1/tasks/'+task['task_id'],headers=headers).json()
                    self.assertEqual(result['status'],'done',result)
                    self.assertEqual(result['result']['status'],'generated',result)
                    return result['result']
                for text,count in [('交领长袍，衣长130cm，袖长55cm',11),
                                   ('圆领长袍，衣长130cm',11),
                                   ('立领上衣，衣长60cm；马面裙，裙长95cm',13),
                                   ('交领上衣，衣长60cm；襦裙，裙长95cm',19)]:
                    with self.subTest(text=text):
                        result=generate(text)
                        self.assertEqual(result['pattern']['panel_count'],count)
                        response=client.get('/api/v1/download',headers=headers)
                        self.assertEqual(response.status_code,200,response.text)
                        with ZipFile(io.BytesIO(response.content)) as archive:
                            self.assertIsNone(archive.testzip())
                            self.assertIn('README.txt',archive.namelist())
                        self.assertEqual(client.get(result['pattern']['body_layout_dimension_svg_url']).status_code,200)
                        history=client.get('/api/v1/design/history',headers=headers)
                        self.assertEqual(history.status_code,200,history.text)


if __name__=='__main__':unittest.main()
