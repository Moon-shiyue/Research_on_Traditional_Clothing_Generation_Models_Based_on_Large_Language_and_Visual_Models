"""
广袖 / 窄袖 — pygarment 原生实现（批次 3）

对应项目中的：
  garment_components/sleeves/wide_sleeve.py   （广袖，汉/魏晋/唐）
  garment_components/sleeves/narrow_sleeve.py （窄袖，历代通用）

形制约束：
  广袖：袖口宽 > 袖根宽（外展特征）
  窄袖：袖口宽 < 袖根宽（微锥收窄），肘部微弧贴合
"""
from __future__ import annotations

import pygarment as pyg


# ═══════════════════════════════════════════════════════════════
# 广袖 — 袖身自 flare 起点向外展放，袖口宽大
# ═══════════════════════════════════════════════════════════════

class WideSleevePanel(pyg.Panel):
    """广袖裁片 — 梯形展放 + 弧形袖山（单侧，另一侧镜像）。"""

    def __init__(self, name, length, cuff_w, root_w, flare_ratio, cap_h):
        super().__init__(name)

        # 形制约束（对应项目校验规则"广袖袖口宽大于袖根宽"）
        if cuff_w <= root_w:
            raise ValueError(
                f'广袖袖口宽({cuff_w:.1f}) 必须大于袖根宽({root_w:.1f})')

        sl, cw, rw = length, cuff_w, root_w
        fy = sl * flare_ratio                 # flare 起始高度

        root_l = [-rw / 2, 0.0]
        root_r = [rw / 2, 0.0]
        flare_l = [-rw / 2, -fy]
        flare_r = [rw / 2, -fy]
        cuff_l = [-cw / 2, -sl]
        cuff_r = [cw / 2, -sl]
        grow = cw - rw

        # 1. 右袖线：flare 起点 → 袖口右
        self.edges.append(pyg.Edge(root_r, flare_r, label='right_top'))
        # 2. 右侧展放弧（贝塞尔）
        self.edges.append(pyg.CurveEdge(
            flare_r, cuff_r,
            control_points=[[rw / 2 + grow * 0.15, -fy - (sl - fy) * 0.40],
                            [cw / 2 - grow * 0.10, -fy - (sl - fy) * 0.75]],
            relative=False, label='flare_r'))
        # 3. 袖口（右 → 左）
        self.edges.append(pyg.Edge(cuff_r, cuff_l, label='cuff'))
        # 4. 左侧展放弧
        self.edges.append(pyg.CurveEdge(
            cuff_l, flare_l,
            control_points=[[-cw / 2 + grow * 0.10, -fy - (sl - fy) * 0.75],
                            [-rw / 2 - grow * 0.15, -fy - (sl - fy) * 0.40]],
            relative=False, label='flare_l'))
        # 5. 左袖线：flare 起点 → 袖根左
        self.edges.append(pyg.Edge(flare_l, root_l, label='left_top'))
        # 6. 袖山弧（袖根左 → 袖根右，向上隆起）—— 闭合轮廓
        self.edges.append(pyg.CurveEdge(
            root_l, root_r,
            control_points=[[-rw * 0.2, cap_h], [rw * 0.2, cap_h]],
            relative=False, label='armhole'))

        self.interfaces = {
            'armhole': pyg.Interface(self, self.edges[5]).reverse(True),
            'cuff': pyg.Interface(self, self.edges[2]),
            'top': pyg.Interface.from_multiple(
                pyg.Interface(self, self.edges[0]),
                pyg.Interface(self, self.edges[1])),
            'bottom': pyg.Interface.from_multiple(
                pyg.Interface(self, self.edges[3]),
                pyg.Interface(self, self.edges[4])),
        }


class WideSleeve(pyg.Component):
    """广袖 — 汉/魏晋/唐标志性宽袖。"""

    def __init__(self, body, design, tag='', mirrored=True):
        super().__init__(f'WideSleeve{"_" + tag if tag else ""}')
        self.body = body
        self.design = design
        d = design['wide-sleeve']

        arm_len = body['arm_length']
        length = float(d['length']['v']) * arm_len
        cuff_w = float(d['cuff_width']['v'])
        root_w = float(d['root_width']['v'])
        flare_ratio = float(d['flare_start_ratio']['v'])
        cap_h = float(d['sleeve_cap_height']['v'])

        self.warnings = []
        if cuff_w <= root_w:
            self.warnings.append(
                f'广袖袖口宽({cuff_w}) 应大于袖根宽({root_w})（形制要求）')
        if length < cap_h * 2:
            self.warnings.append(f'袖长 {length:.0f}cm 相对袖山高过短')

        self.right = WideSleevePanel('wide_sleeve_right', length, cuff_w,
                                     root_w, flare_ratio, cap_h)
        self.left = None
        if mirrored:
            self.left = WideSleevePanel('wide_sleeve_left', length, cuff_w,
                                        root_w, flare_ratio, cap_h)
            self.left.mirror()

        self.interfaces = {
            'armhole_r': pyg.Interface.from_multiple(self.right.interfaces['armhole']),
            'armhole_l': pyg.Interface.from_multiple(self.left.interfaces['armhole'])
            if self.left is not None else None,
        }

    def summary(self):
        d = self.design['wide-sleeve']
        return (f'广袖 | 袖长 {d["length"]["v"]:.2f}×臂长 | '
                f'袖口 {d["cuff_width"]["v"]} > 袖根 {d["root_width"]["v"]} cm')


# ═══════════════════════════════════════════════════════════════
# 窄袖 — 微锥形直袖，肘部微弧
# ═══════════════════════════════════════════════════════════════

class NarrowSleevePanel(pyg.Panel):
    """窄袖裁片 — 袖根 → 肘部微扩 → 袖口收窄。"""

    def __init__(self, name, length, cuff_w, root_w, elbow_w, elbow_pos, cap_h):
        super().__init__(name)

        sl, cw, rw, ew = length, cuff_w, root_w, elbow_w
        ey = sl * elbow_pos

        root_l = [-rw / 2, 0.0]
        root_r = [rw / 2, 0.0]
        elbow_l = [-ew / 2, -ey]
        elbow_r = [ew / 2, -ey]
        cuff_l = [-cw / 2, -sl]
        cuff_r = [cw / 2, -sl]

        # 1. 右上段（袖根右 → 肘右）
        self.edges.append(pyg.Edge(root_r, elbow_r, label='right_top'))
        # 2. 右下段（肘右 → 袖口右），微弧贴合手臂
        self.edges.append(pyg.CurveEdge(
            elbow_r, cuff_r,
            control_points=[[(ew / 2 + cw / 2) / 2 + 0.3, -(ey + (sl - ey) * 0.5)]],
            relative=False, label='right_low'))
        # 3. 袖口
        self.edges.append(pyg.Edge(cuff_r, cuff_l, label='cuff'))
        # 4. 左下段（袖口左 → 肘左）
        self.edges.append(pyg.CurveEdge(
            cuff_l, elbow_l,
            control_points=[[-(ew / 2 + cw / 2) / 2 - 0.3, -(ey + (sl - ey) * 0.5)]],
            relative=False, label='left_low'))
        # 5. 左上段（肘左 → 袖根左）
        self.edges.append(pyg.Edge(elbow_l, root_l, label='left_top'))
        # 6. 袖山（闭合）
        self.edges.append(pyg.CurveEdge(
            root_l, root_r,
            control_points=[[-rw * 0.2, cap_h], [rw * 0.2, cap_h]],
            relative=False, label='armhole'))

        self.interfaces = {
            'armhole': pyg.Interface(self, self.edges[5]).reverse(True),
            'cuff': pyg.Interface(self, self.edges[2]),
            'top': pyg.Interface.from_multiple(
                pyg.Interface(self, self.edges[0]),
                pyg.Interface(self, self.edges[1])),
            'bottom': pyg.Interface.from_multiple(
                pyg.Interface(self, self.edges[3]),
                pyg.Interface(self, self.edges[4])),
        }


class NarrowSleeve(pyg.Component):
    """窄袖 — 历代通用的日常袖型。"""

    def __init__(self, body, design, tag='', mirrored=True):
        super().__init__(f'NarrowSleeve{"_" + tag if tag else ""}')
        self.body = body
        self.design = design
        d = design['narrow-sleeve']

        arm_len = body['arm_length']
        length = float(d['length']['v']) * arm_len
        cuff_w = float(d['cuff_width']['v'])
        root_w = float(d['root_width']['v'])
        elbow_w = float(d['elbow_width']['v'])
        elbow_pos = float(d['elbow_position']['v'])
        cap_h = float(d['sleeve_cap_height']['v'])

        self.warnings = []
        if not (cuff_w < root_w < elbow_w):
            self.warnings.append(
                f'窄袖应满足 袖口({cuff_w}) < 袖根({root_w}) < 肘宽({elbow_w})')
        if length < cap_h * 2:
            self.warnings.append(f'袖长 {length:.0f}cm 相对袖山高过短')

        self.right = NarrowSleevePanel('narrow_sleeve_right', length, cuff_w,
                                       root_w, elbow_w, elbow_pos, cap_h)
        self.left = None
        if mirrored:
            self.left = NarrowSleevePanel('narrow_sleeve_left', length, cuff_w,
                                          root_w, elbow_w, elbow_pos, cap_h)
            self.left.mirror()

        self.interfaces = {
            'armhole_r': pyg.Interface.from_multiple(self.right.interfaces['armhole']),
            'armhole_l': pyg.Interface.from_multiple(self.left.interfaces['armhole'])
            if self.left is not None else None,
        }

    def summary(self):
        d = self.design['narrow-sleeve']
        return (f'窄袖 | 袖长 {d["length"]["v"]:.2f}×臂长 | '
                f'袖口 {d["cuff_width"]["v"]} < 袖根 {d["root_width"]["v"]} '
                f'< 肘宽 {d["elbow_width"]["v"]} cm')
