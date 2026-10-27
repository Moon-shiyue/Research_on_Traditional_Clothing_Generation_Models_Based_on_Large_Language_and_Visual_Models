from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os

from .common import SYSTEM_PROMPT, digest, read_jsonl, resolve
from .schema import validate_patch


def environment():
    import platform
    import torch
    versions = {}
    for name in ['torch', 'transformers', 'peft', 'accelerate', 'safetensors', 'PyYAML']:
        versions[name] = importlib.metadata.version(name)
    if versions['transformers'] != '4.46.2' or versions['peft'] != '0.13.2':
        raise ValueError('This training pipeline was checked with transformers==4.46.2 and peft==0.13.2')
    return {'python': platform.python_version(), 'packages': versions, 'cuda_available': torch.cuda.is_available(),
            'gpu': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            'cuda_version': torch.version.cuda}


def verify_data(data_dir):
    stats = json.loads((data_dir / 'stats.json').read_text(encoding='utf-8'))
    for name, key in [('schema.json', 'schema_sha256'), ('split_manifest.json', 'split_manifest_sha256')]:
        if digest(data_dir / name) != stats[key]:
            raise ValueError(f'{name} changed since preparation')
    schema = json.loads((data_dir / 'schema.json').read_text(encoding='utf-8'))
    rows = {}
    for split in ['train', 'val', 'test']:
        path = data_dir / (split + '.jsonl')
        if digest(path) != stats['splits'][split]['sha256']:
            raise ValueError(f'{split} changed since preparation')
        rows[split] = read_jsonl(path)
        if len(rows[split]) != stats['splits'][split]['prompt_rows']:
            raise ValueError(f'{split} row count changed')
        ids = set()
        for row in rows[split]:
            if row['id'] in ids or validate_patch(row['target'], schema):
                raise ValueError(f'{split}: duplicate ID or invalid target')
            ids.add(row['id'])
    for a, b in [('train', 'val'), ('train', 'test'), ('val', 'test')]:
        for field in ['geometry_group', 'prompt', 'src_id']:
            if {r[field] for r in rows[a]} & {r[field] for r in rows[b]}:
                raise ValueError(f'{field} overlaps between {a} and {b}')
    return rows, schema, stats


def tokenizer_from(model_path):
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    if tokenizer.pad_token_id is None or tokenizer.eos_token_id is None or not tokenizer.chat_template:
        raise ValueError('Base tokenizer must define padding, EOS and a chat template')
    return tokenizer


def require_gpu():
    import torch
    if int(os.environ.get('WORLD_SIZE', '1')) != 1:
        raise ValueError('This first version supports one GPU, not distributed execution')
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA GPU is required for full-model training/inference; run --preflight locally first')
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError('This configuration requires a BF16-capable GPU')


def load_model(model_path, adapter=None, training=False):
    import torch
    from transformers import Qwen2VLForConditionalGeneration
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        str(model_path), local_files_only=True, torch_dtype=torch.bfloat16,
        attn_implementation='sdpa', low_cpu_mem_usage=True,
    )
    if adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, str(adapter), is_trainable=training)
    return model.to('cuda')


def attach_lora(model, config):
    from peft import LoraConfig, get_peft_model
    model = get_peft_model(model, LoraConfig(
        task_type='CAUSAL_LM', r=config['lora_rank'], lora_alpha=config['lora_alpha'],
        lora_dropout=config['lora_dropout'], bias='none',
        target_modules=r'model\.layers\.\d+\.self_attn\.(q_proj|k_proj|v_proj|o_proj)',
    ))
    trained = [(name, param) for name, param in model.named_parameters() if param.requires_grad]
    if not trained or any('visual' in name or 'lora_' not in name for name, _ in trained):
        raise ValueError('LoRA must train only language attention adapters')
    return model, {'trainable_parameters': sum(p.numel() for _, p in trained),
                   'total_parameters': sum(p.numel() for p in model.parameters()),
                   'trainable_tensor_names': [name for name, _ in trained]}


def prompt_hash():
    return hashlib.sha256(SYSTEM_PROMPT.encode('utf-8')).hexdigest()
