"""A long-sleeved short open blouse is neither banbi nor a closed standing collar."""
from collections import Counter
import io,json
from pathlib import Path
import tempfile
import unittest,uuid
from zipfile import ZipFile
from fastapi.testclient import TestClient
from .app import create_app
from .engine import PaperEngine
from .patterns import build_geometry,generate_pattern
from .outfits import interpret_outfit,interpret_outfit_scene
from .body_layout import placements,landmarks
from .vision_fixtures import accounted_scene
from .session_restore import restore_saved_design


class OpenUpperTests(unittest.TestCase):
    def setUp(self):self.engine=PaperEngine(object())

    def test_long_sleeve_short_body_and_front_openings_are_real_geometry(self):
        result=self.engine.interpret('直领对襟上衣，衣长50cm，袖长55cm，袖口整围36cm',None,{})
        self.assertEqual(result['status'],'ready',result)
        pattern,body,_,report,_,validation=build_geometry(result['patch'],self.engine.template,{})
        self.assertEqual(len(pattern.pattern['panels']),8)
        self.assertAlmostEqual(report['finished_length'],50.,places=5)
        self.assertAlmostEqual(report['sleeve_length_from_shoulder'],55.,places=5)
        self.assertEqual(report['front_opening'],'open')
        self.assertTrue(report['open_front'])
        self.assertNotIn('opening_type',result['patch']['duijin-upper'])
        fronts={'duijin-upper_front_left','duijin-upper_front_right'}
        self.assertFalse(any({r['panel'] for r in pair[:2]}==fronts for pair in pattern.pattern['stitches']))
        self.assertTrue(validation['sampled_outline_valid'])
        self.assertLess(validation['max_seam_length_difference_cm'],.02)
        posed=placements(pattern,'duijin-upper',body,None,report,landmarks(body))
        self.assertEqual(sum(p['mode']=='open-front' for p in posed),2)

    def test_actual_pipa_cuffs_and_slits_stay_matched(self):
        for body in [{},{'height':185,'bust':112,'hips':114}]:
            result=self.engine.interpret('对襟长袖上衣，衣长60cm，琵琶袖，袖口条宽4cm，侧衩高15cm',None,body)
            self.assertEqual(result['status'],'ready',result)
            p,_,_,a,_,v=build_geometry(result['patch'],self.engine.template,body)
            self.assertEqual(len(p.pattern['panels']),10)
            self.assertEqual(a['sleeve_type'],'pipa');self.assertEqual(a['cuff_band_finished_height'],4.)
            refs=Counter((r['panel'],r['edge']) for pair in p.pattern['stitches'] for r in pair[:2])
            loose=[r for r in a['free_edges'] if r['reason']=='unsewn side slit']
            self.assertEqual(len(loose),4);self.assertTrue(all(refs[(r['panel'],r['edge'])]==0 for r in loose))
            self.assertLess(v['max_seam_length_difference_cm'],.02)

    def test_closed_or_sleeveless_necklines_cannot_be_silently_replaced(self):
        for text in ['直领对襟上衣，立领','对襟长袖上衣，圆领','对襟短衫，无袖','直领对襟上衣，右斜襟']:
            self.assertEqual(self.engine.interpret(text,None,{})['status'],'needs_input',text)
        for front in ['closed','crossed','unclear']:
            scene=accounted_scene([{'component':'duijin-upper','reason':'test','features':{'upper_front':front}}])
            self.assertNotIn('suggested_component',interpret_outfit_scene(self.engine,'',scene,{}))
        scene=accounted_scene([{'component':'duijin-upper','reason':'long garment','features':{'upper_front':'open','length':'full'}}])
        self.assertNotIn('suggested_component',interpret_outfit_scene(self.engine,'',scene,{}))

    def test_generic_alias_inside_a_specific_collar_is_not_an_extra_garment(self):
        for text,c in [('立领对襟上衣','stand-upper'),('圆领对襟上衣','round-upper')]:
            self.assertEqual(self.engine.find_components(text),[c])
            self.assertEqual(self.engine.interpret(text,None,{})['status'],'ready')
            combined=interpret_outfit(self.engine,text+'；直领对襟上衣；马面裙',{})
            self.assertEqual(combined['status'],'ready',combined)
            self.assertEqual([m['component'] for m in combined['garments']],[c,'duijin-upper','mamian-skirt'])
        simple=interpret_outfit(self.engine,'直领对襟上衣；襦裙',{})
        self.assertEqual([m['id'] for m in simple['garments']],['upper','lower'])
        for longer in ['立领对襟上衣','圆领对襟上衣']:
            self.assertEqual(self.engine.find_components('不要'+longer+'，只做马面裙'),['mamian-skirt'])
            self.assertEqual(self.engine.find_components('不要'+longer+'；直领对襟上衣'),['duijin-upper'])
        self.assertEqual(self.engine.find_components('不要立领对襟上衣，只做立领领片'),['stand-collar'])

    def test_layered_full_outfit_export_and_restore_keep_the_new_outer(self):
        text='交领上衣，衣长55cm；直领对襟上衣，衣长60cm，袖长50cm；马面裙，裙长95cm；披帛，净长300cm，净幅宽30cm'
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);sid=str(uuid.uuid4());headers={'X-Session-Id':sid}
            with TestClient(create_app(self.engine,root)) as client:
                task=client.post('/api/v1/parse',headers=headers,json={'text':text}).json()
                result=client.get('/api/v1/tasks/'+task['task_id'],headers=headers).json()['result']
                self.assertEqual(result['status'],'generated',result)
                members=result['pattern']['garments']
                self.assertEqual([g['id'] for g in members],['upper','outer','lower','drape'])
                self.assertEqual(members[1]['component'],'duijin-upper')
                folder=root/'patterns'/sid/result['pattern']['svg_url'].split('/')[-2]
                self.assertEqual(len(restore_saved_design(self.engine,root,sid,folder.name)['outfit']),4)
                response=client.get('/api/v1/download',headers=headers)
                with ZipFile(io.BytesIO(response.content)) as archive:
                    self.assertIsNone(archive.testzip());self.assertIn('outer/assembly.json',archive.namelist())
                    self.assertEqual(json.loads(archive.read('outer/assembly.json'))['front_opening'],'open')
                plan=client.get('/api/v1/print/plan',headers=headers)
                self.assertEqual(plan.status_code,200,plan.text)


if __name__=='__main__':unittest.main()
