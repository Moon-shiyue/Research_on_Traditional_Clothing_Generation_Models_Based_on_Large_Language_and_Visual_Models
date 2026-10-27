"""A shorter complete-outfit canvas must retain every unscaled cutting path."""
import hashlib
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
from .body_layout import tag
from .outfits import combine_nets
from .design_integrity import verify_design


class PreviewPackingTests(unittest.TestCase):
    def test_complete_nets_are_compact_unscaled_non_overlapping_and_exported_with_the_same_size(self):
        for text in ['交领上衣，衣长55cm，宽袖，袖口条宽4cm；襦裙，裙长95cm',
                     '直幅系带抹胸；直领对襟上衣；马面裙；双层云肩；披帛，披帛长320cm']:
            with self.subTest(text=text),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);headers={'X-Session-Id':str(uuid.uuid4())};app=create_app(PaperEngine(object()),root)
                with TestClient(app) as c:
                    request=c.post('/api/v1/parse',headers=headers,json={'text':text})
                    task=c.get('/api/v1/tasks/'+request.json()['task_id'],headers=headers).json()
                    self.assertEqual(task['status'],'done',task)
                    result=task['result'];self.assertEqual(result['status'],'generated',result)
                    folder=app.state.sessions[headers['X-Session-Id']]['folder']
                    plan=json.loads((folder/'preview-layout.json').read_text(encoding='utf-8'))
                    self.assertEqual(plan['shared_scale'],1.);self.assertEqual(plan['rotation_degrees'],0)
                    plain=ET.parse(folder/'preview.svg').getroot()
                    dimensions=ET.parse(folder/'preview-dimensions.svg').getroot()
                    self.assertEqual(plain.attrib['viewBox'],dimensions.attrib['viewBox'])
                    seen=[]
                    for block in plan['members']:
                        frames=list(block['placements'].values())
                        for i,a in enumerate(frames):
                            self.assertGreaterEqual(a['x'],0.);self.assertGreaterEqual(a['y'],0.)
                            self.assertLessEqual(a['x']+a['width'],plan['width']+1e-6)
                            for b in frames[i+1:]:
                                overlap=(min(a['x']+a['width'],b['x']+b['width'])-max(a['x'],b['x'])>1e-6
                                    and min(a['y']+a['height'],b['y']+b['height'])-max(a['y'],b['y'])>1e-6)
                                self.assertFalse(overlap)
                        for source in ['preview.svg','preview-dimensions.svg']:
                            output=ET.parse(folder/source).getroot()
                            group=output.find(tag('g')+'[@data-garment="'+block['id']+'"]')
                            original=ET.parse(folder/block['id']/source).getroot()
                            self.assertEqual([p.attrib['d'] for p in group.iter(tag('path'))],
                                             [p.attrib['d'] for p in original.iter(tag('path'))])
                            self.assertFalse(any('scale' in node.attrib.get('transform','') or 'rotate' in node.attrib.get('transform','') for node in group.iter()))
                        seen += [block['id']+'__'+item['panel'] for item in block['items']]
                    geometry=json.loads((folder/'pattern.json').read_text(encoding='utf-8'))
                    self.assertEqual(sorted(seen),sorted(geometry['panels']))
                    self.assertEqual(len(seen),result['pattern']['panel_count'])
                    if text.startswith('交领'):
                        old=combine_nets(folder,app.state.sessions[headers['X-Session-Id']]['outfit'],'preview.svg','comparison-old-preview.svg')
                        old_height=float(old.attrib['viewBox'].split()[3])
                        self.assertLess(plan['height'],old_height*.8)
                    archive=c.get('/api/v1/download',headers=headers)
                    self.assertEqual(archive.status_code,200)
                    with ZipFile(io.BytesIO(archive.content)) as z:
                        self.assertIsNone(z.testzip());self.assertIn('preview-layout.json',z.namelist())
                        manifest=json.loads(z.read('export-manifest.json'))
                        self.assertEqual(hashlib.sha256(z.read('preview-layout.json')).hexdigest(),manifest['files']['preview-layout.json']['sha256'])
                    print_plan=c.get('/api/v1/print/plan',headers=headers)
                    self.assertEqual(print_plan.status_code,200,print_plan.text)
                    self.assertEqual(print_plan.json()['fabric_panel_count'],len(seen))
                    verify_design(folder,result['pattern']['integrity_version'])
                    (folder/'preview-layout.json').write_text('{}',encoding='utf-8')
                    self.assertEqual(c.get('/api/v1/download',headers=headers).status_code,409)


if __name__=='__main__':unittest.main()
