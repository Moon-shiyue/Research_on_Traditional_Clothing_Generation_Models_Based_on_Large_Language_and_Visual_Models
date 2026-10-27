"""Print scale, page coverage, duplicate cut counts and session export isolation."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
import threading
import numpy as np
from svgpathtools.parser import parse_transform
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from xml.etree import ElementTree as ET

from fastapi.testclient import TestClient
from pypdf import PdfReader
from pypdf.generic import ContentStream

from .app import create_app
from .body_layout import tag
from .engine import PaperEngine
from .patterns import generate_pattern
from .printing import (CM, PLOT_CM, OVERLAP_CM, _templates, _panel_svg,
                       build_print_pdf, export_print_pdf, print_plan)


class PrintTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.engine=PaperEngine(model=object())

    def generate(self,component):
        folder=self.root/component
        meta=generate_pattern(self.engine.defaults(component),self.engine.template,{},folder)
        (folder/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False),encoding='utf-8')
        return folder

    def test_all_components_covered_once_and_sheet_windows_cover_full_net(self):
        for component in self.engine.names:
            with self.subTest(component=component):
                folder=self.generate(component)
                plan=print_plan(folder)
                geometry=json.loads((folder/'pattern.json').read_text(encoding='utf-8'))
                ids=[i for p in plan['panels'] for i in p['panel_ids']]
                self.assertEqual(sorted(ids),sorted(geometry['panels']))
                self.assertEqual(len(ids),len(set(ids)))
                self.assertEqual(sum(p['cut_count'] for p in plan['panels']),len(ids))
                self.assertEqual(plan['page_count'],1+sum(p['pages'] for p in plan['panels']))
                for p in plan['panels']:
                    self.assertGreaterEqual(PLOT_CM[2]+(p['columns']-1)*(PLOT_CM[2]-OVERLAP_CM)+1e-8,p['paper_width_cm'])
                    self.assertGreaterEqual(PLOT_CM[3]+(p['rows']-1)*(PLOT_CM[3]-OVERLAP_CM)+1e-8,p['paper_height_cm'])

    def test_only_identical_ruqun_gores_share_template(self):
        plan=print_plan(self.generate('ruqun-skirt'))
        self.assertEqual(plan['fabric_panel_count'],9)
        self.assertEqual(plan['paper_template_count'],4)
        self.assertEqual([p['cut_count'] for p in plan['panels']],[6,1,1,1])
        plan=print_plan(self.generate('mamian-skirt'))
        self.assertEqual(plan['paper_template_count'],3)
        self.assertEqual([p['cut_count'] for p in plan['panels']],[1,1,1])

    def test_outer_canvas_keeps_full_dimension_labels_after_rotation(self):
        # A real downloaded rotated waistband lost the first digit of "10.0":
        # the label extended beyond the SVG canvas before A4 tile splitting.
        # Use conservative glyph envelopes; 0.65 em covers numeric widths.
        for component in ['ruqun-skirt', 'pipa-sleeve', 'stand-collar']:
            folder=self.generate(component)
            plan=print_plan(folder)
            for item,public in zip(_templates(folder),plan['panels']):
                item.update(public)
                svg=ET.fromstring(_panel_svg(item))
                group=svg.find(tag('g'))
                matrix=parse_transform(group.attrib['transform'])
                for label in group.findall(tag('text')):
                    if label.attrib.get('class')!='edge-dimension':continue
                    x=float(label.attrib['x']);y=float(label.attrib['y'])
                    size=float(label.attrib['font-size'])
                    half_width=len(label.text)*size*.65/2
                    half_height=size*.65
                    for dx,dy in [(-half_width,-half_height),(-half_width,half_height),
                                  (half_width,-half_height),(half_width,half_height)]:
                        px,py,_=matrix @ np.array([x+dx,y+dy,1])
                        with self.subTest(component=component,panel=item['panel_id'],label=label.text):
                            self.assertGreaterEqual(px,-1e-6)
                            self.assertGreaterEqual(py,-1e-6)
                            self.assertLessEqual(px,item['paper_width_cm']+1e-6)
                            self.assertLessEqual(py,item['paper_height_cm']+1e-6)

    def test_panel_curve_and_fold_marks_are_not_reconstructed_or_scaled(self):
        folder=self.generate('mamian-skirt')
        plan=print_plan(folder)
        items=_templates(folder)
        for item,public in zip(items,plan['panels']):
            item.update(public)
            before=item['_group']
            after=ET.fromstring(_panel_svg(item)).find(tag('g'))
            self.assertEqual([p.attrib['d'] for p in before.iter(tag('path'))],
                             [p.attrib['d'] for p in after.iter(tag('path'))])
            self.assertEqual([p.attrib for p in before.iter(tag('line'))],
                             [p.attrib for p in after.iter(tag('line'))])
            self.assertTrue(after.attrib['transform'].startswith('matrix(0 1 -1 0 ') if item['rotation_degrees'] else after.attrib['transform'].startswith('translate('))
            self.assertNotIn('scale',after.attrib['transform'])

    def test_pdf_a4_calibration_and_translation_only_merge(self):
        output,plan=build_print_pdf(self.generate('stand-collar'))
        reader=PdfReader(output)
        self.assertEqual(len(reader.pages),plan['page_count'])
        for page in reader.pages:
            self.assertAlmostEqual(float(page.mediabox.width),21*CM,places=3)
            self.assertAlmostEqual(float(page.mediabox.height),29.7*CM,places=3)
        content=ContentStream(reader.pages[0].get_contents(),reader)
        squares=[args for args,op in content.operations if op==b're' and abs(float(args[2])-10*CM)<.001 and abs(float(args[3])-10*CM)<.001]
        self.assertEqual(len(squares),1)
        expected=[]
        for item in plan['panels']:
            for row in range(item['rows']):
                for column in range(item['columns']):
                    left=column*(PLOT_CM[2]-OVERLAP_CM)
                    bottom=item['paper_height_cm']-row*(PLOT_CM[3]-OVERLAP_CM)-PLOT_CM[3]
                    expected.append([1.,0.,0.,1.,(PLOT_CM[0]-left)*CM,(PLOT_CM[1]-bottom)*CM])
        for page,wanted in zip(reader.pages[1:],expected):
            ops=ContentStream(page.get_contents(),reader).operations
            # pypdf's outer placement applies only translation, at the physical point scale.
            transforms=[args for args,op in ops if op==b'cm']
            for actual,value in zip(transforms[0],wanted):self.assertAlmostEqual(float(actual),value,places=5)
        self.assertFalse(plan['seam_allowance_included'])

    def test_corrupt_cache_is_regenerated_and_valid_cache_is_reused(self):
        folder=self.generate('round-collar')
        output,plan=export_print_pdf(folder)
        digest=hashlib.sha256(output.read_bytes()).hexdigest()
        with patch('backend.printing.build_print_pdf',side_effect=AssertionError('Cache should be reused')):
            again,repeat=export_print_pdf(folder)
        self.assertEqual(repeat,plan)
        self.assertEqual(hashlib.sha256(again.read_bytes()).hexdigest(),digest)
        output.write_bytes(b'broken')
        again,repeat=export_print_pdf(folder)
        self.assertEqual(len(PdfReader(again).pages),plan['page_count'])
        (folder/'print-a4.json').write_text('{truncated',encoding='utf-8')
        again,repeat=export_print_pdf(folder)
        self.assertEqual(len(PdfReader(again).pages),plan['page_count'])

    def test_gore_with_distinct_mark_is_not_deduplicated(self):
        folder=self.generate('ruqun-skirt')
        svg=folder/'pattern-dimensions.svg'
        root=ET.parse(svg).getroot()
        ET.SubElement(root.findall(tag('g'))[1],tag('line'),{'x1':'0','y1':'0','x2':'1','y2':'1'})
        ET.ElementTree(root).write(svg,encoding='utf-8')
        plan=print_plan(folder)
        self.assertEqual(plan['paper_template_count'],5)
        self.assertEqual(sum(p['cut_count'] for p in plan['panels']),9)

    def test_missing_dimensions_and_mismatched_svg_are_rejected(self):
        folder=self.generate('stand-collar')
        file=folder/'metadata.json'
        meta=json.loads(file.read_text(encoding='utf-8'))
        original=json.loads(json.dumps(meta))
        del meta['panel_measurements']
        file.write_text(json.dumps(meta),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'旧纸样'):
            print_plan(folder)
        original['panel_measurements'][0]['width_cm']+=1
        file.write_text(json.dumps(original),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'尺寸不一致'):
            print_plan(folder)


class PrintApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app=create_app(PaperEngine(model=object()),Path(self.temp.name))
        self.client=TestClient(self.app)
        self.addCleanup(self.client.close)
        self.headers={'X-Session-Id':str(uuid.uuid4())}

    def generate(self,text):
        response=self.client.post('/api/v1/parse',headers=self.headers,json={'text':text})
        self.assertEqual(response.status_code,202,response.text)
        task=self.client.get('/api/v1/tasks/'+response.json()['task_id'],headers=self.headers).json()
        self.assertEqual(task['status'],'done',task)
        self.assertEqual(task['result']['status'],'generated',task)
        return task['result']

    def test_session_isolation_download_and_changed_body_gets_new_print(self):
        self.assertEqual(self.client.get('/api/v1/print/plan',headers=self.headers).status_code,400)
        self.generate('明代圆领，常服')
        plan=self.client.get('/api/v1/print/plan',headers=self.headers).json()
        other={'X-Session-Id':str(uuid.uuid4())}
        self.assertEqual(self.client.post('/api/v1/print/link',headers=other).status_code,400)
        response=self.client.post('/api/v1/print/link',headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        first=response.json()
        download=self.client.get(first['url'])
        self.assertEqual(download.status_code,200)
        self.assertEqual(len(PdfReader(io.BytesIO(download.content)).pages),plan['page_count'])
        body=self.client.put('/api/v1/body/params',headers=self.headers,json={'path':['height'],'value':175})
        self.assertEqual(body.status_code,200,body.text)
        second=self.client.post('/api/v1/print/link',headers=self.headers).json()
        self.assertNotEqual(first['url'],second['url'])
        self.assertEqual(self.client.get(first['url']).content,download.content)
        with patch('backend.app.export_print_pdf',side_effect=AssertionError('Stale preview must not build PDF')):
            stale=self.client.post('/api/v1/print/link',headers=self.headers,json={'pattern_url':first['pattern_url']})
        self.assertEqual(stale.status_code,409)
        self.assertEqual(stale.json()['error']['code'],'print_changed')

    def test_outfit_plan_counts_every_member_and_busy_state_is_released_on_failure(self):
        result=self.generate('唐代半臂，衣长50cm；襦裙，裙长95cm，常服')
        plan=self.client.get('/api/v1/print/plan',headers=self.headers).json()
        self.assertEqual(plan['fabric_panel_count'],17)
        self.assertEqual(plan['paper_template_count'],12)
        ids=[p['panel_id'] for p in plan['panels']]
        self.assertTrue(any(p.startswith('upper__') for p in ids))
        self.assertTrue(any(p.startswith('lower__') for p in ids))
        with patch('backend.app.export_print_pdf',side_effect=ValueError('test export rejection')):
            response=self.client.post('/api/v1/print/link',headers=self.headers)
        self.assertEqual(response.status_code,422)
        state=self.app.state.sessions[self.headers['X-Session-Id']]
        self.assertFalse(state['busy'])
        state['busy']=True
        self.assertEqual(self.client.get('/api/v1/print/plan',headers=self.headers).status_code,409)
        self.assertEqual(self.client.post('/api/v1/print/link',headers=self.headers).status_code,409)
        self.assertEqual(state['pattern']['svg_url'],result['pattern']['svg_url'])

    def test_pdf_build_does_not_hold_global_lock_or_allow_same_session_mutation(self):
        self.generate('明代圆领，常服')
        started=threading.Event();release=threading.Event()
        def slow_export(folder):
            started.set()
            if not release.wait(5):raise AssertionError('Test export release timed out')
            file=folder/'test-only.pdf';file.write_bytes(b'test-only mock export')
            return file,{}
        with patch('backend.app.export_print_pdf',side_effect=slow_export),ThreadPoolExecutor(max_workers=2) as pool:
            pending=pool.submit(self.client.post,'/api/v1/print/link',headers=self.headers)
            try:
                self.assertTrue(started.wait(2))
                other={'X-Session-Id':str(uuid.uuid4())}
                independent=pool.submit(self.client.get,'/api/v1/design/params',headers=other)
                self.assertEqual(independent.result(timeout=2).status_code,200)
                edit=pool.submit(self.client.put,'/api/v1/body/params',headers=self.headers,
                                 json={'path':['height'],'value':180})
                self.assertEqual(edit.result(timeout=2).status_code,409)
            finally:
                release.set()
            self.assertEqual(pending.result(timeout=2).status_code,200)
        self.assertFalse(self.app.state.sessions[self.headers['X-Session-Id']]['busy'])


if __name__=='__main__':
    unittest.main()
