"""One actual image-to-complete-pattern call, with a recorded confirmation.

Uses the configured localhost service; does not read login data or change
providers. No automatic re-submission on vision failures or ambiguous clothes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import uuid

import httpx


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def perform(client,headers,payload):
    response=client.post('/api/v1/parse',headers=headers,json=payload)
    response.raise_for_status();task_id=response.json()['task_id'];end=time.monotonic()+125
    while time.monotonic()<end:
        task=client.get('/api/v1/tasks/'+task_id,headers=headers).json()
        if task['status'] in {'done','failed'}:
            if task['status']!='done':raise RuntimeError(str(task.get('error')))
            return task['result']
        time.sleep(.4)
    raise TimeoutError('Image task exceeded 125s; not automatically submitted again')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--image',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True);parser.add_argument('--expect',required=True)
    parser.add_argument('--opening',choices=['center','right']);parser.add_argument('--text',default='')
    parser.add_argument('--skirt',choices=['mamian-skirt','ruqun-skirt'])
    parser.add_argument('--innerwear',choices=['chest-wrap'])
    args=parser.parse_args();sid=str(uuid.uuid4());headers={'X-Session-Id':sid}
    record={'image':str(args.image.resolve()),'image_sha256':hashlib.sha256(args.image.read_bytes()).hexdigest(),
            'session':sid,'expected_components':args.expect.split(','),'opening_choice_used':None,
            'skirt_choice_used':None,'confirmation_steps':[],
            'scope':'one case, not an accuracy estimate'}
    try:
        with httpx.Client(base_url='http://127.0.0.1:8000',timeout=30,trust_env=False) as client:
            client.get('/api/v1/health').raise_for_status()
            with args.image.open('rb') as source:
                upload=client.post('/api/v1/upload/image',headers=headers,files={'file':(args.image.name,source,'image/png' if args.image.suffix.lower()=='.png' else 'image/jpeg')})
            upload.raise_for_status()
            proposal=perform(client,headers,{'image':upload.json()['image_id'],'text':args.text,'scope':'outfit'})
            record['proposal']=proposal;save(args.report,record)
            result=proposal
            for _ in range(4):
                if result['status']!='needs_input':break
                if not result.get('image_proposal_id'):
                    record.update(status='needs_input',note='No full safe candidate; no partial generation')
                    save(args.report,record);print(json.dumps({'status':'needs_input','reply':result['reply']},ensure_ascii=False));return 2
                payload={'text':result['suggested_text'],'image_proposal_id':result['image_proposal_id'],'scope':'outfit'}
                if result.get('innerwear_choices'):
                    if not args.innerwear:
                        record.update(status='needs_innerwear_choice');save(args.report,record);return 2
                    assert args.innerwear in {c['id'] for c in result['innerwear_choices']}
                    payload['innerwear_choice']=args.innerwear;record['innerwear_choice_used']=args.innerwear
                if result.get('skirt_choices'):
                    if not args.skirt:
                        record.update(status='needs_skirt_choice');save(args.report,record)
                        print('Skirt type is occluded; --skirt is required for this explicit test variant');return 2
                    assert args.skirt in {c['id'] for c in result['skirt_choices']},'Selected skirt is not offered'
                    payload['skirt_choice']=args.skirt;record['skirt_choice_used']=args.skirt
                if result.get('opening_choices'):
                    if not args.opening:
                        record.update(status='needs_opening_choice');save(args.report,record)
                        print('Opening is occluded; --opening is required for this explicit test variant');return 2
                    payload['opening_choice']=args.opening;record['opening_choice_used']=args.opening
                result=perform(client,headers,payload)
                record['confirmation_steps'].append({'request':payload,'result':result});save(args.report,record)
            record['result']=result
            assert result['status']=='generated',result
            pattern=result['pattern'];actual=[g['component'] for g in pattern.get('garments',[])] or [pattern['component']]
            assert actual==record['expected_components'],actual
            assert pattern['geometry_finite'] is True and pattern['is_self_intersecting'] is False
            assert len(pattern['panel_measurements'])==pattern['panel_count']
            record.update(status='pass',actual_components=actual,panel_count=pattern['panel_count'],
                          svg_url=pattern['svg_url'])
            save(args.report,record)
            print(json.dumps({k:record[k] for k in ['status','session','actual_components','panel_count','svg_url','opening_choice_used']},ensure_ascii=False))
    except Exception as error:
        record.update(status='failed',error=str(error)[:2000]);save(args.report,record);raise
    return 0


if __name__=='__main__':raise SystemExit(main())
