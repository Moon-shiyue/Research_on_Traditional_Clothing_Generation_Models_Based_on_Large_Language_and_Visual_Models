"""Snapshot and inspect saved whole-garment geometry; no model calls or secrets."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.settings import GARMENT_ROOT, ADAPTER_PATH


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--design',required=True)
    parser.add_argument('--out',required=True);args=parser.parse_args()
    folder=Path(args.design).resolve();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    meta=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
    import cairosvg
    for name in ['body-layout-dimensions','pattern-dimensions','style']:
        source=folder/(name+'.svg')
        if source.is_file():
            cairosvg.svg2png(url=str(source),write_to=str(out/(name+'.png')),output_width=1800,background_color='white')
    frozen={}
    old=json.loads((ROOT/'docs/quota-cycle-2026-10-24/second-window/frozen-files-second.json').read_text(encoding='utf-8'))
    for name,record in old.items():
        path=(ADAPTER_PATH/'adapter_model.safetensors' if name=='adapter_model.safetensors' else GARMENT_ROOT/'data/training_v1'/name)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        frozen[name]={'expected':record['actual'],'actual':digest,'pass':digest==record['actual']}
    assert all(row['pass'] for row in frozen.values()),'Frozen inputs changed'
    write(out/'frozen-files.json',frozen)
    write(out/'saved-design.json',{'folder':str(folder),'component':meta['component'],
        'panel_count':meta['panel_count'],'garments':meta.get('garments'),
        'geometry_validation':meta.get('geometry_validation'),
        'body_layout':meta.get('body_layout'),'parameter_sources':meta.get('parameter_sources')})
    print(json.dumps({'out':str(out),'panel_count':meta['panel_count'],'frozen_unchanged':True},ensure_ascii=False))


if __name__=='__main__':main()
