"""
数据集校验 — 交付前/拿到数据后自查

检查项：
  ① 文件完整性（各格式文件存在、非空）
  ② 源数据集字段完整性（11 个必需字段）
  ③ 训练/验证划分无泄露（id 集合无交集）
  ④ 格式正确性（Alpaca / ShareGPT / OpenAI / D2GC 字段齐全）
  ⑤ 配置可执行性抽样（随机抽 N 条，真实调用组件 assembly）
  ⑥ 统计一致性（与 stats.json 对齐）

用法（在 GarmentCode 目录下）：
    python traditional_ext/validate_dataset.py
    python traditional_ext/validate_dataset.py --sample 50     # 抽样可执行性检查条数
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_DIR = os.path.join('data', 'traditional_instruct')
SRC_FILE = os.path.join(DATA_DIR, 'traditional_design_dataset.jsonl')
FMT_DIR = os.path.join(DATA_DIR, 'training_formats')

REQUIRED_SRC_FIELDS = ['id', 'component', 'component_class', 'dynasty',
                       'occasion', 'instructions_cn', 'caption', 'design',
                       'target_code', 'pattern', 'meta']
REQUIRED_FMT = {
    'alpaca': ['alpaca_train.json', 'alpaca_val.json'],
    'sharegpt': ['sharegpt_train.json', 'sharegpt_val.json'],
    'openai': ['openai_train.jsonl', 'openai_val.jsonl'],
    'd2gc': ['d2gc_caption2design_train.json', 'd2gc_caption2design_val.json'],
}

OK = '[OK]'
FAIL = '[FAIL]'
WARN = '[WARN]'
results = []


def check(name, ok, detail=''):
    tag = OK if ok else FAIL
    results.append((ok, name, detail))
    print(f'  {tag:<7} {name}' + (f'  — {detail}' if detail else ''))


def load_jsonl(p):
    with open(p, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def load_json(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample', type=int, default=20,
                    help='可执行性抽样检查条数（0 = 跳过）')
    args = ap.parse_args()

    print('=' * 66)
    print('  传统服饰设计数据集 — 交付校验')
    print('=' * 66)

    # ── ① 文件完整性 ──
    print('\n[1] 文件完整性')
    check('源数据集存在', os.path.exists(SRC_FILE),
          f'{os.path.getsize(SRC_FILE) / 1024:.0f} KB' if os.path.exists(SRC_FILE) else '缺失')
    for fmt, files in REQUIRED_FMT.items():
        for fn in files:
            p = os.path.join(FMT_DIR, fn)
            exists = os.path.exists(p) and os.path.getsize(p) > 0
            check(f'{fmt}: {fn}', exists,
                  f'{os.path.getsize(p) / 1024 / 1024:.2f} MB' if exists else '缺失/空')

    if not os.path.exists(SRC_FILE):
        print('\n源数据集缺失，终止')
        return 1

    # ── ② 源数据字段 ──
    print('\n[2] 源数据集字段完整性')
    src = load_jsonl(SRC_FILE)
    check('样本数 > 0', len(src) > 0, f'{len(src)} 条')

    missing = {}
    for r in src:
        for f in REQUIRED_SRC_FIELDS:
            if f not in r:
                missing[f] = missing.get(f, 0) + 1
    check('11 个必需字段齐全', not missing,
          f'缺失字段: {missing}' if missing else '全部样本字段完整')

    check('全部 verified', all(r.get('meta', {}).get('verified') for r in src))
    check('全部有 3 种句式',
          all(len(r.get('instructions_cn', [])) == 3 for r in src))
    check('全部有 caption',
          all(len(r.get('caption', [])) >= 3 for r in src))
    check('全部有纸样统计',
          all(r.get('pattern', {}).get('panels', 0) > 0 for r in src))
    check('组件数 = 12', len(set(r['component'] for r in src)) == 12,
          f"{len(set(r['component'] for r in src))} 个")

    # ── ③ 划分无泄露 ──
    print('\n[3] 训练/验证划分防泄露')
    try:
        sg_train = load_json(os.path.join(FMT_DIR, 'sharegpt_train.json'))
        sg_val = load_json(os.path.join(FMT_DIR, 'sharegpt_val.json'))
        # 从 meta.id 反推源 id（去掉 __task 后缀）
        def src_of(row):
            return row['meta']['id'].split('__')[0]
        train_ids = {src_of(r) for r in sg_train}
        val_ids = {src_of(r) for r in sg_val}
        inter = train_ids & val_ids
        check('train/val 源 id 无交集', not inter,
              f'交集 {len(inter)} 个' if inter else
              f'train {len(train_ids)} 组合 / val {len(val_ids)} 组合')
        check('无样本遗漏',
              len(train_ids | val_ids) == len(set(r["id"] for r in src)),
              f'并集 {len(train_ids | val_ids)} / 源 {len(set(r["id"] for r in src))}')
    except Exception as exc:
        check('划分检查', False, f'{type(exc).__name__}: {exc}')

    # ── ④ 格式正确性 ──
    print('\n[4] 各格式字段正确性')
    try:
        a = load_json(os.path.join(FMT_DIR, 'alpaca_train.json'))
        check('Alpaca 字段', all(set(['instruction', 'input', 'output']) <= set(r) for r in a[:200]),
              f'{len(a)} 条')
    except Exception as exc:
        check('Alpaca 字段', False, str(exc))

    try:
        s = load_json(os.path.join(FMT_DIR, 'sharegpt_train.json'))
        ok = all(('conversations' in r and len(r['conversations']) == 2
                  and r['conversations'][0]['from'] == 'human'
                  and r['conversations'][1]['from'] == 'gpt'
                  and r.get('system')) for r in s[:200])
        check('ShareGPT 字段', ok, f'{len(s)} 条')
    except Exception as exc:
        check('ShareGPT 字段', False, str(exc))

    try:
        o = load_jsonl(os.path.join(FMT_DIR, 'openai_train.jsonl'))
        ok = all(('messages' in r and len(r['messages']) == 3
                  and [m['role'] for m in r['messages']] == ['system', 'user', 'assistant'])
                 for r in o[:200])
        check('OpenAI 字段', ok, f'{len(o)} 条')
    except Exception as exc:
        check('OpenAI 字段', False, str(exc))

    try:
        d = load_json(os.path.join(FMT_DIR, 'd2gc_caption2design_train.json'))
        check('D2GC 字段', all(set(['caption', 'design', 'text', 'id']) <= set(r) for r in d[:200]),
              f'{len(d)} 条')
    except Exception as exc:
        check('D2GC 字段', False, str(exc))

    # ── ⑤ 可执行性抽样 ──
    if args.sample > 0:
        print(f'\n[5] 配置可执行性抽样（{args.sample} 条真实调用 assembly）')
        try:
            from assets.bodies.body_params import BodyParameters
            from traditional_ext.build_dataset import build_component
            import yaml

            with open('./assets/design_params/traditional.yaml', encoding='utf-8') as f:
                base_design = yaml.safe_load(f)['design']
            body = BodyParameters('./assets/bodies/mean_female.yaml')

            random.seed(0)
            picks = random.sample(src, min(args.sample, len(src)))
            ok_n, fail_detail = 0, []
            for r in picks:
                try:
                    design = yaml.safe_load(yaml.safe_dump(base_design))
                    # 用样本自带 design 覆盖（构造完整 design 树）
                    for node, params in r['design'].items():
                        if node in design:
                            for k, v in params.items():
                                design[node][k] = v
                    comp = build_component(r['component'], body, design, {})
                    pattern = comp.assembly()
                    if pattern.pattern['panels']:
                        ok_n += 1
                except Exception as exc:
                    fail_detail.append(f"{r['id']}: {type(exc).__name__}")
            check(f'抽样可执行 {ok_n}/{len(picks)}', ok_n == len(picks),
                  '; '.join(fail_detail[:3]) if fail_detail else '全部可执行')
        except Exception as exc:
            check('可执行性抽样', False, f'环境不可用: {type(exc).__name__}: {exc}')
            print('       （需要 GarmentCode 环境：pip install -e . 后重试）')

    # ── ⑥ 统计一致性 ──
    print('\n[6] 统计一致性')
    try:
        st = load_json(os.path.join(DATA_DIR, 'stats.json'))
        check('源样本数一致', st['total'] == len(src),
              f"stats={st['total']} vs 实际={len(src)}")
        check('组件分布一致',
              sum(st['by_component'].values()) == len(src))
    except Exception as exc:
        check('统计一致性', False, str(exc))

    # ── 汇总 ──
    n_fail = sum(1 for ok, _, _ in results if not ok)
    print('\n' + '=' * 66)
    if n_fail == 0:
        print(f'  ✅ 全部通过（{len(results)} 项检查）— 数据集可交付')
    else:
        print(f'  ❌ {n_fail}/{len(results)} 项失败')
        for ok, name, detail in results:
            if not ok:
                print(f'     - {name}: {detail}')
    print('=' * 66)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
