import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from fastapi.testclient import TestClient

from .app import create_app
from .body_layout import tag
from .engine import PaperEngine
from .outfits import interpret_outfit
from PIL import Image


class NoModel:
    def text(self, *args):
        raise AssertionError('Explicit outfit parameters must not load a model')


class OutfitTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine=PaperEngine(model=NoModel())
        self.app=create_app(self.engine,Path(self.temp.name))
        self.client=TestClient(self.app)
        self.addCleanup(self.client.close)
        self.headers={'X-Session-Id':str(uuid.uuid4())}

    def generate(self,text='明代褙子，衣长110cm，袖长48cm；马面裙，裙长95cm，褶量比2.4，常服'):
        response=self.client.post('/api/v1/parse',headers=self.headers,json={'text':text})
        self.assertEqual(response.status_code,202,response.text)
        task=self.client.get('/api/v1/tasks/'+response.json()['task_id'],headers=self.headers).json()
        self.assertEqual(task['status'],'done',task)
        return task['result']

    def archive(self):
        response=self.client.get('/api/v1/download',headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        return ZipFile(io.BytesIO(response.content))

    def test_two_supported_outfits_have_all_panels_and_scoped_lengths(self):
        for text,components,count in [
                ('明代褙子，衣长110cm；马面裙，裙长95cm，常服',['beizi','mamian-skirt'],11),
                ('唐代半臂，衣长50cm；襦裙，裙长95cm，常服',['banbi','ruqun-skirt'],17),
                ('马面裙，裙长95cm；褙子，衣长110cm，明代常服',['beizi','mamian-skirt'],11)]:
            with self.subTest(text=text):
                result=self.generate(text)
                self.assertEqual(result['status'],'generated',result)
                meta=result['pattern']
                self.assertEqual([g['component'] for g in meta['garments']],components)
                self.assertEqual(meta['panel_count'],count)
                self.assertEqual(len(meta['panel_measurements']),count)
                self.assertAlmostEqual(meta['absolute_lengths_cm'][components[1]+'.length'],95)
                self.assertEqual(set(result['design_params']),set(components+['traditional']))

    def test_single_body_unscaled_nets_unique_clip_ids_and_no_cross_garment_seams(self):
        self.generate()
        with self.archive() as z:
            svg=ET.fromstring(z.read('body-layout-dimensions.svg'))
            self.assertEqual(len(svg.findall('.//'+tag('g')+'[@class="body-outline"]')),1)
            right=svg.find(tag('g')+'[@id="net-layout"]')
            self.assertIsNone(right.find('.//'+tag('g')+'[@class="body-outline"]'))
            ids=[n.attrib['id'] for n in svg.iter() if 'id' in n.attrib]
            self.assertEqual(len(ids),len(set(ids)))
            root_metadata=json.loads(z.read('metadata.json'))
            table={row['panel_id']:row for row in root_metadata['panel_measurements']}
            nets=[node for node in right.iter(tag('g')) if 'data-panel' in node.attrib]
            self.assertEqual(len(nets),len(table))
            for node in nets:
                row=table[node.attrib['data-panel']]
                label=node.find(tag('text')+'[@class="panel-size-label"]')
                self.assertAlmostEqual(row['width_cm'],float(label.attrib['data-width-cm']))
                self.assertAlmostEqual(row['height_cm'],float(label.attrib['data-height-cm']))
            for member in ['upper','lower']:
                group=right.find(tag('g')+'[@data-garment="'+member+'"]')
                original=ET.fromstring(z.read(member+'/body-layout-dimensions.svg'))
                original_net=original.find(tag('g')+'[@id="net-layout"]')
                self.assertEqual([n.attrib['d'] for n in group.iter(tag('path'))],
                    [n.attrib['d'] for n in original_net.iter(tag('path'))])
                self.assertNotIn('scale',group.attrib.get('transform',''))
            geometry=json.loads(z.read('pattern.json'))
            self.assertEqual(len(geometry['panels']),11)
            for seam in geometry['stitches']:
                refs=[v['panel'] for v in seam if isinstance(v,dict) and 'panel' in v]
                self.assertEqual(len({p.split('__')[0] for p in refs}),1)
                self.assertTrue(all(p in geometry['panels'] for p in refs))

    def test_body_changes_regenerate_both_and_preserve_all_fixed_lengths(self):
        self.generate()
        with self.archive() as z:
            old_upper=z.read('upper/pattern.json'); old_lower=z.read('lower/pattern.json')
        for key,value in [('height',180),('waist',88)]:
            response=self.client.put('/api/v1/body/params',headers=self.headers,json={'path':[key],'value':value})
            self.assertEqual(response.status_code,200,response.text)
        with self.archive() as z:
            self.assertNotEqual(old_upper,z.read('upper/pattern.json'))
            self.assertNotEqual(old_lower,z.read('lower/pattern.json'))
            self.assertEqual(z.read('body.json'),z.read('upper/body.json'))
            self.assertEqual(z.read('body.json'),z.read('lower/body.json'))
            upper=json.loads(z.read('upper/metadata.json'))
            lower=json.loads(z.read('lower/metadata.json'))
            self.assertEqual(upper['absolute_lengths_cm'],{'beizi.length':110,'beizi.sleeve_length':48})
            self.assertEqual(lower['absolute_lengths_cm'],{'mamian-skirt.length':95})
            self.assertAlmostEqual(lower['construction']['skirt_length'],95,places=5)

    def test_one_garment_edit_keeps_other_geometry_and_invalid_edits_are_atomic(self):
        self.generate()
        with self.archive() as z:
            before_upper=z.read('upper/pattern.json')
        response=self.client.put('/api/v1/design/params',headers=self.headers,
            json={'path':['mamian-skirt','length'],'value':100,'unit':'cm'})
        self.assertEqual(response.status_code,200,response.text)
        with self.archive() as z:
            self.assertEqual(before_upper,z.read('upper/pattern.json'))
            self.assertAlmostEqual(json.loads(z.read('lower/metadata.json'))['construction']['skirt_length'],100,places=5)
        before=self.client.get('/api/v1/pattern',headers=self.headers).json()
        bad=self.client.put('/api/v1/design/params',headers=self.headers,
            json={'path':['beizi','length'],'value':-1})
        self.assertEqual(bad.status_code,422)
        self.assertEqual(before,self.client.get('/api/v1/pattern',headers=self.headers).json())
        # Failure in the second generator cannot commit the first one's update.
        from .outfits import generate_pattern
        def fail_lower(patch,*args,**kwargs):
            if 'mamian-skirt' in patch:
                raise ValueError('Test second garment geometry failure')
            return generate_pattern(patch,*args,**kwargs)
        with patch('backend.outfits.generate_pattern',side_effect=fail_lower):
            response=self.client.put('/api/v1/body/params',headers=self.headers,json={'path':['waist'],'value':90})
        self.assertEqual(response.status_code,422)
        self.assertEqual(before,self.client.get('/api/v1/pattern',headers=self.headers).json())

    def test_context_defaults_random_and_single_item_transition(self):
        self.generate()
        params=self.client.get('/api/v1/design/params',headers=self.headers).json()['params']
        self.assertEqual(params['traditional']['dynasty']['range'],['Ming'])
        bad=self.client.put('/api/v1/design/params',headers=self.headers,
            json={'path':['traditional','dynasty'],'value':'Qing'})
        self.assertEqual(bad.status_code,422)
        randomized=self.client.post('/api/v1/design/random',headers=self.headers)
        self.assertEqual(randomized.status_code,200,randomized.text)
        current=self.client.get('/api/v1/pattern',headers=self.headers).json()
        self.assertEqual(current['parameter_sources']['traditional.dynasty'],'text')
        for route in ['default','random']:
            response=self.client.post('/api/v1/design/'+route,headers=self.headers)
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(set(response.json()['params']),{'beizi','mamian-skirt','traditional'})
            self.assertEqual(self.client.get('/api/v1/pattern',headers=self.headers).json()['component'],'outfit')
        result=self.generate('马面裙，裙长95cm')
        self.assertEqual(result['pattern']['component'],'mamian-skirt')
        self.assertNotIn('garments',result['pattern'])

    def test_whole_export_integrity_and_child_guidance(self):
        self.generate()
        link=self.client.post('/api/v1/download/link',headers=self.headers).json()
        with ZipFile(io.BytesIO(self.client.get(link['url']).content)) as z:
            self.assertIsNone(z.testzip())
            manifest=json.loads(z.read('export-manifest.json'))
            self.assertEqual(set(manifest['files']),set(z.namelist())-{'export-manifest.json'})
            for name,record in manifest['files'].items():
                self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(),record['sha256'],name)
            self.assertIn('lower/cutting-a.svg',z.namelist())
            self.assertIn('upper/assembly.json',z.namelist())
            self.assertIn('分别缝制',z.read('README.txt').decode('utf-8'))

    def test_outfit_scope_never_invents_extra_garments_or_connects_separates(self):
        for text in ['褙子＋马面裙，连体结构',
                     '宋代褙子＋明代马面裙','褙子＋马面裙＋云肩＋半臂','旗袍、褙子、马面裙']:
            with self.subTest(text=text):
                result=interpret_outfit(self.engine,text,{})
                self.assertEqual(result['status'],'needs_input',result)
        self.assertIsNone(interpret_outfit(self.engine,'不要褙子，只做马面裙',{}))

    def test_shared_closing_measurements_and_outfit_wording_keep_role_ownership(self):
        result=self.generate('整套汉服，褙子＋马面裙，衣长110cm，袖长48cm，裙长90cm，广袖，开衩比例0.6，明代常服')
        self.assertEqual(result['status'],'generated',result)
        self.assertEqual(result['pattern']['absolute_lengths_cm'],
            {'beizi.length':110,'beizi.sleeve_length':48,'mamian-skirt.length':90})
        self.assertEqual(result['design_params']['beizi']['sleeve_cuff_width']['v'],60)
        self.assertEqual(result['design_params']['beizi']['slit_height']['v'],.6)

    def test_excluded_robe_and_non_connected_wording_do_not_block_supported_pair(self):
        result=self.generate('不要圆领袍，不要连体，明代褙子，衣长110cm；马面裙，裙长95cm，常服')
        self.assertEqual(result['status'],'generated',result)
        self.assertEqual(result['pattern']['panel_count'],11)

    def test_explicit_extra_sleeve_or_collar_is_never_silently_ignored(self):
        for text in ['褙子＋马面裙，另做广袖', '褙子＋马面裙，单独制作对襟领',
                     '半臂＋襦裙，另外做窄袖']:
            with self.subTest(text=text):
                result=self.generate(text)
                self.assertEqual(result['status'],'needs_input',result)
                self.assertIn('另做的领片或袖片',result['reply'])

    def test_banbi_explicit_half_cuff_width_survives_outfit_scoping(self):
        result=self.generate('唐代半臂，衣长50cm，袖长23cm，袖口平铺半围24cm；襦裙，裙长95cm，常服')
        self.assertEqual(result['status'],'generated',result)
        self.assertEqual(result['design_params']['banbi']['sleeve_width']['v'],24)
        self.assertEqual(result['pattern']['parameter_sources']['banbi.sleeve_width'],'text')

    def test_excluded_sleeves_and_contexts_do_not_reappear_during_scoping(self):
        for text,component,width in [
                ('褙子＋马面裙，不要窄袖，采用广袖，不要宋代，明代常服','beizi',60),
                ('半臂＋襦裙，不要宽袖，用窄袖，不要宋代，唐代常服','banbi',14)]:
            with self.subTest(text=text):
                result=self.generate(text)
                self.assertEqual(result['status'],'generated',result)
                field='sleeve_cuff_width' if component=='beizi' else 'sleeve_width'
                self.assertEqual(result['design_params'][component][field]['v'],width)
                self.assertEqual(result['design_params']['traditional']['dynasty']['v'],'Ming' if component=='beizi' else 'Tang')

    def test_excluded_numeric_role_in_shared_clause_keeps_old_pattern(self):
        good=self.generate()
        for text in ['褙子＋马面裙，不要衣长100cm',
                     '半臂＋襦裙，不用袖口半围24cm',
                     '马面裙＋褙子，不要裙长90cm']:
            with self.subTest(text=text):
                result=self.generate(text)
                self.assertEqual(result['status'],'needs_input',result)
                self.assertEqual(result['pattern'],good['pattern'])
                self.assertIn('排除条件',result['reply'])

    def test_exclusion_without_positive_choice_never_reverts_to_forbidden_default(self):
        for text in ['褙子＋马面裙，不要窄袖','半臂＋襦裙，不要宽袖，不要窄袖',
                     '褙子＋马面裙，不要明代','半臂＋襦裙，不要唐代']:
            with self.subTest(text=text):
                self.assertEqual(self.generate(text)['status'],'needs_input')

    def test_failed_new_parse_keeps_last_valid_outfit_and_removes_partial_files(self):
        good=self.generate()
        before=good['pattern']
        bad=self.generate('褙子＋马面裙，裙长-10cm')
        self.assertEqual(bad['status'],'needs_input')
        self.assertEqual(bad['pattern'],before)
        folders=list((Path(self.temp.name)/'patterns'/self.headers['X-Session-Id']).iterdir())
        from .outfits import generate_pattern
        def fail_lower(patch,*args,**kwargs):
            if 'mamian-skirt' in patch:
                raise ValueError('Test lower failure')
            return generate_pattern(patch,*args,**kwargs)
        with patch('backend.outfits.generate_pattern',side_effect=fail_lower):
            bad=self.generate()
        self.assertEqual(bad['status'],'needs_input')
        self.assertEqual(bad['pattern'],before)
        self.assertEqual(folders,list((Path(self.temp.name)/'patterns'/self.headers['X-Session-Id']).iterdir()))

    def image_proposal(self,text=''):
        photo=io.BytesIO()
        Image.new('RGB',(50,90)).save(photo,format='PNG')
        upload=self.client.post('/api/v1/upload/image',headers=self.headers,
            files={'file':('fixture.png',photo.getvalue(),'image/png')}).json()
        response=self.client.post('/api/v1/parse',headers=self.headers,
            json={'text':text,'image':upload['image_id'],'scope':'outfit'})
        return self.client.get('/api/v1/tasks/'+response.json()['task_id'],headers=self.headers).json()['result']

    def observations(self):
        from .vision_fixtures import accounted_scene
        return accounted_scene([
            {'component':'beizi','reason':'Test: open coat','features':{'upper_front':'open','sleeve_shape':'wide'}},
            {'component':'mamian-skirt','reason':'Test: front door and side pleats',
             'features':{'flat_front':True,'side_pleats':True,'length':'full','hem_shape':'wide'}}])

    def test_image_pair_requires_confirmation_then_preserves_observed_styles_and_explicit_cm(self):
        with patch.object(self.engine.model,'image_outfit',return_value=self.observations(),create=True) as recognize:
            proposal=self.image_proposal('身高170cm，腰围80cm，衣长110cm，裙长90cm')
        self.assertEqual(proposal['status'],'needs_input',proposal)
        self.assertTrue(proposal['suggested_outfit'])
        self.assertIsNone(proposal['pattern'])
        response=self.client.post('/api/v1/parse',headers=self.headers,json={
            'text':proposal['suggested_text'],'image_proposal_id':proposal['image_proposal_id']})
        result=self.client.get('/api/v1/tasks/'+response.json()['task_id'],headers=self.headers).json()['result']
        self.assertEqual(result['status'],'generated',result)
        self.assertEqual(result['pattern']['panel_count'],11)
        self.assertEqual(result['design_params']['beizi']['sleeve_cuff_width']['v'],60)
        self.assertEqual(result['design_params']['mamian-skirt']['pleat_ruffle']['v'],3)
        self.assertEqual(result['pattern']['absolute_lengths_cm']['mamian-skirt.length'],90)
        self.assertEqual(result['pattern']['parameter_sources']['mamian-skirt.length'],'text')
        self.assertEqual(recognize.call_count,1)
        self.assertEqual(self.client.post('/api/v1/parse',headers=self.headers,json={
            'text':proposal['suggested_text'],'image_proposal_id':proposal['image_proposal_id']}).status_code,422)

    def test_image_missing_closed_or_excluded_garments_never_become_outfit(self):
        for variant in ['missing','closed','unclear','excluded','pipa']:
            with self.subTest(variant=variant):
                result=self.observations()
                if variant=='missing':
                    result['observations'].pop(0)
                elif variant in {'closed','unclear'}:
                    result['observations'][0]['features']['upper_front']=variant
                elif variant=='pipa':
                    result['observations'][0]['features']['sleeve_shape']='pipa'
                with patch.object(self.engine.model,'image_outfit',return_value=result,create=True):
                    proposal=self.image_proposal('不要褙子' if variant=='excluded' else '')
                self.assertEqual(proposal['status'],'needs_input')
                self.assertNotIn('suggested_outfit',proposal)

    def test_image_long_skirt_default_is_disclosed_and_preserved_after_body_change(self):
        with patch.object(self.engine.model,'image_outfit',return_value=self.observations(),create=True):
            proposal=self.image_proposal()
        self.assertIn('95cm默认裙长',proposal['reply'])
        response=self.client.post('/api/v1/parse',headers=self.headers,json={
            'text':proposal['suggested_text'],'image_proposal_id':proposal['image_proposal_id']})
        result=self.client.get('/api/v1/tasks/'+response.json()['task_id'],headers=self.headers).json()['result']
        self.assertEqual(result['status'],'generated',result)
        self.assertEqual(result['pattern']['absolute_lengths_cm']['mamian-skirt.length'],95)
        self.assertEqual(result['pattern']['parameter_sources']['mamian-skirt.length'],'image_style_default')
        response=self.client.put('/api/v1/body/params',headers=self.headers,json={'path':['height'],'value':180})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['absolute_lengths_cm']['mamian-skirt.length'],95)
        self.assertEqual(response.json()['parameter_sources']['mamian-skirt.length'],'image_style_default')


if __name__ == '__main__':
    unittest.main()
