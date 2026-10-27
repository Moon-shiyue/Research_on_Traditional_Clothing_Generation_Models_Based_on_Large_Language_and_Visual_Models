"""
马面裙 — pygarment 原生实现（含腰头）

从 PoC 升级为完整下装：
  前马面 + 后马面 + 左褶裥侧片 + 右褶裥侧片 + 腰头

对应项目中的 garment_components/skirts/mamian_skirt.py，
参数全部改从 design 参数树读取（可被 caption / LMM 控制）。
"""
from __future__ import annotations

import pygarment as pyg


# ─────────────────────────────────────────────────────────────
# 裁片
# ─────────────────────────────────────────────────────────────

class MamianPanel(pyg.Panel):
    """马面裁片 — 平整矩形（无褶），前后各一片。

    形制约束：马面宽 ≥ 15cm（典型 20-35cm），是马面裙的核心特征。
    """

    def __init__(self, name, width, length):
        super().__init__(name)
        self.edges.append(pyg.Edge([0, 0], [width, 0], label='top'))
        self.edges.append(pyg.Edge([width, 0], [width, -length], label='right'))
        self.edges.append(pyg.Edge([width, -length], [0, -length], label='bottom'))
        self.edges.close_loop()          # 自动补 left 边

        self.interfaces = {
            'top': pyg.Interface(self, self.edges[0]),
            'bottom': pyg.Interface(self, self.edges[2]),
            'left': pyg.Interface(self, self.edges[3]),
            'right': pyg.Interface(self, self.edges[1]),
        }


class PleatedSidePanel(pyg.Panel):
    """褶裥侧片 — 密排对褶，展开宽 = 收拢可见宽 × 褶量比。

    ⭐ 关键：用 Interface(ruffle=) 表达褶裥，无需手工计算每个褶位坐标。
       ruffle = 展开宽 / 收拢宽
    """

    def __init__(self, name, unfolded_width, length, ruffle):
        super().__init__(name)
        self.edges.append(pyg.Edge([0, 0], [unfolded_width, 0], label='top'))
        self.edges.append(pyg.Edge([unfolded_width, 0], [unfolded_width, -length], label='right'))
        self.edges.append(pyg.Edge([unfolded_width, -length], [0, -length], label='bottom'))
        self.edges.close_loop()

        self.interfaces = {
            # ⭐ 褶裥：缝合时该边被收拢到 1/ruffle
            'top': pyg.Interface(self, self.edges[0], ruffle=ruffle).reverse(True),
            'bottom': pyg.Interface(self, self.edges[2]),
            'left': pyg.Interface(self, self.edges[3]),
            'right': pyg.Interface(self, self.edges[1]),
        }


class WaistbandPanel(pyg.Panel):
    """腰头裁片 — 横长矩形，上缘接裙身，两端接系带。"""

    def __init__(self, name, width, height):
        super().__init__(name)
        self.edges.append(pyg.Edge([0, 0], [width, 0], label='bottom'))
        self.edges.append(pyg.Edge([width, 0], [width, height], label='right'))
        self.edges.append(pyg.Edge([width, height], [0, height], label='top'))
        self.edges.close_loop()

        self.interfaces = {
            'bottom': pyg.Interface(self, self.edges[0]).reverse(True),  # 接裙身腰口
            'top': pyg.Interface(self, self.edges[2]),                    # 腰头外缘
            'left': pyg.Interface(self, self.edges[3]),
            'right': pyg.Interface(self, self.edges[1]),
        }


# ─────────────────────────────────────────────────────────────
# 组件
# ─────────────────────────────────────────────────────────────

class MamianSkirt(pyg.Component):
    """马面裙 — 明/清制女裙。

    参数来源（design['mamian-skirt']）：
      length            裙长（× body._leg_length）
      mamian_width      马面宽 (cm)
      pleat_ruffle      褶量比
      rise              腰位
      waistband_width   腰头高（× body.hips_line）
    """

    def __init__(self, body, design, tag=''):
        super().__init__(f'MamianSkirt{"_" + tag if tag else ""}')
        self.body = body
        self.design = design

        d = design['mamian-skirt']

        # ── 参数（从参数树读取）──
        length = d['length']['v'] * body['_leg_length']
        mamian_w = float(d['mamian_width']['v'])
        ruffle = float(d['pleat_ruffle']['v'])
        rise = d['rise']['v']
        wb_height = d['waistband_width']['v'] * body['hips_line']

        # ── 形制自检容器（对应项目的校验引擎）──
        warnings = []

        # ── 腰位派生 ──
        hips_line = body['hips_line']
        self.rise = rise
        waist = pyg.utils.lin_interpolation(body['hips'], body['waist'], rise)
        waist_level = rise * hips_line

        # ── 裙身宽度分配 ──
        # 收拢后可见宽 = (腰围 - 2×马面宽) / 2；展开宽 = 可见宽 × 褶量比
        side_visible = (waist - 2 * mamian_w) / 2.0
        self.side_visible = side_visible

        # ── 形制自检（对应项目校验引擎的规则）──
        if mamian_w < 15.0:
            warnings.append(f'马面宽 {mamian_w}cm < 15cm（形制硬性要求 ≥15）')
        if ruffle < 1.0:
            warnings.append(f'褶量比 {ruffle} < 1.0 不合理（展开宽应大于收拢宽）')
        if side_visible < 3.0:
            warnings.append(
                f'侧片收拢宽仅 {side_visible:.1f}cm（< 3cm 褶裥空间不足）：'
                f'腰围 {waist:.1f}cm 容纳 2×{mamian_w}cm 马面过挤，'
                f'建议减小马面宽或增大腰围')
        if side_visible <= 0:
            warnings.append(f'侧片收拢宽 {side_visible:.1f}cm ≤ 0：几何不可行！')

        side_visible = max(side_visible, 0.5)   # 生成时兜底，避免负数
        side_unfolded = side_visible * ruffle
        self.side_unfolded = side_unfolded
        self.warnings = warnings

        # ── 面板 ──
        self.front = MamianPanel('mamian_front', mamian_w, length).translate_by(
            [0, waist_level, 15])
        self.back = MamianPanel('mamian_back', mamian_w, length).translate_by(
            [0, waist_level, -15])
        self.left_side = PleatedSidePanel(
            'mamian_left_side', side_unfolded, length, ruffle).translate_by(
            [0, waist_level, 15])
        self.right_side = PleatedSidePanel(
            'mamian_right_side', side_unfolded, length, ruffle).translate_by(
            [0, waist_level, -15])
        self.waistband = WaistbandPanel('mamian_waistband', waist, wb_height).translate_by(
            [0, waist_level, 0])

        # ── 缝合：裙身成圈 ──
        self.stitching_rules = pyg.Stitches(
            # 前后马面 ↔ 左右侧片
            (self.front.interfaces['right'], self.left_side.interfaces['left']),
            (self.left_side.interfaces['right'], self.back.interfaces['right']),
            (self.back.interfaces['left'], self.right_side.interfaces['right']),
            (self.right_side.interfaces['left'], self.front.interfaces['left']),
            # 腰头下缘 ↔ 裙身腰口（褶量在此收拢）
            (self.waistband.interfaces['bottom'], self.front.interfaces['top']),
        )

        # ── 对外接口（供上衣/其他部件对接）──
        self.interfaces = {
            'top': pyg.Interface.from_multiple(self.waistband.interfaces['top']),
            'bottom': pyg.Interface.from_multiple(
                self.front.interfaces['bottom'],
                self.left_side.interfaces['bottom'],
                self.back.interfaces['bottom'],
                self.right_side.interfaces['bottom'],
            ),
        }

    def summary(self):
        return (f'马面裙 | 裙长 {self.design["mamian-skirt"]["length"]["v"]:.2f}×腿长 | '
                f'马面 {self.design["mamian-skirt"]["mamian_width"]["v"]}cm ×2 | '
                f'褶量比 {self.design["mamian-skirt"]["pleat_ruffle"]["v"]} | '
                f'侧片 {self.side_visible:.1f}→{self.side_unfolded:.1f}cm')
