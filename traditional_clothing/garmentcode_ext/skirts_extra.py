"""
襦裙 — pygarment 原生实现（批次 4）

对应项目 garment_components/skirts/ruqun_skirt.py。
上襦下裙结构，唐代高腰齐胸穿法最经典。

裁片：前裙片（梯形）+ 后裙片（梯形）+ 腰头系带片（长条）
"""
from __future__ import annotations

import pygarment as pyg


class RuqunSkirtPanel(pyg.Panel):
    """襦裙裙片 — 上窄下宽的梯形（前/后各一）。"""

    def __init__(self, name, half_waist, half_hem, length):
        super().__init__(name)
        # y 负方向 = 向下（裙身自腰口向下延伸）
        self.edges.append(pyg.Edge([0.0, 0.0], [half_waist, 0.0], label='top'))
        self.edges.append(pyg.Edge([half_waist, 0.0], [half_hem, -length],
                                   label='right'))
        self.edges.append(pyg.Edge([half_hem, -length], [0.0, -length],
                                   label='hem'))
        self.edges.close_loop()

        self.interfaces = {
            'top': pyg.Interface(self, self.edges[0]),
            'hem': pyg.Interface(self, self.edges[2]),
            'left': pyg.Interface(self, self.edges[3]),
            'right': pyg.Interface(self, self.edges[1]),
        }


class RuqunWaistbandPanel(pyg.Panel):
    """襦裙腰头系带片 — 横长条，两端延伸为系带。"""

    def __init__(self, name, waist_circ, height, tie_length):
        super().__init__(name)
        w, h, t = waist_circ, height, tie_length
        self.edges.append(pyg.Edge([-t, 0.0], [w + t, 0.0], label='bottom'))
        self.edges.append(pyg.Edge([w + t, 0.0], [w + t, -h], label='right'))
        self.edges.append(pyg.Edge([w + t, -h], [-t, -h], label='top'))
        self.edges.close_loop()

        self.interfaces = {
            'bottom': pyg.Interface(self, self.edges[0]),
            'top': pyg.Interface(self, self.edges[2]),
            'left': pyg.Interface(self, self.edges[3]),
            'right': pyg.Interface(self, self.edges[1]),
        }


class RuqunSkirt(pyg.Component):
    """襦裙下裳 — 汉/唐/宋基础裙式。"""

    def __init__(self, body, design, tag=''):
        super().__init__(f'RuqunSkirt{"_" + tag if tag else ""}')
        self.body = body
        self.design = design
        d = design['ruqun-skirt']

        length = float(d['length']['v']) * body['_leg_length']
        waist_ratio = float(d['waist_ratio']['v'])          # 相对腰围
        hem_ratio = float(d['hem_ratio']['v'])              # 相对腰围（裙摆展宽）
        wb_height = float(d['waistband_width']['v']) * body['hips_line']
        tie_len = float(d['tie_length']['v'])
        waist_pos = float(d['waist_position']['v'])

        waist = body['waist'] * waist_ratio
        hem = waist * hem_ratio
        self.waist_circ = waist

        self.warnings = []
        if waist_pos > 0.9 and length > body['_leg_length'] * 0.95:
            self.warnings.append('齐胸高腰配及地长裙，行走可能不便（形制少见）')
        if hem < waist * 1.5:
            self.warnings.append(f'裙摆展宽不足（hem/waist={hem / waist:.2f}，建议 ≥1.5）')

        self.front = RuqunSkirtPanel('ruqun_front', waist / 2, hem / 2, length)
        self.back = RuqunSkirtPanel('ruqun_back', waist / 2, hem / 2, length)
        self.waistband = RuqunWaistbandPanel('ruqun_waistband', waist,
                                             wb_height, tie_len)

        self.stitching_rules = pyg.Stitches(
            (self.waistband.interfaces['bottom'], self.front.interfaces['top']),
            (self.waistband.interfaces['bottom'], self.back.interfaces['top']),
            (self.front.interfaces['right'], self.back.interfaces['right']),
            (self.front.interfaces['left'], self.back.interfaces['left']),
        )

        self.interfaces = {
            'top': pyg.Interface.from_multiple(self.waistband.interfaces['top']),
            'hem': pyg.Interface.from_multiple(
                self.front.interfaces['hem'], self.back.interfaces['hem']),
        }

    def summary(self):
        d = self.design['ruqun-skirt']
        return (f'襦裙 | 裙长 {d["length"]["v"]:.2f}×腿长 | '
                f'腰围 {self.waist_circ:.1f}cm | '
                f'腰位 {d["waist_position"]["v"]:.2f} | 展宽比 {d["hem_ratio"]["v"]}')
