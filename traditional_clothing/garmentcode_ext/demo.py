"""
传统服饰生成链路演示 — caption → 参数树 → 纸样

验证路线 A 的完整可行性：
  LMM 输出 caption（此处手工模拟）
      ↓  caption2design()
  参数树 traditional.yaml
      ↓  MamianSkirt(body, design)
  pygarment 组件 → assembly() → specification.json

用法：
  cd GarmentCode
  python traditional_ext/demo.py
"""
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml

# 让脚本可从 GarmentCode 根目录运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from assets.bodies.body_params import BodyParameters
from pygarment.data_config import Properties
from traditional_ext.params import caption2design, design_summary
from traditional_ext.mamian_skirt import MamianSkirt


PARAMS_YAML = './assets/design_params/traditional.yaml'


def load_design():
    with open(PARAMS_YAML, encoding='utf-8') as f:
        return yaml.safe_load(f)['design']


def run_case(body, caption, label, out_root):
    """应用一组 caption 并生成纸样，返回统计信息。"""
    print(f'\n{"─" * 62}')
    print(f'【{label}】')
    print(f'  caption: {caption}')

    design = load_design()
    design, _ = caption2design(caption, design, verbose=True)

    print('\n  传统服饰参数:')
    print(design_summary(design))

    skirt = MamianSkirt(body, design)
    print(f'\n  {skirt.summary()}')

    if skirt.warnings:
        for w in skirt.warnings:
            print(f'  ⚠ 形制警告: {w}')

    pattern = skirt.assembly()
    panels = pattern.pattern['panels']

    stats = {}
    for name, p in panels.items():
        v = p['vertices']
        w = max(pt[0] for pt in v) - min(pt[0] for pt in v)
        h = max(pt[1] for pt in v) - min(pt[1] for pt in v)
        stats[name] = (w, h)

    print(f'\n  裁片 ({len(panels)} 片) / 缝合 ({len(pattern.pattern["stitches"])} 条):')
    for name, (w, h) in stats.items():
        print(f'     {name:<22} {w:6.1f} × {h:6.1f} cm')

    total = sum(w * h for w, h in stats.values())
    print(f'  裁片包围盒总面积: {total:.0f} cm² ({total / 10000:.3f} m²)')

    folder = pattern.serialize(
        Path(out_root),
        tag=f'_{label}_' + datetime.now().strftime('%H%M%S'),
        to_subfolder=True, with_3d=False, with_text=False,
        view_ids=False, with_printable=False,
    )
    print(f'  ✅ 已保存: {folder}')
    return stats


if __name__ == '__main__':
    print('=' * 62)
    print('  传统服饰生成链路演示（caption → 参数 → 纸样）')
    print('=' * 62)

    body = BodyParameters('./assets/bodies/mean_female.yaml')
    print(f'\n体型: 腰围 {body["waist"]:.1f}cm | 臀线 {body["hips_line"]:.1f}cm | '
          f'腿长 {body["_leg_length"]:.1f}cm')

    out_root = './Logs/traditional_demo'
    os.makedirs(out_root, exist_ok=True)

    # ── 案例 1：明代标准马面裙 ──
    case1 = [
        'traditional__dynasty__Ming',
        'traditional__collar__Liling',        # 立领
        'traditional__sleeve__Pipaxiu',       # 琵琶袖（明代独有）
        'traditional__occasion__Changfu',     # 常服
        'mamian-skirt__length__floor-length', # 及踝长裙
        'mamian-skirt__mamian_width__standard',  # 28cm
        'mamian-skirt__pleat_ruffle__medium',    # 褶量比 1.8
        'mamian-skirt__rise__mid',
    ]
    run_case(body, case1, 'ming_standard', out_root)

    # ── 案例 2：改为宽马面 + 密褶 ──
    case2 = [
        'traditional__dynasty__Ming',
        'mamian-skirt__length__midi',            # 中长
        'mamian-skirt__mamian_width__wide',      # 35cm
        'mamian-skirt__pleat_ruffle__rich',      # 褶量比 2.4
        'mamian-skirt__rise__high',
    ]
    run_case(body, case2, 'ming_wide_rich', out_root)

    # ── 案例 3：窄马面 + 疏褶（对比）──
    case3 = [
        'mamian-skirt__length__knee-length',
        'mamian-skirt__mamian_width__narrow',    # 20cm
        'mamian-skirt__pleat_ruffle__light',     # 褶量比 1.4
    ]
    run_case(body, case3, 'ming_narrow_light', out_root)

    print('\n' + '=' * 62)
    print('  ✅ 演示完成：caption 可有效控制传统服饰参数与纸样')
    print(f'  输出目录: {out_root}')
    print('=' * 62)
