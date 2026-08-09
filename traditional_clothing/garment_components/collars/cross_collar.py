"""
交领 (Cross Collar / Jiaoling) — 中国最经典的领型部件

交领右衽是汉族传统服饰的标志性领型，呈 Y 形交叉结构。
左前襟压右前襟（右衽），广泛用于汉、魏晋、唐、宋、明各朝代的
深衣、袍服、襦裙等服饰中。

结构特征：
  - Y 形交叉：左前领片（外层）覆盖右前领片（内层）
  - 三片式结构：左前领片、右前领片、后领片
  - 领缘装饰边（border_width）沿外缘分布
  - cross_angle 控制交叉角度，collar_depth 控制领深
  - curve_radius 控制领口弧线的圆润程度
"""

from __future__ import annotations

import math
from typing import List

from ..base import (
    GarmentComponent, ComponentType, Dynasty,
    Panel, SewingEdge, Point2D, StitchType,
)
from ..curves import line, bezier_curve

# 贝塞尔曲线采样密度
_NECKLINE_POINTS = 30
_OUTER_EDGE_POINTS = 24


class CrossCollar(GarmentComponent):
    """交领右衽 — Y 形交叉领型。

    三片式结构：左前领片（外层）覆盖右前领片（内层），
    后领片连接两侧形成完整领部。
    适配汉、魏晋、唐、宋、明各朝代。
    """

    # 交领为汉族传统服饰各朝代通用领型
    # 注：Dynasty 枚举不含魏晋，魏晋时期服饰可归入汉制参考
    compatible_dynasties: List[Dynasty] = [
        Dynasty.HAN,
        Dynasty.TANG,
        Dynasty.SONG,
        Dynasty.MING,
    ]

    def __init__(
        self,
        name: str = "交领",
        collar_width: float = 20.0,
        collar_depth: float = 25.0,
        cross_angle: float = 50.0,
        border_width: float = 3.0,
        overlap_amount: float = 8.0,
        curve_radius: float = 4.0,
        front_neck_depth: float = 8.0,
        back_neck_depth: float = 3.0,
        seam_allowance: float = 1.0,
    ):
        """初始化交领参数。

        Args:
            name: 部件名称
            collar_width: 领宽（厘米），后领口半宽，范围 12~30
            collar_depth: 领深（厘米），交叉延伸长度，范围 15~40
            cross_angle: 交叉角度（度），单侧偏离垂直方向的角度，范围 30~70
            border_width: 缘边宽度（厘米），领缘装饰带宽度，范围 1~8
            overlap_amount: 左右襟重叠量（厘米），左襟超出右襟的量，范围 4~15
            curve_radius: 领口弧线半径（厘米），控制前领弧线曲率，范围 1~10
            front_neck_depth: 前领深（厘米），领口前沿下挖深度，范围 5~15
            back_neck_depth: 后领深（厘米），领口后沿下挖深度，范围 1.5~6
            seam_allowance: 缝份（厘米），范围 0.5~2
        """
        super().__init__(
            name=name,
            component_type=ComponentType.COLLAR,
            seam_allowance=seam_allowance,
        )
        # 参数钳位
        self.collar_width = max(12.0, min(30.0, collar_width))
        self.collar_depth = max(15.0, min(40.0, collar_depth))
        self.cross_angle = max(30.0, min(70.0, cross_angle))
        self.border_width = max(1.0, min(8.0, border_width))
        self.overlap_amount = max(4.0, min(15.0, overlap_amount))
        self.curve_radius = max(1.0, min(10.0, curve_radius))
        self.front_neck_depth = max(5.0, min(15.0, front_neck_depth))
        self.back_neck_depth = max(1.5, min(6.0, back_neck_depth))

    # ─── 派生几何参数 ─────────────────────────────────────────────
    @property
    def _cross_angle_rad(self) -> float:
        """交叉角度（弧度）。"""
        return math.radians(self.cross_angle)

    @property
    def _half_cross_rad(self) -> float:
        """半交叉角（弧度），左右领片各偏一半。"""
        return math.radians(self.cross_angle / 2.0)

    # ─── 关键点计算 ───────────────────────────────────────────────
    def _build_back_panel(self) -> Panel:
        """构建后领片 — 连接左右前领片的矩形面板。

        后领片位于领口后方，是一块弧形条带。
        坐标系原点 (0,0) 为后领口中点。
        """
        cw = self.collar_width
        bnd = self.back_neck_depth

        # 轮廓（逆时针）：左上 → 右上 → 右下 → 左下
        outline = [
            Point2D(-cw, 0),          # 后领左上角（接左前领片）
            Point2D(cw, 0),           # 后领右上角（接右前领片）
            Point2D(cw, -bnd),        # 后领右下角
            Point2D(-cw, -bnd),       # 后领左下角
        ]

        # 上边 — 与左/右前领片缝合
        top_edge = SewingEdge(
            name="后领上边（接前领片）",
            points=[outline[0], outline[1]],
            stitch_type=StitchType.PLAIN_SEAM,
            seam_allowance=self.seam_allowance,
            mate_edge_name="前领片后接边",
        )

        # 下边 — 与衣身领口缝合
        bottom_edge = SewingEdge(
            name="后领下边（接衣身）",
            points=[outline[3], outline[2]],  # 逆向：左下→右下
            stitch_type=StitchType.PLAIN_SEAM,
            seam_allowance=self.seam_allowance,
            mate_edge_name="衣身后领口",
        )

        return Panel(
            name="后领片",
            component_type=ComponentType.COLLAR,
            outline=outline,
            sewing_edges=[top_edge, bottom_edge],
            grain_angle_rad=0.0,
            fabric_layers=1,
            metadata={"panel_side": "back"},
        )

    def _build_front_panel(self, side: str) -> Panel:
        """构建前领片（左外层或右内层）。

        Args:
            side: 'left' 为左前领片（外层，覆盖于上），
                  'right' 为右前领片（内层，被覆盖）。

        面板轮廓（逆时针）：
          1. 后连接点（领口后端）
          2. 领口弧线 → 前领深点（中心）
          3. 交叉延伸线 → 交叉下端点
          4. 外缘弧线 → 返回后连接点
        """
        cw = self.collar_width
        cd = self.collar_depth
        bw = self.border_width
        ov = self.overlap_amount
        fnd = self.front_neck_depth
        cr = self.curve_radius
        is_outer = (side == "left")

        # 符号系数：左侧 = +1（向右交叉），右侧 = -1（向左交叉）
        sign = 1.0 if is_outer else -1.0

        # ── 关键点 ──
        # A — 后领连接点
        pt_back = Point2D(-sign * cw, 0)

        # B — 前领深点（领口中心最低点）
        pt_front_neck = Point2D(0, -fnd)

        # C — 交叉延伸端点
        # 左领（外层）向右下延伸，右领（内层）向左下延伸
        # 左领延伸量含 overlap_amount，使外层覆盖更为饱满
        ext_len = cd + (ov * 0.6 if is_outer else 0)
        cross_dir = -math.pi / 2 + sign * self._half_cross_rad
        pt_cross = pt_front_neck.polar(ext_len, cross_dir)

        # D — 外缘下角（向外偏移 border_width）
        # 垂直于交叉方向的"外侧"
        outward_angle = sign * (math.pi / 2 + self._half_cross_rad)
        pt_outer_bottom = pt_cross.polar(bw, outward_angle)

        # E — 外缘上角（后领外侧收束点）
        pt_outer_top = Point2D(
            -sign * (cw + bw * 0.85),
            -2.0,
        )

        # ── 各段轮廓线 ──
        # 段1：后连接点 → 前领深点（领口弧线，贝塞尔曲线）
        neckline_cp1 = Point2D(
            pt_back.x + sign * cr * 0.4,
            pt_back.y - fnd * 0.3,
        )
        neckline_cp2 = Point2D(
            pt_front_neck.x - sign * cr * 0.3,
            pt_front_neck.y + fnd * 0.25,
        )
        neckline_pts = bezier_curve(
            [pt_back, neckline_cp1, neckline_cp2, pt_front_neck],
            num_points=_NECKLINE_POINTS,
        )

        # 段2：前领深点 → 交叉端点（直线）
        cross_pts = line(pt_front_neck, pt_cross, num_points=0)

        # 段3：交叉端点 → 外缘下角（直线过渡）
        bottom_pts = line(pt_cross, pt_outer_bottom, num_points=0)

        # 段4：外缘下角 → 外缘上角（外缘弧线，贝塞尔曲线）
        outer_cp = Point2D(
            pt_outer_bottom.x + sign * bw * 0.5,
            (pt_outer_bottom.y + pt_outer_top.y) / 2,
        )
        outer_pts = bezier_curve(
            [pt_outer_bottom, outer_cp, pt_outer_top],
            num_points=_OUTER_EDGE_POINTS,
        )

        # 段5：外缘上角 → 后连接点（闭合边）
        close_pts = line(pt_outer_top, pt_back, num_points=0)

        # ── 组装轮廓（逆时针） ──
        outline: List[Point2D] = []
        outline.extend(neckline_pts)
        outline.extend(cross_pts[1:])       # 跳过与 neckline 末点重合
        outline.extend(bottom_pts[1:])       # 跳过与 cross 末点重合
        outline.extend(outer_pts[1:])        # 跳过与 bottom 末点重合
        outline.extend(close_pts[1:-1])      # 跳过首尾重合点

        # ── 缝边定义 ──
        n_neck = len(neckline_pts)
        n_cross = len(cross_pts) - 1
        n_bottom = len(bottom_pts) - 1
        n_outer = len(outer_pts) - 1

        neck_edge = SewingEdge(
            name=f"{'左' if is_outer else '右'}前领片_领口边",
            points=outline[:n_neck],
            stitch_type=StitchType.PLAIN_SEAM,
            seam_allowance=self.seam_allowance,
            mate_edge_name="衣身前领口",
        )

        cross_edge = SewingEdge(
            name=f"{'左' if is_outer else '右'}前领片_交叉边",
            points=outline[n_neck : n_neck + n_cross],
            stitch_type=StitchType.NONE,
            seam_allowance=0.0,
            is_hem=True,
        )

        # 外缘 + 闭合边合并为外缘装饰边
        outer_full = (
            outline[n_neck + n_cross + n_bottom :]
            + [outline[0]]
        )
        outer_edge = SewingEdge(
            name=f"{'左' if is_outer else '右'}前领片_外缘",
            points=outer_full,
            stitch_type=StitchType.HEM,
            seam_allowance=self.border_width,
            is_hem=True,
        )

        side_label = "左前领片（外层）" if is_outer else "右前领片（内层）"
        return Panel(
            name=side_label,
            component_type=ComponentType.COLLAR,
            outline=outline,
            sewing_edges=[neck_edge, cross_edge, outer_edge],
            grain_angle_rad=0.0,
            fabric_layers=1,
            metadata={
                "panel_side": side,
                "is_outer": is_outer,
                "cross_angle_deg": self.cross_angle,
                "overlap_amount": self.overlap_amount,
            },
        )

    # ─── build_panels ────────────────────────────────────────────
    def build_panels(self) -> List[Panel]:
        """构建交领的全部裁片面板。

        Returns:
            包含左前领片（外层）、右前领片（内层）、后领片的面板列表。
        """
        panels: List[Panel] = []

        # 后领片
        panels.append(self._build_back_panel())

        # 左前领片（外层，覆盖于上，右衽特征）
        panels.append(self._build_front_panel(side="left"))

        # 右前领片（内层，被覆盖）
        panels.append(self._build_front_panel(side="right"))

        return panels

    # ─── to_garment_code ──────────────────────────────────────────
    def to_garment_code(self) -> str:
        """导出交领的服装 DSL 代码。

        DSL 格式示例:
            COLLAR 交领 {
                TYPE CrossCollar
                DYNASTY 汉，唐，宋，明
                COLLAR_WIDTH 20.0
                COLLAR_DEPTH 25.0
                CROSS_ANGLE 50.0
                BORDER_WIDTH 3.0
                OVERLAP_AMOUNT 8.0
                CURVE_RADIUS 4.0
                FRONT_NECK_DEPTH 8.0
                BACK_NECK_DEPTH 3.0
                LEFT_OVER_RIGHT true
                SEAM_ALLOWANCE 1.0
            }
        """
        dynasty_names = "，".join(d.value for d in self.compatible_dynasties)
        lines = [
            f"COLLAR {self.name} {{",
            f"    TYPE CrossCollar",
            f"    DYNASTY {dynasty_names}",
            f"    COLLAR_WIDTH {self.collar_width:.1f}",
            f"    COLLAR_DEPTH {self.collar_depth:.1f}",
            f"    CROSS_ANGLE {self.cross_angle:.1f}",
            f"    BORDER_WIDTH {self.border_width:.1f}",
            f"    OVERLAP_AMOUNT {self.overlap_amount:.1f}",
            f"    CURVE_RADIUS {self.curve_radius:.1f}",
            f"    FRONT_NECK_DEPTH {self.front_neck_depth:.1f}",
            f"    BACK_NECK_DEPTH {self.back_neck_depth:.1f}",
            f"    LEFT_OVER_RIGHT true   # 右衽：左襟压右襟",
            f"    SEAM_ALLOWANCE {self.seam_allowance:.1f}",
            f"}}",
        ]
        return "\n".join(lines)

    # ─── validate ─────────────────────────────────────────────────
    def validate(self) -> List[str]:
        """验证参数合理性。"""
        issues = super().validate()
        if self.collar_width < 12:
            issues.append(f"[{self.name}] 领宽过小（{self.collar_width:.0f}cm），建议 ≥12cm")
        if self.collar_width > 30:
            issues.append(f"[{self.name}] 领宽过大（{self.collar_width:.0f}cm），建议 ≤30cm")
        if self.collar_depth < 15:
            issues.append(f"[{self.name}] 领深过浅（{self.collar_depth:.0f}cm），建议 ≥15cm")
        if self.collar_depth > 40:
            issues.append(f"[{self.name}] 领深过深（{self.collar_depth:.0f}cm），建议 ≤40cm")
        if self.cross_angle < 30:
            issues.append(f"[{self.name}] 交叉角度过小（{self.cross_angle:.0f}°），Y 形不明显")
        if self.cross_angle > 70:
            issues.append(f"[{self.name}] 交叉角度过大（{self.cross_angle:.0f}°），领型过宽")
        if self.overlap_amount < 2:
            issues.append(f"[{self.name}] 重叠量过小（{self.overlap_amount:.0f}cm），左右襟可能无法正确覆盖")
        if self.front_neck_depth < self.back_neck_depth:
            issues.append(
                f"[{self.name}] 前领深（{self.front_neck_depth:.0f}cm）应大于后领深"
                f"（{self.back_neck_depth:.0f}cm）"
            )
        if self.curve_radius > self.front_neck_depth:
            issues.append(
                f"[{self.name}] 弧线半径（{self.curve_radius:.0f}cm）不应超过前领深"
                f"（{self.front_neck_depth:.0f}cm）"
            )
        return issues

    def __repr__(self) -> str:
        return (
            f"CrossCollar(name='{self.name}', width={self.collar_width:.0f}cm, "
            f"depth={self.collar_depth:.0f}cm, angle={self.cross_angle:.0f}°, "
            f"overlap={self.overlap_amount:.0f}cm, "
            f"dynasties={[d.value for d in self.compatible_dynasties]})"
        )
