"""Whole-garment UI controls return committed parameters and meaningful variations."""
import json
from pathlib import Path
import random
import tempfile
import unittest
import uuid
from fastapi.testclient import TestClient
from .app import create_app
from .engine import PaperEngine
from .patterns import build_geometry


class WholeControlTests(unittest.TestCase):
    def test_visible_absence_of_belt_does_not_add_an_unseen_belt_piece(self):
        engine=PaperEngine(model=object())
        for visible in ['present','absent']:
            visual={'component':'stand-robe','features':{'length':'full','upper_front':'closed',
                'front_opening':'center','waist_belt':visible}}
            result=engine.interpret('立领长衫',None,{},visual)
            self.assertEqual(result['status'],'ready',result)
            pattern=build_geometry(result['patch'],engine.template,{})[0]
            self.assertEqual('stand-robe_belt' in pattern.pattern['panels'],visible=='present')
            self.assertEqual(result['sources']['stand-robe.belt'],'image_observation')

    def test_default_response_matches_adapted_committed_length_and_random_keeps_whole_body(self):
        state=random.getstate();self.addCleanup(random.setstate,state);random.seed(109)
        with tempfile.TemporaryDirectory() as temp:
            app=create_app(PaperEngine(model=object()),Path(temp));headers={'X-Session-Id':str(uuid.uuid4())}
            with TestClient(app) as client:
                submitted=client.post('/api/v1/parse',headers=headers,json={'text':'圆领长袍，衣长130cm'}).json()
                result=client.get('/api/v1/tasks/'+submitted['task_id'],headers=headers).json()
                self.assertEqual(result['result']['status'],'generated',result)
                reset=client.post('/api/v1/design/default',headers=headers)
                self.assertEqual(reset.status_code,200,reset.text)
                self.assertEqual(reset.json(),client.get('/api/v1/design/params',headers=headers).json())
                seen=set()
                for _ in range(4):
                    changed=client.post('/api/v1/design/random',headers=headers)
                    self.assertEqual(changed.status_code,200,changed.text)
                    self.assertEqual(changed.json(),client.get('/api/v1/design/params',headers=headers).json())
                    values=changed.json()['params']['round-robe'];seen.add(tuple((key,node['v']) for key,node in values.items()))
                    folder=app.state.sessions[headers['X-Session-Id']]['folder']
                    geometry=json.loads((folder/'pattern.json').read_text(encoding='utf-8'))
                    self.assertTrue(all('round-robe_'+part in geometry['panels'] for part in ['back','front_left','front_right','sleeve_left','sleeve_right']))
                    meta=client.get('/api/v1/pattern',headers=headers).json()
                    self.assertEqual(meta['component'],'round-robe')
                    self.assertEqual(meta['parameter_sources']['round-robe.length'],'random')
                self.assertGreater(len(seen),1)


if __name__=='__main__':unittest.main()
