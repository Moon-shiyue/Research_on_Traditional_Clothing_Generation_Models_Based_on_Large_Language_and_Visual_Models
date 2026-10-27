"""Selecting a prior complete result is reversible and survives a process restart."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from fastapi.testclient import TestClient
from PIL import Image
from .app import create_app
from .engine import PaperEngine


class Model:
    def text(self,*_):
        raise AssertionError('Explicit inputs need no weights')
    def image(self,*_):
        return {'component':'cloud-shoulder','reason':'Controlled visible layer',
                'features':{'cloud_layers':1,'tassels':'absent'}}


class HistoryTests(unittest.TestCase):
    def test_drape_and_five_member_history_summaries_restore_without_omitting_any_member(self):
        single=self.parse(text='直幅披帛，披帛长320cm，幅宽30cm')['pattern'];single_id=self.folder().name
        full=self.parse(text='直幅系带抹胸；直领对襟上衣；马面裙；双层云肩；披帛，披帛长300cm，幅宽25cm')['pattern']
        full_id=self.folder().name
        for _ in range(2):
            history=self.get('design/history')['items']
            self.assertEqual(len(history),2)
            one=next(item for item in history if item['design_id']==single_id)
            five=next(item for item in history if item['design_id']==full_id)
            self.assertIn('披帛长320cm/幅宽30cm',one['summary'])
            self.assertIn('披帛长300cm/幅宽25cm',five['summary'])
            self.assertIn('围前净高30cm',five['summary'])
            self.assertEqual(five['panel_count'],full['panel_count'])
            self.assertEqual(self.restore(single_id).status_code,200)
            self.assertEqual(self.get('pattern'),single)
            self.assertEqual(self.restore(full_id).status_code,200)
            self.assertEqual(self.get('pattern'),full)
            self.open()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.headers={'X-Session-Id':str(uuid.uuid4())}
        self.open()

    def open(self):
        self.app=create_app(PaperEngine(Model()),self.root)
        self.client=TestClient(self.app);self.addCleanup(self.client.close)

    def parse(self,**payload):
        payload.setdefault('scope','component')
        response=self.client.post('/api/v1/parse',headers=self.headers,json=payload)
        self.assertEqual(response.status_code,202,response.text)
        task=self.client.get('/api/v1/tasks/'+response.json()['task_id'],headers=self.headers).json()
        self.assertEqual(task['status'],'done',task)
        return task['result']

    def get(self,path):
        response=self.client.get('/api/v1/'+path,headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def restore(self,ident):
        return self.client.post('/api/v1/design/restore',headers=self.headers,json={'design_id':ident})

    def folder(self):
        return self.app.state.sessions[self.headers['X-Session-Id']]['folder']

    def test_restore_older_body_and_fixed_lengths_without_rewriting_design_artifacts(self):
        before=self.parse(text='马面裙，裙长90cm，身高170cm，腰围80cm')['pattern']
        folder=self.folder()
        original={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}
        params=self.get('design/params');body=self.get('body/params')
        self.parse(text='宋代褙子，衣长110cm，身高175cm，腰围88cm')
        history=self.get('design/history')['items']
        self.assertEqual(len(history),2)
        self.assertEqual(sum(item['current'] for item in history),1)
        older=next(item for item in history if item['design_id']==folder.name)
        self.assertIn('裙长90.0cm',older['summary'])
        self.assertIn('身高170cm',older['summary'])
        self.assertIn('腰围80cm',older['summary'])
        response=self.restore(folder.name)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.get('pattern'),before)
        self.assertEqual(self.get('design/params'),params)
        self.assertEqual(self.get('body/params'),body)
        self.assertEqual({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()},original)
        self.open()
        self.assertEqual(self.get('pattern'),before)
        self.assertEqual(self.get('body/params'),body)
        self.assertTrue(next(i for i in self.get('design/history')['items'] if i['design_id']==folder.name)['current'])
        self.assertEqual(self.client.get('/api/v1/download',headers=self.headers).status_code,200)

    def test_reference_and_outfit_can_both_be_restored_without_reviving_proposals(self):
        raw=io.BytesIO();Image.new('RGB',(40,50)).save(raw,format='PNG')
        upload=self.client.post('/api/v1/upload/image',headers=self.headers,
            files={'file':('cloud.png',raw.getvalue(),'image/png')}).json()
        suggestion=self.parse(image=upload['image_id'])
        pictured=self.parse(text=suggestion['suggested_text'],image_proposal_id=suggestion['image_proposal_id'])['pattern']
        picture_id=self.folder().name
        outfit=self.parse(text='半臂，衣长50cm；襦裙，裙长95cm')['pattern']
        outfit_id=self.folder().name
        self.assertEqual(self.restore(picture_id).status_code,200)
        self.assertEqual(self.get('pattern'),pictured)
        self.assertEqual(self.client.get(pictured['reference_image_url']).content,self.client.get(upload['url']).content)
        self.assertIsNone(self.app.state.sessions[self.headers['X-Session-Id']]['image_proposal'])
        self.assertEqual(self.restore(outfit_id).status_code,200)
        self.assertEqual(self.get('pattern'),outfit)
        self.open()
        self.assertEqual(self.get('pattern'),outfit)

    def test_invalid_corrupt_or_other_session_design_never_replaces_current(self):
        self.parse(text='半臂，衣长50cm');broken=self.folder()
        before=self.parse(text='马面裙，裙长95cm')['pattern']
        (broken/'pattern-dimensions.svg').write_text('<svg>broken',encoding='utf-8')
        for ident in [broken.name,'a'*32,'../'+'a'*29]:
            response=self.restore(ident)
            self.assertEqual(response.status_code,422,response.text)
            self.assertEqual(self.get('pattern'),before)
        outsider={'X-Session-Id':str(uuid.uuid4())}
        self.assertEqual(self.client.get('/api/v1/design/history',headers=outsider).json()['items'],[])
        response=self.client.post('/api/v1/design/restore',headers=outsider,json={'design_id':self.folder().name})
        self.assertEqual(response.status_code,422)
        self.assertEqual(len(self.get('design/history')['items']),1)

    def test_busy_restore_conflicts_and_corrupt_selection_falls_back_to_latest_complete(self):
        first=self.parse(text='半臂，衣长50cm')['pattern'];first_id=self.folder().name
        latest=self.parse(text='马面裙，裙长95cm')['pattern']
        state=self.app.state.sessions[self.headers['X-Session-Id']]
        state['busy']=True
        self.assertEqual(self.restore(first_id).status_code,409)
        state['busy']=False
        self.assertEqual(self.get('pattern'),latest)
        (self.folder().parent/'current.json').write_text('{truncated',encoding='utf-8')
        self.open()
        self.assertEqual(self.get('pattern'),latest)

    def test_recent_history_is_bounded_and_needs_input_adds_no_version(self):
        for i in range(12):
            self.parse(text='马面裙，裙长'+str(85+i)+'cm')
        history=self.get('design/history')['items']
        self.assertEqual(len(history),10)
        self.assertEqual(sum(i['current'] for i in history),1)
        self.parse(text='马面裙，裙长80至90cm')
        self.assertEqual(self.get('design/history')['items'],history)

    def test_valid_json_geometry_or_body_change_is_rejected_without_replacing_current(self):
        for file in ['pattern.json','body.json','metadata.json','preview.svg']:
            with self.subTest(file=file):
                self.parse(text='半臂，衣长50cm');candidate=self.folder()
                before=self.parse(text='马面裙，裙长95cm')['pattern']
                if file=='preview.svg':
                    content=(candidate/file).read_text(encoding='utf-8')
                    (candidate/file).write_text(content.replace('#73717d','#ff0000'),encoding='utf-8')
                    self.assertEqual(self.restore(candidate.name).status_code,422)
                    self.assertEqual(self.get('pattern'),before)
                    continue
                data=json.loads((candidate/file).read_text(encoding='utf-8'))
                if file=='pattern.json':
                    next(iter(data['panels'].values()))['vertices'][0][0]+=1
                elif file=='body.json':
                    data['waist']+=1
                else:
                    data['parameter_sources']['banbi.length']='unknown_changed_source'
                (candidate/file).write_text(json.dumps(data),encoding='utf-8')
                response=self.restore(candidate.name)
                self.assertEqual(response.status_code,422,response.text[:200])
                self.assertEqual(self.get('pattern'),before)

    def test_partial_commit_without_receipt_cannot_be_selected_or_restored_at_restart(self):
        before=self.parse(text='半臂，衣长50cm')['pattern']
        self.parse(text='马面裙，裙长95cm');candidate=self.folder()
        receipt=candidate/'design-receipt.json'
        self.assertTrue(receipt.is_file())
        receipt.unlink()
        self.open()
        self.assertEqual(self.get('pattern'),before)

    def test_export_and_print_cache_do_not_change_saved_design_integrity(self):
        before=self.parse(text='云肩，层数一，无穗须')['pattern']
        ident=self.folder().name
        self.assertEqual(self.client.post('/api/v1/download/link',headers=self.headers).status_code,200)
        plan=self.get('print/plan')
        response=self.client.post('/api/v1/print/link',headers=self.headers,json={'pattern_url':plan['pattern_url']})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.restore(ident).status_code,200)
        self.open()
        self.assertEqual(self.get('pattern'),before)

    def test_changed_current_files_cannot_be_exported_as_valid_zip_or_print(self):
        self.parse(text='半臂，衣长50cm');original_id=self.folder().name
        self.parse(text='马面裙，裙长95cm')
        source=self.folder()/'pattern.json'
        data=json.loads(source.read_text(encoding='utf-8'))
        next(iter(data['panels'].values()))['vertices'][0][0]+=1
        source.write_text(json.dumps(data),encoding='utf-8')
        for method,path in [('get','download'),('post','download/link'),('get','print/plan'),('post','print/link')]:
            response=getattr(self.client,method)('/api/v1/'+path,headers=self.headers)
            self.assertEqual(response.status_code,409,response.text[:200])
            self.assertEqual(response.json()['error']['code'],'saved_design_changed')
        self.assertEqual(self.restore(original_id).status_code,200)
        self.assertEqual(self.client.get('/api/v1/download',headers=self.headers).status_code,200)


if __name__=='__main__':
    unittest.main()
