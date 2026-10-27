from __future__ import annotations

import argparse
from collections import defaultdict
import importlib
import json
import math
from numbers import Real
import warnings

from .common import ROOT, digest, flatten, read_jsonl, resolve, write_json
from .schema import extract_json, finite_number, form_errors, merge_defaults, validate_patch

MODULE_MAP = {
    'mamian-skirt': ('mamian_skirt', 'MamianSkirt'), 'pipa-sleeve': ('sleeves', 'PipaSleeve'),
    'stand-collar': ('collars', 'StandCollar'), 'cross-collar': ('collars_extra', 'CrossCollar'),
    'round-collar': ('collars_extra', 'RoundCollar'), 'duijin-collar': ('collars_extra', 'DuijinCollar'),
    'wide-sleeve': ('sleeves_extra', 'WideSleeve'), 'narrow-sleeve': ('sleeves_extra', 'NarrowSleeve'),
    'ruqun-skirt': ('skirts_extra', 'RuqunSkirt'), 'cloud-shoulder': ('accessories', 'CloudShoulder'),
    'beizi': ('accessories', 'Beizi'), 'banbi': ('accessories', 'Banbi'),
}


def execute_patch(patch, template, body):
    component = next(key for key in patch if key != 'traditional')
    module, name = MODULE_MAP[component]
    cls = getattr(importlib.import_module('traditional_ext.' + module), name)
    # Prediction selects a whitelisted class, never evaluated Python code.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', RuntimeWarning)
        obj = cls(body, merge_defaults(patch, template))
        pattern = obj.assembly()
    component_warnings = list(getattr(obj, 'warnings', []))
    panels = pattern.pattern.get('panels', {})
    def finite_tree(value):
        if isinstance(value, Real):
            return finite_number(value.item() if hasattr(value, 'item') else value)
        if isinstance(value, dict):
            return all(finite_tree(v) for v in value.values())
        if isinstance(value, (list, tuple)):
            return all(finite_tree(v) for v in value)
        if hasattr(value, 'tolist'):
            return finite_tree(value.tolist())
        return True
    return {'nonempty_panels': bool(panels), 'panel_count': len(panels), 'warnings': component_warnings,
            'geometry_finite': finite_tree(pattern.pattern),
            'runtime_warnings': sorted({str(w.message) for w in caught})}


def score(rows, predictions, schema, template, execute=False):
    ids = {row['id'] for row in rows}
    if len(ids) != len(rows) or not rows:
        raise ValueError('Ground truth must contain distinct IDs and at least one record')
    by_id = {}
    for prediction in predictions:
        ident = prediction['id']
        if ident in by_id or ident not in ids:
            raise ValueError(f'Duplicate or unknown prediction ID: {ident}')
        by_id[ident] = prediction
    body = None
    if execute:
        from assets.bodies.body_params import BodyParameters
        body = BodyParameters(str(ROOT / 'assets/bodies/mean_female.yaml'))
    details, numeric = [], defaultdict(lambda: {'errors': [], 'expected': 0})
    for row in rows:
        target = flatten(row['target'])
        supplied = by_id.get(row['id'])
        patch = extract_json(supplied.get('prediction')) if supplied else None
        flat = flatten(patch) if patch is not None else {}
        errors = validate_patch(patch, schema)
        predicted_component = [key for key in (patch or {}) if key in schema['components']]
        present, matched, numeric_matched, categorical_matched = 0, 0, 0, 0
        numeric_expected = sum(isinstance(v, (int, float)) and not isinstance(v, bool) for v in target.values())
        for key, expected in target.items():
            value = flat.get(key)
            is_number = isinstance(expected, (int, float)) and not isinstance(expected, bool)
            valid_value = finite_number(value) if is_number else isinstance(value, str)
            if valid_value:
                present += 1
            equal = valid_value and value == expected
            matched += int(equal)
            numeric_matched += int(equal and is_number)
            categorical_matched += int(equal and not is_number)
            if is_number:
                stats = numeric['.'.join(key)]
                stats['expected'] += 1
                if valid_value:
                    stats['errors'].append(abs(value - expected))
        rules = form_errors(patch, template) if not errors else ['Schema invalid; form not evaluated']
        item = {
            'id': row['id'], 'component': row['component'], 'prediction_present': supplied is not None,
            'json_object_valid': patch is not None, 'schema_valid': not errors,
            'component_correct': predicted_component == [row['component']],
            'required_fields_complete': present == len(target), 'field_expected': len(target),
            'field_correct': matched, 'numeric_expected': numeric_expected,
            'numeric_correct': numeric_matched, 'categorical_expected': len(target) - numeric_expected,
            'categorical_correct': categorical_matched,
            'config_match': not errors and matched == len(target),
            'form_pass': not errors and not rules, 'schema_errors': errors, 'form_errors': rules,
        }
        if execute and not errors:
            try:
                item['execution'] = execute_patch(patch, template, body)
            except Exception as exc:
                item['execution'] = {'nonempty_panels': False, 'error': f'{type(exc).__name__}: {exc}'}
        if execute:
            item['execution_success'] = item.get('execution', {}).get('nonempty_panels', False)
            item['geometry_finite'] = item.get('execution', {}).get('geometry_finite', False)
            item['runtime_warning_free'] = bool(item.get('execution')) and not item['execution'].get('runtime_warnings') and 'error' not in item['execution']
        details.append(item)

    rates = ['json_object_valid', 'schema_valid', 'component_correct', 'required_fields_complete',
             'config_match', 'form_pass'] + (['execution_success', 'geometry_finite', 'runtime_warning_free'] if execute else [])

    def aggregate(items):
        result = {'rows': len(items), 'missing_predictions': sum(not r['prediction_present'] for r in items)}
        result.update({key: sum(r[key] for r in items) / len(items) for key in rates})
        for kind in ['field', 'numeric', 'categorical']:
            count = sum(r[kind + '_expected'] for r in items)
            result[kind + '_accuracy'] = sum(r[kind + '_correct'] for r in items) / count if count else None
        return result

    grouped = defaultdict(list)
    for row in details:
        grouped[row['component']].append(row)
    per_component = {name: aggregate(items) for name, items in sorted(grouped.items())}
    overall = aggregate(details)
    macro = {key: sum(value[key] for value in per_component.values()) / len(per_component)
             for key in rates + ['field_accuracy', 'numeric_accuracy', 'categorical_accuracy']}
    return {'overall': overall, 'macro': macro, 'per_component': per_component,
            'numeric_mae': {key: {'mae': sum(v['errors']) / len(v['errors']) if v['errors'] else None,
                                  'valid_predictions': len(v['errors']), 'expected_predictions': v['expected']}
                            for key, v in sorted(numeric.items())},
            'execution_checked': execute,
            'limits': ['Execution success only means assembly returned nonempty panels; manufacturing and 3D fit are unverified.',
                       'Form rules follow project conventions; cultural authenticity needs independent expert review.',
                       'MAE is per field and only over numeric predictions; always read its coverage alongside accuracy.'],
            'details': details}


def main():
    import yaml
    parser = argparse.ArgumentParser(description='Evaluate raw JSON predictions without default-value scoring')
    parser.add_argument('--data-dir', default='data/training_v1')
    parser.add_argument('--split', choices=['val', 'test'], default='val')
    parser.add_argument('--predictions', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--template', default='assets/design_params/traditional.yaml')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    data = resolve(args.data_dir)
    schema = json.loads((data / 'schema.json').read_text(encoding='utf-8'))
    if digest(resolve(args.template)) != schema['template_sha256']:
        raise ValueError('Template changed since data preparation')
    rows = read_jsonl(data / (args.split + '.jsonl'))
    stats = json.loads((data / 'stats.json').read_text(encoding='utf-8'))
    if digest(data / (args.split + '.jsonl')) != stats['splits'][args.split]['sha256']:
        raise ValueError('Dataset changed since preparation')
    template = yaml.safe_load(resolve(args.template).read_text(encoding='utf-8'))['design']
    report = score(rows, read_jsonl(resolve(args.predictions)), schema, template, args.execute)
    report['provenance'] = {'split': args.split, 'ground_truth_sha256': digest(data / (args.split + '.jsonl')),
                            'predictions_sha256': digest(resolve(args.predictions)), 'schema_sha256': digest(data / 'schema.json')}
    write_json(resolve(args.report), report)
    print(json.dumps({'overall': report['overall'], 'macro': report['macro']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
