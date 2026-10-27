from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import time

from .common import canonical, digest, resolve, write_json, write_jsonl
from .runtime import attach_lora, environment, load_model, prompt_hash, require_gpu, tokenizer_from, verify_data
from .tokenization import AnswerCollator, SupervisedDataset


def balanced_subset(rows, count):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['component']].append(row)
    if count < len(grouped):
        raise ValueError('Smoke sample count must cover every component')
    selected = []
    while len(selected) < min(count, len(rows)):
        for key in sorted(grouped):
            if grouped[key] and len(selected) < count:
                selected.append(grouped[key].pop(0))
    return selected


def preflight(config):
    import yaml
    env = environment()
    model_path = resolve(config['model_path'])
    model_config = json.loads((model_path / 'config.json').read_text(encoding='utf-8'))
    if model_config.get('model_type') != 'qwen2_vl':
        raise ValueError('Expected a native Qwen2-VL base model')
    weight_map = json.loads((model_path / 'model.safetensors.index.json').read_text(encoding='utf-8'))['weight_map']
    for filename in set(weight_map.values()):
        if not (model_path / filename).is_file():
            raise FileNotFoundError(f'Local model shard is missing: {filename}')
    rows, schema, stats = verify_data(resolve(config['data_dir']))
    reference = resolve('training/reference_files.json')
    if reference.exists():
        for relative, expected_hash in json.loads(reference.read_text(encoding='utf-8')).items():
            if digest(resolve(relative)) != expected_hash:
                raise ValueError(f'Reference code or data differs from the prepared version: {relative}')
    if digest(resolve(config['template_path'])) != schema['template_sha256']:
        raise ValueError('Traditional template changed since data preparation')
    tokenizer = tokenizer_from(model_path)
    datasets = {name: SupervisedDataset(items, tokenizer, config['max_length']) for name, items in rows.items()}
    lengths = {}
    for name, dataset in datasets.items():
        full = sorted(len(item['input_ids']) for item in dataset.items)
        answers = sorted(sum(v != -100 for v in item['labels']) for item in dataset.items)
        if max(answers) > config['max_new_tokens']:
            raise ValueError('Generation limit is shorter than a complete supervised answer')
        lengths[name] = {'rows': len(full), 'max_tokens': max(full), 'p95_tokens': full[int(.95 * (len(full) - 1))],
                         'max_answer_tokens': max(answers), 'min_answer_tokens': min(answers)}
    template = yaml.safe_load(resolve(config['template_path']).read_text(encoding='utf-8'))['design']
    from .schema import form_errors
    for name, items in rows.items():
        if any(form_errors(item['target'], template) for item in items):
            raise ValueError(f'{name}: invalid form-rule target')
    report = {'environment': env, 'token_lengths': lengths, 'system_prompt_sha256': prompt_hash(),
              'model_config_sha256': digest(model_path / 'config.json'),
              'tokenizer_sha256': digest(model_path / 'tokenizer.json'), 'dataset_stats': stats,
              'answer_only_supervision': True, 'answer_truncation_count': 0,
              'limits': 'Preflight does not load full base weights, exercise CUDA, or demonstrate model quality.'}
    return report, rows, schema, template, tokenizer, datasets


def main():
    parser = argparse.ArgumentParser(description='Independent traditional component JSON LoRA training')
    parser.add_argument('--config', default='training/config_v1.json')
    parser.add_argument('--preflight', action='store_true', help='Verify local data, tokenizer and lengths without loading base weights')
    parser.add_argument('--report', help='Optional preflight report destination')
    parser.add_argument('--smoke', action='store_true', help='Short balanced 24-example run in a separate output directory')
    parser.add_argument('--smoke-steps', type=int, default=30)
    parser.add_argument('--output-dir')
    parser.add_argument('--resume', help='An existing Trainer checkpoint within this output directory')
    args = parser.parse_args()
    config = json.loads(resolve(args.config).read_text(encoding='utf-8'))
    if args.output_dir:
        config['output_dir'] = args.output_dir
    if args.smoke:
        if args.smoke_steps < 1:
            raise ValueError('Smoke steps must be positive')
        if not args.output_dir:
            config['output_dir'] += '-smoke'
        config['gradient_accumulation_steps'] = 2
        config['logging_steps'] = 1
    report, rows, schema, template, tokenizer, datasets = preflight(config)
    if args.report:
        write_json(resolve(args.report), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.preflight:
        return
    require_gpu()

    import torch
    from transformers import Trainer, TrainerCallback, TrainingArguments, set_seed
    from .evaluate import score
    from .infer import generate_predictions

    output = resolve(config['output_dir'])
    manifest = {'config': config, 'smoke': args.smoke, 'smoke_steps': args.smoke_steps if args.smoke else None,
                'system_prompt_sha256': report['system_prompt_sha256'],
                'model_config_sha256': report['model_config_sha256'], 'tokenizer_sha256': report['tokenizer_sha256'],
                'dataset_stats': report['dataset_stats'], 'environment': report['environment']}
    manifest['generation_tf32'] = True
    resume = resolve(args.resume) if args.resume else None
    if resume:
        if not resume.is_dir() or resume.parent != output or not (resume / 'trainer_state.json').exists():
            raise ValueError('Resume must point to a Trainer checkpoint directly inside this output directory')
        previous = json.loads((output / 'run_manifest.json').read_text(encoding='utf-8'))
        for key in ['config', 'smoke', 'smoke_steps', 'system_prompt_sha256', 'model_config_sha256', 'tokenizer_sha256', 'dataset_stats']:
            if canonical(previous[key]) != canonical(manifest[key]):
                raise ValueError(f'Resume configuration mismatch: {key}')
    elif output.exists() and any(output.iterdir()):
        raise FileExistsError(f'Output is nonempty. Choose a new directory or explicitly resume: {output}')
    output.mkdir(parents=True, exist_ok=True)
    set_seed(config['seed'])
    if args.smoke:
        rows = {name: balanced_subset(items, 24) for name, items in rows.items() if name != 'test'}
        datasets = {name: SupervisedDataset(items, tokenizer, config['max_length']) for name, items in rows.items()}
    manifest['used_train_ids'] = [row['id'] for row in rows['train']]
    manifest['used_val_ids'] = [row['id'] for row in rows['val']]
    manifest['status'] = 'starting'
    write_json(output / 'run_manifest.json', manifest)
    write_json(output / 'preflight.json', report)
    model, lora_audit = attach_lora(load_model(resolve(config['model_path']), training=True), config)
    manifest['lora_audit'] = lora_audit
    write_json(output / 'run_manifest.json', manifest)
    model.config.use_cache = False
    model.enable_input_require_grads()

    class GradientGuard(TrainerCallback):
        def __init__(self):
            self.checked = False

        def on_pre_optimizer_step(self, args, state, control, model=None, **kwargs):
            if self.checked:
                return
            grads = [(name, p.grad) for name, p in model.named_parameters() if p.requires_grad]
            finite = all(g is not None and bool(torch.isfinite(g).all()) for _, g in grads)
            nonzero = sum(bool(torch.count_nonzero(g)) for _, g in grads if g is not None)
            result = {'finite_gradients_for_all_trainable_tensors': finite, 'nonzero_gradient_tensors': nonzero,
                      'trainable_tensors': len(grads), 'global_step_before_update': state.global_step}
            write_json(output / 'gradient_check.json', result)
            if not finite or nonzero == 0:
                raise RuntimeError('LoRA gradients are missing, zero, or nonfinite')
            self.checked = True

    class ConfigurationTrainer(Trainer):
        def evaluate(self, eval_dataset=None, ignore_keys=None, metric_key_prefix='eval'):
            metrics = super().evaluate(eval_dataset, ignore_keys, metric_key_prefix)
            if not math.isfinite(metrics[metric_key_prefix + '_loss']):
                raise RuntimeError('Validation loss is nonfinite')
            predictions = generate_predictions(self.model, tokenizer, rows['val'], config['generation_batch_size'], config['max_new_tokens'])
            scored = score(rows['val'], predictions, schema, template)
            score_metrics = {metric_key_prefix + '_' + key: scored['macro'][key]
                             for key in ['config_match', 'schema_valid', 'field_accuracy', 'form_pass']}
            metrics.update(score_metrics)
            self.log(score_metrics)
            write_jsonl(output / f'val-step-{self.state.global_step}.jsonl', predictions)
            write_json(output / f'val-step-{self.state.global_step}.metrics.json', scored)
            return metrics

    step_mode = args.smoke
    arguments = TrainingArguments(
        output_dir=str(output), num_train_epochs=config['epochs'], max_steps=args.smoke_steps if step_mode else -1,
        per_device_train_batch_size=config['micro_batch_size'], per_device_eval_batch_size=1,
        gradient_accumulation_steps=config['gradient_accumulation_steps'], learning_rate=config['learning_rate'],
        warmup_ratio=config['warmup_ratio'], weight_decay=config['weight_decay'], bf16=True, tf32=True,
        gradient_checkpointing=True, gradient_checkpointing_kwargs={'use_reentrant': False},
        eval_strategy='steps' if step_mode else 'epoch', save_strategy='steps' if step_mode else 'epoch',
        eval_steps=args.smoke_steps if step_mode else None, save_steps=args.smoke_steps if step_mode else 500,
        logging_steps=config['logging_steps'], logging_nan_inf_filter=False,
        load_best_model_at_end=True, metric_for_best_model='config_match', greater_is_better=True,
        save_total_limit=3, save_safetensors=True, prediction_loss_only=True,
        remove_unused_columns=False, report_to=[], seed=config['seed'], data_seed=config['seed'], dataloader_num_workers=0,
    )
    trainer = ConfigurationTrainer(model=model, args=arguments, train_dataset=datasets['train'], eval_dataset=datasets['val'],
                                   data_collator=AnswerCollator(tokenizer.pad_token_id), callbacks=[GradientGuard()])
    started = time.monotonic()
    torch.cuda.reset_peak_memory_stats()
    try:
        result = trainer.train(resume_from_checkpoint=str(resume) if resume else None)
        trainer.save_model(str(output))
        tokenizer.save_pretrained(str(output))
        trainer.save_state()
        manifest['adapter_file_sha256'] = digest(output / 'adapter_model.safetensors')
        manifest.update({'status': 'complete', 'train_metrics': result.metrics,
                         'best_validation_checkpoint': trainer.state.best_model_checkpoint,
                         'best_validation_macro_config_match': trainer.state.best_metric})
    except Exception as exc:
        manifest.update({'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'})
        raise
    finally:
        manifest.update({'elapsed_seconds': time.monotonic() - started,
                         'peak_cuda_allocated_bytes': torch.cuda.max_memory_allocated(),
                         'peak_cuda_reserved_bytes': torch.cuda.max_memory_reserved()})
        write_json(output / 'run_manifest.json', manifest)


if __name__ == '__main__':
    main()
