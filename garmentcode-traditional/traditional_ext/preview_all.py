"""
一键生成全部 12 个组件的纸样预览

用途：答辩 / 演示 / 核对组件正确性。跑一次即得到 12 张统一风格的 1:1 纸样图。

用法：
    cd GarmentCode
    python traditional_ext/preview_all.py
    python traditional_ext/preview_all.py --out Logs/preview   # 指定输出目录
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

from assets.bodies.body_params import BodyParameters
from traditional_ext.params import caption2design
from traditional_ext.exporter import export_pattern

# 12 个组件：标签、模块、类名、示例 caption（形制上下文 + 典型参数）
COMPONENTS = [
    # ── 领型 ──
    ('交领', 'collars_extra', 'CrossCollar',
     ['traditional__dynasty__Ming', 'traditional__occasion__Changfu',
      'cross-collar__collar_depth__standard', 'cross-collar__cross_angle__standard',
      'cross-collar__overlap_amount__standard', 'cross-collar__border_width__standard']),
    ('圆领', 'collars_extra', 'RoundCollar',
     ['traditional__dynasty__Tang', 'traditional__occasion__Changfu',
      'round-collar__front_depth__standard', 'round-collar__back_depth__shallow',
      'round-collar__border_width__standard']),
    ('立领', 'collars', 'StandCollar',
     ['traditional__dynasty__Ming', 'traditional__occasion__Changfu',
      'stand-collar__collar_height__ming-high', 'stand-collar__collar_flare__slight']),
    ('对襟', 'collars_extra', 'DuijinCollar',
     ['traditional__dynasty__Song', 'traditional__occasion__Changfu',
      'duijin-collar__front_width__standard', 'duijin-collar__neck_depth__standard',
      'duijin-collar__placket_width__standard']),
    # ── 袖型 ──
    ('广袖', 'sleeves_extra', 'WideSleeve',
     ['traditional__dynasty__Tang', 'traditional__occasion__Lifu',
      'wide-sleeve__length__standard', 'wide-sleeve__cuff_width__standard',
      'wide-sleeve__root_width__standard']),
    ('窄袖', 'sleeves_extra', 'NarrowSleeve',
     ['traditional__dynasty__Song', 'traditional__occasion__Changfu',
      'narrow-sleeve__length__standard', 'narrow-sleeve__cuff_width__standard',
      'narrow-sleeve__root_width__standard']),
    ('琵琶袖', 'sleeves', 'PipaSleeve',
     ['traditional__dynasty__Ming', 'traditional__occasion__Changfu',
      'pipa-sleeve__length__standard', 'pipa-sleeve__cuff_width__narrow',
      'pipa-sleeve__root_width__standard', 'pipa-sleeve__bulge_width__standard']),
    # ── 下裳 ──
    ('襦裙', 'skirts_extra', 'RuqunSkirt',
     ['traditional__dynasty__Tang', 'traditional__occasion__Changfu',
      'ruqun-skirt__length__floor-length', 'ruqun-skirt__hem_ratio__full',
      'ruqun-skirt__waist_position__high']),
    ('马面裙', 'mamian_skirt', 'MamianSkirt',
     ['traditional__dynasty__Ming', 'traditional__occasion__Changfu',
      'mamian-skirt__length__floor-length', 'mamian-skirt__mamian_width__standard',
      'mamian-skirt__pleat_ruffle__medium', 'mamian-skirt__rise__mid']),
    # ── 配饰 ──
    ('云肩', 'accessories', 'CloudShoulder',
     ['traditional__dynasty__Ming', 'traditional__occasion__Lifu',
      'cloud-shoulder__layers__double', 'cloud-shoulder__petal_count__standard',
      'cloud-shoulder__tassel_length__short']),
    ('褙子', 'accessories', 'Beizi',
     ['traditional__dynasty__Song', 'traditional__occasion__Changfu',
      'beizi__length__midi', 'beizi__slit_height__standard',
      'beizi__sleeve_length__standard']),
    ('半臂', 'accessories', 'Banbi',
     ['traditional__dynasty__Tang', 'traditional__occasion__Changfu',
      'banbi__length__standard', 'banbi__sleeve_length__standard',
      'banbi__sleeve_width__standard']),
]

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join('Logs', 'preview'),
                    help='输出目录')
    args = ap.parse_args()

    with open('./assets/design_params/traditional.yaml', encoding='utf-8') as f:
        base_design = yaml.safe_load(f)['design']
    body = BodyParameters('./assets/bodies/mean_female.yaml')

    os.makedirs(args.out, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d')

    print('=' * 66)
    print('  生成全部 12 个组件的纸样预览')
    print('=' * 66)
    print(f'\n体型: 体重指数参照 mean_female | 输出: {args.out}\n')

    ok = 0
    total_panels = 0
    for label, mod, cls_name, caption in COMPONENTS:
        try:
            m = __import__(f'traditional_ext.{mod}', fromlist=[cls_name])
            cls = getattr(m, cls_name)

            design = yaml.safe_load(yaml.safe_dump(base_design))
            design, _ = caption2design(caption, design, verbose=False)
            comp = cls(body, design)
            pattern = comp.assembly()
            n = len(pattern.pattern['panels'])
            total_panels += n

            warns = getattr(comp, 'warnings', [])
            svg, png, st = export_pattern(
                pattern, args.out, tag=f'{label}',
                title=f'{label} — 传统服饰组件纸样  v{stamp}')

            flag = '⚠' if warns else '✓'
            print(f'  {flag} {label:<6} {comp.summary()}')
            print(f'           裁片 {n} 片 | 面积 {st["area_cm2"]:.0f} cm² | '
                  f'{os.path.basename(png)}')
            for w in warns:
                print(f'           形制警告: {w}')
            ok += 1
        except Exception as exc:
            print(f'  ✗ {label:<6} 失败: {type(exc).__name__}: {exc}')

    print('\n' + '=' * 66)
    print(f'  {ok}/{len(COMPONENTS)} 个组件预览生成成功，共 {total_panels} 片裁片')
    print(f'  输出目录: {os.path.abspath(args.out)}')
    print('=' * 66)
