"""Every layer survives edits, reopening, print planning and archive export."""
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
from .design_integrity import verify_design
from .outfits import interpret_outfit,interpret_outfit_image


class LayeredOutfitTests(unittest.TestCase):
    def test_two_upper_lengths_are_scoped_and_not_copied_to_the_other_layer(self):
        engine=PaperEngine(model=object())
        text='交领上衣，衣长55cm，袖长45cm，窄袖；褙子，衣长110cm，袖长50cm，宽袖；马面裙，裙长95cm；双层云肩'
        r=interpret_outfit(engine,text,{})
        self.assertEqual(r['status'],'ready',r)
        self.assertEqual([g['id'] for g in r['garments']],['upper','outer','lower','accessory'])
        upper,outer=r['garments'][:2]
        self.assertEqual(upper['absolute_lengths_cm'],{'cross-upper.length':55.,'cross-upper.sleeve_length':45.})
        self.assertEqual(outer['absolute_lengths_cm'],{'beizi.length':110.,'beizi.sleeve_length':50.})
        self.assertEqual(upper['patch']['cross-upper']['sleeve_cuff_width']['v'],26.)
        self.assertEqual(outer['patch']['beizi']['sleeve_cuff_width']['v'],60.)

    def test_four_items_remain_separate_in_nets_receipt_restore_zip_and_print_plan(self):
        engine=PaperEngine(model=object())
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);headers={'X-Session-Id':str(uuid.uuid4())}
            app=create_app(engine,root)
            with TestClient(app) as client:
                response=client.post('/api/v1/parse',headers=headers,json={'text':
                    '交领上衣，衣长55cm，袖长45cm；褙子，衣长110cm，袖长50cm；马面裙，裙长95cm；双层云肩'})
                task=client.get('/api/v1/tasks/'+response.json()['task_id'],headers=headers).json()
                self.assertEqual(task['status'],'done',task)
                result=task['result'];self.assertEqual(result['status'],'generated',result)
                folder=app.state.sessions[headers['X-Session-Id']]['folder']
                receipt=json.loads((folder/'design-receipt.json').read_text(encoding='utf-8'))
                self.assertIn('outer/pattern.json',receipt['files'])
                svg=ET.parse(folder/'body-layout.svg').getroot()
                left=svg.find(tag('g')+'[@id="body-placement"]')
                self.assertEqual([n.attrib['data-garment'] for n in left if 'data-garment' in n.attrib],['lower','upper','outer','accessory'])
                self.assertEqual(len(svg.findall('.//'+tag('g')+'[@class="body-outline"]')),1)
                edited=client.put('/api/v1/body/params',headers=headers,json={'path':['height'],'value':182})
                self.assertEqual(edited.status_code,200,edited.text)
                self.assertEqual(len(edited.json()['garments']),4)
                self.assertEqual(edited.json()['absolute_lengths_cm']['beizi.length'],110.)
                exported=client.get('/api/v1/download',headers=headers)
                with ZipFile(io.BytesIO(exported.content)) as z:
                    self.assertIsNone(z.testzip())
                    for role in ['upper','outer','lower','accessory']:self.assertIn(role+'/pattern.json',z.namelist())
                    geometry=json.loads(z.read('pattern.json'))
                    for stitch in geometry['stitches']:
                        self.assertEqual(stitch[0]['panel'].split('__')[0],stitch[1]['panel'].split('__')[0])
                plan=client.get('/api/v1/print/plan',headers=headers)
                self.assertEqual(plan.status_code,200,plan.text)
                self.assertTrue(any(p['panel_id'].startswith('outer__') for p in plan.json()['panels']))
            with TestClient(create_app(PaperEngine(model=object()),root)) as fresh:
                restored=fresh.get('/api/v1/pattern',headers=headers)
                self.assertEqual(restored.status_code,200,restored.text)
                self.assertEqual(len(restored.json()['garments']),4)
                # Verify the actual committed folder rather than trusting a
                # successful API response after an outer-file alteration.
                folder=fresh.app.state.sessions[headers['X-Session-Id']]['folder']
                meta=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
                verify_design(folder,meta['integrity_version'])
                (folder/'outer/design.json').write_text('{}',encoding='utf-8')
                with self.assertRaises(ValueError):verify_design(folder,meta['integrity_version'])


if __name__=='__main__':unittest.main()
