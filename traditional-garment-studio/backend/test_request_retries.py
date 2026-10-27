"""A lost response must not duplicate recognition or consume a choice twice."""
import copy
import io
from pathlib import Path
import tempfile
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from PIL import Image
from .app import create_app
from .engine import PaperEngine
from .test_sequential_choices import Vision,scene


class RequestRetryTests(unittest.TestCase):
    def upload(self,c,h):
        data=io.BytesIO();Image.new('RGB',(40,80),'white').save(data,format='PNG')
        return c.post('/api/v1/upload/image',headers=h,files={'file':('ref.png',data.getvalue(),'image/png')}).json()['image_id']

    def test_lost_acknowledgement_reuses_each_task_across_two_choices_and_complete_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            model=Vision(scene(extras=True));app=create_app(PaperEngine(model),Path(temp));h={'X-Session-Id':str(uuid.uuid4())}
            with TestClient(app) as c:
                image=self.upload(c,h)
                def twice(payload):
                    first=c.post('/api/v1/parse',headers=h,json=payload)
                    self.assertEqual(first.status_code,202,first.text)
                    again=c.post('/api/v1/parse',headers=h,json=payload)
                    self.assertEqual(again.status_code,202,again.text)
                    self.assertEqual(again.json()['task_id'],first.json()['task_id'])
                    task=c.get('/api/v1/tasks/'+first.json()['task_id'],headers=h).json()
                    self.assertEqual(task['status'],'done',task)
                    return task['result']
                first_payload={'image':image,'request_id':uuid.uuid4().hex}
                first=twice(first_payload)
                second_payload={'text':first['suggested_text'],'image_proposal_id':first['image_proposal_id'],
                                'innerwear_choice':'chest-wrap','request_id':uuid.uuid4().hex}
                second=twice(second_payload)
                self.assertIn('skirt_choices',second)
                third_payload={'text':second['suggested_text'],'image_proposal_id':second['image_proposal_id'],
                               'skirt_choice':'ruqun-skirt','request_id':uuid.uuid4().hex}
                result=twice(third_payload)
                self.assertEqual(result['status'],'generated',result)
                self.assertEqual(len(result['pattern']['garments']),5)
                self.assertEqual(len(app.state.tasks),3)
                self.assertEqual(model.calls,1)
                folders=[p for p in (Path(temp)/'patterns'/h['X-Session-Id']).iterdir() if p.is_dir()]
                self.assertEqual(len(folders),1)
                (Path(temp)/'uploads'/h['X-Session-Id']/(image+'.jpg')).unlink()
                cached=c.post('/api/v1/parse',headers=h,json=first_payload)
                self.assertEqual(cached.status_code,202,cached.text)
                self.assertEqual(model.calls,1)
                # A reused identifier cannot change text, scope or selected type.
                for change in [{'text':'different'},{'scope':'component'},{'skirt_choice':'mamian-skirt'}]:
                    changed=c.post('/api/v1/parse',headers=h,json=dict(third_payload,**change))
                    self.assertEqual(changed.status_code,409,changed.text)
                    self.assertEqual(changed.json()['error']['code'],'request_id_conflict')
                foreign=c.post('/api/v1/parse',headers={'X-Session-Id':str(uuid.uuid4())},json=first_payload)
                self.assertEqual(foreign.status_code,400)
                self.assertEqual(foreign.json()['error']['code'],'image_not_found')
                self.assertEqual(len(app.state.tasks),3)

    def test_an_inflight_duplicate_reads_the_accepted_task_but_different_work_still_conflicts(self):
        started=threading.Event();release=threading.Event()
        class BlockingVision(Vision):
            def image_outfit(self,*args):
                self.calls+=1;started.set()
                if not release.wait(8):raise RuntimeError('test release timeout')
                return copy.deepcopy(self.value)
        with tempfile.TemporaryDirectory() as temp:
            model=BlockingVision(scene());app=create_app(PaperEngine(model),Path(temp));h={'X-Session-Id':str(uuid.uuid4())}
            with TestClient(app) as c,ThreadPoolExecutor(max_workers=1) as executor:
                payload={'image':self.upload(c,h),'request_id':uuid.uuid4().hex}
                future=executor.submit(c.post,'/api/v1/parse',headers=h,json=payload)
                try:
                    self.assertTrue(started.wait(4))
                    duplicate=c.post('/api/v1/parse',headers=h,json=payload)
                    self.assertEqual(duplicate.status_code,202,duplicate.text)
                    self.assertEqual(len(app.state.tasks),1)
                    different=c.post('/api/v1/parse',headers=h,json=dict(payload,request_id=uuid.uuid4().hex))
                    self.assertEqual(different.status_code,409,different.text)
                    self.assertEqual(model.calls,1)
                finally:release.set()
                original=future.result(timeout=10)
                self.assertEqual(original.json()['task_id'],duplicate.json()['task_id'])


if __name__=='__main__':unittest.main()
