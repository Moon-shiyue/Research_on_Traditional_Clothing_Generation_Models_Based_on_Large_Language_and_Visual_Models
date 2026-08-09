"""
襦裙 (Ruqun Skirt) — 汉/唐/宋时期的基础裙式
上襦下裙结构，唐代高腰齐胸穿法最为经典。
"""
from __future__ import annotations
from typing import List
from ..base import GarmentComponent, ComponentType, Dynasty, Panel, SewingEdge, Point2D, StitchType
from ..curves import line, bezier_curve

class RuqunSkirt(GarmentComponent):
    """襦裙下裳 — 上襦下裙，系带长裙，裙摆宽大飘逸。"""
    compatible_dynasties: List[Dynasty] = [Dynasty.HAN, Dynasty.TANG, Dynasty.SONG]

    def __init__(self, name="襦裙", skirt_length=100.0, waist_circumference=70.0,
                 hem_width=180.0, waistband_height=5.0, pleat_count=12,
                 tie_length=80.0, waist_position=0.75, seam_allowance=1.0):
        super().__init__(name=name, component_type=ComponentType.SKIRT, seam_allowance=seam_allowance)
        self.skirt_length = max(70, min(130, skirt_length))
        self.waist_circumference = max(55, min(100, waist_circumference))
        self.hem_width = max(100, min(300, hem_width))
        self.waistband_height = max(3, min(8, waistband_height))
        self.pleat_count = max(4, min(24, pleat_count))
        self.tie_length = max(50, min(150, tie_length))
        self.waist_position = max(0.5, min(0.95, waist_position))

    def build_panels(self) -> List[Panel]:
        panels = []
        hw = self.waist_circumference / 2
        hh = self.hem_width / 2
        L = self.skirt_length
        sa = self.seam_allowance

        # 前裙片（梯形）
        front = Panel(
            name="前裙片",
            component_type=ComponentType.SKIRT,
            outline=[Point2D(0, 0), Point2D(hw, 0), Point2D(hh, -L), Point2D(0, -L)],
            sewing_edges=[SewingEdge(name="前裙上缘", points=[Point2D(0, 0), Point2D(hw, 0)],
                                     stitch_type=StitchType.PLAIN_SEAM, seam_allowance=sa,
                                     mate_edge_name="腰头底边")],
        )
        panels.append(front)

        # 后裙片
        back = Panel(
            name="后裙片",
            component_type=ComponentType.SKIRT,
            outline=[Point2D(0, 0), Point2D(hw, 0), Point2D(hh, -L), Point2D(0, -L)],
            sewing_edges=[SewingEdge(name="后裙上缘", points=[Point2D(0, 0), Point2D(hw, 0)],
                                     stitch_type=StitchType.PLAIN_SEAM, seam_allowance=sa)],
        )
        panels.append(back)

        # 腰头系带片
        bw = self.waist_circumference
        H = self.waistband_height
        T = self.tie_length
        wb = Panel(
            name="腰头系带片",
            component_type=ComponentType.SKIRT,
            outline=[Point2D(-T, 0), Point2D(bw + T, 0), Point2D(bw + T, H), Point2D(-T, H)],
        )
        panels.append(wb)
        return panels

    def to_garment_code(self) -> str:
        lines = ["# 襦裙 (Ruqun Skirt)", "ruqun_skirt = SkirtPanel("]
        for n in ["skirt_length", "waist_circumference", "hem_width",
                   "waistband_height", "pleat_count", "tie_length", "waist_position"]:
            lines.append(f"    {n}={getattr(self, n)},")
        lines.append("    type='ruqun'")
        lines.append(")")
        return "\n".join(lines)
