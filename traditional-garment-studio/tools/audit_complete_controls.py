"""Exercise whole-garment controls on this run's isolated audit sessions only."""
import argparse
import json
from pathlib import Path
import httpx


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);args=p.parse_args()
    source=json.loads(args.source.read_text(encoding='utf-8'))['cases']
    selected=[];seen=set()
    for case in source:
        components=case['expected_components'];key=tuple(components)
        wanted=(len(components)==1 and (components[0].endswith(('robe','upper')) or components[0]=='bijia'))
        wanted|=len(components)==4 and components[0] in {'cross-upper','stand-upper'} and components[1] in {'beizi','bijia'}
        if case['status']=='pass' and wanted and key not in seen:
            selected.append(case);seen.add(key)
    reports=[]
    with httpx.Client(base_url='http://127.0.0.1:8000',timeout=45,trust_env=False) as client:
        for case in selected:
            row={'session':case['session'],'expected_components':case['expected_components']}
            headers={'X-Session-Id':case['session']}
            try:
                for action in ['random','default']:
                    r=client.post('/api/v1/design/'+action,headers=headers);r.raise_for_status()
                    current=client.get('/api/v1/pattern',headers=headers);current.raise_for_status();meta=current.json()
                    actual=[g['component'] for g in meta.get('garments',[])] or [meta['component']]
                    assert actual==case['expected_components'],(action,actual)
                    assert len(meta['panel_measurements'])==meta['panel_count']
                    assert meta['geometry_finite'] and not meta['is_self_intersecting']
                    assert meta['absolute_lengths_cm']=={}
                    row[action]={'panels':meta['panel_count'],'svg_url':meta['svg_url']}
                row['status']='pass'
            except Exception as error:row.update(status='fail',error=str(error)[:1500])
            reports.append(row);print(row['status'],','.join(case['expected_components']),flush=True)
    result={'rows':len(reports),'passed':sum(r['status']=='pass' for r in reports),'cases':reports}
    args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    assert result['rows']==result['passed'],result
    print({'rows':result['rows'],'passed':result['passed']})


if __name__=='__main__':main()
