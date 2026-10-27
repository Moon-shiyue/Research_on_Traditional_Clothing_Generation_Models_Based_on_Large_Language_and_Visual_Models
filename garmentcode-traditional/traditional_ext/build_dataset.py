"""
构建传统服饰指令数据集 — 按 Design2GarmentCode 的「Program Learning」方法

论文方法（arXiv:2412.08603, §3.2.1）：
    D = {( Γ_cmt(f_i), f_i ) | f_i ∈ ℱ }
  即用已有程序代码 + 配套的自然语言制版说明构成配对数据，教模型 DSL 语法。

本脚本的对应实现（传统服饰领域适配）：
    ① 枚举传统服饰组件的合法参数组合（形制约束过滤）
    ② 对每种组合【真实调用组件生成纸样】—— 保证每条样本都可由 GarmentCode 执行
    ③ 生成三类监督目标：
         - instruction  自然语言制版说明（多句式变体，模拟 Γ_cmt）
         - caption      D2GC 兼容的参数路径标签（caption2yaml 可解析）
         - design       设计配置树（可直接喂给组件）
    ④ 用形制规则过滤非法组合（例如明代立领超高、琵琶袖尺寸倒置）
    ⑤ 输出 JSONL + 统计报告

用法：
    cd GarmentCode
    python traditional_ext/build_dataset.py
输出：
    data/traditional_instruct/traditional_design_dataset.jsonl
    data/traditional_instruct/README.md
    data/traditional_instruct/stats.json
"""
from __future__ import annotations

import itertools
import json
import os
import random
import sys
from collections import Counter
from datetime import datetime

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from assets.bodies.body_params import BodyParameters
from traditional_ext.mamian_skirt import MamianSkirt
from traditional_ext.sleeves import PipaSleeve
from traditional_ext.collars import StandCollar
from traditional_ext.params import caption2design

PARAMS_YAML = './assets/design_params/traditional.yaml'
OUT_DIR = os.path.join('data', 'traditional_instruct')
RANDOM_SEED = 42


# ═══════════════════════════════════════════════════════════════
# 1. 参数空间（每个组件的可枚举参数 + 候选标签）
# ═══════════════════════════════════════════════════════════════

SPACES = {
    'mamian-skirt': {
        'length':          ['knee-length', 'midi', 'floor-length'],
        'mamian_width':    ['narrow', 'standard', 'wide'],
        'pleat_ruffle':    ['light', 'medium', 'rich'],
        'rise':            ['mid', 'high'],
    },
    'pipa-sleeve': {
        'length':          ['short', 'standard', 'long'],
        'cuff_width':      ['narrow', 'standard', 'wide'],
        'root_width':      ['narrow', 'standard', 'wide'],
        'bulge_width':     ['slight', 'standard', 'rich'],
    },
    'stand-collar': {
        'collar_height':   ['ming-low', 'ming-high', 'qing'],
        'collar_flare':    ['straight', 'slight', 'flared'],
        'top_curve':       ['flat', 'slight', 'curved'],
    },
    # ── 批次 2：领型 ──
    'cross-collar': {
        'collar_depth':    ['shallow', 'standard', 'deep'],
        'cross_angle':     ['narrow', 'standard', 'wide'],
        'overlap_amount':  ['slight', 'standard', 'deep'],
        'border_width':    ['narrow', 'standard', 'wide'],
    },
    'round-collar': {
        'front_depth':     ['shallow', 'standard', 'deep'],
        'back_depth':      ['shallow', 'standard', 'deep'],
        'border_width':    ['narrow', 'standard', 'wide'],
    },
    'duijin-collar': {
        'front_width':     ['narrow', 'standard', 'wide'],
        'neck_depth':      ['shallow', 'standard', 'deep'],
        'placket_width':   ['narrow', 'standard', 'wide'],
    },
    # ── 批次 3：袖型 ──
    'wide-sleeve': {
        'length':          ['short', 'standard', 'long'],
        'cuff_width':      ['moderate', 'standard', 'grand'],
        'root_width':      ['narrow', 'standard', 'wide'],
    },
    'narrow-sleeve': {
        'length':          ['short', 'standard', 'long'],
        'cuff_width':      ['narrow', 'standard', 'wide'],
        'root_width':      ['narrow', 'standard', 'wide'],
        'elbow_width':     ['slight', 'standard', 'loose'],
    },
    # ── 批次 4：下裳 ──
    'ruqun-skirt': {
        'length':          ['knee-length', 'midi', 'floor-length'],
        'hem_ratio':       ['moderate', 'full', 'grand'],
        'waist_position':  ['mid', 'high', 'chest'],
    },
    # ── 批次 5：配饰 ──
    'cloud-shoulder': {
        'layers':          ['single', 'double', 'triple'],
        'petal_count':     ['sparse', 'standard', 'dense'],
        'tassel_length':   ['none', 'short', 'long'],
    },
    'beizi': {
        'length':          ['knee', 'midi', 'ankle'],
        'slit_height':     ['low', 'standard', 'high'],
        'sleeve_length':   ['short', 'standard', 'long'],
    },
    'banbi': {
        'length':          ['short', 'standard', 'long'],
        'sleeve_length':   ['short', 'standard', 'long'],
        'sleeve_width':    ['narrow', 'standard', 'wide'],
    },
}

# 每个组件可搭配的形制上下文（朝代 / 场合）
CONTEXT = {
    'mamian-skirt': {
        'dynasty':  ['Ming', 'Qing'],       # 马面裙为明/清制
        'occasion': ['Changfu', 'Lifu'],
    },
    'pipa-sleeve': {
        'dynasty':  ['Ming'],               # 琵琶袖仅明代
        'occasion': ['Changfu', 'Lifu'],
    },
    'stand-collar': {
        'dynasty':  ['Ming', 'Qing'],
        'occasion': ['Changfu', 'Chaofu'],
    },
    'cross-collar': {
        'dynasty':  ['Han', 'Tang', 'Song', 'Ming'],   # 交领历代通用
        'occasion': ['Changfu', 'Lifu'],
    },
    'round-collar': {
        'dynasty':  ['Tang', 'Song', 'Ming'],
        'occasion': ['Changfu', 'Chaofu'],
    },
    'duijin-collar': {
        'dynasty':  ['Song', 'Ming'],
        'occasion': ['Changfu', 'Lifu'],
    },
    'wide-sleeve': {
        'dynasty':  ['Han', 'WeiJin', 'Tang'],         # 广袖汉唐风格
        'occasion': ['Lifu', 'Changfu'],
    },
    'narrow-sleeve': {
        'dynasty':  ['Han', 'Tang', 'Song', 'Ming', 'Qing'],
        'occasion': ['Changfu', 'Bianfu'],
    },
    'ruqun-skirt': {
        'dynasty':  ['Han', 'Tang', 'Song'],
        'occasion': ['Changfu', 'Lifu'],
    },
    'cloud-shoulder': {
        'dynasty':  ['Ming', 'Qing'],       # 云肩明清华丽
        'occasion': ['Lifu', 'Changfu'],
    },
    'beizi': {
        'dynasty':  ['Song', 'Ming'],       # 褙子宋代标志
        'occasion': ['Changfu', 'Lifu'],
    },
    'banbi': {
        'dynasty':  ['Tang', 'Song'],       # 半臂唐/宋
        'occasion': ['Changfu', 'Bianfu'],
    },
}

# 朝代 / 场合中文名
DYN_CN = {'Ming': '明代', 'Qing': '清代', 'Tang': '唐代', 'Song': '宋代',
          'Han': '汉代', 'WeiJin': '魏晋'}
OCC_CN = {'Changfu': '常服', 'Lifu': '礼服', 'Chaofu': '朝服', 'Bianfu': '便服'}

# ── 制版说明短语（含具体数值，模拟真实制版说明的语气）──
PHRASE = {
    'mamian-skirt': {
        'length':       {'knee-length': '裙长及膝', 'midi': '裙长及小腿',
                         'floor-length': '裙长及踝'},
        'mamian_width': {'narrow': '马面宽约20cm', 'standard': '马面宽约28cm',
                         'wide': '马面宽约35cm'},
        'pleat_ruffle': {'light': '褶裥稀疏（褶量比1.4）', 'medium': '褶量适中（褶量比1.8）',
                         'rich': '褶裥密集（褶量比2.4）'},
        'rise':         {'mid': '中腰位', 'high': '高腰位'},
    },
    'pipa-sleeve': {
        'length':      {'short': '袖长约臂长的0.7倍', 'standard': '袖长约臂长的0.95倍',
                        'long': '袖长超过臂长'},
        'cuff_width':  {'narrow': '袖口宽12cm', 'standard': '袖口宽15cm', 'wide': '袖口宽18cm'},
        'root_width':  {'narrow': '袖根宽18cm', 'standard': '袖根宽22cm', 'wide': '袖根宽27cm'},
        'bulge_width': {'slight': '袖身微膨（28cm）', 'standard': '袖身膨起35cm',
                        'rich': '袖身大膨起（42cm）'},
    },
    'stand-collar': {
        'collar_height': {'ming-low': '领高2.5cm', 'ming-high': '领高3.5cm（明制）',
                          'qing': '领高5cm（清制）'},
        'collar_flare':  {'straight': '直筒不倾', 'slight': '领口微外倾5°',
                          'flared': '领口外倾12°'},
        'top_curve':     {'flat': '领上缘平直', 'slight': '领上缘微弧',
                          'curved': '领上缘弧起'},
    },
    # ── 批次 2：领型 ──
    'cross-collar': {
        'collar_depth':   {'shallow': '领深18cm', 'standard': '领深25cm', 'deep': '领深33cm'},
        'cross_angle':    {'narrow': '交叉角35°', 'standard': '交叉角50°', 'wide': '交叉角65°'},
        'overlap_amount': {'slight': '左右襟重叠5cm', 'standard': '左右襟重叠8cm',
                           'deep': '左右襟重叠12cm'},
        'border_width':   {'narrow': '领缘宽1.5cm', 'standard': '领缘宽3cm', 'wide': '领缘宽5cm'},
    },
    'round-collar': {
        'front_depth':  {'shallow': '前领深7cm', 'standard': '前领深10cm', 'deep': '前领深15cm'},
        'back_depth':   {'shallow': '后领深2.5cm', 'standard': '后领深4cm', 'deep': '后领深6cm'},
        'border_width': {'narrow': '领缘宽1.2cm', 'standard': '领缘宽2.5cm', 'wide': '领缘宽4.5cm'},
    },
    'duijin-collar': {
        'front_width':   {'narrow': '前襟宽5cm', 'standard': '前襟宽8cm', 'wide': '前襟宽12cm'},
        'neck_depth':    {'shallow': '领深8cm', 'standard': '领深12cm', 'deep': '领深18cm'},
        'placket_width': {'narrow': '门襟宽2cm', 'standard': '门襟宽3cm', 'wide': '门襟宽5cm'},
    },
    # ── 批次 3：袖型 ──
    'wide-sleeve': {
        'length':     {'short': '袖长约臂长的0.85倍', 'standard': '袖长约臂长的1.05倍',
                       'long': '袖长超过臂长1.25倍'},
        'cuff_width': {'moderate': '袖口宽45cm', 'standard': '袖口宽60cm', 'grand': '袖口宽90cm'},
        'root_width': {'narrow': '袖根宽16cm', 'standard': '袖根宽20cm', 'wide': '袖根宽25cm'},
    },
    'narrow-sleeve': {
        'length':      {'short': '袖长约臂长', 'standard': '袖长约臂长的1.2倍',
                        'long': '袖长超过臂长1.4倍'},
        'cuff_width':  {'narrow': '袖口宽14cm', 'standard': '袖口宽18cm', 'wide': '袖口宽22cm'},
        'root_width':  {'narrow': '袖根宽17cm', 'standard': '袖根宽20cm', 'wide': '袖根宽24cm'},
        'elbow_width': {'slight': '肘部宽20cm', 'standard': '肘部宽22cm', 'loose': '肘部宽26cm'},
    },
    # ── 批次 4：下裳 ──
    'ruqun-skirt': {
        'length':         {'knee-length': '裙长及膝', 'midi': '裙长及小腿',
                           'floor-length': '裙长及踝'},
        'hem_ratio':      {'moderate': '裙摆展宽1.8倍', 'full': '裙摆展宽2.5倍',
                           'grand': '裙摆展宽3.5倍'},
        'waist_position': {'mid': '中腰', 'high': '高腰', 'chest': '齐胸高腰'},
    },
    # ── 批次 5：配饰 ──
    'cloud-shoulder': {
        'layers':        {'single': '单层云肩', 'double': '双层云肩', 'triple': '三层云肩'},
        'petal_count':   {'sparse': '4 云头', 'standard': '6 云头', 'dense': '8 云头'},
        'tassel_length': {'none': '无垂须', 'short': '垂须6cm', 'long': '垂须12cm'},
    },
    'beizi': {
        'length':        {'knee': '衣长及膝', 'midi': '衣长及小腿', 'ankle': '衣长及踝'},
        'slit_height':   {'low': '开衩较低（0.3）', 'standard': '开衩中等（0.45）',
                          'high': '开衩较高（0.6）'},
        'sleeve_length': {'short': '袖长约臂长的0.7倍', 'standard': '袖长约臂长的0.9倍',
                          'long': '袖长超过臂长'},
    },
    'banbi': {
        'length':        {'short': '衣长较短（0.5倍腿长）', 'standard': '衣长中等（0.62倍）',
                          'long': '衣长较长（0.78倍）'},
        'sleeve_length': {'short': '半袖较短', 'standard': '半袖中等', 'long': '半袖较长'},
        'sleeve_width':  {'narrow': '袖口宽14cm', 'standard': '袖口宽18cm',
                          'wide': '袖口宽24cm'},
    },
}

# 组件量词
QUANTIFIER = {
    'mamian-skirt': '条', 'pipa-sleeve': '对', 'stand-collar': '个',
    'cross-collar': '个', 'round-collar': '个', 'duijin-collar': '件',
    'wide-sleeve': '对', 'narrow-sleeve': '对', 'ruqun-skirt': '条',
    'cloud-shoulder': '件', 'beizi': '件', 'banbi': '件',
}

COMPONENT_CLASS = {
    'mamian-skirt': ('MamianSkirt', '马面裙'),
    'pipa-sleeve': ('PipaSleeve', '琵琶袖'),
    'stand-collar': ('StandCollar', '立领'),
    'cross-collar': ('CrossCollar', '交领'),
    'round-collar': ('RoundCollar', '圆领'),
    'duijin-collar': ('DuijinCollar', '对襟'),
    'wide-sleeve': ('WideSleeve', '广袖'),
    'narrow-sleeve': ('NarrowSleeve', '窄袖'),
    'ruqun-skirt': ('RuqunSkirt', '襦裙'),
    'cloud-shoulder': ('CloudShoulder', '云肩'),
    'beizi': ('Beizi', '褙子'),
    'banbi': ('Banbi', '半臂'),
}

# 句式模板（随机组合，模拟不同人的表述习惯）
TEMPLATES = [
    '{dyn}{cname}，{feat}，{occ}。',
    '请设计一{quant}{dyn}{occ}{cname}，要求：{feat}。',
    '我想要一{quant}{dyn}风格的{cname}，{feat}。',
    '{occ}{cname}制版要求：按{dyn}形制，{feat}。',
    '做一{quant}{dyn}{cname}，{feat}，用于{occ}。',
    '设计要点：{dyn}{cname}；{feat}；{occ}。',
    '帮我出一{quant}{cname}的纸样，{dyn}制，{feat}。',
]


# ═══════════════════════════════════════════════════════════════
# 2. 形制约束（过滤非法组合；来源：项目 validation/rules）
# ═══════════════════════════════════════════════════════════════

def form_violation(comp: str, combo: dict, ctx: dict, design: dict) -> str | None:
    """返回违规原因；None 表示合法。"""
    # 琵琶袖：袖口 < 袖根 < 膨起
    if comp == 'pipa-sleeve':
        vals = {k: _label_value(design['pipa-sleeve'][k], v)
                for k, v in combo.items() if k in
                ('cuff_width', 'root_width', 'bulge_width')}
        if not (vals['cuff_width'] < vals['root_width'] < vals['bulge_width']):
            return (f"琵琶袖尺寸约束不满足：袖口{vals['cuff_width']} < "
                    f"袖根{vals['root_width']} < 膨起{vals['bulge_width']}")

    # 立领：明代不宜超过 4cm
    if comp == 'stand-collar':
        h = _label_value(design['stand-collar']['collar_height'],
                         combo['collar_height'])
        if ctx['dynasty'] == 'Ming' and h > 4.0:
            return f'明代立领 {h}cm 超过 4cm（形制禁忌）'
        if ctx['dynasty'] == 'Qing' and h < 4.0:
            return f'清代立领通常 4-6cm，当前 {h}cm 偏矮'

    return None


def _label_value(node: dict, label: str):
    """从参数节点的 range 里取标签对应数值（与 caption2design 同逻辑）。"""
    rng = node.get('range', [])
    if rng and isinstance(rng[0], dict):
        for entry in rng:
            if label in entry:
                return entry[label]
    return label


# ═══════════════════════════════════════════════════════════════
# 3. 自然语言说明生成（多句式，模拟论文的 Γ_cmt）
# ═══════════════════════════════════════════════════════════════

def describe_cn(comp: str, combo: dict, ctx: dict, n: int = 3) -> list[str]:
    """生成多种句式的中文制版说明（含具体数值，模拟 Γ_cmt 的输出）。"""
    cname = COMPONENT_CLASS[comp][1]
    quant = QUANTIFIER[comp]
    dyn = DYN_CN.get(ctx['dynasty'], ctx['dynasty'])
    occ = OCC_CN.get(ctx['occasion'], '')

    phrases = PHRASE[comp]
    feat = '，'.join(phrases[k][v] for k, v in combo.items() if k in phrases)

    pool = []
    for tpl in TEMPLATES:
        pool.append(tpl.format(dyn=dyn, cname=cname, quant=quant,
                               feat=feat, occ=occ))
    # 固定取前 n 条（保证可复现）
    return pool[:n]


def describe_caption(comp: str, combo: dict, ctx: dict) -> list[str]:
    """生成 D2GC 兼容的 caption（参数路径__标签），可被 caption2design 解析。"""
    cap = [f"traditional__dynasty__{ctx['dynasty']}",
           f"traditional__occasion__{ctx['occasion']}"]
    for k, v in combo.items():
        cap.append(f"{comp}__{k}__{v}")
    return cap


# ═══════════════════════════════════════════════════════════════
# 4. 样本构建
# ═══════════════════════════════════════════════════════════════

def build_component(comp: str, body, design, ctx):
    """按组件类型实例化（朝代信息已注入 design['traditional']）。"""
    from traditional_ext.collars_extra import (CrossCollar, RoundCollar,
                                               DuijinCollar)
    from traditional_ext.sleeves_extra import WideSleeve, NarrowSleeve
    from traditional_ext.skirts_extra import RuqunSkirt
    from traditional_ext.accessories import CloudShoulder, Beizi, Banbi
    cls = {
        'mamian-skirt': MamianSkirt,
        'pipa-sleeve': PipaSleeve,
        'stand-collar': StandCollar,
        'cross-collar': CrossCollar,
        'round-collar': RoundCollar,
        'duijin-collar': DuijinCollar,
        'wide-sleeve': WideSleeve,
        'narrow-sleeve': NarrowSleeve,
        'ruqun-skirt': RuqunSkirt,
        'cloud-shoulder': CloudShoulder,
        'beizi': Beizi,
        'banbi': Banbi,
    }[comp]
    return cls(body, design)


def build_sample(comp, combo, ctx, body, base_design, idx):
    """构建单个样本：应用参数 → 真实生成纸样 → 产出监督目标。"""
    design = yaml.safe_load(yaml.safe_dump(base_design))   # 深拷贝
    caption = describe_caption(comp, combo, ctx)
    design, _ = caption2design(caption, design, verbose=False)

    # ── 形制约束过滤 ──
    reason = form_violation(comp, combo, ctx, design)
    if reason:
        return None, reason

    # ── 真实生成（可执行性验证）──
    try:
        comp_obj = build_component(comp, body, design, ctx)
        pattern = comp_obj.assembly()
    except Exception as exc:
        return None, f'生成失败: {type(exc).__name__}: {exc}'

    # ── 形制自检（组件内置规则）──
    warns = getattr(comp_obj, 'warnings', [])
    if warns:
        return None, '形制警告: ' + '; '.join(warns)

    panels = pattern.pattern['panels']
    area = 0.0
    for p in panels.values():
        v = p['vertices']
        a = 0.0
        for i in range(len(v)):
            j = (i + 1) % len(v)
            a += v[i][0] * v[j][1] - v[j][0] * v[i][1]
        area += abs(a) / 2

    cls_name, cname = COMPONENT_CLASS[comp]
    instrs = describe_cn(comp, combo, ctx)

    sample = {
        'id': f'{comp}_{ctx["dynasty"].lower()}_{idx:04d}',
        'component': comp,
        'component_class': cls_name,
        'dynasty': ctx['dynasty'],
        'occasion': ctx['occasion'],
        # ① 自然语言制版说明（多句式，模拟 Γ_cmt）
        'instructions_cn': instrs,
        # ② D2GC 兼容 caption（参数路径标签）
        'caption': caption,
        # ③ 设计配置（可执行）
        'design': {comp: {k: {'v': design[comp][k]['v']} for k in combo},
                   'traditional': {'dynasty': {'v': ctx['dynasty']},
                                   'occasion': {'v': ctx['occasion']}}},
        # ④ 目标代码（可执行调用）
        'target_code': (f"{cls_name}(body, design).assembly()"),
        # ⑤ 可验证的纸样统计
        'pattern': {
            'panels': len(panels),
            'panel_names': list(panels.keys()),
            'area_cm2': round(area, 1),
        },
        'meta': {
            'source': 'procedural_generation',
            'verified': True,          # 已真实执行 GarmentCode 生成纸样
            'generator': 'traditional_ext/build_dataset.py',
            'created_at': datetime.now().strftime('%Y-%m-%d'),
        },
    }
    return sample, None


def main():
    random.seed(RANDOM_SEED)
    os.makedirs(OUT_DIR, exist_ok=True)

    with open(PARAMS_YAML, encoding='utf-8') as f:
        base_design = yaml.safe_load(f)['design']
    body = BodyParameters('./assets/bodies/mean_female.yaml')

    print('=' * 64)
    print('  构建传统服饰设计数据集（按 D2GC Program Learning 方法）')
    print('=' * 64)

    samples, rejected = [], []
    per_comp = Counter()

    for comp, space in SPACES.items():
        keys = list(space.keys())
        combos = list(itertools.product(*[space[k] for k in keys]))
        ctx_list = list(itertools.product(*[CONTEXT[comp][k]
                                            for k in CONTEXT[comp]]))
        ctx_keys = list(CONTEXT[comp].keys())

        print(f'\n[{comp}] 参数组合 {len(combos)} × 形制上下文 {len(ctx_list)}')

        idx = 0
        for combo_vals in combos:
            combo = dict(zip(keys, combo_vals))
            for ctx_vals in ctx_list:
                ctx = dict(zip(ctx_keys, ctx_vals))
                idx += 1
                sample, reason = build_sample(
                    comp, combo, ctx, body, base_design, idx)
                if sample:
                    samples.append(sample)
                    per_comp[comp] += 1
                else:
                    rejected.append({'component': comp, 'combo': combo,
                                     'ctx': ctx, 'reason': reason})

    # ── 输出 ──
    out_path = os.path.join(OUT_DIR, 'traditional_design_dataset.jsonl')
    with open(out_path, 'w', encoding='utf-8') as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + '\n')

    stats = {
        'total': len(samples),
        'rejected': len(rejected),
        'by_component': dict(per_comp),
        'by_dynasty': dict(Counter(s['dynasty'] for s in samples)),
        'by_occasion': dict(Counter(s['occasion'] for s in samples)),
        'total_panels': sum(s['pattern']['panels'] for s in samples),
        'created_at': datetime.now().isoformat(timespec='seconds'),
    }
    with open(os.path.join(OUT_DIR, 'stats.json'), 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print('\n' + '=' * 64)
    print(f'  ✅ 有效样本: {len(samples)} 条')
    print(f'  ⛔ 被形制规则过滤: {len(rejected)} 条')
    for c, n in per_comp.items():
        print(f'     {c:<16} {n} 条')
    print(f'  朝代分布: {stats["by_dynasty"]}')
    print(f'  输出: {out_path}')
    if rejected[:3]:
        print('\n  过滤示例:')
        for r in rejected[:3]:
            print(f'     [{r["component"]}] {r["reason"]}')
    print('=' * 64)


if __name__ == '__main__':
    main()
