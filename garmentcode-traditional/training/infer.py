from __future__ import annotations

import argparse
import json

from .common import digest, read_jsonl, resolve, write_json, write_jsonl
from .runtime import environment, load_model, prompt_hash, require_gpu, tokenizer_from, verify_data
from .tokenization import messages


def generate_predictions(model, tokenizer, rows, batch_size=1, max_new_tokens=256, tf32=True):
    import torch
    if batch_size < 1 or max_new_tokens < 1:
        raise ValueError('Batch size and maximum new tokens must be positive')
    previous_padding, was_training = tokenizer.padding_side, model.training
    previous_tf32 = (torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32)
    device = next(model.parameters()).device
    # TrainingArguments(tf32=True) changes global CUDA flags. Match that
    # policy in standalone inference too, including FP32 LoRA projections.
    if device.type == 'cuda':
        torch.backends.cuda.matmul.allow_tf32 = tf32
        torch.backends.cudnn.allow_tf32 = tf32
    tokenizer.padding_side = 'left'
    model.eval()
    output = []
    try:
        for start in range(0, len(rows), batch_size):
            batch = rows[start:start + batch_size]
            prompts = [tokenizer.apply_chat_template(messages(row['prompt']), tokenize=False, add_generation_prompt=True)
                       for row in batch]
            inputs = tokenizer(prompts, padding=True, add_special_tokens=False, return_tensors='pt')
            inputs = {key: value.to(device) for key, value in inputs.items()}
            with torch.inference_mode():
                generated = model.generate(**inputs, do_sample=False, max_new_tokens=max_new_tokens,
                                           pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id,
                                           use_cache=True)
            suffix = generated[:, inputs['input_ids'].shape[1]:]
            texts = tokenizer.batch_decode(suffix, skip_special_tokens=True, clean_up_tokenization_spaces=False)
            for row, text, ids in zip(batch, texts, suffix):
                ended = bool((ids == tokenizer.eos_token_id).any().item())
                output.append({'id': row['id'], 'prediction': text, 'generation_hit_limit': not ended})
    finally:
        tokenizer.padding_side = previous_padding
        model.train(was_training)
        torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32 = previous_tf32
    return output


def main():
    parser = argparse.ArgumentParser(description='Native Qwen2-VL text-to-component JSON inference')
    parser.add_argument('--model', default='lmm_utils/Qwen/Qwen2-VL-2B-Instruct')
    parser.add_argument('--adapter', help='Omit for the unfinetuned model baseline')
    parser.add_argument('--data-dir', default='data/training_v1')
    parser.add_argument('--split', choices=['val', 'test'], default='val')
    parser.add_argument('--prompt', help='Single explicit component request instead of a dataset split')
    parser.add_argument('--output', required=True)
    parser.add_argument('--batch-size', type=int, default=1)
    parser.add_argument('--max-new-tokens', type=int, default=256)
    parser.add_argument('--limit', type=int, help='Smoke predictions only; report will count omitted examples as missing')
    parser.add_argument('--ids-from', help='Select and order examples using IDs from an earlier prediction file, for reload comparison')
    args = parser.parse_args()
    env = environment()
    require_gpu()
    output = resolve(args.output)
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite predictions: {output}')
    model_path = resolve(args.model)
    adapter = resolve(args.adapter) if args.adapter else None
    if adapter:
        manifest_path = adapter / 'run_manifest.json'
        if not manifest_path.exists():
            manifest_path = adapter.parent / 'run_manifest.json'
        if not manifest_path.exists():
            raise ValueError('Adapter run manifest is missing')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if (manifest['system_prompt_sha256'] != prompt_hash()
                or manifest['model_config_sha256'] != digest(model_path / 'config.json')
                or manifest['tokenizer_sha256'] != digest(model_path / 'tokenizer.json')):
            raise ValueError('Base model configuration or fixed prompt differs from the adapter run')
    if args.prompt:
        rows, ground_hash = [{'id': 'interactive-0001', 'prompt': args.prompt}], None
    else:
        datasets, _, _ = verify_data(resolve(args.data_dir))
        rows = datasets[args.split]
        ground_hash = digest(resolve(args.data_dir) / (args.split + '.jsonl'))
    if args.ids_from:
        if args.prompt:
            raise ValueError('--ids-from requires a dataset split')
        ids = [row['id'] for row in read_jsonl(resolve(args.ids_from))]
        lookup = {row['id']: row for row in rows}
        if len(ids) != len(set(ids)) or any(ident not in lookup for ident in ids) or not ids:
            raise ValueError('--ids-from contains duplicate, unknown, or no IDs')
        rows = [lookup[ident] for ident in ids]
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError('--limit must be positive')
        rows = rows[:args.limit]
    tokenizer = tokenizer_from(model_path)
    model = load_model(model_path, adapter)
    predictions = generate_predictions(model, tokenizer, rows, args.batch_size, args.max_new_tokens)
    write_jsonl(output, predictions)
    write_json(output.with_suffix('.meta.json'), {'model': str(model_path), 'adapter': str(adapter) if adapter else None,
               'environment': env, 'rows': len(rows), 'split': None if args.prompt else args.split,
               'ground_truth_sha256': ground_hash, 'system_prompt_sha256': prompt_hash(),
               'max_new_tokens': args.max_new_tokens, 'do_sample': False,
               'generation_tf32': True,
               'generation_hit_limit_count': sum(p['generation_hit_limit'] for p in predictions)})
    print(json.dumps({'output': str(output), 'rows': len(predictions)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
