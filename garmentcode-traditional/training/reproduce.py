"""Prepare an isolated, verified v1 experiment without changing the studio geometry."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / 'models/traditional-json-lora-v1'
BASE = ROOT / 'lmm_utils/Qwen/Qwen2-VL-2B-Instruct'


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def verified_release():
    hashes = read(RELEASE / 'release_checksums.json')
    for name, expected in hashes.items():
        path = (RELEASE / name).resolve()
        if RELEASE.resolve() not in path.parents or sha256(path) != expected:
            raise ValueError(f'Release file mismatch: {name}')
    manifest = read(RELEASE / 'run_manifest.json')
    if manifest['status'] != 'complete' or sha256(RELEASE / 'adapter_model.safetensors') != manifest['adapter_file_sha256']:
        raise ValueError('Incomplete run or wrong adapter')
    for name, expected in read(ROOT / 'training/reference_files.json').items():
        snapshot = RELEASE / 'reference_snapshot' / name
        if sha256(snapshot if snapshot.exists() else ROOT / name) != expected:
            raise ValueError(f'Historical reference mismatch: {name}')
    stats = read(ROOT / 'data/training_v1/stats.json')
    if stats != manifest['dataset_stats']:
        raise ValueError('Dataset statistics differ from original run')
    for name, expected in [('schema.json', stats['schema_sha256']),
                           ('split_manifest.json', stats['split_manifest_sha256'])] + [
                           (split + '.jsonl', stats['splits'][split]['sha256']) for split in ['train', 'val', 'test']]:
        if sha256(ROOT / 'data/training_v1' / name) != expected:
            raise ValueError(f'Dataset mismatch: {name}')
    print(f'Verified {len(hashes)} release files, adapter, historical references and frozen splits.')


def prepare(output):
    verified_release()
    output = output.resolve()
    if output == ROOT or ROOT in output.parents or output in ROOT.parents:
        raise ValueError('Choose a separate directory outside garmentcode-traditional')
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite existing directory: {output}')
    output.mkdir(parents=True)
    for name in ['training', 'data', 'assets', 'pygarment', 'traditional_ext', 'models']:
        shutil.copytree(ROOT / name, output / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for p in (RELEASE / 'reference_snapshot').rglob('*'):
        if p.is_file():
            shutil.copyfile(p, output / p.relative_to(RELEASE / 'reference_snapshot'))
    for name, expected in read(output / 'training/reference_files.json').items():
        if sha256(output / name) != expected:
            raise ValueError(f'Prepared reference mismatch: {name}')
    for p in ROOT.glob('LICENSE*'):
        shutil.copyfile(p, output / p.name)
    print(f'Historical experiment prepared: {output}')
    print('Change into that directory, then run python -m training.reproduce download-base')


def base_files(download=False, source=None):
    verified_release()
    provenance = read(RELEASE / 'base_source.json')
    if download:
        BASE.mkdir(parents=True, exist_ok=True)
        for p in (RELEASE / 'base_runtime').iterdir():
            target = BASE / p.name
            if target.exists() and sha256(target) != sha256(p):
                raise ValueError(f'Existing runtime file differs; use a clean directory: {target}')
            if not target.exists():
                shutil.copyfile(p, target)
    for name, info in provenance['shards'].items():
        dest = BASE / name
        if not dest.exists() and download:
            partial = dest.with_suffix(dest.suffix + '.partial')
            if source:
                candidate = source / name
                if sha256(candidate) != info['sha256']:
                    raise ValueError(f'Local base shard differs: {candidate}')
                shutil.copyfile(candidate, partial)
            else:
                url = f"https://huggingface.co/{provenance['repo_id']}/resolve/{provenance['revision']}/{name}"
                print(f'Downloading {name} ({info["size"] / 1e9:.2f} GB)', flush=True)
                with urllib.request.urlopen(url, timeout=120) as response, partial.open('wb') as f:
                    done = 0
                    mark = 0
                    while True:
                        block = response.read(8 * 1024 * 1024)
                        if not block:
                            break
                        f.write(block)
                        done += len(block)
                        if done // (256 * 1024 * 1024) > mark:
                            mark = done // (256 * 1024 * 1024)
                            print(f'  {done / 1e9:.2f}/{info["size"] / 1e9:.2f} GB', flush=True)
            if partial.stat().st_size != info['size'] or sha256(partial) != info['sha256']:
                raise ValueError(f'Download failed integrity check: {partial}')
            partial.replace(dest)
        if not dest.is_file() or dest.stat().st_size != info['size'] or sha256(dest) != info['sha256']:
            raise ValueError(f'Missing or mismatched base shard: {dest}')
    for p in (RELEASE / 'base_runtime').iterdir():
        if not (BASE / p.name).is_file() or sha256(BASE / p.name) != sha256(p):
            raise ValueError(f'Missing or mismatched runtime file: {p.name}')
    print('Base shards and exact training runtime/tokenizer verified.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['verify-release', 'prepare', 'download-base', 'verify-base'])
    parser.add_argument('--output', type=Path, default=ROOT.parent / 'reproduction-v1')
    parser.add_argument('--source', type=Path, help='Optional existing official base directory; copy and verify instead of downloading')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.output)
    elif args.action in ['download-base', 'verify-base']:
        base_files(download=args.action == 'download-base', source=args.source)
    else:
        verified_release()


if __name__ == '__main__':
    main()
