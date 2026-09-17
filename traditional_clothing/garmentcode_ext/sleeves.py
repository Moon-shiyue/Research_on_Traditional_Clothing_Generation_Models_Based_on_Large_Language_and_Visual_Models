"""
琵琶袖 — pygarment 原生实现

明代独有袖型：袖口窄小、袖身中部膨起如琵琶共鸣箱、袖根宽度适中。
形制硬性约束：袖口宽 < 袖根宽 < 膨起宽。

对应项目中的 garment_components/sleeves/pipa_sleeve.py，
几何逻辑完全一致（两段三次贝塞尔拼接的上/下缘），
但改用 GarmentCode 的 CurveEdge（最多 2 个控制点 = 三次贝塞尔）。
"""
from __future__ import annotations

import pygarment as pyg


class PipaSleevePanel(pyg.Panel):
    """琵琶袖裁片 — 整片袖，贝塞尔曲线勾勒琵琶形轮廓（右侧，左侧镜像）。"""

    def __init__(self, name, length, cuff_w, root_w, bulge_w,
                 bulge_pos, cap_h):
        super().__init__(name)

        # ── 形制约束（对应项目校验规则"琵琶袖收口特征"）──
        if not (cuff_w < root_w < bulge_w):
            raise ValueError(
                f'琵琶袖尺寸约束不满足：袖口宽({cuff_w:.1f}) < '
                f'袖根宽({root_w:.1f}) < 膨起宽({bulge_w:.1f})')

        # ── 关键点（原点 = 袖根中心，x 向右为袖长方向）──
        rt = [0.0, root_w / 2]                       # 袖根上角
        rb = [0.0, -root_w / 2]                      # 袖根下角
        ct = [length, cuff_w / 2]                    # 袖口上角
        cb = [length, -cuff_w / 2]                   # 袖口下角
        bp_x = length * bulge_pos                    # 膨起处 x
        bt = [bp_x, bulge_w / 2]                     # 膨起上缘点
        bb = [bp_x, -bulge_w / 2]                    # 膨起下缘点

        # ── 轮廓（逆时针），6 条边完整闭合 ──
        # 1. 袖根边（直线）→ 接衣身袖窿
        self.edges.append(pyg.Edge(rb, rt, label='armhole'))

        # 2. 上缘①：袖根上 → 膨起上（三次贝塞尔，含袖山隆起）
        self.edges.append(pyg.CurveEdge(
            rt, bt,
            control_points=[
                [bp_x * 0.40, root_w / 2 + cap_h * 0.55],   # 袖山弧度：向上隆起
                [bp_x * 0.75, bulge_w / 2 + 3.0],           # 接近膨起处，微高于膨起线
            ],
            relative=False, label='top_to_bulge'))

        # 3. 上缘②：膨起上 → 袖口上（缓慢收拢）
        self.edges.append(pyg.CurveEdge(
            bt, ct,
            control_points=[
                [bp_x + (length - bp_x) * 0.25, bulge_w / 2 - 1.0],
                [bp_x + (length - bp_x) * 0.70, cuff_w / 2 + 2.0],
            ],
            relative=False, label='top_to_cuff'))

        # 4. 袖口边（直线）
        self.edges.append(pyg.Edge(ct, cb, label='cuff'))

        # 5. 下缘①：袖口下 → 膨起下
        self.edges.append(pyg.CurveEdge(
            cb, bb,
            control_points=[
                [bp_x + (length - bp_x) * 0.70, -cuff_w / 2 - 2.0],
                [bp_x + (length - bp_x) * 0.25, -bulge_w / 2 + 1.0],
            ],
            relative=False, label='bottom_to_bulge'))

        # 6. 下缘②：膨起下 → 袖根下（回到起点，轮廓闭合）
        self.edges.append(pyg.CurveEdge(
            bb, rb,
            control_points=[
                [bp_x * 0.75, -bulge_w / 2 - 3.0],
                [bp_x * 0.40, -root_w / 2 - cap_h * 0.55],
            ],
            relative=False, label='bottom_to_root'))

        # ── 接口 ──
        self.interfaces = {
            'armhole': pyg.Interface(self, self.edges[0]),   # 接衣身袖窿
            'cuff': pyg.Interface(self, self.edges[3]),      # 袖口
            'top': pyg.Interface(self, self.edges[1]),
            'bottom': pyg.Interface(self, self.edges[5]),
        }


class PipaSleeve(pyg.Component):
    """琵琶袖组件 — 左右两片（左侧镜像）。"""

    def __init__(self, body, design, tag='', mirrored=True):
        super().__init__(f'PipaSleeve{"_" + tag if tag else ""}')
        self.body = body
        self.design = design

        d = design['pipa-sleeve']
        arm_len = body['arm_length']

        # ── 参数归一化 → 绝对尺寸 ──
        length = d['length']['v'] * arm_len
        cuff_w = float(d['cuff_width']['v'])
        root_w = float(d['root_width']['v'])
        bulge_w = float(d['bulge_width']['v'])
        bulge_pos = d['bulge_position']['v']
        cap_h = d['sleeve_cap_height']['v']
        self.warnings = []

        # ── 右袖 ──
        self.right = PipaSleevePanel(
            'pipa_sleeve_right', length, cuff_w, root_w, bulge_w, bulge_pos, cap_h)

        # ── 左袖（镜像）──
        self.left = None
        if mirrored:
            self.left = PipaSleevePanel(
                'pipa_sleeve_left', length, cuff_w, root_w, bulge_w, bulge_pos, cap_h)
            self.left.mirror()               # 绕 Y 轴镜像（左右对称）

        # ── 接口（对外提供袖窿，供上衣对接）──
        self.interfaces = {
            'armhole_r': pyg.Interface.from_multiple(self.right.interfaces['armhole']),
            'armhole_l': pyg.Interface.from_multiple(self.left.interfaces['armhole'])
            if self.left is not None else None,
        }

    def summary(self):
        d = self.design['pipa-sleeve']
        return (f'琵琶袖 | 袖长 {d["length"]["v"]:.2f}×臂长 | '
                f'袖口 {d["cuff_width"]["v"]} < 袖根 {d["root_width"]["v"]} '
                f'< 膨起 {d["bulge_width"]["v"]} cm')
