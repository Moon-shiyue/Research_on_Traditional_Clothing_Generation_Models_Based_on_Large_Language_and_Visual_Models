"""Whole ensembles must keep every garment through edit, restore and export."""
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from zipfile import ZipFile

from fastapi.testclient import TestClient
from .app import create_app
from .engine import PaperEngine
from .design_integrity import verify_design


class CompleteEnsembleTests(unittest.TestCase):
    def test_three_items_and_robe_accessory_survive_edit_restart_export_and_integrity(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);sid=str(uuid.uuid4());headers={'X-Session-Id':sid}
            app=create_app(PaperEngine(model=object()),root)
            with TestClient(app) as client:
                for text,expected,count in [
                    ('交领上衣，衣长60cm；马面裙，裙长95cm；云肩，双层', ['upper','lower','accessory'],16),
                    ('圆领长袍，衣长130cm；云肩，双层', ['upper','accessory'],14),
                    ('立领上衣，衣长60cm，琵琶袖，袖长55cm，袖口条宽4cm；马面裙，裙长95cm', ['upper','lower'],15)]:
                    with self.subTest(text=text):
                        submitted=client.post('/api/v1/parse',headers=headers,json={'text':text})
                        self.assertEqual(submitted.status_code,202,submitted.text)
                        task=client.get('/api/v1/tasks/'+submitted.json()['task_id'],headers=headers).json()
                        self.assertEqual(task['status'],'done',task)
                        result=task['result'];self.assertEqual(result['status'],'generated',result)
                        self.assertEqual(result['pattern']['panel_count'],count)
                        self.assertEqual([g['id'] for g in result['pattern']['garments']],expected)
                        folder=app.state.sessions[sid]['folder']
                        receipt=json.loads((folder/'design-receipt.json').read_text(encoding='utf-8'))
                        if 'accessory' in expected:self.assertIn('accessory/pattern.json',receipt['files'])
                        edited=client.put('/api/v1/body/params',headers=headers,json={'path':['height'],'value':180})
                        self.assertEqual(edited.status_code,200,edited.text)
                        self.assertEqual(edited.json()['panel_count'],count)
                        for key,value in result['pattern']['absolute_lengths_cm'].items():
                            self.assertEqual(edited.json()['absolute_lengths_cm'][key],value)
                        plan=client.get('/api/v1/print/plan',headers=headers)
                        self.assertEqual(plan.status_code,200,plan.text)
                        archive=client.get('/api/v1/download',headers=headers)
                        self.assertEqual(archive.status_code,200,archive.text)
                        with ZipFile(io.BytesIO(archive.content)) as z:
                            self.assertIsNone(z.testzip())
                            for role in expected:self.assertIn(role+'/pattern.json',z.namelist())
                            self.assertEqual(sum(len(json.loads(z.read(role+'/pattern.json'))['panels']) for role in expected),count)
                        with TestClient(create_app(PaperEngine(model=object()),root)) as fresh:
                            restored=fresh.get('/api/v1/pattern',headers=headers).json()
                            self.assertEqual(restored['panel_count'],count)
                            self.assertEqual(restored['svg_url'],edited.json()['svg_url'])
                            if 'accessory' in expected:
                                current=app.state.sessions[sid]['folder']
                                (current/'accessory'/'assembly.json').write_text('{}',encoding='utf-8')
                                with self.assertRaises(ValueError):verify_design(current,restored['integrity_version'])

    def test_cuff_band_is_included_once_in_shoulder_to_wrist_length(self):
        from .patterns import build_geometry
        engine=PaperEngine(model=object())
        intent=engine.interpret('立领上衣，琵琶袖，袖长55cm，袖口条宽4cm',None,{})
        self.assertEqual(intent['status'],'ready',intent)
        pattern,_,_,report,_,validation=build_geometry(intent['patch'],engine.template,{})
        self.assertAlmostEqual(report['sleeve_length_from_shoulder'],55.,places=5)
        self.assertAlmostEqual(report['sleeve_body_length']+report['dropped_shoulder_length']+4,55.,places=5)
        self.assertIn('stand-upper_cuff_left',pattern.pattern['panels'])
        self.assertLess(validation['max_seam_length_difference_cm'],.02)


if __name__=='__main__':unittest.main()
