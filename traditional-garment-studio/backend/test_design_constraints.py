"""Offered bounds must render on the actual committed body, not a fixed mannequin."""
import copy
import unittest
import tempfile
import uuid
from pathlib import Path
from fastapi.testclient import TestClient
from .app import create_app
from .engine import PaperEngine
from .patterns import body_from,build_geometry


class DesignConstraintTests(unittest.TestCase):
    def setUp(self):self.engine=PaperEngine(object())

    def test_slit_maximum_is_renderable_and_tracks_length_and_body(self):
        for text in ['交领上衣，衣长45cm','立领对襟上衣，衣长60cm','圆领对襟比甲，衣长65cm']:
            for body in [{},{'height':180,'armscye_depth':22}]:
                with self.subTest(text=text,body=body):
                    intent=self.engine.interpret(text,None,body)
                    self.assertEqual(intent['status'],'ready',intent)
                    patch=intent['patch'];component=intent['component']
                    controls=self.engine.parameter_response(patch,body)['params'][component]
                    upper=controls['side_slit']['range'][1]
                    self.assertLess(upper,60.)
                    candidate=copy.deepcopy(patch);candidate[component]['side_slit']['v']=upper
                    geometry=build_geometry(candidate,self.engine.template,body)
                    self.assertTrue(geometry[-1]['sampled_outline_valid'])
                    self.assertLessEqual(upper,geometry[3]['finished_length']-geometry[3]['armhole_depth']-3.+1e-5)
                    candidate[component]['side_slit']['v']=upper+1.
                    with self.assertRaises(ValueError):build_geometry(candidate,self.engine.template,body)

    def test_pipa_cuff_maximum_renders_and_wide_cuff_disables_switch_only(self):
        for body in [{},{'armscye_depth':22}]:
            intent=self.engine.interpret('立领对襟上衣，琵琶袖',None,body)
            patch=intent['patch'];component=intent['component']
            control=self.engine.parameter_response(patch,body)['params'][component]
            patch[component]['sleeve_cuff_width']['v']=control['sleeve_cuff_width']['range'][1]
            geometry=build_geometry(patch,self.engine.template,body)
            self.assertTrue(geometry[-1]['sampled_outline_valid'])
        wide=self.engine.interpret('交领上衣，广袖',None,{})['patch']
        original=copy.deepcopy(wide)
        params=self.engine.parameter_response(wide,{})['params']['cross-upper']
        self.assertTrue(params['sleeve_type']['option_disabled'][1])
        self.assertEqual(wide,original)
        self.assertEqual(params['sleeve_cuff_width']['range'],[16.,100.])

    def test_bounds_do_not_modify_frozen_schema_and_follow_explicit_cm_length(self):
        before=copy.deepcopy(self.engine.schema)
        patch=self.engine.interpret('交领长袍，衣长130cm',None,{})['patch']
        initial=self.engine.parameter_response(patch,{})['params']['cross-robe']['side_slit']['range'][1]
        patch=self.engine.preserve_absolute_lengths(patch,{'height':180},{'cross-robe.length':130.})
        after=self.engine.parameter_response(patch,{'height':180})['params']['cross-robe']['side_slit']['range'][1]
        self.assertAlmostEqual(initial,after)
        self.assertEqual(self.engine.schema,before)
        self.assertEqual(len(self.engine.model_schema['components']),12)

    def test_api_limits_use_committed_body_for_each_outfit_member(self):
        with tempfile.TemporaryDirectory() as temp,TestClient(create_app(self.engine,Path(temp))) as client:
            headers={'X-Session-Id':str(uuid.uuid4())}
            request=client.post('/api/v1/parse',headers=headers,json={'text':'交领上衣，衣长45cm；襦裙，裙长95cm'}).json()
            result=client.get('/api/v1/tasks/'+request['task_id'],headers=headers).json()['result']
            self.assertEqual(result['status'],'generated',result)
            changed=client.put('/api/v1/body/params',headers=headers,json={'path':['armscye_depth'],'value':22.})
            self.assertEqual(changed.status_code,200,changed.text)
            params=client.get('/api/v1/design/params',headers=headers).json()['params']
            self.assertAlmostEqual(params['cross-upper']['side_slit']['range'][1],20.)
            endpoint=client.put('/api/v1/design/params',headers=headers,
                json={'path':['cross-upper','side_slit'],'value':20.,'unit':'native'})
            self.assertEqual(endpoint.status_code,200,endpoint.text)
            current=client.get('/api/v1/pattern',headers=headers).json()
            self.assertEqual(len(current['garments']),2)


if __name__=='__main__':unittest.main()
