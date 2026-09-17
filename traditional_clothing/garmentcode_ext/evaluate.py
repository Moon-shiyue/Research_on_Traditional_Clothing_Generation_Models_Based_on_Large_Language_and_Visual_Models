"""
微调效果评测 — 输入模型预测，输出多维评测报告

给负责微调的同学使用：训练完后跑一遍，就知道模型在传统服饰领域"专业"到什么程度。

评测维度（5 项）：
  ① json_valid   预测是否为合法 JSON
  ② parseable    能否解析出 design 配置（含组件节点）
  ③ executable   配置能否真实生成纸样（调用 assembly()，需 GarmentCode 环境）
  ④ compliant    配置是否通过形制校验（组件内置 warnings）
  ⑤ accuracy     与标注答案的参数匹配度（字段级 / 完全匹配）

用法：
    python traditional_ext/evaluate.py \
        --predictions preds.jsonl \
        --gt data/traditional_instruct/training_formats/d2gc_caption2design_val.json \
        --report report.json

预测文件格式（JSONL，每行一条）：
    {"id": "mamian-skirt_ming_0001", "prediction": "{\"mamian-skirt\": {...}}"}
    # id 需与 GT 的 id 对应；prediction 为模型输出的文本

可选：--no-exec 跳过可执行性检查（无 GarmentCode 环境时使用）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict


def find_gc_dir(explicit=None):
    """探测 GarmentCode 根目录（含 assets/bodies 与 pygarment）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    cands = ([explicit] if explicit else []) + [
        os.path.join(here, '..'),           # 脚本在 GarmentCode/traditional_ext/
        os.path.join(here, '..', '..'),
        os.getcwd(),
    ]
    for c in cands:
        if not c:
            continue
        c = os.path.normpath(c)
        if (os.path.exists(os.path.join(c, 'assets', 'bodies', 'mean_female.yaml'))
                and os.path.isdir(os.path.join(c, 'pygarment'))):
            return c
    return None


# 组件 → (模块, 类名)
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


def load_jsonl(p):
    with open(p, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def load_json(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def extract_json(text: str):
    """从模型输出里抽取第一个 JSON 对象（容忍 ```json 代码块与前后文）。"""
    if not isinstance(text, str):
        return None
    t = text.strip()
    t = re.sub(r'^```(?:json)?\s*', '', t)
    t = re.sub(r'\s*```$', '', t)
    try:
        return json.loads(t)
    except Exception:
        pass
    # 退而求其次：找第一个 {...} 平衡片段
    start = t.find('{')
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(t)):
        if t[i] == '{':
            depth += 1
        elif t[i] == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[start:i + 1])
                except Exception:
                    return None
    return None


def compare_design(pred: dict, gt: dict):
    """对比预测配置与标注配置。

    Returns: (n_correct, n_total, exact_bool)
    """
    total = correct = 0
    for node, params in gt.items():
        if not isinstance(params, dict):
            continue
        pred_node = pred.get(node, {}) if isinstance(pred, dict) else {}
        for k, v in params.items():
            if not isinstance(v, dict) or 'v' not in v:
                continue
            total += 1
            pv = pred_node.get(k, {}) if isinstance(pred_node, dict) else {}
            if isinstance(pv, dict) and 'v' in pv:
                a, b = pv['v'], v['v']
                if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                    if abs(float(a) - float(b)) < 1e-6:
                        correct += 1
                elif a == b:
                    correct += 1
    return correct, total, (total > 0 and correct == total)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--predictions', required=True, help='模型预测 JSONL')
    ap.add_argument('--gt', required=True, help='标注答案 JSON（d2gc_*_val.json）')
    ap.add_argument('--report', default='', help='报告输出路径（JSON）')
    ap.add_argument('--no-exec', action='store_true', help='跳过可执行性检查')
    ap.add_argument('--gc-dir', default=None, help='GarmentCode 根目录（自动探测）')
    args = ap.parse_args()

    # 路径解析（支持相对当前工作目录）
    pred_path = os.path.abspath(args.predictions)
    gt_path = os.path.abspath(args.gt)
    for label, p in (('predictions', pred_path), ('gt', gt_path)):
        if not os.path.exists(p):
            print(f'❌ {label} 文件不存在: {p}')
            return 1

    preds_rows = load_jsonl(pred_path)
    preds = {}
    for r in preds_rows:
        key = r.get('id') or r.get('src_id')
        if key:
            preds[key] = r.get('prediction', r.get('output', ''))
    gt_rows = load_json(gt_path)
    gt = {r['id']: r for r in gt_rows}

    print('=' * 66)
    print('  传统服饰设计微调 — 效果评测')
    print('=' * 66)
    print(f'\n预测: {pred_path}  ({len(preds)} 条)')
    print(f'标注: {gt_path}  ({len(gt)} 条)')

    # 环境准备（可执行性检查需要 GarmentCode）
    body = base_design = None
    cwd0 = os.getcwd()
    if not args.no_exec:
        gc_dir = find_gc_dir(args.gc_dir)
        if not gc_dir:
            print('\n⚠ 未找到 GarmentCode 环境，跳过可执行性检查'
                  '（用 --gc-dir 指定，或确认已 pip install -e .）')
            args.no_exec = True
        else:
            sys.path.insert(0, gc_dir)
            os.chdir(gc_dir)
            try:
                import yaml
                from assets.bodies.body_params import BodyParameters
                from traditional_ext.build_dataset import build_component
                with open('./assets/design_params/traditional.yaml',
                          encoding='utf-8') as f:
                    base_design = yaml.safe_load(f)['design']
                body = BodyParameters('./assets/bodies/mean_female.yaml')
                print(f'\nGarmentCode 环境: {gc_dir}')
            except Exception as exc:
                print(f'\n⚠ GarmentCode 环境不可用（{type(exc).__name__}: {exc}），'
                      f'跳过可执行性检查')
                os.chdir(cwd0)
                args.no_exec = True

    stats = Counter()
    field_acc = []
    by_comp = defaultdict(lambda: Counter())
    by_comp_acc = defaultdict(list)
    details = []
    missing = 0

    for sid, grow in gt.items():
        comp = None
        for node in grow['design']:
            if node in MODULE_MAP:
                comp = node
                break
        rec = {'id': sid, 'component': comp}
        stats['total'] += 1
        if comp:
            by_comp[comp]['total'] += 1

        if sid not in preds:
            missing += 1
            rec['status'] = 'missing'
            details.append(rec)
            continue

        raw = preds[sid]
        # ① JSON 合法
        pred = extract_json(raw)
        if pred is None:
            rec['status'] = 'invalid_json'
            stats['json_fail'] += 1
            if comp:
                by_comp[comp]['json_fail'] += 1
            details.append(rec)
            continue
        stats['json_ok'] += 1
        if comp:
            by_comp[comp]['json_ok'] += 1

        # ② 解析出组件节点
        if not (comp and comp in pred):
            rec['status'] = 'no_component_node'
            stats['node_fail'] += 1
            details.append(rec)
            continue
        stats['node_ok'] += 1

        # ③ 可执行
        if not args.no_exec:
            try:
                import yaml as _y
                design = _y.safe_load(_y.safe_dump(base_design))
                for node, params in pred.items():
                    if node in design and isinstance(params, dict):
                        for k, v in params.items():
                            if isinstance(v, dict) and 'v' in v:
                                design.setdefault(node, {})
                                design[node][k] = {'v': v['v']}
                obj = build_component(comp, body, design, {})
                pattern = obj.assembly()
                exec_ok = bool(pattern.pattern['panels'])
                warns = getattr(obj, 'warnings', [])
            except Exception as exc:
                exec_ok, warns = False, [f'{type(exc).__name__}']
            if exec_ok:
                stats['exec_ok'] += 1
                by_comp[comp]['exec_ok'] += 1
            else:
                rec['status'] = 'not_executable'
            if exec_ok and not warns:
                stats['compliant'] += 1
            elif exec_ok:
                rec['warnings'] = warns[:2]

        # ④⑤ 参数准确率
        correct, total, exact = compare_design(pred, grow['design'])
        if total:
            field_acc.append(correct / total)
            by_comp_acc[comp].append(correct / total)
        if exact:
            stats['exact'] += 1
            by_comp[comp]['exact'] += 1

        rec.update({'field_correct': correct, 'field_total': total,
                    'field_acc': round(correct / total, 4) if total else 0.0,
                    'exact': exact, 'status': rec.get('status', 'ok')})
        details.append(rec)

    # ── 报告 ──
    n = stats['total']
    def pct(x):
        return f'{x / n * 100:.1f}%' if n else 'n/a'

    print('\n' + '─' * 66)
    print(f'  样本数: {n}' + (f'（{missing} 条无预测）' if missing else ''))
    print('─' * 66)
    print(f'  ① JSON 合法率      {stats["json_ok"]:>5} / {n}   {pct(stats["json_ok"])}')
    print(f'  ② 组件节点命中率    {stats["node_ok"]:>5} / {n}   {pct(stats["node_ok"])}')
    if not args.no_exec:
        print(f'  ③ 可执行率         {stats["exec_ok"]:>5} / {n}   {pct(stats["exec_ok"])}')
        print(f'  ④ 形制合规率       {stats["compliant"]:>5} / {n}   {pct(stats["compliant"])}')
    print(f'  ⑤ 完全匹配率       {stats["exact"]:>5} / {n}   {pct(stats["exact"])}')
    if field_acc:
        print(f'     参数字段准确率   {sum(field_acc) / len(field_acc) * 100:.1f}%  '
              f'（平均 {sum(field_acc) / len(field_acc):.3f}）')

    if by_comp:
        print('\n  分组件（参数字段准确率 / 完全匹配率）:')
        for c in sorted(by_comp, key=lambda x: -by_comp[x]['total']):
            cs = by_comp[c]
            acc = (sum(by_comp_acc[c]) / len(by_comp_acc[c]) * 100
                   if by_comp_acc[c] else 0.0)
            print(f'     {c:<20} n={cs["total"]:<5} acc={acc:5.1f}%  '
                  f'exact={cs["exact"]}/{cs["total"]}')

    report = {
        'predictions': pred_path, 'gt': gt_path,
        'total': n, 'missing_predictions': missing,
        'json_valid_rate': stats['json_ok'] / n if n else 0,
        'component_node_rate': stats['node_ok'] / n if n else 0,
        'executable_rate': (stats['exec_ok'] / n if n and not args.no_exec else None),
        'compliant_rate': (stats['compliant'] / n if n and not args.no_exec else None),
        'exact_match_rate': stats['exact'] / n if n else 0,
        'field_accuracy': sum(field_acc) / len(field_acc) if field_acc else 0,
        'by_component': {c: dict(v) for c, v in by_comp.items()},
        'details': details,
    }
    os.chdir(cwd0)          # 恢复工作目录（前面为加载 assets 切到过 GarmentCode）
    if args.report:
        with open(os.path.abspath(args.report), 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f'\n  详细报告: {os.path.abspath(args.report)}')
    print('=' * 66)
    return 0


if __name__ == '__main__':
    sys.exit(main())
