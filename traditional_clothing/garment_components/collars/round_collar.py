"""
圆领 (Round Collar) — 简洁大方的圆形领口
"""
from ..base import GarmentComponent, ComponentType, Dynasty, Panel, SewingEdge, Point2D, StitchType
from ..curves import line, arc, bezier_curve

class RoundCollar(GarmentComponent):
    """圆领"""
    compatible_dynasties = [Dynasty.TANG, Dynasty.SONG, Dynasty.MING]

    def __init__(self, name="圆领", neck_radius=12.0, front_depth=10.0,
                 back_depth=4.0, border_width=2.5, seam_allowance=1.0):
        super().__init__(name=name, component_type=ComponentType.COLLAR, seam_allowance=seam_allowance)
        self.neck_radius = max(8, min(18, neck_radius))
        self.front_depth = max(5, min(18, front_depth))
        self.back_depth = max(2, min(8, back_depth))
        self.border_width = max(1, min(6, border_width))

    def build_panels(self):
        r = self.neck_radius
        fd = self.front_depth
        sa = self.seam_allowance
        # 前领口: 上半圆 + 两侧贝塞尔
        pts1 = arc(Point2D(0, 0), r, -1.57, 1.57, num_points=20)
        pts2 = bezier_curve([Point2D(r, 0), Point2D(r*0.3, fd*0.6), Point2D(0, fd)], num_points=30)
        pts3 = bezier_curve([Point2D(0, fd), Point2D(-r*0.3, fd*0.6), Point2D(-r, 0)], num_points=30)
        outline = pts1[:-1] + pts2[1:-1] + pts3[1:-1]
        panel = Panel(
            name="圆领裁片", component_type=ComponentType.COLLAR, outline=outline,
            sewing_edges=[SewingEdge(name="领口弧线", points=pts1,
                                     stitch_type=StitchType.BINDING, seam_allowance=sa)],
        )
        return [panel]

    def to_garment_code(self):
        return f"# 圆领\nround_collar = CollarPanel(neck_radius={self.neck_radius}, front_depth={self.front_depth}, type='round')"
