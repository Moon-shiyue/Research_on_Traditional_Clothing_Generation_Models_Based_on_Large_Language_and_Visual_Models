"""
数据集校验 — 交付前/拿到数据后自查

**自动探测数据目录**，因此在以下两种结构下都能直接运行：
  ① 交付包结构    03_工具/  ← 脚本所在    ../01_数据/       ← 数据
  ② 开发结构      GarmentCode/traditional_ext/  ← 脚本    ../data/traditional_instruct/  ← 数据
也可用 --data-dir 手动指定。

检查项：
  ① 文件完整性   ② 源数据字段完整   ③ 训练/验证划分防泄露
  ④ 各格式字段正确   ⑤ 配置可执行性抽样（需 GarmentCode 环境）
  ⑥ 统计一致性

用法：
    python validate_dataset.py                      # 自动探测路径
    python validate_dataset.py --data-dir ../01_数据
    python validate_dataset.py --sample 0           # 跳过可执行性检查
    python validate_dataset.py --gc-dir /path/to/GarmentCode   # 指定 GarmentCode 目录
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

REQUIRED_SRC_FIELDS = ['id', 'component', 'component_class', 'dynasty',
                       'occasion', 'instructions_cn', 'caption', 'design',
                       'target_code', 'pattern', 'meta']
REQUIRED_FMT = {
    'alpaca': ['alpaca_train.json', 'alpaca_val.json'],
    'sharegpt': ['sharegpt_train.json', 'sharegpt_val.json'],
    'openai': ['openai_train.jsonl', 'openai_val.jsonl'],
    'd2gc': ['d2gc_caption2design_train.json', 'd2gc_caption2design_val.json'],
}

OK, FAIL, WARN = '[OK]', '[FAIL]', '[WARN]'
results = []


def check(name, ok, detail=''):
    results.append((ok, name, detail))
    print(f'  {(OK if ok else FAIL):<7} {name}' + (f'  — {detail}' if detail else ''))


def find_data_dir(explicit=None):
    """自动探测数据目录（含 traditional_design_dataset.jsonl 的目录）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    cwd = os.getcwd()
    cands = []
    if explicit:
        cands.append(explicit)
    cands += [
        os.path.join(here, '..', '01_数据'),                        # 交付包结构
        os.path.join(here, '..', 'data', 'traditional_instruct'),    # 开发结构
        os.path.join(here, '01_数据'),
        os.path.join(here, 'data', 'traditional_instruct'),
        os.path.join(cwd, '01_数据'),
        os.path.join(cwd, 'data', 'traditional_instruct'),
        here,
    ]
    for c in cands:
        c = os.path.normpath(c)
        if os.path.exists(os.path.join(c, 'traditional_design_dataset.jsonl')):
            return c
    return None


def find_gc_dir(explicit=None):
    """探测 GarmentCode 根目录（含 assets/bodies/mean_female.yaml 与 pygarment）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    cands = []
    if explicit:
        cands.append(explicit)
    cands += [
        os.path.join(here, '..'),          # 脚本在 GarmentCode/traditional_ext/
        os.path.join(here, '..', '..'),
        os.getcwd(),
    ]
    for c in cands:
        c = os.path.normpath(c)
        if (os.path.exists(os.path.join(c, 'assets', 'bodies', 'mean_female.yaml'))
                and os.path.isdir(os.path.join(c, 'pygarment'))):
            return c
    return None


def load_jsonl(p):
    with open(p, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def load_json(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default=None, help='数据目录（含传统设计数据集）')
    ap.add_argument('--gc-dir', default=None, help='GarmentCode 根目录')
    ap.add_argument('--sample', type=int, default=20,
                    help='可执行性抽样条数（0 = 跳过）')
    args = ap.parse_args()

    print('=' * 66)
    print('  传统服饰设计数据集 — 交付校验')
    print('=' * 66)

    # ── 定位数据目录 ──
    DATA_DIR = find_data_dir(args.data_dir)
    if not DATA_DIR:
        print(f'\n{FAIL} 未找到数据目录（缺 traditional_design_dataset.jsonl）')
        print('       请用 --data-dir 指定，例如：')
        print('       python validate_dataset.py --data-dir ../01_数据')
        return 1
    SRC_FILE = os.path.join(DATA_DIR, 'traditional_design_dataset.jsonl')
    FMT_DIR = os.path.join(DATA_DIR, 'training_formats')
    print(f'\n数据目录: {DATA_DIR}')

    # ── ① 文件完整性 ──
    print('\n[1] 文件完整性')
    check('源数据集存在', os.path.exists(SRC_FILE),
          f'{os.path.getsize(SRC_FILE) / 1024:.0f} KB' if os.path.exists(SRC_FILE) else '缺失')
    if not os.path.exists(FMT_DIR):
        check('training_formats/ 目录', False, '缺失')
    else:
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
    check(f'{len(REQUIRED_SRC_FIELDS)} 个必需字段齐全', not missing,
          f'缺失字段: {missing}' if missing else '全部样本字段完整')

    check('全部 verified', all(r.get('meta', {}).get('verified') for r in src))
    check('全部有 3 种句式',
          all(len(r.get('instructions_cn', [])) == 3 for r in src))
    check('全部有 caption',
          all(len(r.get('caption', [])) >= 3 for r in src))
    check('全部有纸样统计',
          all(r.get('pattern', {}).get('panels', 0) > 0 for r in src))
    n_comp = len(set(r['component'] for r in src))
    check('组件数 = 12', n_comp == 12, f'{n_comp} 个')

    # ── ③ 划分无泄露 ──
    print('\n[3] 训练/验证划分防泄露')
    train_ids = val_ids = None
    try:
        sg_train = load_json(os.path.join(FMT_DIR, 'sharegpt_train.json'))
        sg_val = load_json(os.path.join(FMT_DIR, 'sharegpt_val.json'))

        def src_of(row):
            return row['meta']['id'].split('__')[0]

        train_ids = {src_of(r) for r in sg_train}
        val_ids = {src_of(r) for r in sg_val}
        inter = train_ids & val_ids
        check('train/val 源 id 无交集', not inter,
              f'交集 {len(inter)} 个' if inter else
              f'train {len(train_ids)} 组合 / val {len(val_ids)} 组合')
        union = train_ids | val_ids
        all_ids = set(r['id'] for r in src)
        check('无样本遗漏', union == all_ids,
              f'并集 {len(union)} / 源 {len(all_ids)}')
    except Exception as exc:
        check('划分检查', False, f'{type(exc).__name__}: {exc}')

    # ── ④ 格式正确性 ──
    print('\n[4] 各格式字段正确性')
    for fmt, (fn, checker) in {
        'Alpaca': ('alpaca_train.json',
                   lambda r: {'instruction', 'input', 'output'} <= set(r)),
        'ShareGPT': ('sharegpt_train.json',
                     lambda r: ('conversations' in r and len(r['conversations']) == 2
                                and r['conversations'][0]['from'] == 'human'
                                and r['conversations'][1]['from'] == 'gpt'
                                and bool(r.get('system')))),
        'OpenAI': ('openai_train.jsonl',
                   lambda r: ('messages' in r and len(r['messages']) == 3
                              and [m['role'] for m in r['messages']]
                              == ['system', 'user', 'assistant'])),
        'D2GC': ('d2gc_caption2design_train.json',
                 lambda r: {'caption', 'design', 'text', 'id'} <= set(r)),
    }.items():
        try:
            p = os.path.join(FMT_DIR, fn)
            rows = load_jsonl(p) if fn.endswith('jsonl') else load_json(p)
            ok = all(checker(r) for r in rows[:200])
            check(f'{fmt} 字段', ok, f'{len(rows)} 条')
        except Exception as exc:
            check(f'{fmt} 字段', False, f'{type(exc).__name__}: {exc}')

    # ── ⑤ 可执行性抽样 ──
    if args.sample > 0:
        print(f'\n[5] 配置可执行性抽样（{args.sample} 条真实调用 assembly）')
        gc_dir = find_gc_dir(args.gc_dir)
        if not gc_dir:
            print(f'  {WARN}   未找到 GarmentCode 环境，跳过此项')
            print('         （需 pip install -e . 安装 GarmentCode 本体；'
                  '或用 --gc-dir 指定）')
            print('         提示：本项不影响数据可用性，仅验证"配置能真实生成纸样"')
        else:
            sys.path.insert(0, gc_dir)
            cwd0 = os.getcwd()
            os.chdir(gc_dir)          # 组件与 assets 用相对路径，需切到根目录
            try:
                import yaml
                from assets.bodies.body_params import BodyParameters
                from traditional_ext.build_dataset import build_component

                with open('./assets/design_params/traditional.yaml',
                          encoding='utf-8') as f:
                    base_design = yaml.safe_load(f)['design']
                body = BodyParameters('./assets/bodies/mean_female.yaml')

                random.seed(0)
                picks = random.sample(src, min(args.sample, len(src)))
                ok_n, fails = 0, []
                for r in picks:
                    try:
                        design = yaml.safe_load(yaml.safe_dump(base_design))
                        for node, params in r['design'].items():
                            if node in design:
                                for k, v in params.items():
                                    design[node][k] = v
                        comp = build_component(r['component'], body, design, {})
                        if comp.assembly().pattern['panels']:
                            ok_n += 1
                    except Exception as exc:
                        fails.append(f"{r['id']}:{type(exc).__name__}")
                check(f'抽样可执行 {ok_n}/{len(picks)}', ok_n == len(picks),
                      '; '.join(fails[:3]) if fails else '全部可执行')
            except Exception as exc:
                print(f'  {WARN}   环境不可用（{type(exc).__name__}: {exc}）')
                print('         请确认已将组件代码放入 GarmentCode/traditional_ext/')
            finally:
                os.chdir(cwd0)

    # ── ⑥ 统计一致性 ──
    print('\n[6] 统计一致性')
    stats_file = os.path.join(DATA_DIR, 'stats.json')
    if not os.path.exists(stats_file):
        stats_file = os.path.join(DATA_DIR, '源数据统计.json')
    try:
        st = load_json(stats_file)
        check('源样本数一致', st.get('total') == len(src),
              f"stats={st.get('total')} vs 实际={len(src)}")
        check('组件分布合计一致',
              sum(st.get('by_component', {}).values()) == len(src))
    except Exception as exc:
        check('统计一致性', False, f'{type(exc).__name__}: {exc}')

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
