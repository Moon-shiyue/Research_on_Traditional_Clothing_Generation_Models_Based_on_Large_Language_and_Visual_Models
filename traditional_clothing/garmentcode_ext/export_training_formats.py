"""
导出标准微调格式 — 把传统服饰设计数据集转成主流训练框架可用的格式

支持输出：
  ① Alpaca 格式        instruction / input / output          （LLaMA-Factory、Axolotl 等）
  ② ShareGPT 格式      conversations[human/gpt]              （LLaMA-Factory、FastChat）
  ③ OpenAI 微调格式     messages[system/user/assistant]       （OpenAI / 兼容接口）
  ④ D2GC 对齐格式       caption → design                      （Design2GarmentCode 的 caption2yaml 链路）

任务形式（一条数据可展开为多种监督目标，提升数据利用率）：
  T1 text2design    制版说明 → 设计配置（主任务）
  T2 text2code      制版说明 → 调用代码
  T3 caption2design 参数路径标签 → 设计配置（与 D2GC 严格对齐）
  T4 design2text    设计配置 → 制版说明（反向任务，增强形制理解）

⚠️ 划分防泄露：
  同一参数组合的 3 种句式必须落在同一个 split（否则验证集"见过"对应配置，指标虚高）。
  本脚本以样本 id（= 一个参数组合）为单位做分层划分（按组件分层）。
"""
from __future__ import annotations

import json
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_FILE = os.path.join('data', 'traditional_instruct',
                         'traditional_design_dataset.jsonl')
OUT_DIR = os.path.join('data', 'traditional_instruct', 'training_formats')
VAL_RATIO = 0.10
SEED = 42

SYSTEM_PROMPT = (
    '你是中国传统服饰制版助手，精通历代服饰形制（汉/魏晋/唐/宋/明/清）与 '
    'GarmentCode 参数化纸样体系。你的任务是把用户的制版要求转换为可直接执行的 '
    '设计配置，并严格遵守形制规范（如琵琶袖仅明代、马面宽≥15cm、明代立领≤4cm）。'
)


# ═══════════════════════════════════════════════════════════════
# 任务模板
# ═══════════════════════════════════════════════════════════════

def _design_json(sample, indent=2):
    return json.dumps(sample['design'], ensure_ascii=False, indent=indent)


def _design_compact(sample):
    return json.dumps(sample['design'], ensure_ascii=False)


def task_text2design(sample, instr, **kw):
    return (instr, _design_json(sample))


# 组件 → (模块, 类名)，用于生成可执行代码
MODULE_MAP = {
    'mamian-skirt': ('mamian_skirt', 'MamianSkirt'),
    'pipa-sleeve': ('sleeves', 'PipaSleeve'),
    'stand-collar': ('collars', 'StandCollar'),
    'cross-collar': ('collars_extra', 'CrossCollar'),
    'round-collar': ('collars_extra', 'RoundCollar'),
    'duijin-collar': ('collars_extra', 'DuijinCollar'),
    'wide-sleeve': ('sleeves_extra', 'WideSleeve'),
    'narrow-sleeve': ('sleeves_extra', 'NarrowSleeve'),
    'ruqun-skirt': ('skirts_extra', 'RuqunSkirt'),
    'cloud-shoulder': ('accessories', 'CloudShoulder'),
    'beizi': ('accessories', 'Beizi'),
    'banbi': ('accessories', 'Banbi'),
}


def task_text2code(sample, instr, **kw):
    """输出完整可执行代码（配置 + 调用），比纯调用语句更有监督价值。"""
    mod, cls = MODULE_MAP[sample['component']]
    code = (
        f"from traditional_ext.{mod} import {cls}\n"
        f"\n"
        f"design = {json.dumps(sample['design'], ensure_ascii=False, indent=4)}\n"
        f"\n"
        f"garment = {cls}(body, design)\n"
        f"pattern = garment.assembly()      # 生成纸样"
    )
    return (instr, code)


def task_caption2design(sample, instr, **kw):
    prompt = ('以下是传统服饰参数的路径标签（格式：节点__参数__取值）。'
              '请据此生成 GarmentCode 设计配置（JSON）。\n\n'
              + '\n'.join(sample['caption']))
    return (prompt, _design_json(sample))


def task_design2text(sample, instr, **kw):
    prompt = ('以下是某传统服饰的 GarmentCode 设计配置，请用中文写出对应的制版说明'
              '（包含朝代、形制、关键尺寸）。\n\n' + _design_compact(sample))
    return (prompt, sample['instructions_cn'][0])


TASKS = {
    'text2design': task_text2design,
    'text2code': task_text2code,
    'caption2design': task_caption2design,
    'design2text': task_design2text,
}


# ═══════════════════════════════════════════════════════════════
# 样本展开
# ═══════════════════════════════════════════════════════════════

def expand(samples, task_names):
    """把每条数据展开为多个训练样本（按任务 × 句式）。"""
    out = []
    for s in samples:
        for tname in task_names:
            fn = TASKS[tname]
            # T1/T2 用 3 种句式，T3/T4 各 1 次
            instrs = s['instructions_cn'] if tname in ('text2design', 'text2code') else [None]
            for i, instr in enumerate(instrs):
                prompt, answer = fn(s, instr)
                out.append({
                    'id': f"{s['id']}__{tname}" + (f"_{i + 1}" if i else ''),
                    'src_id': s['id'],                    # 用于划分（同 src_id 同 split）
                    'task': tname,
                    'component': s['component'],
                    'dynasty': s['dynasty'],
                    'prompt': prompt,
                    'answer': answer,
                })
    return out


# ═══════════════════════════════════════════════════════════════
# 划分（按 src_id 分层，避免同组合跨 split）
# ═══════════════════════════════════════════════════════════════

def split_ids(samples, val_ratio=VAL_RATIO, seed=SEED):
    """按组件分层划分样本 id（不是按展开后的样本）。"""
    random.seed(seed)
    by_comp = defaultdict(list)
    for s in samples:
        by_comp[s['component']].append(s['id'])

    train_ids, val_ids = set(), set()
    for comp, ids in by_comp.items():
        ids = sorted(ids)
        random.shuffle(ids)
        n_val = max(1, int(len(ids) * val_ratio))
        val_ids.update(ids[:n_val])
        train_ids.update(ids[n_val:])
    return train_ids, val_ids


# ═══════════════════════════════════════════════════════════════
# 格式转换
# ═══════════════════════════════════════════════════════════════

def to_alpaca(rows, with_input=True):
    out = []
    for r in rows:
        item = {
            'instruction': r['prompt'],
            'input': '',
            'output': r['answer'],
        }
        if with_input:
            item['instruction'] = r['prompt']
        out.append(item)
    return out


def to_sharegpt(rows):
    out = []
    for r in rows:
        out.append({
            'conversations': [
                {'from': 'human', 'value': r['prompt']},
                {'from': 'gpt', 'value': r['answer']},
            ],
            'system': SYSTEM_PROMPT,
            'meta': {'id': r['id'], 'task': r['task'],
                     'component': r['component'], 'dynasty': r['dynasty']},
        })
    return out


def to_openai(rows):
    return [
        {
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': r['prompt']},
                {'role': 'assistant', 'content': r['answer']},
            ],
            'meta': {'id': r['id'], 'task': r['task']},
        }
        for r in rows
    ]


def write_json(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def write_jsonl(path, rows):
    with open(path, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


# ═══════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)

    with open(DATA_FILE, encoding='utf-8') as f:
        samples = [json.loads(l) for l in f if l.strip()]

    print('=' * 64)
    print('  导出标准微调格式')
    print('=' * 64)
    print(f'\n源数据: {len(samples)} 条（{len(set(s["component"] for s in samples))} 组件）')

    # ── 划分（按 src_id，防泄露）──
    train_ids, val_ids = split_ids(samples)
    train_src = [s for s in samples if s['id'] in train_ids]
    val_src = [s for s in samples if s['id'] in val_ids]
    print(f'\n划分（按参数组合 id，防止同一组合的多种句式跨 split）:')
    print(f'  train: {len(train_src)} 组合  |  val: {len(val_src)} 组合')
    print(f'  校验无重叠: {not (train_ids & val_ids)}')

    # ── 展开任务 ──
    train_rows = expand(train_src, list(TASKS.keys()))
    val_rows = expand(val_src, list(TASKS.keys()))
    print(f'\n展开为训练样本:')
    print(f'  train: {len(train_rows)} 条  |  val: {len(val_rows)} 条')
    print(f'  任务分布(train): {dict(Counter(r["task"] for r in train_rows))}')

    # ── 输出各格式 ──
    outputs = []

    # ① Alpaca
    write_json(os.path.join(OUT_DIR, 'alpaca_train.json'), to_alpaca(train_rows))
    write_json(os.path.join(OUT_DIR, 'alpaca_val.json'), to_alpaca(val_rows))
    outputs.append(('Alpaca', 'alpaca_train.json / alpaca_val.json'))

    # ② ShareGPT
    write_json(os.path.join(OUT_DIR, 'sharegpt_train.json'), to_sharegpt(train_rows))
    write_json(os.path.join(OUT_DIR, 'sharegpt_val.json'), to_sharegpt(val_rows))
    outputs.append(('ShareGPT', 'sharegpt_train.json / sharegpt_val.json'))

    # ③ OpenAI（JSONL）
    write_jsonl(os.path.join(OUT_DIR, 'openai_train.jsonl'), to_openai(train_rows))
    write_jsonl(os.path.join(OUT_DIR, 'openai_val.jsonl'), to_openai(val_rows))
    outputs.append(('OpenAI', 'openai_train.jsonl / openai_val.jsonl'))

    # ④ D2GC 对齐（caption → design，单任务纯净版）
    d2gc_train = [{'caption': s['caption'], 'design': s['design'],
                   'text': s['instructions_cn'][0], 'id': s['id']}
                  for s in train_src]
    d2gc_val = [{'caption': s['caption'], 'design': s['design'],
                 'text': s['instructions_cn'][0], 'id': s['id']}
                for s in val_src]
    write_json(os.path.join(OUT_DIR, 'd2gc_caption2design_train.json'), d2gc_train)
    write_json(os.path.join(OUT_DIR, 'd2gc_caption2design_val.json'), d2gc_val)
    outputs.append(('D2GC 对齐', 'd2gc_caption2design_train.json / _val.json'))

    # ── 统计 ──
    stats = {
        'source_samples': len(samples),
        'train_combos': len(train_src), 'val_combos': len(val_src),
        'train_rows': len(train_rows), 'val_rows': len(val_rows),
        'tasks': dict(Counter(r['task'] for r in train_rows)),
        'by_component_train': dict(Counter(r['component'] for r in train_rows)),
        'by_dynasty_train': dict(Counter(r['dynasty'] for r in train_rows)),
        'val_ratio': VAL_RATIO, 'seed': SEED,
        'created_at': datetime.now().isoformat(timespec='seconds'),
    }
    write_json(os.path.join(OUT_DIR, 'stats.json'), stats)

    print('\n─── 输出文件 ───')
    for name, files in outputs:
        print(f'  {name:<12} {files}')
    print(f'\n输出目录: {OUT_DIR}')

    # ── 样例预览 ──
    print('\n' + '=' * 64)
    print('  样例预览（train 首条，各任务）')
    print('=' * 64)
    seen = set()
    for r in train_rows:
        if r['task'] in seen:
            continue
        seen.add(r['task'])
        print(f"\n【{r['task']}】id={r['id']}")
        print(f"  prompt: {r['prompt'][:150]}")
        print(f"  answer: {r['answer'][:150]}")
    print()
