from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import random

from .common import canonical, digest, generator_constants, geometry_key, read_jsonl, resolve, write_json, write_jsonl
from .schema import build_schema, form_errors, validate_patch


def split_groups(rows, seed=42):
    grouped = defaultdict(dict)
    for row in rows:
        key = geometry_key(row['design'])
        grouped[row['component']].setdefault(key, []).append(row)
    splits = {name: [] for name in ['train', 'val', 'test']}
    manifest = {}
    rng = random.Random(seed)
    for component in sorted(grouped):
        keys = sorted(grouped[component])
        if len(keys) < 3:
            raise ValueError(f'{component}: at least three distinct geometries are needed')
        rng.shuffle(keys)
        count = max(1, round(len(keys) * .1))
        boundaries = {'test': keys[:count], 'val': keys[count:2 * count], 'train': keys[2 * count:]}
        for split, group_keys in boundaries.items():
            for key in group_keys:
                manifest[key] = split
                splits[split].extend(grouped[component][key])
    return splits, manifest


def prepare(source, template_path, output, seed=42):
    import yaml

    rows = read_jsonl(source)
    ids = [row['id'] for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate source IDs')
    template = yaml.safe_load(template_path.read_text(encoding='utf-8'))['design']
    schema = build_schema(template, digest(source), digest(template_path))
    vocab = generator_constants()
    prompts = defaultdict(set)
    rejected = []
    eligible = []
    for row in rows:
        for prompt in row['instructions_cn']:
            prompts[prompt].add(canonical(row['design']))
        errors = validate_patch(row['design'], schema)
        if not errors:
            errors = form_errors(row['design'], template)
        if errors:
            rejected.append({'id': row['id'], 'reason': errors})
        else:
            eligible.append(row)
    if not eligible:
        raise ValueError('No valid source rows')
    splits, groups = split_groups(eligible, seed)
    expanded = {}
    excluded = []
    for split, samples in splits.items():
        records = []
        for row in sorted(samples, key=lambda r: r['id']):
            for i, prompt in enumerate(row['instructions_cn']):
                # Do not supervise a context that was never stated in the prompt.
                occasion = vocab['OCC_CN'][row['occasion']]
                dynasty = vocab['DYN_CN'][row['dynasty']]
                if occasion not in prompt or dynasty not in prompt:
                    excluded.append({'id': row['id'], 'variant': i, 'reason': 'context_not_explicit'})
                    continue
                if len(prompts[prompt]) > 1:
                    excluded.append({'id': row['id'], 'variant': i, 'reason': 'ambiguous_target'})
                    continue
                records.append({
                    'id': f"{row['id']}__text2design_{i}", 'src_id': row['id'],
                    'component': row['component'], 'geometry_group': geometry_key(row['design']),
                    'prompt': prompt, 'target': row['design'],
                })
        if not records:
            raise ValueError(f'Empty {split} set after cleaning')
        expanded[split] = records
    for a, b in [('train', 'val'), ('train', 'test'), ('val', 'test')]:
        for field in ['geometry_group', 'prompt', 'src_id']:
            shared = {r[field] for r in expanded[a]} & {r[field] for r in expanded[b]}
            if shared:
                raise ValueError(f'{field} leakage between {a} and {b}')
    output.mkdir(parents=True, exist_ok=True)
    for split, records in expanded.items():
        write_jsonl(output / f'{split}.jsonl', records)
    write_json(output / 'schema.json', schema)
    write_json(output / 'split_manifest.json', {'seed': seed, 'geometry_to_split': groups})
    write_json(output / 'cleaning_report.json', {'rejected_sources': rejected, 'excluded_prompts': excluded})
    coverage = {}
    for name, records in expanded.items():
        by_field = defaultdict(set)
        for row in records:
            for key, node in row['target'][row['component']].items():
                by_field[f"{row['component']}.{key}"].add(node['v'])
        coverage[name] = by_field
    unseen = {
        name: {field: sorted(values - coverage['train'].get(field, set()))
               for field, values in coverage[name].items() if values - coverage['train'].get(field, set())}
        for name in ['val', 'test']
    }
    stats = {
        'version': schema['version'], 'seed': seed,
        'source_sha256': digest(source), 'template_sha256': digest(template_path),
        'source_rows': len(rows), 'accepted_sources': len(eligible), 'rejected_sources': len(rejected),
        'raw_unique_geometry_groups': len({geometry_key(row['design']) for row in rows}),
        'raw_ambiguous_prompt_strings': sum(len(v) > 1 for v in prompts.values()),
        'excluded_prompt_rows': len(excluded), 'unseen_parameter_values': unseen,
        'schema_sha256': digest(output / 'schema.json'),
        'split_manifest_sha256': digest(output / 'split_manifest.json'),
        'splits': {name: {
            'prompt_rows': len(records), 'source_rows': len({r['src_id'] for r in records}),
            'geometry_groups': len({r['geometry_group'] for r in records}),
            'components': dict(sorted(Counter(r['component'] for r in records).items())),
            'sha256': digest(output / f'{name}.jsonl'),
        } for name, records in expanded.items()},
        'cross_split_geometry_prompt_and_id_overlap': 0,
    }
    write_json(output / 'stats.json', stats)
    return stats


def main():
    parser = argparse.ArgumentParser(description='Audit, clean and group-split traditional component data')
    parser.add_argument('--source', default='data/traditional_design_dataset.jsonl')
    parser.add_argument('--template', default='assets/design_params/traditional.yaml')
    parser.add_argument('--output', default='data/training_v1')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    stats = prepare(resolve(args.source), resolve(args.template), resolve(args.output), args.seed)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
