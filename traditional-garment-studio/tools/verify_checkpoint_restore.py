"""Verify archive hashes and generate a complete outfit from its restored sources."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
CHILD=r'''
import io,json,uuid
from pathlib import Path
from zipfile import ZipFile
from fastapi.testclient import TestClient
import backend
assert Path(backend.__file__).resolve().is_relative_to(Path.cwd().resolve())
from backend.app import create_app
from backend.engine import PaperEngine
app=create_app(PaperEngine(model=object()),Path('restored-api-check'))
headers={'X-Session-Id':str(uuid.uuid4())}
with TestClient(app) as c:
    health=c.get('/api/v1/health').json()
    from tools.check_studio import health_capabilities
    assert health_capabilities(health)[0],health
    text='cross-upper length:55cm;bijia length:80cm;mamian-skirt length:95cm;cloud-shoulder layers:2'
    if 'duijin-upper' in health['components']:
        text=text.replace('bijia length:80cm','duijin-upper length:60cm,sleeve_length:55cm')
    if 'chest-wrap' in health['components']:
        text=text.replace('cross-upper length:55cm','chest-wrap panel_height:30cm')
    roles=['upper','outer','lower','accessory']
    if 'pibo' in health['components']:
        text+=';pibo strip_length:300cm,strip_width:30cm';roles.append('drape')
    request=c.post('/api/v1/parse',headers=headers,json={'text':text});assert request.status_code==202,request.text
    task=c.get('/api/v1/tasks/'+request.json()['task_id'],headers=headers).json()
    assert task['status']=='done',task
    result=task['result'];assert result['status']=='generated',result
    pattern=result['pattern'];assert [g['id'] for g in pattern['garments']]==roles
    response=c.get('/api/v1/download',headers=headers);assert response.status_code==200,response.text
    with ZipFile(io.BytesIO(response.content)) as z:
        assert z.testzip() is None
        for role in roles:assert role+'/pattern.json' in z.namelist()
        if 'chest-wrap' in health['components']:
            assert json.loads(z.read('upper/assembly.json'))['panel_height']==30.
        if 'drape' in roles:
            strip=json.loads(z.read('drape/assembly.json'))
            assert strip['strip_length']==300. and strip['strip_width']==30.
    plan=c.get('/api/v1/print/plan',headers=headers);assert plan.status_code==200,plan.text
    fixed=pattern['absolute_lengths_cm']
    edit=c.put('/api/v1/body/params',headers=headers,json={'path':['height'],'value':180.})
    assert edit.status_code==200 and edit.json()['absolute_lengths_cm']==fixed,edit.text
with TestClient(create_app(PaperEngine(model=object()),Path('restored-api-check'))) as c:
    restored=c.get('/api/v1/pattern',headers=headers);assert restored.status_code==200,restored.text
    pattern=restored.json();assert pattern['absolute_lengths_cm']==fixed
    assert [g['id'] for g in pattern['garments']]==roles
    if 'duijin-upper' in health['components']:
        assert pattern['garments'][1]['component']=='duijin-upper'
    body=c.get('/api/v1/body/params',headers=headers).json();assert body['params']['height']==180.
    print(json.dumps({'components':len(health['components']),'ensembles':len(health['ensembles']),
        'restored_outfit_members':len(roles),'panels':pattern['panel_count'],'export_crc_ok':True,
        'print_plan_ok':True,'fresh_process_session_restore':True,'fixed_cm_after_height_edit':True,'native_model_loaded':health['model_loaded']}))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--tests',action='store_true',help='Also run the backend regression suite from restored sources')
    args=p.parse_args()
    parent=ROOT/'output/checkpoint-checks';parent.mkdir(parents=True,exist_ok=True)
    assert parent.resolve().is_relative_to(ROOT.resolve())
    record={'archive':str(args.archive.resolve()),'sha256':hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        'scope':'Restore sources and compiled UI; existing external geometry environment, no training, credentials or vision calls.'}
    with tempfile.TemporaryDirectory(dir=parent,prefix='restore-') as temp:
        target=Path(temp).resolve();assert target.is_relative_to(parent.resolve())
        with ZipFile(args.archive) as z:
            assert z.testzip() is None
            manifest=json.loads(z.read('checkpoint-manifest.json'))
            for name,digest in manifest['files'].items():
                assert (target/name).resolve().is_relative_to(target)
                assert hashlib.sha256(z.read(name)).hexdigest()==digest,name
            for name in z.namelist():assert (target/name).resolve().is_relative_to(target)
            z.extractall(target)
        assert (target/'frontend/dist/index.html').is_file()
        env=dict(os.environ,GARMENT_ROOT=os.environ.get('GARMENT_ROOT',str(ROOT.parent/'garmentcode-traditional')),
                 GARMENT_RUNTIME_DIR=str(target/'isolated-runtime'))
        run=subprocess.run([sys.executable,'-X','utf8','-c',CHILD],cwd=target,env=env,
            capture_output=True,text=True,encoding='utf-8',timeout=90)
        record.update(returncode=run.returncode,stdout=run.stdout,stderr=run.stderr[-1500:])
        record['status']='pass' if run.returncode==0 else 'fail'
        if args.tests and run.returncode==0:
            regression=subprocess.run([sys.executable,'-X','utf8','-W','ignore::DeprecationWarning',
                '-m','unittest','discover','-s','backend','-t','.','-q'],cwd=target,env=env,
                capture_output=True,text=True,encoding='utf-8',timeout=200)
            record['restored_backend_tests']={'returncode':regression.returncode,
                'stdout':regression.stdout[-1500:],'stderr':regression.stderr[-5000:]}
            if regression.returncode:record['status']='fail'
    args.report.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False,indent=2));assert record['status']=='pass'


if __name__=='__main__':main()
