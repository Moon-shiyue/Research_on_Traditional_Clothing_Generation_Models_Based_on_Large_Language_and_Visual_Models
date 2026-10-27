"""Cloud coverage defaults, actual centimetres and old-outline compatibility."""
import copy
import hashlib
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
from .patterns import build_geometry,body_from
from .style_features import visual_parameters
from .design_integrity import seal_design


class CloudSizingTests(unittest.TestCase):
    def test_centimetres_change_real_outline_but_not_the_shared_neckline(self):
        e=PaperEngine(object());variants=[]
        for extension in [0.,10.,20.]:
            r=e.interpret('云肩，云头外伸长14cm，前摆加长'+str(extension)+'cm，层数2',None,{'shoulder_w':35.})
            self.assertEqual(r['status'],'ready',r)
            self.assertEqual(r['absolute_lengths_cm']['cloud-shoulder.petal_length'],14.)
            p,_,_,a,_,v=build_geometry(r['patch'],e.template,{'shoulder_w':35.})
            self.assertAlmostEqual(a['petal_length_cm'],14.,places=6)
            self.assertEqual(a['front_extension_cm'],extension)
            self.assertTrue(v['sampled_outline_valid'])
            variants.append((p,a))
        original=variants[0][0].pattern['panels']['cloud_layer_01']
        inner_start=4*12+1
        for p,a in variants[1:]:
            self.assertEqual(p.pattern['panels']['cloud_layer_01']['vertices'][inner_start:],original['vertices'][inner_start:])
            self.assertEqual(a['neck_binding_length'],variants[0][1]['neck_binding_length'])
            self.assertLess(min(v[1] for v in p.pattern['panels']['cloud_layer_01']['vertices']),min(v[1] for v in original['vertices'])-7.)
        self.assertEqual(set(e.model_schema['components']['cloud-shoulder']['fields']),{'layers','petal_count','tassel_length'})
        self.assertEqual(e.interpret('云肩，直径60cm',None,{})['status'],'needs_input')

    def test_visible_coverage_uses_disclosed_defaults_and_explicit_dimensions_take_priority(self):
        e=PaperEngine(object())
        for coverage,expected in [('neck',(.22,0.)),('shoulders',(.38,0.)),('chest',(.38,10.))]:
            f={'neckwear_shape':'cloud-lobes','cloud_coverage':coverage,'cloud_layers':1}
            values=visual_parameters('cloud-shoulder',f)
            self.assertEqual((values['petal_length']['value'],values['front_extension']['value']),expected)
            r=e.interpret('云肩，云头外伸长12cm，前摆加长6cm',None,{},
                {'component':'cloud-shoulder','features':f})
            self.assertEqual(r['status'],'ready',r)
            self.assertAlmostEqual(r['patch']['cloud-shoulder']['petal_length']['v']*body_from()['shoulder_w'],12.,places=6)
            self.assertEqual(r['patch']['cloud-shoulder']['front_extension']['v'],6.)
            self.assertEqual(r['sources']['cloud-shoulder.front_extension'],'text')
        self.assertNotIn('petal_length',visual_parameters('cloud-shoulder',{}))

    def test_legacy_outline_is_inferred_without_rewriting_and_fixed_cm_survive_body_export_restart(self):
        e=PaperEngine(object())
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);h={'X-Session-Id':str(uuid.uuid4())};app=create_app(e,root)
            with TestClient(app) as c:
                request=c.post('/api/v1/parse',headers=h,json={'text':'云肩，层数3，云头数6，petal_length:0.38'})
                result=c.get('/api/v1/tasks/'+request.json()['task_id'],headers=h).json()['result']
                self.assertEqual(result['status'],'generated',result)
                folder=app.state.sessions[h['X-Session-Id']]['folder']
                # The old equation is identical when extension=0. Construct a
                # sealed old-schema fixture with a non-default inferred size.
                design=json.loads((folder/'design.json').read_text(encoding='utf-8'))
                for key in ['petal_length','front_extension']:design['cloud-shoulder'].pop(key)
                (folder/'design.json').write_text(json.dumps(design),encoding='utf-8')
                for name in ['assembly.json','metadata.json']:
                    value=json.loads((folder/name).read_text(encoding='utf-8'))
                    a=value if name=='assembly.json' else value['assembly'];a['version']='traditional-basics-2026-10-18'
                    for key in ['petal_length_cm','petal_length_ratio','front_extension_cm']:a.pop(key,None)
                    if name=='metadata.json':
                        for key in ['petal_length','front_extension']:
                            value['parameter_sources'].pop('cloud-shoulder.'+key,None)
                            value['default_fields']=[p for p in value['default_fields'] if p!='cloud-shoulder.'+key]
                    (folder/name).write_text(json.dumps(value),encoding='utf-8')
                geometry=json.loads((folder/'pattern.json').read_text(encoding='utf-8'));geometry['template_version']='traditional-basics-2026-10-18'
                (folder/'pattern.json').write_text(json.dumps(geometry),encoding='utf-8');seal_design(folder)
                originals={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}
            with TestClient(create_app(PaperEngine(object()),root)) as c:
                old=c.get('/api/v1/pattern',headers=h);self.assertEqual(old.status_code,200,old.text)
                controls=c.get('/api/v1/design/params',headers=h).json()['params']['cloud-shoulder']
                self.assertEqual(controls['petal_length']['v'],.38)
                self.assertEqual(old.json()['parameter_sources']['cloud-shoulder.petal_length'],'restored_geometry')
                self.assertEqual({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()},originals)
                r=c.put('/api/v1/design/params',headers=h,json={'path':['cloud-shoulder','petal_length'],'value':14.,'unit':'cm'})
                self.assertEqual(r.status_code,200,r.text)
                r=c.put('/api/v1/design/params',headers=h,json={'path':['cloud-shoulder','front_extension'],'value':10.})
                self.assertEqual(r.status_code,200,r.text)
                for shoulder in [28.,42.]:
                    r=c.put('/api/v1/body/params',headers=h,json={'path':['shoulder_w'],'value':shoulder})
                    self.assertEqual(r.status_code,200,r.text)
                    self.assertAlmostEqual(r.json()['assembly']['petal_length_cm'],14.,places=6)
                with ZipFile(io.BytesIO(c.get('/api/v1/download',headers=h).content)) as z:
                    a=json.loads(z.read('assembly.json'));self.assertAlmostEqual(a['petal_length_cm'],14.,places=6)
                    self.assertEqual(a['front_extension_cm'],10.)
                current=c.get('/api/v1/pattern',headers=h).json()
            with TestClient(create_app(PaperEngine(object()),root)) as c:
                self.assertEqual(c.get('/api/v1/pattern',headers=h).json(),current)


if __name__=='__main__':unittest.main()
