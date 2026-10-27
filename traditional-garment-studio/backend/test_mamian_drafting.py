"""Physical allowance and export checks for the readable cutting sheets."""
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from fastapi.testclient import TestClient
from training.schema import merge_defaults
from .app import create_app
from .engine import PaperEngine
from .mamian_v2 import build_mamian
from .mamian_drafting import cut_data
from .patterns import body_from


class NoModel:
    def text(self,*args):
        raise AssertionError('Explicit dimensions must not invoke a model')


class MamianDraftingTests(unittest.TestCase):
    def test_cut_dimensions_and_fabric_allowances_preserve_net_geometry(self):
        engine=PaperEngine(model=NoModel())
        d=merge_defaults(engine.defaults('mamian-skirt'),engine.template)
        d['mamian-skirt']['mamian_width']['v']=20
        d['mamian-skirt']['pleat_ruffle']['v']=2
        _,c=build_mamian(body_from({'waist':80,'hips':80}),d)
        data=cut_data(c)
        a,b,band=data['pieces']
        self.assertEqual(a['net_width_cm'],80)
        self.assertEqual(a['cut_width_cm'],82)
        self.assertEqual(a['cut_height_cm']-a['net_height_cm'],4)
        self.assertEqual(a['cut_outline'][0],[-1,-1])
        self.assertEqual(a['cut_outline'][2],[81,a['net_height_cm']+3])
        self.assertEqual(a['net_width_cm'],b['net_width_cm'])
        self.assertEqual(band['net_width_cm'],190)  # 100 attachment + 2*45 ties
        self.assertEqual(band['cut_width_cm'],192)
        self.assertEqual(band['cut_height_cm']-band['net_height_cm'],2)
        for piece in [a,b]:
            self.assertEqual(len(piece['folds']),8)
            self.assertTrue(all(20<v['x']<60 for v in piece['folds']))
            self.assertEqual(piece['waist_match_x_cm'],[0,20,60,80])
        self.assertEqual(band['waist_match_x_cm'],[45,65,85,105,125,145])

    def test_live_contract_and_zip_include_cut_style_and_detail_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TestClient(create_app(PaperEngine(model=NoModel()),Path(tmp))) as client:
                headers={'X-Session-Id':str(uuid.uuid4())}
                response=client.post('/api/v1/parse',headers=headers,json={'text':'明代马面裙，裙长95cm，马面宽28cm，常服'})
                task=client.get('/api/v1/tasks/'+response.json()['task_id'],headers=headers).json()
                self.assertEqual(task['status'],'done',task)
                pattern=task['result']['pattern']
                ns='{http://www.w3.org/2000/svg}'
                for key in ['cutting_svg_url','style_svg_url','pleat_detail_svg_url','cutting_a_svg_url','cutting_b_svg_url','cutting_waistband_svg_url']:
                    response=client.get(pattern[key])
                    self.assertEqual(response.status_code,200)
                    root=ET.fromstring(response.content)
                    self.assertTrue(root.attrib['width'].endswith('cm'))
                whole=ET.fromstring(client.get(pattern['cutting_svg_url']).content)
                self.assertEqual(len(whole.findall('.//'+ns+'rect[@class="cut-outline"]')),3)
                self.assertEqual(len(whole.findall('.//'+ns+'rect[@class="door-zone"]')),4)
                self.assertEqual(len(whole.findall('.//'+ns+'line[@class="fold-mark"]')),16)
                texts=' '.join(t.text or '' for t in whole.iter(ns+'text'))
                for token in ['M1','M2','M3','M4','P1','P4','Ac–Ad + Ba–Bb','下摆余量 3 cm']:
                    self.assertIn(token,texts)
                with ZipFile(io.BytesIO(client.get('/api/v1/download',headers=headers).content)) as z:
                    self.assertIsNone(z.testzip())
                    self.assertEqual(len(z.namelist()),20)
                    cut=json.loads(z.read('cutting.json'))
                    self.assertAlmostEqual(cut['pieces'][0]['net_height_cm'],95,places=5)
                    self.assertAlmostEqual(cut['pieces'][0]['cut_height_cm'],99,places=5)
                    self.assertIn('style.svg',z.namelist())
                    self.assertIn('pleat-detail.svg',z.namelist())
                    net=json.loads(z.read('pattern.json'))
                    self.assertEqual(len(net['panels']),3)
