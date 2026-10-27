from __future__ import annotations

import argparse
import json
from pathlib import Path

from .common import digest, read_jsonl, resolve, write_json, write_jsonl
from .infer import generate_predictions
from .runtime import environment, load_model, prompt_hash, require_gpu, tokenizer_from, verify_data
from .verify_reload import compare


def compare_adapter_files(first, second):
    import torch
    from safetensors.torch import load_file
    a, b = load_file(str(first), device='cpu'), load_file(str(second), device='cpu')
    missing, extra = sorted(a.keys() - b.keys()), sorted(b.keys() - a.keys())
    mismatched = [key for key in sorted(a.keys() & b.keys())
                  if a[key].dtype != b[key].dtype or a[key].shape != b[key].shape or not torch.equal(a[key], b[key])]
    return {'first_tensors': len(a), 'second_tensors': len(b), 'missing': missing, 'extra': extra,
            'different_tensors': mismatched, 'tensor_values_identical': not (missing or extra or mismatched),
            'first_sha256': digest(first), 'second_sha256': digest(second)}


def main():
    parser = argparse.ArgumentParser(description='Audit adapter tensors and CUDA TF32 generation policy on the same examples')
    parser.add_argument('--adapter', default='runs/traditional-json-lora-v1-smoke')
    parser.add_argument('--before', default='runs/traditional-json-lora-v1-smoke/val-step-30.jsonl')
    parser.add_argument('--output-dir', default='runs/reload-audit-v1')
    args = parser.parse_args()
    adapter, output = resolve(args.adapter), resolve(args.output_dir)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Audit output directory is nonempty; use a new --output-dir')
    manifest = json.loads((adapter / 'run_manifest.json').read_text(encoding='utf-8'))
    if manifest['status'] != 'complete':
        raise ValueError('Training run has not completed')
    checkpoint = Path(manifest['best_validation_checkpoint'])
    if not checkpoint.is_absolute():
        checkpoint = resolve(checkpoint)
    config = manifest['config']
    model_path = resolve(config['model_path'])
    if (prompt_hash() != manifest['system_prompt_sha256']
            or digest(model_path / 'config.json') != manifest['model_config_sha256']
            or digest(model_path / 'tokenizer.json') != manifest['tokenizer_sha256']):
        raise ValueError('Base model or fixed prompt changed since training')
    weights = compare_adapter_files(checkpoint / 'adapter_model.safetensors', adapter / 'adapter_model.safetensors')
    report = {'adapter_weights': weights, 'environment': environment()}
    write_json(output / 'report.json', report)
    print(json.dumps({'adapter_weights': weights}, ensure_ascii=False, indent=2), flush=True)
    if not weights['tensor_values_identical']:
        raise SystemExit('Saved adapter differs from the selected checkpoint; investigate before generation')
    require_gpu()
    datasets, _, stats = verify_data(resolve(config['data_dir']))
    if stats != manifest['dataset_stats']:
        raise ValueError('Dataset version differs from training')
    before = read_jsonl(resolve(args.before))
    lookup = {row['id']: row for row in datasets['val']}
    ids = [p['id'] for p in before]
    if not ids or len(ids) != len(set(ids)) or any(ident not in lookup for ident in ids):
        raise ValueError('Earlier predictions must contain distinct validation IDs')
    if set(ids) != set(manifest['used_val_ids']):
        raise ValueError('Earlier predictions differ from the training run validation IDs')
    rows = [lookup[ident] for ident in ids]
    tokenizer = tokenizer_from(model_path)
    model = load_model(model_path, adapter)
    report['parameter_dtypes'] = {name: str(param.dtype) for name, param in model.named_parameters()
                                  if 'lora_' in name}
    report['generation_modes'] = {}
    for enabled in [False, True]:
        mode = 'tf32_on' if enabled else 'tf32_off'
        preds = generate_predictions(model, tokenizer, rows, config['generation_batch_size'], config['max_new_tokens'], tf32=enabled)
        write_jsonl(output / (mode + '.jsonl'), preds)
        result = compare(before, preds)
        report['generation_modes'][mode] = result
        write_json(output / 'report.json', report)
        print(json.dumps({mode: result}, ensure_ascii=False, indent=2), flush=True)
    report['tf32_on_matches_all'] = report['generation_modes']['tf32_on']['identical_predictions'] == len(rows)
    report['limits'] = 'Tensor equality and generation equality are separate checks. TF32 as the cause is confirmed only if the same adapter matches the original outputs with TF32 on.'
    write_json(output / 'report.json', report)


if __name__ == '__main__':
    main()
