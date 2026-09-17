"""
交领 / 圆领 / 对襟 — pygarment 原生实现（批次 2）

对应项目中的：
  garment_components/collars/cross_collar.py   （交领，明制袄裙常用）
  garment_components/collars/round_collar.py   （圆领，唐/宋/明）
  garment_components/collars/duijin_collar.py  （对襟，宋/明）

设计原则（与立领/马面裙/琵琶袖一致）：
  - 用 pyg.Panel + Edge/CurveEdge/CircleEdgeFactory 表达几何
  - 参数从 design 参数树读取，可被 caption 控制
  - 组件内置形制自检（warnings）
"""
from __future__ import annotations

import math

import pygarment as pyg


# ═══════════════════════════════════════════════════════════════
# 交领（右衽）— 三片式：左前领片（外层）+ 右前领片（内层）+ 后领片
# ═══════════════════════════════════════════════════════════════

class CrossCollarFrontPanel(pyg.Panel):
    """交领前领片 — 领口弧线 + 交叉延伸 + 外缘。

    关键形制特征：左襟压右襟（右衽），两片交叉成 Y 形。
    """

    def __init__(self, name, half_width, depth, cross_angle_deg,
                 overlap, border, is_outer):
        super().__init__(name)
        sign = 1.0 if is_outer else -1.0          # 左片向右交叉，右片向左
        half_ang = math.radians(cross_angle_deg / 2.0)

        pt_back = [sign * half_width * -1.0, 0.0]  # 后领连接点
        pt_neck = [0.0, -depth * 0.35]             # 前领深点
        # 交叉延伸端点（沿领深方向偏转半交叉角）
        ext = depth * 0.65 + (overlap * 0.6 if is_outer else 0.0)
        cx = pt_neck[0] + sign * ext * math.sin(half_ang)
        cy = pt_neck[1] - ext * math.cos(half_ang)
        pt_cross = [cx, cy]
        # 外缘下角（两侧外扩缘边）
        pt_outer = [cx + sign * border, cy - border * 0.6]
        pt_top = [pt_back[0] - sign * border * 0.8, 0.0 + border * 0.5]

        # 1. 领口弧线（后领点 → 前领深点）
        self.edges.append(pyg.CurveEdge(
            pt_back, pt_neck,
            control_points=[[pt_back[0] * 0.55, -depth * 0.12],
                            [pt_neck[0] + sign * 0.3, pt_neck[1] * 0.55]],
            relative=False, label='neckline'))
        # 2. 交叉边（前领深点 → 交叉端点）
        self.edges.append(pyg.Edge(pt_neck, pt_cross, label='cross'))
        # 3. 外缘（交叉端点 → 外缘上角）
        self.edges.append(pyg.CurveEdge(
            pt_cross, pt_top,
            control_points=[[pt_outer[0] + sign * 0.4, (pt_cross[1] + pt_top[1]) / 2.0]],
            relative=False, label='outer'))
        # 4. 闭合边（外缘上角 → 后领点）
        self.edges.close_loop()

        self.interfaces = {
            'neckline': pyg.Interface(self, self.edges[0]),
            'cross': pyg.Interface(self, self.edges[1]),
            'outer': pyg.Interface(self, self.edges[2]),
            'back': pyg.Interface(self, self.edges[3]),
        }


class CrossCollarBackPanel(pyg.Panel):
    """交领后领片 — 连接左右前领片的矩形条带。"""

    def __init__(self, name, half_width, back_depth):
        super().__init__(name)
        self.edges.append(pyg.Edge([-half_width, 0.0], [half_width, 0.0],
                                   label='top'))
        self.edges.append(pyg.Edge([half_width, 0.0], [half_width, -back_depth],
                                   label='right'))
        self.edges.append(pyg.Edge([half_width, -back_depth],
                                   [-half_width, -back_depth], label='bottom'))
        self.edges.close_loop()

        self.interfaces = {
            'top': pyg.Interface(self, self.edges[0]),
            'bottom': pyg.Interface(self, self.edges[2]),
            'left': pyg.Interface(self, self.edges[3]),
            'right': pyg.Interface(self, self.edges[1]),
        }


class CrossCollar(pyg.Component):
    """交领（右衽）— 汉族传统服饰最经典领型，各朝代通用。"""

    def __init__(self, body, design, tag=''):
        super().__init__(f'CrossCollar{"_" + tag if tag else ""}')
        self.body = body
        self.design = design
        d = design['cross-collar']

        half_width = body['neck_w'] / 2.0 + float(d['collar_width']['v']) * 0.15
        depth = float(d['collar_depth']['v'])
        angle = float(d['cross_angle']['v'])
        overlap = float(d['overlap_amount']['v'])
        border = float(d['border_width']['v'])
        back_depth = float(d['back_neck_depth']['v'])

        self.warnings = []
        if angle < 30:
            self.warnings.append(f'交叉角 {angle}° < 30°，Y 形不明显')
        if angle > 70:
            self.warnings.append(f'交叉角 {angle}° > 70°，领型过宽')
        if overlap < 4.0:
            self.warnings.append(f'重叠量 {overlap}cm < 4cm，左右襟可能覆盖不足')

        self.right_front = CrossCollarFrontPanel(
            'cross_collar_right_front', half_width, depth, angle, overlap,
            border, is_outer=False)
        self.left_front = CrossCollarFrontPanel(
            'cross_collar_left_front', half_width, depth, angle, overlap,
            border, is_outer=True)
        self.back = CrossCollarBackPanel(
            'cross_collar_back', half_width, back_depth)

        self.stitching_rules = pyg.Stitches(
            (self.left_front.interfaces['back'], self.back.interfaces['right']),
            (self.right_front.interfaces['back'], self.back.interfaces['left']),
        )

        self.interfaces = {
            'neckline_l': pyg.Interface.from_multiple(
                self.left_front.interfaces['neckline']),
            'neckline_r': pyg.Interface.from_multiple(
                self.right_front.interfaces['neckline']),
            'neckline_back': pyg.Interface.from_multiple(
                self.back.interfaces['bottom']),
        }

    def summary(self):
        d = self.design['cross-collar']
        return (f'交领（右衽）| 领深 {d["collar_depth"]["v"]}cm | '
                f'交叉角 {d["cross_angle"]["v"]}° | 重叠 {d["overlap_amount"]["v"]}cm')


# ═══════════════════════════════════════════════════════════════
# 圆领 — 圆弧领口 + 前领深
# ═══════════════════════════════════════════════════════════════

class RoundCollarPanel(pyg.Panel):
    """圆领领片 — 半圆弧后领口 + 两条贝塞尔构成前领深。"""

    def __init__(self, name, radius, front_depth, back_depth):
        super().__init__(name)
        r = radius
        fd = front_depth

        pt_l = [-r, 0.0]          # 左侧点
        pt_r = [r, 0.0]           # 右侧点
        pt_front = [0.0, -fd]     # 前领深点
        pt_back = [0.0, back_depth]   # 后领中点

        # 1. 后领弧（左 → 后中 → 右），用三点圆弧
        back_arc = pyg.CircleEdgeFactory.from_three_points(
            pt_l, pt_r, pt_back, relative=False)
        back_arc.label = 'back_arc'          # CircleEdgeFactory 不支持 label 参数
        self.edges.append(back_arc)
        # 2. 前领右弧（右 → 前领深点）
        self.edges.append(pyg.CurveEdge(
            pt_r, pt_front,
            control_points=[[r * 0.32, -fd * 0.58]],
            relative=False, label='front_arc_r'))
        # 3. 前领左弧（前领深点 → 左）
        self.edges.append(pyg.CurveEdge(
            pt_front, pt_l,
            control_points=[[-r * 0.32, -fd * 0.58]],
            relative=False, label='front_arc_l'))


        # 三段弧首尾相接已闭合轮廓（无需 close_loop，也没有第 4 条边）
        # 领口 = 后领弧 + 前领左右弧
        self.interfaces = {
            'neckline': pyg.Interface.from_multiple(
                pyg.Interface(self, self.edges[0]),
                pyg.Interface(self, self.edges[1]),
                pyg.Interface(self, self.edges[2])).reverse(True),
        }


class RoundCollar(pyg.Component):
    """圆领 — 唐/宋/明常见，简洁大方。"""

    def __init__(self, body, design, tag=''):
        super().__init__(f'RoundCollar{"_" + tag if tag else ""}')
        self.body = body
        self.design = design
        d = design['round-collar']

        radius = body['neck_w'] / 2.0 + float(d['front_depth']['v']) * 0.1
        front_depth = float(d['front_depth']['v'])
        back_depth = float(d['back_depth']['v'])
        border = float(d['border_width']['v'])

        self.warnings = []
        if front_depth <= back_depth:
            self.warnings.append(
                f'圆领前领深 {front_depth}cm 应大于后领深 {back_depth}cm（形制要求）')

        self.panel = RoundCollarPanel(
            'round_collar', radius, front_depth, back_depth)

        self.interfaces = {
            'neckline': pyg.Interface.from_multiple(
                self.panel.interfaces['neckline']),
        }

    def summary(self):
        d = self.design['round-collar']
        return (f'圆领 | 前领深 {d["front_depth"]["v"]}cm | '
                f'后领深 {d["back_depth"]["v"]}cm | 缘边 {d["border_width"]["v"]}cm')


# ═══════════════════════════════════════════════════════════════
# 对襟 — 左右前襟正中对齐
# ═══════════════════════════════════════════════════════════════

class DuijinPanel(pyg.Panel):
    """对襟片 — 领口曲线 + 门襟条带（左右各一片）。"""

    def __init__(self, name, front_width, neck_depth, placket_width,
                 placket_height, side='right'):
        super().__init__(name)
        sgn = 1.0 if side == 'right' else -1.0
        fw, nd, pw, ph = front_width, neck_depth, placket_width, placket_height

        p0 = [0.0, 0.0]                      # 前中上端
        p1 = [sgn * fw, 0.0]                 # 肩端
        p2 = [0.0, -nd]                      # 前中领深点
        p3 = [0.0, -(nd + ph)]               # 门襟下端（前中）
        p4 = [sgn * (fw + pw), -(nd + ph)]   # 门襟外下角
        p5 = [sgn * (fw + pw), 0.0]          # 门襟外上角

        # 1. 肩线（前中上端 → 肩端）
        self.edges.append(pyg.Edge(p0, p1, label='shoulder'))
        # 2. 领口弧（肩端 → 前中领深点）
        self.edges.append(pyg.CurveEdge(
            p1, p2,
            control_points=[[sgn * fw * 0.38, -nd * 0.52]],
            relative=False, label='neckline'))
        # 3. 前中线（领深点 → 门襟下端）
        self.edges.append(pyg.Edge(p2, p3, label='center'))
        # 4. 门襟底边
        self.edges.append(pyg.Edge(p3, p4, label='placket_bottom'))
        # 5. 门襟外边（→ 门襟外上角）
        self.edges.append(pyg.Edge(p4, p5, label='placket_outer'))
        # 6. 闭合（门襟外上角 → 前中上端）
        self.edges.close_loop()

        self.interfaces = {
            'neckline': pyg.Interface(self, self.edges[1]),
            'center': pyg.Interface(self, self.edges[2]),
            'shoulder': pyg.Interface(self, self.edges[0]),
            'placket': pyg.Interface(self, self.edges[4]),
        }


class DuijinCollar(pyg.Component):
    """对襟 — 左右衣襟正中对齐闭合，宋明常用。"""

    def __init__(self, body, design, tag=''):
        super().__init__(f'DuijinCollar{"_" + tag if tag else ""}')
        self.body = body
        self.design = design
        d = design['duijin-collar']

        front_width = float(d['front_width']['v'])
        neck_depth = float(d['neck_depth']['v'])
        placket_width = float(d['placket_width']['v'])
        placket_height = float(d['placket_height']['v'])
        stand = float(d['collar_stand_height']['v'])

        self.warnings = []
        if neck_depth < 8.0:
            self.warnings.append(f'对襟领深 {neck_depth}cm 偏浅（建议 ≥8cm）')
        if placket_width > 6.0:
            self.warnings.append(f'门襟宽 {placket_width}cm 偏宽（建议 ≤6cm）')

        self.right = DuijinPanel('duijin_right_front', front_width, neck_depth,
                                 placket_width, placket_height, side='right')
        self.left = DuijinPanel('duijin_left_front', front_width, neck_depth,
                                placket_width, placket_height, side='left')

        self.interfaces = {
            'neckline_r': pyg.Interface.from_multiple(
                self.right.interfaces['neckline']),
            'neckline_l': pyg.Interface.from_multiple(
                self.left.interfaces['neckline']),
        }

    def summary(self):
        d = self.design['duijin-collar']
        return (f'对襟 | 前襟宽 {d["front_width"]["v"]}cm | '
                f'领深 {d["neck_depth"]["v"]}cm | 门襟宽 {d["placket_width"]["v"]}cm')
