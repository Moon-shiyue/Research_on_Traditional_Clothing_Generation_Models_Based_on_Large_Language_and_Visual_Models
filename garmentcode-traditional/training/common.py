from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PROMPT = (
    '你是传统服饰组件制版配置助手。根据用户明确给出的组件、尺寸、朝代和场合，'
    '只输出一个 JSON 对象，结构为 {组件名: {参数名: {"v": 值}}, '
    '"traditional": {"dynasty": {"v": 朝代}, "occasion": {"v": 场合}}}。'
    '保持参数名和单位与 GarmentCode 传统组件一致，不输出解释或 Python 代码。'
)


def resolve(path):
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    with Path(path).open(encoding='utf-8') as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Preserve frozen v1 JSON bytes (created on Windows) on every platform.
    with path.open('w', encoding='utf-8', newline='\r\n') as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='\n') as handle:
        for row in rows:
            handle.write(canonical(row) + '\n')


def generator_constants():
    """Read the existing generator's vocabulary without importing geometry code."""
    tree = ast.parse((ROOT / 'traditional_ext/build_dataset.py').read_text(encoding='utf-8'))
    names = {'SPACES', 'CONTEXT', 'DYN_CN', 'OCC_CN', 'PHRASE', 'COMPONENT_CLASS'}
    result = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    result[target.id] = ast.literal_eval(node.value)
    if result.keys() != names:
        raise ValueError('Generator vocabulary is incomplete')
    return result


def geometry_key(design):
    geometry = {key: value for key, value in design.items() if key != 'traditional'}
    return hashlib.sha256(canonical(geometry).encode('utf-8')).hexdigest()


def flatten(design):
    result = {}
    for section, fields in design.items():
        if isinstance(fields, dict):
            for key, node in fields.items():
                if isinstance(node, dict) and 'v' in node:
                    result[(section, key)] = node['v']
    return result
