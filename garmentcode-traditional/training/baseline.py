from __future__ import annotations

import argparse
import json

from .common import canonical, generator_constants, read_jsonl, resolve, write_json, write_jsonl


def extract(prompt, schema, vocab):
    components = [key for key, (_, name) in vocab['COMPONENT_CLASS'].items() if name in prompt]
    if len(components) != 1:
        raise ValueError('Exactly one explicit component name is needed')
    comp = components[0]
    patch = {comp: {}, 'traditional': {}}
    for field, phrases in vocab['PHRASE'][comp].items():
        matches = [(label, phrase) for label, phrase in phrases.items() if phrase in prompt]
        # "齐胸高腰" contains "高腰": keep the longer matched phrase.
        matches = [(label, phrase) for label, phrase in matches
                   if not any(phrase != other and phrase in other for _, other in matches)]
        if len(matches) != 1:
            raise ValueError(f'Missing or ambiguous parameter phrase: {comp}.{field}')
        label = matches[0][0]
        patch[comp][field] = {'v': schema['components'][comp]['fields'][field]['labels'][label]}
    for field, mapping in [('dynasty', vocab['DYN_CN']), ('occasion', vocab['OCC_CN'])]:
        matches = [label for label, phrase in mapping.items() if phrase in prompt]
        if len(matches) != 1:
            raise ValueError(f'Missing or ambiguous context: {field}')
        patch['traditional'][field] = {'v': matches[0]}
    return patch


def main():
    parser = argparse.ArgumentParser(description='Literal template baseline; reads prompts, never target answers')
    parser.add_argument('--data-dir', default='data/training_v1')
    parser.add_argument('--split', choices=['val', 'test'], default='val')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    data = resolve(args.data_dir)
    schema = json.loads((data / 'schema.json').read_text(encoding='utf-8'))
    vocab = generator_constants()
    output, failures = [], []
    for row in read_jsonl(data / (args.split + '.jsonl')):
        try:
            prediction = canonical(extract(row['prompt'], schema, vocab))
        except ValueError as exc:
            prediction = ''
            failures.append({'id': row['id'], 'reason': str(exc)})
        output.append({'id': row['id'], 'prediction': prediction})
    write_jsonl(resolve(args.output), output)
    write_json(resolve(args.output).with_suffix('.failures.json'), failures)
    print(json.dumps({'rows': len(output), 'extraction_failures': len(failures)}))


if __name__ == '__main__':
    main()
