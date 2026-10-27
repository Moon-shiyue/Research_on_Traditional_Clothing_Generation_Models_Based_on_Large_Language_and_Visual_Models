"""Reproducible geometry coverage audit for the researched app templates.

Run: python -m backend.audit_traditional_templates
No model, vision API, credential store or GPU is used.
"""
import hashlib
import itertools
import json
import time
import argparse
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path

from .engine import PaperEngine
from .patterns import body_from
from .settings import GARMENT_ROOT,STUDIO_ROOT
from .traditional_templates import SUPPORTED,VERSION,build_traditional
from training.common import read_jsonl
from training.schema import merge_defaults


def audit():
    engine=PaperEngine(model=object())
    body=body_from()
    counts=Counter()
    failures=[]
    max_error=0.
    started=time.monotonic()
    def check(patch,body,context):
        nonlocal max_error
        component=next(k for k in patch if k!='traditional')
        try:
            _,report=build_traditional(body,merge_defaults(patch,engine.template),component)
            max_error=max(max_error,report['validation']['max_seam_length_difference_cm'])
        except Exception as error:
            failures.append({**context,'error':str(error)})
    for split in ['val','test']:
        for row in read_jsonl(GARMENT_ROOT/f'data/training_v1/{split}.jsonl'):
            if row['component'] not in SUPPORTED:
                continue
            counts[row['component']]+=1
            check(row['target'],body,{'split':split,'id':row['id']})
    profiles=[{'height':150,'waist':68,'hips':90,'bust':84},
              {'height':170,'waist':80,'hips':105,'bust':98},
              {'height':185,'waist':100,'hips':120,'bust':112}]
    extra=0
    for values in profiles:
        body=body_from(values)
        for component in sorted(SUPPORTED):
            spec=engine.schema['components'][component]['fields']
            for combination in itertools.product(*(f['training_values'] for f in spec.values())):
                patch=engine.defaults(component)
                for key,value in zip(spec,combination):
                    patch[component][key]['v']=value
                extra+=1
                check(patch,body,{'body':values,'component':component,'values':combination})
    files=['backend/traditional_templates.py','backend/traditional_style.py','backend/patterns.py']
    return {'version':VERSION,'scope':'application flat geometry; no model accuracy or physical fit test',
        'frozen_rows':sum(counts.values()),'by_component':dict(counts),
        'additional_geometry_cases':extra,'body_profiles':profiles,
        'max_seam_error_cm':max_error,'failures':failures,
        'elapsed_seconds':time.monotonic()-started,
        'source_sha256':{p:hashlib.sha256((STUDIO_ROOT/p).read_bytes()).hexdigest() for p in files},
        'frozen_data_sha256':{name:hashlib.sha256((GARMENT_ROOT/'data/training_v1'/name).read_bytes()).hexdigest()
                              for name in ['train.jsonl','val.jsonl','test.jsonl','schema.json']}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination=args.report or STUDIO_ROOT/'docs'/('template-audit-'+stamp+'.json')
    if destination.exists():
        parser.error('报告已存在，请换一个文件名以保留旧记录。')
    report=audit()
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('x',encoding='utf-8') as handle:
        json.dump(report,handle,ensure_ascii=False,indent=2)
    print(json.dumps({'rows':report['frozen_rows'],'additional_cases':report['additional_geometry_cases'],
                      'failures':len(report['failures']),'report':str(destination)},ensure_ascii=False))
    if report['failures']:
        raise SystemExit(1)
