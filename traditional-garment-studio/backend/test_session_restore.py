"""Restart recovery must preserve actual design files and never revive image tokens."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid

from fastapi.testclient import TestClient
from .app import create_app
from .engine import PaperEngine


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.headers={'X-Session-Id':str(uuid.uuid4())}
        self.open()

    def open(self):
        self.app=create_app(PaperEngine(model=object()),self.root)
        self.client=TestClient(self.app)
        self.addCleanup(self.client.close)

    def generate(self,text):
        response=self.client.post('/api/v1/parse',headers=self.headers,json={'text':text})
        self.assertEqual(response.status_code,202,response.text)
        result=self.client.get('/api/v1/tasks/'+response.json()['task_id'],headers=self.headers).json()
        self.assertEqual(result['status'],'done',result)
        self.assertEqual(result['result']['status'],'generated',result)
        return result['result']

    def get(self,path):
        response=self.client.get('/api/v1/'+path,headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def test_single_design_body_provenance_and_export_survive_restart(self):
        before=self.generate('明代马面裙，裙长95cm，常服。身高170cm，腰围80cm。')
        params=self.get('design/params');body=self.get('body/params')
        state=self.app.state.sessions[self.headers['X-Session-Id']]
        folder=state['folder']
        hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}
        state['image_proposal']={'id':'expired-test-only-proposal'}
        self.open()
        self.assertEqual(self.get('pattern'),before['pattern'])
        self.assertEqual(self.get('design/params'),params)
        self.assertEqual(self.get('body/params'),body)
        restored=self.app.state.sessions[self.headers['X-Session-Id']]
        self.assertIsNone(restored['image_proposal'])
        self.assertEqual(self.app.state.tasks,{})
        self.assertFalse(restored['busy'])
        self.assertEqual({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()},hashes)
        self.assertEqual(self.get('print/plan')['fabric_panel_count'],3)
        self.assertEqual(self.client.get('/api/v1/download',headers=self.headers).status_code,200)

    def test_both_outfits_restore_all_members_and_keep_fixed_cm_after_body_edit(self):
        for text,upper in [('明代褙子，衣长110cm；马面裙，裙长95cm，常服。身高170cm，腰围80cm。','beizi'),
                           ('唐代半臂，衣长50cm；襦裙，裙长95cm，常服。身高170cm，腰围80cm。','banbi')]:
            with self.subTest(upper=upper):
                before=self.generate(text)
                params=self.get('design/params')
                self.open()
                self.assertEqual(self.get('pattern'),before['pattern'])
                self.assertEqual(self.get('design/params'),params)
                response=self.client.put('/api/v1/body/params',headers=self.headers,json={'path':['height'],'value':180})
                self.assertEqual(response.status_code,200,response.text)
                after=self.get('pattern')
                self.assertEqual(after['panel_count'],before['pattern']['panel_count'])
                self.assertEqual(after['absolute_lengths_cm'],before['pattern']['absolute_lengths_cm'])
                self.assertNotEqual(after['svg_url'],before['pattern']['svg_url'])

    def test_incomplete_or_corrupt_newer_folder_falls_back_without_touching_old_files(self):
        first=self.generate('明代马面裙，裙长90cm，常服')
        old_folder=self.app.state.sessions[self.headers['X-Session-Id']]['folder']
        self.generate('明代马面裙，裙长95cm，常服')
        latest=self.app.state.sessions[self.headers['X-Session-Id']]['folder']
        (latest/'metadata.json').write_text('{truncated',encoding='utf-8')
        os.utime(old_folder/'metadata.json',(1,1))
        incomplete=latest.parent/uuid.uuid4().hex
        incomplete.mkdir();(incomplete/'pattern.svg').write_text('incomplete',encoding='utf-8')
        self.open()
        self.assertEqual(self.get('pattern'),first['pattern'])
        self.assertTrue(latest.is_dir())
        self.assertTrue(incomplete.is_dir())
        self.generate('明代马面裙，裙长95cm，常服')
        latest=self.app.state.sessions[self.headers['X-Session-Id']]['folder']
        (latest/'pattern-dimensions.svg').write_text('<svg>truncated',encoding='utf-8')
        self.open()
        self.assertEqual(self.get('pattern'),first['pattern'])

    def test_every_component_restores_the_same_parameters_and_piece_count(self):
        for component,name in self.app.state.engine.names.items():
            with self.subTest(component=component):
                before=self.generate(name)
                params=self.get('design/params')
                self.open()
                self.assertEqual(self.get('pattern'),before['pattern'])
                self.assertEqual(self.get('design/params'),params)

    def test_other_session_and_external_resource_url_are_not_restored(self):
        self.generate('唐代半臂，常服')
        folder=self.app.state.sessions[self.headers['X-Session-Id']]['folder']
        meta=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
        meta['svg_url']='https://example.invalid/untrusted.svg'
        (folder/'metadata.json').write_text(json.dumps(meta),encoding='utf-8')
        self.open()
        self.assertIsNone(self.get('pattern')['svg_url'])
        other={'X-Session-Id':str(uuid.uuid4())}
        self.assertIsNone(self.client.get('/api/v1/pattern',headers=other).json()['svg_url'])

    def test_evicted_session_restores_without_a_process_restart(self):
        before=self.generate('宋代褙子，衣长105cm，常服')
        self.app.state.sessions.clear()
        self.assertEqual(self.get('pattern'),before['pattern'])


if __name__=='__main__':
    unittest.main()
