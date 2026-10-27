"""Audit current application builders, preserving historical reports and data."""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .engine import PaperEngine
from .patterns import build_geometry
from .settings import GARMENT_ROOT, STUDIO_ROOT
from training.common import read_jsonl, digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    now=datetime.now(timezone.utc)
    out=args.report or STUDIO_ROOT/'docs'/('geometry-audit-'+now.strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    if out.exists():
        parser.error('报告已存在，请换一个文件名以保留旧记录。')
    engine=PaperEngine(model=object())
    counts=Counter()
    failures=[]
    maximum=0.
    for split in ['val','test']:
        for row in read_jsonl(GARMENT_ROOT/f'data/training_v1/{split}.jsonl'):
            counts[row['component']]+=1
            try:
                _,_,_,_,_,validation=build_geometry(row['target'],engine.template,{})
                maximum=max(maximum,validation['max_seam_length_difference_cm'])
                if validation['runtime_warnings']:
                    failures.append({'split':split,'id':row['id'],'warnings':validation['runtime_warnings']})
            except Exception as error:
                failures.append({'split':split,'id':row['id'],'error':type(error).__name__+': '+str(error)})
    report={'created_at':now.isoformat(),'scope':'Current application geometry from frozen val/test targets; no model inference, image accuracy or physical fit claim',
        'rows':sum(counts.values()),'components':dict(counts),'failures':failures,
        'max_seam_length_difference_cm':maximum,
        'backend_sha256':{p.name:digest(p) for p in (STUDIO_ROOT/'backend').glob('*.py')},
        'frozen_data_sha256':{name:digest(GARMENT_ROOT/'data/training_v1'/name)
            for name in ['schema.json','train.jsonl','val.jsonl','test.jsonl']}}
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as handle:
        json.dump(report,handle,ensure_ascii=False,indent=2)
    print(json.dumps({'rows':report['rows'],'failures':len(failures),
        'max_seam_length_difference_cm':maximum,'report':str(out)},ensure_ascii=False))
    return 1 if failures else 0


if __name__=='__main__':
    raise SystemExit(main())
