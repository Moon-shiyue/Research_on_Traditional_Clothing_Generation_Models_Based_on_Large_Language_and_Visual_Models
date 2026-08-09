"""
广袖 (Wide Sleeve) — 汉唐经典宽袖组件

参考：汉代曲裾宽袖、唐代大袖衫。袖口宽大，袖身自肘部起向外展放，
呈梯形，以贝塞尔曲线实现平滑起翘。
"""
from ..base import (
    GarmentComponent, ComponentType, Dynasty,
    Panel, SewingEdge, Point2D, StitchType,
)
from ..curves import line, bezier_curve


class WideSleeve(GarmentComponent):
    """广袖 — 袖口宽大、线条流畅的梯形袖片，适用汉、魏晋、唐。

    参数范围：
      - 袖长 50~150cm（默认 90cm）
      - 袖口宽 30~120cm（默认 60cm）
      - 袖根宽 14~28cm（默认 20cm）
      - 起翘比例 0.1~0.5（默认 0.3）
      - 袖山高 8~18cm（默认 13cm）
    """

    compatible_dynasties = [Dynasty.HAN, Dynasty.WEI_JIN, Dynasty.TANG]

    def __init__(self, name="广袖", sleeve_length=90.0, cuff_width=60.0,
                 root_width=20.0, flare_start_ratio=0.3, sleeve_cap_height=13.0,
                 seam_allowance=1.0):
        super().__init__(name=name, component_type=ComponentType.SLEEVE,
                         seam_allowance=seam_allowance)
        # 尺寸参数（单位：cm）
        self.sleeve_length = sleeve_length            # 袖长
        self.cuff_width = cuff_width                  # 袖口宽
        self.root_width = root_width                  # 袖根宽（接衣身处）
        self.flare_start_ratio = flare_start_ratio    # 起翘起始位置比例
        self.sleeve_cap_height = sleeve_cap_height    # 袖山高

    def build_panels(self):
        """构建广袖裁片面板：梯形轮廓 + 贝塞尔起翘 + 弧形袖山。"""
        sl = self.sleeve_length
        cw = self.cuff_width
        rw = self.root_width
        fsr = self.flare_start_ratio
        sch = self.sleeve_cap_height
        sa = self.seam_allowance

        # ── 关键坐标 ──
        flare_y = sl * fsr                           # flare 起始高度

        root_l = Point2D(-rw / 2, 0)                 # 袖根左
        root_r = Point2D(rw / 2, 0)                  # 袖根右
        cuff_l = Point2D(-cw / 2, sl)                # 袖口左
        cuff_r = Point2D(cw / 2, sl)                 # 袖口右
        flare_l = Point2D(-rw / 2, flare_y)          # 左侧 flare 起点
        flare_r = Point2D(rw / 2, flare_y)           # 右侧 flare 起点

        # ── 右侧 flare 贝塞尔曲线（flare起点 → 袖口右端）──
        flare_r_pts = bezier_curve([
            flare_r,
            Point2D(rw / 2 + (cw - rw) * 0.15, flare_y + (sl - flare_y) * 0.4),
            Point2D(cw / 2 - (cw - rw) * 0.10, flare_y + (sl - flare_y) * 0.75),
            cuff_r,
        ], num_points=25)

        # ── 左侧 flare 贝塞尔曲线（袖口左端 → flare起点）──
        flare_l_pts = bezier_curve([
            cuff_l,
            Point2D(-cw / 2 + (cw - rw) * 0.10, flare_y + (sl - flare_y) * 0.75),
            Point2D(-rw / 2 - (cw - rw) * 0.15, flare_y + (sl - flare_y) * 0.4),
            flare_l,
        ], num_points=25)

        # ── 袖山弧形曲线（袖根左 → 袖根右，经袖山顶点）──
        cap_pts = bezier_curve([
            root_l,
            Point2D(-rw * 0.2, -sch),
            Point2D(rw * 0.2, -sch),
            root_r,
        ], num_points=20)

        # ── 构建外轮廓（逆时针闭合）──
        outline = []
        outline.append(root_r)                 # ① 袖根右
        outline.append(flare_r)                # ② flare 右起点
        outline.extend(flare_r_pts[1:])        # ③ 右侧 flare 曲线
        outline.append(cuff_l)                 # ④ 袖口（右→左直线）
        outline.extend(flare_l_pts[1:])        # ⑤ 左侧 flare 曲线
        outline.append(root_l)                 # ⑥ flare 左 → 袖根左
        outline.extend(cap_pts[1:-1])          # ⑦ 袖山曲线（闭合回到袖根右）

        # ── 缝边 ──
        armhole_edge = SewingEdge(
            name="袖窿缝", points=list(cap_pts),
            stitch_type=StitchType.PLAIN_SEAM, seam_allowance=sa,
            mate_edge_name="衣身袖窿",
        )
        cuff_edge = SewingEdge(
            name="袖口褶边", points=[cuff_r, cuff_l],
            stitch_type=StitchType.HEM, seam_allowance=sa, is_hem=True,
        )

        panel = Panel(
            name="广袖裁片", component_type=ComponentType.SLEEVE,
            outline=outline, sewing_edges=[armhole_edge, cuff_edge],
            mirrored=True,  # 左右袖对称
        )
        return [panel]

    def to_garment_code(self):
        """导出 DSL 服装描述代码。"""
        return (
            f"# 广袖 (Wide Sleeve) — 汉唐宽袖\n"
            f"wide_sleeve = SleevePanel(\n"
            f"    style='wide',\n"
            f"    sleeve_length={self.sleeve_length},\n"
            f"    cuff_width={self.cuff_width},\n"
            f"    root_width={self.root_width},\n"
            f"    flare_start_ratio={self.flare_start_ratio},\n"
            f"    sleeve_cap_height={self.sleeve_cap_height},\n"
            f"    seam_allowance={self.seam_allowance},\n"
            f"    mirrored=True,\n"
            f")"
        )

    def validate(self):
        """参数合理性验证。"""
        issues = super().validate()
        if self.cuff_width < self.root_width:
            issues.append(f"[{self.name}] 广袖袖口宽({self.cuff_width}cm)应大于袖根宽({self.root_width}cm)")
        if self.sleeve_length < self.sleeve_cap_height * 2:
            issues.append(f"[{self.name}] 袖长({self.sleeve_length}cm)过短")
        return issues
