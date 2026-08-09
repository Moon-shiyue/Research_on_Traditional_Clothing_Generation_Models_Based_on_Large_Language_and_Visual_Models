"""
半臂 (Banbi) - 唐宋风格半袖短外衣

半臂是一种短袖上衣，袖长至肘部以上，流行于唐代与宋代。
常作为外搭穿着于长袖襦衫之外，兼具实用与装饰功能。

结构特征：
  - 交领右衽（左前片压右前片）
  - 半袖，袖口位于肘部以上
  - 衣长较短，通常至腰胯之间
  - 两侧开衩

面板组成：
  1. 后片  — 背部主体裁片
  2. 左前片 — 左侧前身裁片（含交领延伸）
  3. 右前片 — 右侧前身裁片（含交领延伸）
  4. 左半袖 — 左侧短袖裁片
  5. 右半袖 — 右侧短袖裁片
"""

from __future__ import annotations

import math
from typing import List, Optional, Dict, Any

from ..base import (
    GarmentComponent,
    ComponentType,
    Dynasty,
    Panel,
    SewingEdge,
    Point2D,
    StitchType,
)
from ..curves import line, bezier_curve


class Banbi(GarmentComponent):
    """半臂 - 唐宋时期的半袖短外衣。

    袖长仅及肘部以上，衣身较短，交领右衽。
    适用于唐代与宋代传统服饰搭配。

    Attributes:
        garment_length: 衣长，从肩线到下摆（厘米），范围 40-70，默认 55
        half_sleeve_length: 半袖长，从肩点到袖口（厘米），范围 15-35，默认 25
        chest_width: 胸宽，半幅胸围（厘米），默认 52
        collar_type: 领型，默认 "交领"
        seam_allowance: 缝份宽度（厘米），默认 1.0
    """

    # 兼容朝代
    compatible_dynasties: List[Dynasty] = [Dynasty.TANG, Dynasty.SONG]

    # ── 参数范围常量 ─────────────────────────────────────────────────
    GARMENT_LENGTH_MIN: float = 40.0
    GARMENT_LENGTH_MAX: float = 70.0
    HALF_SLEEVE_LENGTH_MIN: float = 15.0
    HALF_SLEEVE_LENGTH_MAX: float = 35.0

    def __init__(
        self,
        garment_length: float = 55.0,
        half_sleeve_length: float = 25.0,
        chest_width: float = 52.0,
        collar_type: str = "交领",
        seam_allowance: float = 1.0,
    ):
        """初始化半臂部件。

        Args:
            garment_length: 衣长（厘米），范围 40-70
            half_sleeve_length: 半袖长（厘米），范围 15-35
            chest_width: 胸宽，即半幅胸围（厘米）
            collar_type: 领型，支持 "交领"
            seam_allowance: 缝份（厘米）
        """
        super().__init__(
            name="半臂",
            component_type=ComponentType.ACCESSORY,
            seam_allowance=seam_allowance,
        )

        # 主参数
        self.garment_length = max(self.GARMENT_LENGTH_MIN,
                                  min(self.GARMENT_LENGTH_MAX, garment_length))
        self.half_sleeve_length = max(self.HALF_SLEEVE_LENGTH_MIN,
                                      min(self.HALF_SLEEVE_LENGTH_MAX, half_sleeve_length))
        self.chest_width = max(30.0, chest_width)
        self.collar_type = collar_type

        # 缓存派生尺寸
        self._derived: Dict[str, float] = {}
        self._compute_derived_dimensions()

    # ── 派生尺寸计算 ─────────────────────────────────────────────────

    def _compute_derived_dimensions(self) -> None:
        """根据主参数计算所有派生尺寸。"""
        cw = self.chest_width
        gl = self.garment_length

        # 身体面板半幅宽度（后片宽 = 胸宽一半稍减，为交领前片留重叠空间）
        self._derived["back_panel_width"] = cw * 0.48
        self._derived["front_panel_width"] = cw * 0.52 + 8.0  # 前片含交领重叠延伸

        # 领口尺寸
        self._derived["neck_half_width"] = 6.5       # 半领宽
        self._derived["neck_depth_back"] = 2.0        # 后领深
        self._derived["neck_depth_front"] = 5.0       # 前领深

        # 肩部
        self._derived["shoulder_slope"] = 10.0        # 肩斜宽（领口到肩点）
        self._derived["total_shoulder"] = self._derived["shoulder_slope"] * 2 + 13.0

        # 袖窿
        self._derived["armhole_depth"] = 22.0         # 袖窿深
        self._derived["armhole_curve_offset"] = 4.0   # 袖窿弧线控制点偏移

        # 半袖
        self._derived["sleeve_top_width"] = 20.0      # 袖山宽
        self._derived["sleeve_bottom_width"] = 16.0   # 袖口宽
        self._derived["sleeve_cap_height"] = 6.0      # 袖山高

        # 下摆
        self._derived["hem_width_expand"] = 2.0       # 下摆微扩量

        # 交领
        self._derived["collar_overlap"] = 10.0        # 交领重叠量
        self._derived["collar_diag_depth"] = gl * 0.65  # 交领斜线下止点（衣身比例）

    # ── 面板构建入口 ─────────────────────────────────────────────────

    def build_panels(self) -> List[Panel]:
        """构建半臂全部裁片面板。

        Returns:
            包含后片、左前片、右前片、左半袖、右半袖的 Panel 列表。
        """
        panels: List[Panel] = []

        panels.append(self._build_back_panel())
        panels.append(self._build_front_panel("左"))
        panels.append(self._build_front_panel("右"))
        panels.append(self._build_half_sleeve("左"))
        panels.append(self._build_half_sleeve("右"))

        return panels

    # ── 后片 (Back Panel) ────────────────────────────────────────────

    def _build_back_panel(self) -> Panel:
        """构建后片面板。

        后片为对称裁片，中心线为对称轴（对折裁剪）。
        外轮廓：矩形基础上方裁剪出后领弧线，两侧裁剪袖窿。

        坐标系：原点 (0,0) 为左肩点。
        """
        d = self._derived
        bw = d["back_panel_width"]
        gl = self.garment_length
        ah = d["armhole_depth"]
        nw = d["neck_half_width"]
        nbd = d["neck_depth_back"]
        sa = self.seam_allowance

        # ── 外轮廓点（逆时针，从下摆左侧开始）──
        outline: List[Point2D] = []

        # 关键点定义
        left_hem = Point2D(0, gl)                                    # 左下摆
        right_hem = Point2D(bw, gl)                                  # 右下摆
        right_armhole = Point2D(bw, ah)                              # 右腋下 / 袖窿底
        right_shoulder = Point2D(bw, 0)                              # 右肩点
        right_neck = Point2D(bw - d["shoulder_slope"], nbd)          # 右领口
        center_neck = Point2D(bw / 2, nbd)                           # 后领中
        left_neck = Point2D(d["shoulder_slope"], nbd)                # 左领口
        left_shoulder = Point2D(0, 0)                                # 左肩点
        left_armhole = Point2D(0, ah)                                # 左腋下 / 袖窿底

        # 组装轮廓（ccw）：下摆 → 右侧 → 肩顶领弧 → 左侧
        outline.append(left_hem)
        outline.append(right_hem)
        outline.append(right_armhole)
        outline.append(right_shoulder)
        # 后领弧线：右肩 → 后领中 → 左肩，使用贝塞尔曲线
        neck_curve_back = bezier_curve(
            [right_shoulder, right_neck, center_neck, left_neck, left_shoulder],
            num_points=40,
        )
        outline.extend(neck_curve_back[1:])  # 跳过重合的右肩点
        outline.append(left_armhole)

        # ── 缝边 ──
        sewing_edges: List[SewingEdge] = []

        # 左侧缝边（与左前片侧缝缝合）
        left_side_points = [left_armhole, left_hem]
        sewing_edges.append(SewingEdge(
            name="后片-左侧缝",
            points=left_side_points,
            stitch_type=StitchType.PLAIN_SEAM,
            seam_allowance=sa,
            mate_edge_name="左前片-左侧缝",
        ))

        # 右侧缝边（与右前片侧缝缝合）
        right_side_points = [right_armhole, right_hem]
        sewing_edges.append(SewingEdge(
            name="后片-右侧缝",
            points=right_side_points,
            stitch_type=StitchType.PLAIN_SEAM,
            seam_allowance=sa,
            mate_edge_name="右前片-右侧缝",
        ))

        # 袖窿缝合边（与半袖的袖山缝合）
        armhole_points = [left_armhole, left_shoulder]
        armhole_points.extend(neck_curve_back[:1])  # 含肩点
        # 重新组织：左肩点 → 左腋下（袖窿弧线）
        left_armhole_curve = bezier_curve(
            [
                left_shoulder,
                Point2D(0, ah * 0.35),
                Point2D(d["armhole_curve_offset"], ah * 0.7),
                left_armhole,
            ],
            num_points=25,
        )
        sewing_edges.append(SewingEdge(
            name="后片-左袖窿",
            points=left_armhole_curve,
            stitch_type=StitchType.PLAIN_SEAM,
            seam_allowance=sa,
            mate_edge_name="左半袖-袖山",
        ))

        # 右袖窿弧线
        right_armhole_curve = bezier_curve(
            [
                right_shoulder,
                Point2D(bw, ah * 0.35),
                Point2D(bw - d["armhole_curve_offset"], ah * 0.7),
                right_armhole,
            ],
            num_points=25,
        )
        sewing_edges.append(SewingEdge(
            name="后片-右袖窿",
            points=right_armhole_curve,
            stitch_type=StitchType.PLAIN_SEAM,
            seam_allowance=sa,
            mate_edge_name="右半袖-袖山",
        ))

        # 肩缝（与左右前片肩部缝合）
        sewing_edges.append(SewingEdge(
            name="后片-左肩缝",
            points=[left_neck, left_shoulder],
            stitch_type=StitchType.PLAIN_SEAM,
            seam_allowance=sa,
            mate_edge_name="左前片-肩缝",
        ))
        sewing_edges.append(SewingEdge(
            name="后片-右肩缝",
            points=[right_neck, right_shoulder],
            stitch_type=StitchType.PLAIN_SEAM,
            seam_allowance=sa,
            mate_edge_name="右前片-肩缝",
        ))

        # 下摆折边
        hem_points = line(left_hem, right_hem, num_points=0)
        sewing_edges.append(SewingEdge(
            name="后片-下摆",
            points=hem_points,
            stitch_type=StitchType.HEM,
            seam_allowance=2.5,
            is_hem=True,
        ))

        return Panel(
            name="半臂-后片",
            component_type=ComponentType.ACCESSORY,
            outline=outline,
            sewing_edges=sewing_edges,
            grain_angle_rad=0.0,
            fabric_layers=1,
            mirrored=False,
            metadata={
                "piece": "back",
                "garment": "半臂",
                "dynasty": "唐宋",
            },
        )

    # ── 前片 (Front Panel) ───────────────────────────────────────────

    def _build_front_panel(self, side: str) -> Panel:
        """构建前片面板（左前片或右前片）。

        前片特征：
          - 交领斜襟：从肩颈点斜向下至对侧腰部
          - 一侧为侧缝边，另一侧为交领斜边
          - 左前片压在右前片之上（右衽）

        Args:
            side: "左" 或 "右"，指定构建哪一侧的前片。

        坐标系：原点 (0,0) 为肩点（外侧，即靠近袖窿一侧）。
        """
        d = self._derived
        fw = d["front_panel_width"]
        gl = self.garment_length
        ah = d["armhole_depth"]
        nfd = d["neck_depth_front"]
        nbd = d["neck_depth_back"]
        shoulder_slope = d["shoulder_slope"]
        collar_overlap = d["collar_overlap"]
        collar_diag = d["collar_diag_depth"]
        sa = self.seam_allowance

        # ── 关键点 ──
        # 外侧 = 靠近袖窿 / 侧缝一侧
        # 内侧 = 靠近身体中线 / 交领一侧
        outer_shoulder = Point2D(0, 0)                           # 外侧肩点
        neck_point = Point2D(shoulder_slope, 0)                  # 颈侧点（领口外侧）
        outer_armhole = Point2D(0, ah)                           # 外侧腋下
        outer_hem = Point2D(0, gl)                               # 外侧下摆角
        inner_hem = Point2D(fw, gl)                              # 内侧下摆角
        # 交领斜线：从外侧颈侧点斜向下到内侧某位置
        collar_inner_neck = Point2D(fw, -nfd + nbd)              # 内侧领深点（交领内颈点）
        collar_anchor = Point2D(fw, collar_diag)                 # 交领斜线下端锚点

        # ── 外轮廓（ccw）──
        outline: List[Point2D] = []

        if side == "左":
            # 左前片：右衽，左片压右片
            # 外侧 = 左（靠近左袖窿），内侧 = 右（交领重叠部分向右延伸）
            outline.append(outer_hem)                            # 左下摆
            outline.append(inner_hem)                            # 右下摆（交领侧）
            outline.append(Point2D(fw, collar_diag))             # 交领斜线下端
            outline.append(Point2D(fw, -nfd + nbd))              # 交领内颈点（高于肩线，表示领深）

            # 领口弧线：内颈点 → 外颈点
            collar_curve = bezier_curve(
                [
                    Point2D(fw, -nfd + nbd),
                    Point2D(fw * 0.6, -nfd + nbd - 2),
                    Point2D(shoulder_slope * 0.8, nbd * 0.5),
                    neck_point,
                ],
                num_points=30,
            )
            outline.extend(collar_curve[1:])

            outline.append(outer_shoulder)
            outline.append(outer_armhole)

            # ── 缝边 ──
            sewing_edges: List[SewingEdge] = []

            # 外侧缝（与后片左侧缝缝合）
            sewing_edges.append(SewingEdge(
                name="左前片-左侧缝",
                points=[outer_armhole, outer_hem],
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="后片-左侧缝",
            ))

            # 肩缝（与后片左肩缝合）
            sewing_edges.append(SewingEdge(
                name="左前片-肩缝",
                points=[neck_point, outer_shoulder],
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="后片-左肩缝",
            ))

            # 袖窿（与左半袖缝合）
            left_front_armhole = bezier_curve(
                [
                    outer_shoulder,
                    Point2D(0, ah * 0.35),
                    Point2D(d["armhole_curve_offset"], ah * 0.7),
                    outer_armhole,
                ],
                num_points=25,
            )
            sewing_edges.append(SewingEdge(
                name="左前片-袖窿",
                points=left_front_armhole,
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="左半袖-袖山",
            ))

            # 交领斜边（无缝合，为衣襟边缘）
            lapel_points = [Point2D(fw, collar_diag), Point2D(fw, -nfd + nbd)]
            sewing_edges.append(SewingEdge(
                name="左前片-衣襟",
                points=lapel_points,
                stitch_type=StitchType.NONE,
                seam_allowance=0.0,
            ))

            # 下摆折边
            sewing_edges.append(SewingEdge(
                name="左前片-下摆",
                points=line(outer_hem, inner_hem, num_points=0),
                stitch_type=StitchType.HEM,
                seam_allowance=2.5,
                is_hem=True,
            ))

            panel_name = "半臂-左前片"
            metadata = {"piece": "left_front", "garment": "半臂", "dynasty": "唐宋"}

        else:  # side == "右"
            # 右前片：右衽，右片被左片压住
            # 外侧 = 右（靠近右袖窿），内侧 = 左（交领重叠部分向左延伸）
            # 为保持 ccw，坐标系需要镜像翻转

            # 以右袖窿侧为原点 (0,0)，向外侧展开
            outline.append(inner_hem)                            # 左下摆（交领侧）
            outline.append(outer_hem)                            # 右下摆（外侧）
            outline.append(outer_armhole)
            outline.append(outer_shoulder)

            # 领口弧线：外颈点 → 内颈点
            collar_curve_right = bezier_curve(
                [
                    neck_point,
                    Point2D(shoulder_slope * 0.8, nbd * 0.5),
                    Point2D(fw * 0.6, -nfd + nbd - 2),
                    Point2D(fw, -nfd + nbd),
                ],
                num_points=30,
            )
            outline.extend(collar_curve_right[1:])

            outline.append(Point2D(fw, collar_diag))

            # ── 缝边 ──
            sewing_edges: List[SewingEdge] = []

            # 外侧缝（与后片右侧缝缝合）
            sewing_edges.append(SewingEdge(
                name="右前片-右侧缝",
                points=[outer_armhole, outer_hem],
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="后片-右侧缝",
            ))

            # 肩缝（与后片右肩缝合）
            sewing_edges.append(SewingEdge(
                name="右前片-肩缝",
                points=[outer_shoulder, neck_point],
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="后片-右肩缝",
            ))

            # 袖窿（与右半袖缝合）
            right_front_armhole = bezier_curve(
                [
                    outer_shoulder,
                    Point2D(0, ah * 0.35),
                    Point2D(d["armhole_curve_offset"], ah * 0.7),
                    outer_armhole,
                ],
                num_points=25,
            )
            sewing_edges.append(SewingEdge(
                name="右前片-袖窿",
                points=right_front_armhole,
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="右半袖-袖山",
            ))

            # 交领斜边
            sewing_edges.append(SewingEdge(
                name="右前片-衣襟",
                points=[Point2D(fw, -nfd + nbd), Point2D(fw, collar_diag)],
                stitch_type=StitchType.NONE,
                seam_allowance=0.0,
            ))

            # 下摆折边
            sewing_edges.append(SewingEdge(
                name="右前片-下摆",
                points=line(inner_hem, outer_hem, num_points=0),
                stitch_type=StitchType.HEM,
                seam_allowance=2.5,
                is_hem=True,
            ))

            panel_name = "半臂-右前片"
            metadata = {"piece": "right_front", "garment": "半臂", "dynasty": "唐宋"}

        return Panel(
            name=panel_name,
            component_type=ComponentType.ACCESSORY,
            outline=outline,
            sewing_edges=sewing_edges,
            grain_angle_rad=0.0,
            fabric_layers=1,
            mirrored=False,
            metadata=metadata,
        )

    # ── 半袖 (Half Sleeve) ───────────────────────────────────────────

    def _build_half_sleeve(self, side: str) -> Panel:
        """构建半袖面板（左或右）。

        半袖特征：
          - 袖长仅及肘部以上
          - 袖山与身体袖窿缝合
          - 袖口处自然收窄
          - 袖底缝在腋下侧

        坐标系：原点 (0,0) 为袖山中点（肩点对应位置）。
        x 轴正方向为袖长方向（从肩点指向袖口）。

        Args:
            side: "左" 或 "右"
        """
        d = self._derived
        hsl = self.half_sleeve_length     # 半袖长
        stw = d["sleeve_top_width"]       # 袖山宽
        sbw = d["sleeve_bottom_width"]    # 袖口宽
        sch = d["sleeve_cap_height"]      # 袖山高
        sa = self.seam_allowance

        # ── 关键点 ──
        # 袖口端点
        sleeve_end_upper = Point2D(hsl, -sbw / 2 + sch)          # 袖口上侧（靠近肩线方向）
        sleeve_end_lower = Point2D(hsl, sbw / 2 + sch)           # 袖口下侧（靠近腋下方向）

        # 袖山（与身体袖窿缝合的曲线边）
        # 从袖山前侧（前片侧）到袖山后侧（后片侧）
        cap_top = Point2D(0, 0)                                  # 袖山顶（对应肩点）
        cap_front = Point2D(0, sch + stw / 2)                    # 袖山前下角
        cap_back = Point2D(0, sch - stw / 2)                     # 袖山后下角

        # 重新定义：袖山曲线从腋下前侧 → 袖山顶 → 腋下后侧
        # 但这样的 ccw 包围应该是：
        # 腋下后侧 → 袖山顶 → 腋下前侧 → 袖口下侧 → 袖口上侧

        # 实际坐标（袖长沿 +x 方向，袖宽沿 y 方向展开）：
        sleeve_back_bottom = Point2D(0, stw / 2 + sch)           # 腋下后侧（大身侧）
        cap_peak = Point2D(0, 0)                                 # 袖山顶
        sleeve_front_bottom = Point2D(0, -stw / 2 + sch)         # 腋下前侧
        sleeve_upper_end = Point2D(hsl, -sbw / 2 + sch)          # 袖口上端
        sleeve_lower_end = Point2D(hsl, sbw / 2 + sch)           # 袖口下端

        # ── 外轮廓（ccw，从袖口上端开始）──
        outline: List[Point2D] = []

        outline.append(sleeve_upper_end)                         # 袖口上端
        outline.append(sleeve_lower_end)                         # 袖口下端
        outline.append(sleeve_front_bottom)                      # 腋下前侧

        # 袖山曲线（贝塞尔，从腋下前侧经袖山顶到腋下后侧）
        sleeve_cap_curve = bezier_curve(
            [
                sleeve_front_bottom,
                Point2D(0, sch * 0.3),
                cap_peak,
                Point2D(0, sch * 0.3 + stw * 0.5),
                sleeve_back_bottom,
            ],
            num_points=30,
        )
        outline.extend(sleeve_cap_curve[1:])

        # ── 缝边 ──
        sewing_edges: List[SewingEdge] = []

        # 袖山缝边（与身体袖窿缝合）
        sewing_edges.append(SewingEdge(
            name=f"{'左' if side == '左' else '右'}半袖-袖山",
            points=sleeve_cap_curve,
            stitch_type=StitchType.PLAIN_SEAM,
            seam_allowance=sa,
            mate_edge_name=f"{'后片' if side == '左' else '后片'}-{'左' if side == '左' else '右'}袖窿",
        ))

        # 袖底缝（从腋下到袖口）
        sleeve_bottom_seam = line(sleeve_back_bottom, sleeve_lower_end, num_points=0)
        sewing_edges.append(SewingEdge(
            name=f"{'左' if side == '左' else '右'}半袖-袖底缝",
            points=sleeve_bottom_seam,
            stitch_type=StitchType.PLAIN_SEAM,
            seam_allowance=sa,
        ))

        # 袖口卷边
        sleeve_hem = line(sleeve_lower_end, sleeve_upper_end, num_points=0)
        sewing_edges.append(SewingEdge(
            name=f"{'左' if side == '左' else '右'}半袖-袖口",
            points=sleeve_hem,
            stitch_type=StitchType.HEM,
            seam_allowance=2.0,
            is_hem=True,
        ))

        # 袖上缝（从袖山到袖口上端）
        sleeve_top_seam = line(sleeve_back_bottom, sleeve_upper_end, num_points=0)
        sewing_edges.append(SewingEdge(
            name=f"{'左' if side == '左' else '右'}半袖-袖上缝",
            points=sleeve_top_seam,
            stitch_type=StitchType.PLAIN_SEAM,
            seam_allowance=sa,
        ))

        return Panel(
            name=f"半臂-{'左' if side == '左' else '右'}半袖",
            component_type=ComponentType.ACCESSORY,
            outline=outline,
            sewing_edges=sewing_edges,
            grain_angle_rad=math.pi / 2,  # 纹理沿袖长方向
            fabric_layers=1,
            mirrored=(side == "右"),       # 右半袖为左半袖的镜像
            metadata={
                "piece": f"{'left' if side == '左' else 'right'}_half_sleeve",
                "garment": "半臂",
                "sleeve_length": self.half_sleeve_length,
            },
        )

    # ── DSL 代码导出 ──────────────────────────────────────────────────

    def to_garment_code(self) -> str:
        """将半臂部件导出为服装 DSL 描述代码。

        生成的 DSL 包含：
          - 部件元数据
          - 参数定义
          - 裁片面板定义及其几何轮廓
          - 缝合指令（面板配对 + 缝边映射）
          - 工艺说明

        Returns:
            服装 DSL 代码字符串。
        """
        lines: List[str] = []
        self._panels = self.build_panels()

        # ── 文件头 ──
        lines.append("# ============================================================")
        lines.append(f"# 传统服饰 DSL - {self.name}")
        lines.append("# 朝代兼容: 唐代, 宋代")
        lines.append("# 半臂：半袖短外衣，袖长至肘部以上，交领右衽")
        lines.append("# ============================================================")
        lines.append("")

        # ── 部件声明 ──
        lines.append(f"garment {self._safe_identifier(self.name)} {{")
        lines.append(f"    type = \"accessory\"")
        lines.append(f"    category = \"半臂\"")
        lines.append(f"    dynasties = [\"唐\", \"宋\"]")
        lines.append("")
        lines.append("    # ── 参数 ──")
        lines.append(f"    param 衣长 = {self.garment_length:.1f}cm   " +
                     f"# 范围 {self.GARMENT_LENGTH_MIN:.0f}-{self.GARMENT_LENGTH_MAX:.0f}")
        lines.append(f"    param 半袖长 = {self.half_sleeve_length:.1f}cm " +
                     f"# 范围 {self.HALF_SLEEVE_LENGTH_MIN:.0f}-{self.HALF_SLEEVE_LENGTH_MAX:.0f}")
        lines.append(f"    param 胸宽 = {self.chest_width:.1f}cm")
        lines.append(f"    param 领型 = \"{self.collar_type}\"")
        lines.append(f"    param 缝份 = {self.seam_allowance:.1f}cm")
        lines.append("")

        # ── 面板定义 ──
        lines.append("    # ── 裁片面板 ──")
        for i, panel in enumerate(self._panels):
            panel_id = self._safe_identifier(panel.name)
            lines.append(f"    panel {panel_id} {{")
            lines.append(f"        label = \"{panel.name}\"")
            lines.append(f"        fabric_layers = {panel.fabric_layers}")
            lines.append(f"        mirrored = {str(panel.mirrored).lower()}")
            lines.append(f"        grain_angle = {panel.grain_angle_rad:.4f}rad")

            # 外轮廓
            if panel.outline:
                lines.append("")
                lines.append("        # 外轮廓 (ccw)")
                lines.append(f"        outline (count={len(panel.outline)}) {{")
                for pt in panel.outline:
                    lines.append(f"            ({pt.x:.2f}, {pt.y:.2f})")
                lines.append("        }")

            # 缝边
            if panel.sewing_edges:
                lines.append("")
                lines.append("        # 缝边定义")
                for edge in panel.sewing_edges:
                    edge_id = self._safe_identifier(edge.name)
                    lines.append(f"        sewing_edge {edge_id} {{")
                    lines.append(f"            stitch = {edge.stitch_type.name}")
                    lines.append(f"            seam_allowance = {edge.seam_allowance:.1f}")
                    lines.append(f"            is_hem = {str(edge.is_hem).lower()}")
                    if edge.mate_edge_name:
                        lines.append(f"            mate = {self._safe_identifier(edge.mate_edge_name)}")
                    lines.append(f"            points (count={len(edge.points)}) {{")
                    for pt in edge.points:
                        lines.append(f"                ({pt.x:.2f}, {pt.y:.2f})")
                    lines.append("            }")
                    lines.append("        }")

            # 元数据
            if panel.metadata:
                lines.append("")
                lines.append("        # 元数据")
                lines.append("        metadata {")
                for k, v in panel.metadata.items():
                    if isinstance(v, str):
                        lines.append(f"            {k} = \"{v}\"")
                    else:
                        lines.append(f"            {k} = {v}")
                lines.append("        }")

            lines.append("    }")
            lines.append("")

        # ── 缝合指令 ──
        lines.append("    # ── 缝合指令 ──")
        seam_pairs = self._collect_seam_pairs()
        for i, (edge_a, edge_b) in enumerate(seam_pairs):
            lines.append(f"    stitch seam_{i+1:02d} {{")
            lines.append(f"        edge_a = {self._safe_identifier(edge_a.name)}")
            lines.append(f"        edge_b = {self._safe_identifier(edge_b.name)}")
            lines.append(f"        type = {edge_a.stitch_type.name}")
            lines.append(f"        allowance = {edge_a.seam_allowance:.1f}")
            lines.append("    }")

        # ── 工艺说明 ──
        lines.append("")
        lines.append("    # ── 工艺说明 ──")
        lines.append("    construction_notes {")
        lines.append("        step_1 = \"缝合左右肩缝：后片-肩缝 与 前片-肩缝\"")
        lines.append("        step_2 = \"缝合左右半袖：半袖-袖山 与 前后片-袖窿\"")
        lines.append("        step_3 = \"缝合侧缝：后片-侧缝 与 前片-侧缝（含袖底缝）\"")
        lines.append("        step_4 = \"处理下摆和袖口卷边\"")
        lines.append("        step_5 = \"交领衣襟按右衽方式整理成形\"")
        lines.append("    }")
        lines.append("")

        lines.append("    # ── 派生尺寸 ──")
        for key, val in self._derived.items():
            lines.append(f"    derived {key} = {val:.2f}")
        lines.append("")

        lines.append("}")  # end garment
        lines.append("")

        return "\n".join(lines)

    # ── 辅助方法 ──────────────────────────────────────────────────────

    def _collect_seam_pairs(self) -> List[tuple]:
        """收集所有缝边配对，用于 DSL 缝合指令生成。

        遍历各面板的 sewing_edges，查找 mate_edge_name 不为空的边，
        并与其配对边组成缝合对。

        Returns:
            (sewing_edge, mate_sewing_edge) 元组列表。
        """
        pairs: List[tuple] = []
        # 构建边名到 (panel, edge) 的映射
        edge_map: Dict[str, SewingEdge] = {}
        for panel in self._panels:
            for edge in panel.sewing_edges:
                # 使用 "面板名-边名" 作为全限定标识
                full_name = f"{panel.name}-{edge.name}"
                edge_map[full_name] = edge

        # 收集配对
        seen: set = set()
        for panel in self._panels:
            for edge in panel.sewing_edges:
                if edge.mate_edge_name and edge.mate_edge_name in edge_map:
                    key = tuple(sorted([f"{panel.name}-{edge.name}", edge.mate_edge_name]))
                    if key not in seen:
                        seen.add(key)
                        pairs.append((edge, edge_map[edge.mate_edge_name]))

        return pairs

    @staticmethod
    def _safe_identifier(name: str) -> str:
        """将中文名称转换为安全的 DSL 标识符。"""
        # 保留中文字符，将特殊字符替换为下划线
        result = name.strip()
        # 移除或替换不安全的字符
        unsafe = " -（）()[]{},.:;!@#$%^&*+=|\\/\"'`~"
        for ch in unsafe:
            result = result.replace(ch, "_")
        # 压缩连续下划线
        while "__" in result:
            result = result.replace("__", "_")
        return result.strip("_")

    # ── 验证 ──────────────────────────────────────────────────────────

    def validate(self) -> List[str]:
        """验证半臂参数合理性。

        Returns:
            警告/错误信息列表。空列表表示一切正常。
        """
        issues = super().validate()

        if self.collar_type not in ("交领",):
            issues.append(f"[{self.name}] 不支持的领型 '{self.collar_type}'，" +
                          "当前仅支持 '交领'")

        if self.garment_length < self.GARMENT_LENGTH_MIN:
            issues.append(f"[{self.name}] 衣长 {self.garment_length}cm 小于最小值 " +
                          f"{self.GARMENT_LENGTH_MIN}cm，已自动修正")
        if self.garment_length > self.GARMENT_LENGTH_MAX:
            issues.append(f"[{self.name}] 衣长 {self.garment_length}cm 超过最大值 " +
                          f"{self.GARMENT_LENGTH_MAX}cm，已自动修正")

        if self.half_sleeve_length < self.HALF_SLEEVE_LENGTH_MIN:
            issues.append(f"[{self.name}] 半袖长 {self.half_sleeve_length}cm 小于最小值 " +
                          f"{self.HALF_SLEEVE_LENGTH_MIN}cm，已自动修正")
        if self.half_sleeve_length > self.HALF_SLEEVE_LENGTH_MAX:
            issues.append(f"[{self.name}] 半袖长 {self.half_sleeve_length}cm 超过最大值 " +
                          f"{self.HALF_SLEEVE_LENGTH_MAX}cm，已自动修正")

        if self.half_sleeve_length >= self.garment_length * 0.7:
            issues.append(f"[{self.name}] 半袖长 ({self.half_sleeve_length}cm) " +
                          "接近衣长，不符合半臂短袖特征")

        return issues

    # ── 便捷信息 ──────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"Banbi(衣长={self.garment_length}cm, 半袖长={self.half_sleeve_length}cm, "
            f"胸宽={self.chest_width}cm, 领型='{self.collar_type}')"
        )

    def summary(self) -> Dict[str, Any]:
        """返回半臂部件的摘要信息。"""
        return {
            "名称": self.name,
            "类型": "半臂（半袖短外衣）",
            "朝代": ["唐", "宋"],
            "衣长_cm": self.garment_length,
            "半袖长_cm": self.half_sleeve_length,
            "胸宽_cm": self.chest_width,
            "领型": self.collar_type,
            "缝份_cm": self.seam_allowance,
            "面板数量": len(self._panels),
            "面板列表": [p.name for p in self._panels],
            "派生尺寸": self._derived,
        }
