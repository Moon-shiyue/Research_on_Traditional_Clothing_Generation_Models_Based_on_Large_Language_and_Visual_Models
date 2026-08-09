"""
对襟 (Duijin / Parallel-Front Collar) — 宋明常用门襟样式
"""
from ..base import GarmentComponent, ComponentType, Dynasty, Panel, SewingEdge, Point2D, StitchType
from ..curves import line, bezier_curve

class DuijinCollar(GarmentComponent):
    """对襟 — 左右衣襟正中对齐闭合"""
    compatible_dynasties = [Dynasty.SONG, Dynasty.MING]

    def __init__(self, name="对襟", front_width=8.0, neck_depth=12.0,
                 placket_width=3.0, button_count=3, collar_stand_height=1.0,
                 seam_allowance=1.0):
        super().__init__(name=name, component_type=ComponentType.COLLAR, seam_allowance=seam_allowance)
        self.front_width = max(4, min(15, front_width))
        self.neck_depth = max(6, min(22, neck_depth))
        self.placket_width = max(1.5, min(6, placket_width))
        self.button_count = button_count
        self.collar_stand_height = max(0, min(3, collar_stand_height))

    def build_panels(self):
        fw = self.front_width
        nd = self.neck_depth
        pw = self.placket_width
        panels = []
        # 右前对襟片
        r_pts = line(Point2D(0, 0), Point2D(fw, 0))
        r_pts += bezier_curve([Point2D(fw, 0), Point2D(fw*0.4, nd*0.5), Point2D(0, nd)], num_points=20)
        r_pts += line(Point2D(0, nd), Point2D(0, nd+5))
        r_pts += line(Point2D(0, nd+5), Point2D(fw+pw, nd+5))
        r_pts += line(Point2D(fw+pw, nd+5), Point2D(fw+pw, 0))
        panels.append(Panel(name="右前对襟片", component_type=ComponentType.COLLAR, outline=r_pts))
        # 左前对襟片
        l_pts = line(Point2D(-fw, 0), Point2D(0, 0))
        l_pts += bezier_curve([Point2D(-fw, 0), Point2D(-fw*0.4, nd*0.5), Point2D(0, nd)], num_points=20)
        l_pts += line(Point2D(0, nd), Point2D(0, nd+5))
        l_pts += line(Point2D(0, nd+5), Point2D(-fw-pw, nd+5))
        l_pts += line(Point2D(-fw-pw, nd+5), Point2D(-fw-pw, 0))
        panels.append(Panel(name="左前对襟片", component_type=ComponentType.COLLAR, outline=l_pts))
        return panels

    def to_garment_code(self):
        return f"# 对襟\nduijin_collar = CollarPanel(front_width={self.front_width}, type='duijin')"
