"""
立领 — pygarment 原生实现

直立环绕颈部的领型：明代 2-3cm 高，清代 4-6cm 高。
领片为弧形带状，后中对折（本实现构建右侧一半）。

对应项目中的 garment_components/collars/stand_collar.py。
"""
from __future__ import annotations

import math

import pygarment as pyg


class StandCollarPanel(pyg.Panel):
    """立领领片 — 半片（后中对折），底边接衣身领圈。

    关键点（原点 = 后中底点）：
        cb      后中底点  [0, 0]
        cf      前中底点  [half_neck, 0]
        cf_top  前中顶点  [half_neck + flare_offset, height]
        cb_top  后中顶点  [0, height]
    """

    def __init__(self, name, height, half_neck, flare_deg, top_curve):
        super().__init__(name)

        # 外倾角 → 顶部外扩量
        flare_offset = height * math.tan(math.radians(flare_deg))

        cb = [0.0, 0.0]
        cf = [half_neck, 0.0]
        cf_top = [half_neck + flare_offset, height]
        cb_top = [0.0, height]

        # 1. 底边（直）— 接衣身领圈
        self.edges.append(pyg.Edge(cb, cf, label='neckline'))
        # 2. 前中边（直）— 门襟开口边（扣位）
        self.edges.append(pyg.Edge(cf, cf_top, label='front'))
        # 3. 顶边（弧形）— 领上缘微隆
        self.edges.append(pyg.CurveEdge(
            cf_top, cb_top,
            control_points=[[(cf_top[0] + cb_top[0]) / 2.0, height + top_curve]],
            relative=False, label='top'))
        # 4. 后中边 — 对折线（由 close_loop 自动补齐）
        self.edges.close_loop()

        self.interfaces = {
            'neckline': pyg.Interface(self, self.edges[0]).reverse(True),  # 接衣身
            'front': pyg.Interface(self, self.edges[1]),                   # 门襟
            'top': pyg.Interface(self, self.edges[2]),                     # 领上缘
            'back': pyg.Interface(self, self.edges[3]),                    # 后中对折
        }


class StandCollar(pyg.Component):
    """立领组件 — 左右两半（左侧镜像）。"""

    def __init__(self, body, design, tag='', mirrored=True):
        super().__init__(f'StandCollar{"_" + tag if tag else ""}')
        self.body = body
        self.design = design

        d = design['stand-collar']

        # ── 参数 ──
        height = float(d['collar_height']['v'])
        flare_deg = float(d['collar_flare']['v'])
        top_curve = float(d['top_curve']['v'])

        # 半颈围：以颈宽近似颈围（颈围 ≈ 颈宽 × 2.2）
        neck_circ = body['neck_w'] * 2.2
        half_neck = neck_circ / 2.0

        self.warnings = []
        # ── 形制自检（对应项目"立领高度不超过8cm"等规则）──
        if height > 8.0:
            self.warnings.append(f'立领高 {height}cm > 8cm（形制上限）')
        dynasty = design.get('traditional', {}).get('dynasty', {}).get('v', '')
        if dynasty in ('Ming',) and height > 4.0:
            self.warnings.append(
                f'明代立领通常 2-3cm，当前 {height}cm 偏高')

        # ── 右半片 ──
        self.right = StandCollarPanel(
            'stand_collar_right', height, half_neck, flare_deg, top_curve)

        # ── 左半片（镜像）──
        self.left = None
        if mirrored:
            self.left = StandCollarPanel(
                'stand_collar_left', height, half_neck, flare_deg, top_curve)
            self.left.mirror()               # 绕 Y 轴镜像（左右对称）

        self.interfaces = {
            'neckline_r': pyg.Interface.from_multiple(self.right.interfaces['neckline']),
            'neckline_l': pyg.Interface.from_multiple(self.left.interfaces['neckline'])
            if self.left is not None else None,
        }

    def summary(self):
        d = self.design['stand-collar']
        return (f'立领 | 领高 {d["collar_height"]["v"]}cm | '
                f'外倾 {d["collar_flare"]["v"]}° | 顶弧 {d["top_curve"]["v"]}cm')
