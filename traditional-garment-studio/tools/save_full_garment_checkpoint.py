"""Archive public app sources and selected evidence, excluding private runtime/weights."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
SUFFIXES={'.py','.js','.vue','.json','.jsonl','.css','.svg','.png','.jpg','.jpeg',
          '.md','.html','.txt','.yaml','.yml','.cmd','.pdf','.zip'}
EXCLUDE={'node_modules','__pycache__','.private','.git','.pytest_cache'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--demo',type=Path,action='append',default=[])
    args=parser.parse_args()
    sources=[ROOT/p for p in ['backend','tools','frontend/src','frontend/public','frontend/tests','frontend/dist']]
    evidence=args.evidence.resolve()
    if not evidence.is_relative_to(ROOT/'docs'):raise ValueError('Evidence must be inside project docs')
    sources.append(evidence)
    for demo in args.demo:
        path=demo.resolve()
        if not path.is_relative_to(ROOT/'runtime/patterns'):raise ValueError('Demo must be a saved pattern folder')
        sources.append(path)
    files={ROOT/name for name in ['docs/软件使用指南.md','docs/完整服饰支持范围.md',
        'docs/api-complete-garments-2026-10-25.md','docs/api-complete-garments-2026-10-26.md','docs/api-v0.3.md','docs/api-v0.2.md',
        'docs/quota-cycle-2026-10-24/second-window/frozen-files-second.json',
        'docs/typical-garments-2026-10-18/reference-banbi.png',
        'docs/typical-garments-2026-10-18/imagegen-prompts.json',
        'docs/quota-cycle-2026-10-25/reference-round-robe.png',
        'docs/quota-cycle-2026-10-25/reference-stand-robe.png',
        'docs/quota-cycle-2026-10-25/reference-bijia-three.png']}
    if any(not path.is_file() for path in files):raise ValueError('Required documentation or baseline is missing')
    files.update((ROOT/'docs').glob('api-complete-garments-*.md'))
    for folder in sources:
        for path in folder.rglob('*'):
            if path.is_file() and path.suffix.lower() in SUFFIXES and not EXCLUDE.intersection(path.relative_to(ROOT).parts):
                if path.name in {'reference.jpg','reference.png'} or path.name.startswith('reference-image.'):continue
                files.add(path)
    for folder in [ROOT,ROOT/'frontend']:
        files.update(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {'.md','.cmd','.json','.js','.html'})
    files.update(p for p in [ROOT/'.gitignore',ROOT/'frontend/.gitignore'] if p.is_file())
    files={p for p in files if not p.is_symlink() and p.resolve().is_relative_to(ROOT)}
    manifest={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    record={'created_local':datetime.now().isoformat(timespec='seconds'),'files':manifest,
        'scope':'App sources, current evidence and explicit demo folders. No frozen weights/dataset, private settings, node_modules, runtime reference photos or general runtime. Explicit test images in evidence are retained.',
        'dependencies':'Run in existing d2g environment with adjacent garmentcode-traditional resources; frontend npm ci restores dependencies.'}
    output=ROOT/'output/handoff';output.mkdir(parents=True,exist_ok=True)
    archive=output/('studio-complete-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.zip')
    with ZipFile(archive,'x',ZIP_DEFLATED) as z:
        for path in sorted(files):z.write(path,path.relative_to(ROOT).as_posix())
        z.writestr('checkpoint-manifest.json',json.dumps(record,ensure_ascii=False,indent=2))
    with ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(name)).hexdigest()==digest for name,digest in manifest.items())
    result={'archive':str(archive),'files':len(files),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'verified':True}
    archive.with_suffix('.sha256.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
