"""
立领 (Stand Collar) — 直立环绕颈部的领型
明代 2-3cm 高，清代 4-6cm 高。挺拔直立，围绕颈项。
"""
from ..base import (
    GarmentComponent, ComponentType, Dynasty,
    Panel, SewingEdge, Point2D, StitchType,
)
from ..curves import line, bezier_curve
import math


class StandCollar(GarmentComponent):
    """立领 — 直立式领型，围绕颈部竖立。

    明代立领较为低矮（2-3cm），清代立领较高挺（4-6cm），
    民国时期延续清代高领风格。领片为弧形带状裁片，
    底边与衣身领圈缝合，顶边自然竖立。
    """

    compatible_dynasties = [Dynasty.MING, Dynasty.QING]

    def __init__(self, name="立领", component_id=None):
        super().__init__(name=name, comp_type=ComponentType.COLLAR,
                         component_id=component_id or "stand_collar")
        self.description = "立领，直立环绕颈部的领型。明代2-3cm高，清代4-6cm高。"

    def define_params(self):
        self.add_param("collar_height", 4.0, 1.5, 8.0, description="领高")
        self.add_param("neck_circumference", 38.0, 30.0, 50.0, description="颈围")
        self.add_param("stiffness", 0.7, 0.3, 1.0, description="挺括度")
        self.add_param("button_position", 2.0, 1.0, 5.0, description="扣位距顶边")
        self.add_param("collar_flare", 5.0, 0.0, 15.0, unit="度", description="领口外倾角")
        self.add_param("seam_allowance", 1.0, 0.5, 2.0, description="缝份")
        self.add_param("collar_band_top_curve", 1.5, 0.0, 3.0, description="领上缘弧度")

    def build_panels(self):
        panels = []
        ch = self.get_param("collar_height")
        nc = self.get_param("neck_circumference")
        st = self.get_param("stiffness")
        bp = self.get_param("button_position")
        cf = self.get_param("collar_flare")
        sa = self.get_param("seam_allowance")
        tc = self.get_param("collar_band_top_curve")

        # 半颈围（对称裁片，后中对折，只构建右侧一半）
        half_nc = nc / 2.0
        # 外倾角（弧度）→ 顶部外扩量
        flare_rad = math.radians(cf)
        flare_offset = ch * math.tan(flare_rad)

        origin = Point2D(0, 0)

        # 领片四角关键点（逆时针：后中底→前中底→前中顶→后中顶）
        p_cb_bottom = Point2D(origin.x, origin.y)                       # 后中底点
        p_cf_bottom = Point2D(origin.x + half_nc, origin.y)             # 前中底点
        p_cf_top = Point2D(origin.x + half_nc + flare_offset,           # 前中顶点
                           origin.y + ch)                                # （考虑外倾）
        p_cb_top = Point2D(origin.x, origin.y + ch)                     # 后中顶点

        # 领上缘弧度控制点 — 中点向上隆起 collar_band_top_curve
        top_mid_ctrl = Point2D(
            (p_cb_top.x + p_cf_top.x) / 2.0,
            p_cb_top.y + tc,
        )

        curves = [
            # 0: 底边 后中→前中 — 接衣身领圈的缝合边
            line(p_cb_bottom, p_cf_bottom),
            # 1: 前中边 底→顶 — 门襟开口边（扣位在此边上距顶 bp cm）
            line(p_cf_bottom, p_cf_top),
            # 2: 顶边 前中→后中 — 领上缘，弧形微隆
            bezier_curve([p_cf_top, top_mid_ctrl, p_cb_top]),
            # 3: 后中边 顶→底 — 对折线（后中缝合线）
            line(p_cb_top, p_cb_bottom),
        ]

        collar_panel = Panel(
            panel_id=f"{self.component_id}_band",
            name="立领领片",
            curves=curves,
            sewing_edges=[
                SewingEdge(
                    edge_id=f"{self.component_id}_bottom",
                    panel_id=f"{self.component_id}_band",
                    curve=curves[0],
                    stitch_type=StitchType.REGULAR,
                    seam_allowance=sa,
                    label="领底缝边（接衣身领圈）"
                ),
                SewingEdge(
                    edge_id=f"{self.component_id}_top",
                    panel_id=f"{self.component_id}_band",
                    curve=curves[2],
                    stitch_type=StitchType.REGULAR,
                    seam_allowance=sa,
                    label="领上缘缝边"
                ),
                SewingEdge(
                    edge_id=f"{self.component_id}_center",
                    panel_id=f"{self.component_id}_band",
                    curve=curves[3],
                    stitch_type=StitchType.REGULAR,
                    seam_allowance=sa,
                    label="后中缝边（对折/缝合）"
                ),
            ]
        )
        panels.append(collar_panel)

        return panels

    def to_garment_code(self):
        lines = ["# 立领 (Stand Collar / 立领)", "stand_collar = CollarPanel("]
        for n in ["collar_height", "neck_circumference", "stiffness",
                   "button_position", "collar_flare", "collar_band_top_curve"]:
            lines.append(f"    {n}={self.get_param(n)},")
        lines.append("    collar_type=\"stand\",")
        lines.append(")")
        return "\n".join(lines)
