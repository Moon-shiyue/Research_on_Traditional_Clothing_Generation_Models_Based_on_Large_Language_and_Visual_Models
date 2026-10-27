"""Live localhost audit: whole clothes, sizes, coverage and ZIP consistency.

No vision calls, no model training, no credentials. Every case uses its own
temporary test session so the user's current design remains selected.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import uuid
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.whole_catalog import NAMES
from backend.outfits import PAIRS,LABELS,LAYERED
import httpx


def cases():
    bodies=[{'height':150,'bust':82,'waist':65,'hips':88},
            {'height':182,'bust':106,'waist':90,'hips':110}]
    for body in bodies:
        for component,name in NAMES.items():
            yield body,[component],name+('，衣长130cm' if component.endswith('robe') else '，衣长60cm')+('' if component=='bijia' else '，袖长55cm')
        for upper,lower in PAIRS:
            yield body,[upper,lower],LABELS[upper]+('，围前净高30cm' if upper=='chest-wrap' else '，衣长50cm' if upper=='banbi' else '，衣长110cm' if upper=='beizi' else '，衣长60cm')+'；'+LABELS[lower]+'，裙长95cm'
    for upper,lower in PAIRS:
        yield bodies[0],[upper,lower,'cloud-shoulder'],LABELS[upper]+('，围前净高30cm' if upper=='chest-wrap' else '，衣长50cm' if upper=='banbi' else '，衣长100cm' if upper=='beizi' else '，衣长60cm')+'；'+LABELS[lower]+'，裙长90cm；双层云肩'
    for component in ['cross-robe','round-robe','stand-robe']:
        yield bodies[1],[component,'cloud-shoulder'],NAMES[component]+'，衣长130cm；双层云肩'
    for name in ['圆领对襟上衣','立领对襟上衣']:
        yield bodies[1],['round-upper' if name.startswith('圆') else 'stand-upper','mamian-skirt'],name+'，衣长60cm，袖长55cm，琵琶袖，袖口条宽4cm；马面裙，裙长95cm'
    for body in bodies:
        for group in LAYERED:
            inner,outer,lower=group
            text=LABELS[inner]+('，围前净高30cm；' if inner=='chest-wrap' else '，衣长55cm，袖长45cm；')+LABELS[outer]+(
                '，衣长110cm，袖长48cm' if outer=='beizi' else '，衣长90cm，侧衩高20cm' if outer=='bijia' else '，衣长60cm，袖长50cm' if outer=='duijin-upper' else '，衣长50cm，袖长20cm')+'；'+LABELS[lower]+'，裙长95cm'
            yield body,list(group),text
            yield body,list(group)+['cloud-shoulder'],text+'；双层云肩'


def task(client,headers,payload):
    r=client.post('/api/v1/parse',headers=headers,json=payload);r.raise_for_status()
    end=time.monotonic()+30
    while time.monotonic()<end:
        result=client.get('/api/v1/tasks/'+r.json()['task_id'],headers=headers).json()
        if result['status'] in {'done','failed'}:return result
        time.sleep(.15)
    raise TimeoutError('Local geometry task exceeded 30 seconds')


def draped_cases():
    from backend.outfits import GROUPS,ordered_members
    for body in [{'height':150,'bust':82,'waist':65,'hips':88},
                 {'height':182,'bust':106,'waist':90,'hips':110}]:
        for group in GROUPS:
            if 'pibo' not in group:continue
            expected=ordered_members(group)
            clauses=[]
            for component in expected:
                if component=='chest-wrap':clause='直幅系带抹胸，围前净高30cm'
                elif component=='pibo':clause='直幅披帛，披帛长320cm，幅宽30cm'
                elif component=='cloud-shoulder':clause='双层云肩'
                elif component.endswith('skirt'):clause=LABELS[component]+'，裙长95cm'
                else:clause=LABELS[component]+'，衣长'+('130cm' if component.endswith('robe') else '100cm' if component=='beizi' else '80cm' if component=='bijia' else '50cm' if component=='banbi' else '55cm')
                clauses.append(clause)
            yield body,expected,'；'.join(clauses)


def open_upper_cases():
    from backend.outfits import GROUPS,ordered_members
    for body in [{'height':150,'bust':82,'waist':65,'hips':88},
                 {'height':182,'bust':106,'waist':90,'hips':110}]:
        yield body,['duijin-upper'],'直领对襟上衣，衣长60cm，袖长55cm'
        for group in GROUPS:
            if 'duijin-upper' not in group:continue
            expected=ordered_members(group)
            clauses=[]
            for c in expected:
                if c=='chest-wrap':clause='直幅系带抹胸，围前净高30cm'
                elif c=='pibo':clause='直幅披帛，披帛长320cm，幅宽30cm'
                elif c=='cloud-shoulder':clause='双层云肩'
                elif c.endswith('skirt'):clause=LABELS[c]+'，裙长95cm'
                else:clause=LABELS[c]+'，衣长'+('60cm' if c=='duijin-upper' else '55cm')+'，袖长55cm'
                clauses.append(clause)
            yield body,expected,'；'.join(clauses)


def chest_wrap_cases():
    from backend.outfits import GROUPS,ordered_members
    for body in [{'height':150,'bust':82,'waist':65,'hips':88},{'height':182,'bust':106,'waist':90,'hips':110}]:
        yield body,['chest-wrap'],'直幅系带抹胸，围前净高30cm'
        for group in GROUPS:
            if 'chest-wrap' not in group:continue
            expected=ordered_members(group);clauses=[]
            for c in expected:
                if c=='chest-wrap':clause='直幅系带抹胸，围前净高30cm'
                elif c=='pibo':clause='直幅披帛，净长300cm，净幅宽30cm'
                elif c=='cloud-shoulder':clause='双层云肩'
                elif c.endswith('skirt'):clause=LABELS[c]+'，裙长95cm'
                else:clause=LABELS[c]+'，衣长'+('100cm' if c=='beizi' else '80cm' if c=='bijia' else '50cm' if c=='banbi' else '60cm')
                clauses.append(clause)
            yield body,expected,'；'.join(clauses)


def run(base,output,draped_only=False,open_upper_only=False,baseline_only=False,chest_wrap_only=False):
    reports=[]
    with httpx.Client(base_url=base,timeout=35,trust_env=False) as client:
        health_before=client.get('/api/v1/health').json()
        selected=chest_wrap_cases() if chest_wrap_only else open_upper_cases() if open_upper_only else draped_cases() if draped_only else cases()
        if baseline_only:selected=(row for row in selected if not {'duijin-upper','chest-wrap'}&set(row[1]))
        for index,(body,expected,text) in enumerate(selected):
            sid=str(uuid.uuid4());headers={'X-Session-Id':sid}
            body_text='，'.join(label+str(body[key])+'cm' for key,label in [('height','身高'),('bust','胸围'),('waist','腰围'),('hips','臀围')])
            report={'index':index,'session':sid,'text':text,'body':body,'expected_components':expected}
            try:
                result=task(client,headers,{'text':body_text+'；'+text})
                assert result['status']=='done',result
                result=result['result'];assert result['status']=='generated',result
                pattern=result['pattern'];members=pattern.get('garments') or [pattern]
                assert [g['component'] for g in members]==expected,pattern
                assert pattern['geometry_finite'] is True and pattern['is_self_intersecting'] is False
                assert pattern['panel_count']==len(pattern['panel_measurements'])
                assert len({p['panel_id'] for p in pattern['panel_measurements']})==pattern['panel_count']
                dimensions=client.get(pattern['body_layout_dimension_svg_url']);dimensions.raise_for_status()
                report.update(status='pass',panel_count=pattern['panel_count'],svg_url=pattern['svg_url'],
                              absolute_lengths_cm=pattern.get('absolute_lengths_cm',{}))
                if index in (0,4,32,45,46) or index>=47 and index%12==0:
                    response=client.get('/api/v1/download',headers=headers);response.raise_for_status()
                    with ZipFile(io.BytesIO(response.content)) as z:
                        assert z.testzip() is None
                        manifest=json.loads(z.read('export-manifest.json'))
                        for name,record in manifest['files'].items():
                            assert hashlib.sha256(z.read(name)).hexdigest()==record['sha256'],name
                        report['zip_files']=len(z.namelist())
                if index in (0,4,32,45,46) or index>=47 and index%12==0:
                    old=pattern['absolute_lengths_cm']
                    edited=client.put('/api/v1/body/params',headers=headers,json={'path':['height'],'value':170})
                    edited.raise_for_status();assert edited.json()['absolute_lengths_cm']==old
                    report['fixed_lengths_after_height_edit']=True
            except Exception as exc:
                report.update(status='fail',error=str(exc)[:1800])
            reports.append(report)
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(json.dumps({'cases':reports},ensure_ascii=False,indent=2),encoding='utf-8')
            print(index,report['status'],','.join(expected),flush=True)
        health_after=client.get('/api/v1/health').json()
    answer={'rows':len(reports),'passed':sum(r['status']=='pass' for r in reports),
            'failed':sum(r['status']=='fail' for r in reports),
            'native_model_loaded_before':health_before['model_loaded'],
            'native_model_loaded_after':health_after['model_loaded'],'cases':reports}
    output.write_text(json.dumps(answer,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in answer.items() if k!='cases'}))
    return answer['failed']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8000');p.add_argument('--output',type=Path,required=True)
    selection=p.add_mutually_exclusive_group()
    selection.add_argument('--draped-only',action='store_true',help='Pibo groups on two bodies; baseline cases are separate')
    selection.add_argument('--open-upper-only',action='store_true',help='New straight open upper and its 33 groups on two bodies')
    selection.add_argument('--baseline-only',action='store_true',help='Original 127 complete-garment cases, excluding later catalog additions')
    selection.add_argument('--chest-wrap-only',action='store_true',help='New chest wrap plus its41 groups on two bodies')
    args=p.parse_args();raise SystemExit(bool(run(args.base,args.output,args.draped_only,args.open_upper_only,args.baseline_only,args.chest_wrap_only)))
