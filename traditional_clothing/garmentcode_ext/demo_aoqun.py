"""
明代袄裙三件套演示 — 立领 + 琵琶袖 + 马面裙

验证迁移进度：3/12 个组件已用 pygarment 原生实现。
  ✅ MamianSkirt 马面裙（5 片：前/后马面 + 左右侧片 + 腰头）
  ✅ PipaSleeve  琵琶袖（2 片：左右）
  ✅ StandCollar 立领  （2 片：左右）

用法：
  cd GarmentCode
  python traditional_ext/demo_aoqun.py
"""
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from assets.bodies.body_params import BodyParameters
from pygarment.data_config import Properties
from traditional_ext.params import caption2design, design_summary
from traditional_ext.mamian_skirt import MamianSkirt
from traditional_ext.sleeves import PipaSleeve
from traditional_ext.collars import StandCollar
from traditional_ext.export import save_all, save_flat_preview
from traditional_ext.exporter import export_pattern


PARAMS_YAML = './assets/design_params/traditional.yaml'


def load_design():
    with open(PARAMS_YAML, encoding='utf-8') as f:
        return yaml.safe_load(f)['design']


def panel_stats(pattern):
    """返回 {裁片名: (宽, 高, 面积)}"""
    out = {}
    for name, p in pattern.pattern['panels'].items():
        v = p['vertices']
        w = max(pt[0] for pt in v) - min(pt[0] for pt in v)
        h = max(pt[1] for pt in v) - min(pt[1] for pt in v)
        area = 0.0
        for i in range(len(v)):
            j = (i + 1) % len(v)
            area += v[i][0] * v[j][1] - v[j][0] * v[i][1]
        out[name] = (w, h, abs(area) / 2)
    return out


if __name__ == '__main__':
    print('=' * 64)
    print('  明代袄裙三件套 — 立领 + 琵琶袖 + 马面裙')
    print('=' * 64)

    body = BodyParameters('./assets/bodies/mean_female.yaml')
    print(f'\n体型: 颈宽 {body["neck_w"]:.1f}cm | 臂长 {body["arm_length"]:.1f}cm | '
          f'腰围 {body["waist"]:.1f}cm | 腿长 {body["_leg_length"]:.1f}cm')

    # ── 明代袄裙 caption（模拟 LMM 输出）──
    caption = [
        'traditional__dynasty__Ming',
        'traditional__collar__Liling',        # 立领
        'traditional__sleeve__Pipaxiu',       # 琵琶袖（明代独有）
        'traditional__occasion__Changfu',     # 常服
        'stand-collar__collar_height__ming-high',
        'stand-collar__collar_flare__slight',
        'pipa-sleeve__length__standard',
        'pipa-sleeve__cuff_width__narrow',
        'pipa-sleeve__root_width__standard',
        'pipa-sleeve__bulge_width__standard',
        'mamian-skirt__length__floor-length',
        'mamian-skirt__mamian_width__standard',
        'mamian-skirt__pleat_ruffle__medium',
    ]

    print('\n【caption 应用】')
    design = load_design()
    design, _ = caption2design(caption, design, verbose=True)

    print('\n【传统服饰参数】')
    print(design_summary(design, keys=('traditional', 'stand-collar',
                                       'pipa-sleeve', 'mamian-skirt')))

    out_root = './Logs/traditional_demo'
    os.makedirs(out_root, exist_ok=True)
    stamp = datetime.now().strftime('%H%M%S')

    # ── 三个组件 ──
    parts = [
        ('立领', StandCollar(body, design)),
        ('琵琶袖', PipaSleeve(body, design)),
        ('马面裙', MamianSkirt(body, design)),
    ]

    total_panels = 0
    grand_area = 0.0
    print()
    for label, comp in parts:
        print('─' * 64)
        print(f'【{label}】{comp.summary()}')
        if getattr(comp, 'warnings', None):
            for w in comp.warnings:
                print(f'  ⚠ 形制警告: {w}')

        pattern = comp.assembly()
        stats = panel_stats(pattern)
        n_stitch = len(pattern.pattern['stitches'])
        print(f'  裁片 {len(stats)} 片 / 缝合 {n_stitch} 条')
        for name, (w, h, a) in stats.items():
            print(f'     {name:<24} {w:6.1f} × {h:6.1f} cm   面积 {a:7.1f} cm²')
        area = sum(a for _, _, a in stats.values())
        total_panels += len(stats)
        grand_area += area
        print(f'  小计面积: {area:.0f} cm²')

        res = save_all(pattern, out_root, tag=f'{label}_{stamp}', with_printable=True)
        print(f'  ✅ 输出目录: {res["log_dir"]}')

        # 专业排料图（中文标签 + 布纹线 + 尺寸 + 紧凑布局）
        svg_p, png_p, st = export_pattern(
            pattern, res['log_dir'], tag=f'{label}_{stamp}',
            title=f'{label} — 明代袄裙三件套组件纸样')
        print(f'  📐 专业纸样图: {os.path.basename(png_p)}'
              f'  [{st["panels"]} 片 / {st["area_cm2"]:.0f} cm²]')

    print('\n' + '=' * 64)
    print(f'  明代袄裙三件套: 共 {total_panels} 片裁片, 面料面积 {grand_area:.0f} cm² '
          f'({grand_area / 10000:.3f} m²)')
    print(f'  输出目录: {out_root}')
    print('=' * 64)
