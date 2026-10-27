"""Exercise the actual localhost service, including real uploaded image pixels."""
import json
from pathlib import Path
import time
import uuid
from xml.etree import ElementTree as ET

import httpx

STUDIO = Path(__file__).resolve().parents[1]
results = []
with httpx.Client(base_url='http://127.0.0.1:8000', timeout=45,
                  headers={'X-Session-Id':str(uuid.uuid4())}) as client:
    def generate(text='', image=None):
        start = time.monotonic()
        response = client.post('/api/v1/parse',json={'text':text,'image':image})
        response.raise_for_status()
        ident=response.json()['task_id']
        while time.monotonic()-start < 300:
            task=client.get('/api/v1/tasks/'+ident).json()
            if task['status'] in {'done','failed'}:
                result=task.get('result') or task.get('error')
                if result and result.get('pattern'):
                    svg=client.get(result['pattern']['svg_url'])
                    svg.raise_for_status()
                    ET.fromstring(svg.content)
                return result
            time.sleep(1)
        raise TimeoutError('Native inference exceeded 5 minutes')

    text='宋代褙子，衣长及小腿，开衩较高（0.6），袖长超过臂长，常服。'
    result=generate(text)
    assert result['status']=='generated', result
    assert result['design_params']['beizi']['length']['v']==1
    assert result['design_params']['beizi']['sleeve_length']['v']==1.05
    results.append({'kind':'text','result':result})
    print(json.dumps({'text_flow':'passed'}),flush=True)
    photos=[('traditional','R-C.jpg'),('modern','OIP-C.jpg')]
    for label,name in photos:
        image=STUDIO.parent/'中国传统服饰'/name
        with image.open('rb') as file:
            upload=client.post('/api/v1/upload/image',files={'file':(name,file,'image/jpeg')})
        upload.raise_for_status()
        start=time.monotonic()
        result=generate(image=upload.json()['image_id'])
        assert result['status']=='needs_input' and result['pattern'] is None, result
        if label == 'traditional':
            assert result.get('suggested_component')=='ruqun-skirt', result
            confirmed=generate(result['suggested_name'])
            assert confirmed['status']=='generated', confirmed
            results.append({'kind':'image_confirmation','result':confirmed})
        else:
            assert not result.get('suggested_component'), result
        record={'kind':'image','sample':label,'source_name':name,'elapsed_seconds':time.monotonic()-start,'result':result}
        results.append(record)
        print(json.dumps(record,ensure_ascii=True),flush=True)
    report={'date':'2026-10-06','server':'127.0.0.1:8000','image_confirmation_required':True,'sample_scope':'two local reference images; not an accuracy benchmark','samples':results}
    (STUDIO/'docs/software-live-smoke-2026-10-06.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
