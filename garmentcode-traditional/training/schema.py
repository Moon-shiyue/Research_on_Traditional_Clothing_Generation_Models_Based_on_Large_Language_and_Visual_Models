from __future__ import annotations

import copy
import json
import math

from .common import generator_constants


def build_schema(template, source_hash, template_hash):
    vocab = generator_constants()
    components = {}
    for component, fields in vocab['SPACES'].items():
        specs = {}
        for name in fields:
            node = template[component][name]
            labels = {}
            for item in node.get('range', []):
                if isinstance(item, dict):
                    labels.update(item)
            values = list(labels.values()) if labels else node.get('range', [])
            if not values or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
                raise ValueError(f'Unsupported supervised parameter: {component}.{name}')
            specs[name] = {
                'type': node['type'], 'bounds': [min(values), max(values)],
                'training_values': sorted(set(values)), 'labels': labels,
            }
        components[component] = {'fields': specs, 'contexts': vocab['CONTEXT'][component]}
    return {
        'version': 'traditional-json-v1', 'source_sha256': source_hash,
        'template_sha256': template_hash, 'components': components,
        'note': 'Contexts and form rules are project dataset conventions, not independently verified historical claims.',
    }


def extract_json(text):
    if not isinstance(text, str):
        return None
    text = text.strip()
    if text.startswith('```'):
        lines = text.splitlines()
        if lines and lines[-1].strip() == '```':
            text = '\n'.join(lines[1:-1]).strip()
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=unique_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON value')))
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def validate_patch(patch, schema):
    """Validate raw model output before any defaults or repairs are applied."""
    errors = []
    if not isinstance(patch, dict):
        return ['Output must be a JSON object']
    component_names = [key for key in patch if key in schema['components']]
    if len(component_names) != 1:
        return ['Exactly one supported component is required']
    component = component_names[0]
    if set(patch) != {component, 'traditional'}:
        errors.append('Unknown or missing top-level section')
    fields = patch.get(component)
    spec = schema['components'][component]
    if not isinstance(fields, dict):
        return errors + ['Component parameters must be an object']
    if set(fields) != set(spec['fields']):
        errors.append('Missing or unknown supervised component fields')
    for name, param in spec['fields'].items():
        node = fields.get(name)
        if not isinstance(node, dict) or set(node) != {'v'}:
            errors.append(f'{component}.{name}: expected a v-only object')
            continue
        value = node['v']
        if not finite_number(value):
            errors.append(f'{component}.{name}: finite number required')
        elif param['type'] == 'int' and int(value) != value:
            errors.append(f'{component}.{name}: integer required')
        elif not param['bounds'][0] <= value <= param['bounds'][1]:
            errors.append(f'{component}.{name}: value outside schema bounds')
    context = patch.get('traditional')
    if not isinstance(context, dict) or set(context) != {'dynasty', 'occasion'}:
        errors.append('Both dynasty and occasion must be explicitly predicted')
    else:
        for name in ['dynasty', 'occasion']:
            node = context[name]
            if not isinstance(node, dict) or set(node) != {'v'} or node['v'] not in spec['contexts'][name]:
                errors.append(f'traditional.{name}: unsupported value for this dataset component')
    return errors


def form_errors(patch, template):
    """Apply project rules in value space; use identically in preparation and evaluation."""
    design = merge_defaults(patch, template)
    component = next(key for key in patch if key != 'traditional')
    d = {name: node['v'] for name, node in design[component].items()}
    dynasty = design['traditional']['dynasty']['v']
    errors = []
    if component == 'pipa-sleeve' and not d['cuff_width'] < d['root_width'] < d['bulge_width']:
        errors.append('pipa-sleeve: cuff < root < bulge is required')
    if component == 'stand-collar':
        if dynasty == 'Ming' and d['collar_height'] > 4:
            errors.append('stand-collar: Ming height exceeds the project 4cm limit')
        if dynasty == 'Qing' and d['collar_height'] < 4:
            errors.append('stand-collar: Qing height below the project 4cm limit')
        if d['collar_height'] > 8:
            errors.append('stand-collar: height exceeds 8cm')
    if component == 'mamian-skirt':
        if d['mamian_width'] < 15:
            errors.append('mamian-skirt: width below 15cm')
        if d['pleat_ruffle'] < 1:
            errors.append('mamian-skirt: ruffle below 1')
    if component == 'wide-sleeve' and d['cuff_width'] <= d['root_width']:
        errors.append('wide-sleeve: cuff must exceed root width')
    return errors


def merge_defaults(patch, template):
    design = copy.deepcopy(template)
    for section, fields in patch.items():
        for name, node in fields.items():
            design[section][name]['v'] = node['v']
    return design
