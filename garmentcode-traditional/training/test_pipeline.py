from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

import yaml

from .baseline import extract
from .audit_reload import compare_adapter_files
from .common import ROOT, canonical, digest, generator_constants, read_jsonl, resolve
from .evaluate import execute_patch, score
from .prepare_data import prepare
from .runtime import attach_lora, tokenizer_from, verify_data
from .schema import extract_json, form_errors, validate_patch
from .tokenization import AnswerCollator, encode_record
from .train import balanced_subset
from .verify_reload import compare


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.schema, cls.stats = verify_data(ROOT / 'data/training_v1')
        cls.template = yaml.safe_load((ROOT / 'assets/design_params/traditional.yaml').read_text(encoding='utf-8'))['design']
        cls.vocab = generator_constants()

    def test_repeat_preparation_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            prepare(ROOT / 'data/traditional_design_dataset.jsonl', ROOT / 'assets/design_params/traditional.yaml', directory)
            for name in ['train.jsonl', 'val.jsonl', 'test.jsonl', 'schema.json', 'stats.json', 'split_manifest.json', 'cleaning_report.json']:
                self.assertEqual(digest(directory / name), digest(ROOT / 'data/training_v1' / name), name)

    def test_every_prompt_is_explicit_and_unambiguous(self):
        mapped = {}
        for rows in self.rows.values():
            for row in rows:
                context = row['target']['traditional']
                self.assertIn(self.vocab['DYN_CN'][context['dynasty']['v']], row['prompt'])
                self.assertIn(self.vocab['OCC_CN'][context['occasion']['v']], row['prompt'])
                previous = mapped.setdefault(row['prompt'], canonical(row['target']))
                self.assertEqual(previous, canonical(row['target']))

    def test_rule_extractor_on_validation_without_targets(self):
        for row in self.rows['val']:
            self.assertEqual(extract(row['prompt'], self.schema, self.vocab), row['target'])
        with self.assertRaises(ValueError):
            extract('做一条明代马面裙。', self.schema, self.vocab)

    def test_malformed_and_hostile_json(self):
        for text in ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '[1]', '说明：{"a":1}', '{broken']:
            self.assertIsNone(extract_json(text), text)
        self.assertEqual(extract_json('```json\n{"a":"}"}\n```'), {'a': '}'})
        base = copy.deepcopy(self.rows['train'][0]['target'])
        comp = next(key for key in base if key != 'traditional')
        field = next(iter(base[comp]))
        for bad in [True, '12', float('nan'), 10 ** 400, -1000, 10000]:
            patch = copy.deepcopy(base)
            patch[comp][field]['v'] = bad
            self.assertTrue(validate_patch(patch, self.schema))
        base['unknown'] = {}
        self.assertTrue(validate_patch(base, self.schema))

    def test_qing_low_collar_rule(self):
        row = next(row for row in self.rows['val'] if row['component'] == 'stand-collar')
        patch = copy.deepcopy(row['target'])
        patch['traditional']['dynasty']['v'] = 'Qing'
        patch['stand-collar']['collar_height']['v'] = 2.5
        self.assertFalse(validate_patch(patch, self.schema))
        self.assertTrue(form_errors(patch, self.template))

    def test_missing_field_never_scores_as_complete_with_defaults(self):
        rows = self.rows['val'][:2]
        patch = copy.deepcopy(rows[0]['target'])
        del patch[rows[0]['component']][next(iter(patch[rows[0]['component']]))]
        result = score(rows, [{'id': rows[0]['id'], 'prediction': canonical(patch)}], self.schema, self.template)
        self.assertEqual(result['overall']['missing_predictions'], 1)
        self.assertEqual(result['overall']['schema_valid'], 0)
        self.assertEqual(result['overall']['config_match'], 0)
        self.assertEqual(result['overall']['required_fields_complete'], 0)
        with self.assertRaises(ValueError):
            score(rows, [{'id': 'unknown', 'prediction': '{}'}], self.schema, self.template)

    def test_smoke_selection_covers_components(self):
        rows = balanced_subset(self.rows['train'], 24)
        self.assertEqual(len(rows), 24)
        self.assertEqual({r['component'] for r in rows}, set(self.schema['components']))

    def test_reload_comparison_rejects_missing_or_changed_examples(self):
        before = [{'id': 'a', 'prediction': '{}'}, {'id': 'b', 'prediction': '{"v":1}'}]
        self.assertEqual(compare(before, list(reversed(before)))['identical_predictions'], 2)
        after = [{'id': 'a', 'prediction': '{}'}, {'id': 'b', 'prediction': '{"v":2}'}]
        self.assertEqual(compare(before, after)['changed_ids'], ['b'])
        with self.assertRaises(ValueError):
            compare(before, after[:1])

    def test_saved_adapter_tensor_audit_checks_values_and_not_only_file_bytes(self):
        import torch
        from safetensors.torch import save_file
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / 'a.safetensors', Path(temp) / 'b.safetensors'
            value = torch.arange(6, dtype=torch.float32).reshape(2, 3)
            save_file({'adapter.weight': value}, str(a), metadata={'origin': 'checkpoint'})
            save_file({'adapter.weight': value.clone()}, str(b), metadata={'origin': 'export'})
            result = compare_adapter_files(a, b)
            self.assertTrue(result['tensor_values_identical'])
            self.assertNotEqual(result['first_sha256'], result['second_sha256'])
            changed = value.clone()
            changed[0, 0] += 1
            save_file({'adapter.weight': changed}, str(b))
            self.assertEqual(compare_adapter_files(a, b)['different_tensors'], ['adapter.weight'])

    def test_cuda_generation_precision_is_explicit_and_state_is_restored(self):
        import torch
        from .infer import generate_predictions
        if not torch.cuda.is_available():
            self.skipTest('CUDA is needed to verify CUDA generation policy')

        class Tokenizer:
            padding_side = 'right'
            pad_token_id = 0
            eos_token_id = 2

            def apply_chat_template(self, *args, **kwargs):
                return 'test prompt'

            def __call__(self, texts, **kwargs):
                return {'input_ids': torch.tensor([[1, 4]] * len(texts)),
                        'attention_mask': torch.tensor([[1, 1]] * len(texts))}

            def batch_decode(self, ids, **kwargs):
                return ['{}'] * len(ids)

        class Model(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.anchor = torch.nn.Parameter(torch.zeros(1, device='cuda'))
                self.observed = []
                self.fail = False

            def generate(self, input_ids, **kwargs):
                self.observed.append((torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32))
                if self.fail:
                    raise RuntimeError('Simulated generation failure')
                return torch.cat([input_ids, torch.full((len(input_ids), 1), 2, device=input_ids.device)], dim=1)

        original = (torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32)
        model, tokenizer = Model().train(), Tokenizer()
        try:
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cudnn.allow_tf32 = False
            result = generate_predictions(model, tokenizer, [{'id': 'a', 'prompt': 'example'}])
            self.assertEqual(model.observed[-1], (True, True))
            self.assertFalse(result[0]['generation_hit_limit'])
            self.assertEqual((torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32), (False, False))
            self.assertTrue(model.training)
            self.assertEqual(tokenizer.padding_side, 'right')
            model.fail = True
            with self.assertRaises(RuntimeError):
                generate_predictions(model, tokenizer, [{'id': 'a', 'prompt': 'example'}])
            self.assertTrue(model.training)
            self.assertEqual(tokenizer.padding_side, 'right')
            self.assertEqual((torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32), (False, False))
        finally:
            torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32 = original

    def test_runtime_warnings_are_preserved_separately_from_finite_geometry(self):
        from assets.bodies.body_params import BodyParameters
        row = next(row for row in self.rows['val'] if row['id'] == 'mamian-skirt_ming_0081__text2design_0')
        result = execute_patch(row['target'], self.template, BodyParameters(str(ROOT / 'assets/bodies/mean_female.yaml')))
        self.assertTrue(result['nonempty_panels'])
        self.assertTrue(result['geometry_finite'])
        self.assertIn('invalid value encountered in divide', result['runtime_warnings'])

    def test_answer_masks_and_padding_with_base_tokenizer(self):
        tokenizer = tokenizer_from(ROOT / 'lmm_utils/Qwen/Qwen2-VL-2B-Instruct')
        subset = balanced_subset(self.rows['train'], 24)
        items = [encode_record(row, tokenizer, 1024) for row in subset]
        for row, item in zip(subset, items):
            supervised = [v for v in item['labels'] if v != -100]
            self.assertEqual(supervised[-1], tokenizer.eos_token_id)
            self.assertEqual(extract_json(tokenizer.decode(supervised, skip_special_tokens=True)), row['target'])
            self.assertIn(-100, item['labels'])
        batch = AnswerCollator(tokenizer.pad_token_id)(items)
        self.assertTrue((batch['labels'][batch['attention_mask'] == 0] == -100).all())
        with self.assertRaises(ValueError):
            encode_record(subset[0], tokenizer, 10)

    def test_tiny_native_qwen_lora_gradient_and_reload(self):
        import torch
        from peft import PeftModel
        from transformers import Qwen2VLConfig, Qwen2VLForConditionalGeneration
        torch.manual_seed(42)
        config = Qwen2VLConfig(
            vocab_size=64, hidden_size=16, intermediate_size=32, num_hidden_layers=1,
            num_attention_heads=2, num_key_value_heads=1, max_position_embeddings=64,
            rope_scaling={'type': 'mrope', 'mrope_section': [1, 1, 2]},
            vision_config={'depth': 1, 'embed_dim': 16, 'num_heads': 2, 'hidden_size': 16, 'mlp_ratio': 2,
                           'patch_size': 2, 'spatial_merge_size': 2, 'temporal_patch_size': 1},
            bos_token_id=1, eos_token_id=2, pad_token_id=0,
        )
        base = Qwen2VLForConditionalGeneration(config)
        fresh_base = copy.deepcopy(base)
        adapter, audit = attach_lora(base, {'lora_rank': 2, 'lora_alpha': 4, 'lora_dropout': 0})
        self.assertGreater(audit['trainable_parameters'], 0)
        batch = {'input_ids': torch.tensor([[1, 10, 11, 12, 2]]), 'attention_mask': torch.ones((1, 5), dtype=torch.long),
                 'labels': torch.tensor([[-100, -100, 11, 12, 2]])}
        loss = adapter(**batch).loss
        self.assertTrue(torch.isfinite(loss))
        loss.backward()
        trainable = [p for p in adapter.parameters() if p.requires_grad]
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in trainable))
        self.assertTrue(any(torch.count_nonzero(p.grad) for p in trainable))
        self.assertTrue(all(p.grad is None for p in adapter.parameters() if not p.requires_grad))
        torch.optim.AdamW(trainable, lr=.001).step()
        adapter.eval()
        with torch.no_grad():
            before = adapter(**batch).logits
        with tempfile.TemporaryDirectory() as temp:
            adapter.save_pretrained(temp, safe_serialization=True)
            loaded = PeftModel.from_pretrained(fresh_base, temp).eval()
            with torch.no_grad():
                after = loaded(**batch).logits
            torch.testing.assert_close(before, after, rtol=0, atol=0)


if __name__ == '__main__':
    unittest.main()
