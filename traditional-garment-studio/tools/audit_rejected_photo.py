"""Actual unsupported image must not generate substitutes or replace a valid design."""
import argparse
import hashlib
from pathlib import Path
import uuid
import httpx
from audit_complete_photo import perform,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--session',default=None)
    args=parser.parse_args();sid=args.session or str(uuid.uuid4())
    uuid.UUID(sid)
    headers={'X-Session-Id':sid}
    record={'session':sid,'image':str(args.image.resolve()),
        'image_sha256':hashlib.sha256(args.image.read_bytes()).hexdigest(),
        'scope':'One unsupported-image case; checks refusal and preservation, not an accuracy estimate.'}
    try:
        with httpx.Client(base_url='http://127.0.0.1:8000',timeout=30,trust_env=False) as client:
            before=client.get('/api/v1/pattern',headers=headers);before.raise_for_status()
            record['before']=before.json()
            with args.image.open('rb') as source:
                uploaded=client.post('/api/v1/upload/image',headers=headers,files={
                    'file':(args.image.name,source,'image/png' if args.image.suffix.lower()=='.png' else 'image/jpeg')})
            uploaded.raise_for_status()
            result=perform(client,headers,{'image':uploaded.json()['image_id'],'scope':'outfit'})
            record['result']=result
            assert result['status']=='needs_input',result
            assert not any(result.get(key) for key in ['suggested_component','suggested_outfit','opening_choices']),result
            after=client.get('/api/v1/pattern',headers=headers);after.raise_for_status()
            record['after']=after.json()
            assert record['after'].get('svg_url')==record['before'].get('svg_url'),'A rejected image replaced the saved design'
            record['status']='pass';save(args.report,record)
            print({'status':'pass','preserved_previous':bool(record['before'].get('svg_url')),
                'previous_panels':record['before'].get('panel_count'), 'reply':result['reply']})
    except Exception as error:
        record.update(status='failed',error=str(error)[:2000]);save(args.report,record);raise


if __name__=='__main__':main()
