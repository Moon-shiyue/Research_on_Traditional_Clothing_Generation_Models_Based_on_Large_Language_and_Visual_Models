"""
褙子 (Beizi)

宋代最具代表性的外衣，对襟直领、两侧高开衩、
长度及膝或及踝，穿于襦裙之外。明代褙子形制略有差异。

褙子为直身长背心式外衣，无扣敞开，两侧开衩自下摆向上，
袖型多为窄袖或直袖。宋制褙子长至膝下甚至及踝，
明制褙子稍短，多在膝上。

参数：衣长、肩宽、胸宽、开衩高、袖长、领型
朝代兼容：宋、明
"""

from __future__ import annotations

import math
from typing import List, Optional, Dict, Any, Tuple

from ..base import (
    GarmentComponent, ComponentType, Dynasty,
    Panel, SewingEdge, Point2D, StitchType,
)
from ..curves import line, bezier_curve


# 领型编码映射
COLLAR_TYPE_MAP: Dict[int, str] = {
    0: "交领",
    1: "对襟",
    2: "圆领",
}


class Beizi(GarmentComponent):
    """褙子 - 宋制对襟长背心，无扣敞开，两侧高开衩。"""

    # 朝代兼容性（类变量）
    compatible_dynasties: List[Dynasty] = [Dynasty.SONG, Dynasty.MING]

    def __init__(
        self,
        name: str = "褙子",
        garment_length: float = 110.0,
        shoulder_width: float = 38.0,
        chest_width: float = 55.0,
        slit_height: float = 45.0,
        collar_type: int = 1,
        sleeve_length: float = 60.0,
        seam_allowance: float = 1.0,
    ):
        """
        初始化褙子部件。

        Args:
            name: 部件名称
            garment_length: 衣长（后中量，从后领中点至下摆），80-140cm
            shoulder_width: 肩宽（左肩点至右肩点），32-48cm
            chest_width: 胸宽（平铺，腋下横量），45-75cm
            slit_height: 侧开衩高度（从下摆向上量），25-80cm
            collar_type: 领型 0=交领 1=对襟 2=圆领
            sleeve_length: 袖长（肩点至袖口），45-85cm
            seam_allowance: 缝份（厘米），0.5-2.0cm
        """
        super().__init__(
            name=name,
            component_type=ComponentType.ACCESSORY,
            seam_allowance=seam_allowance,
        )

        # 尺寸参数
        self.garment_length = garment_length
        self.shoulder_width = shoulder_width
        self.chest_width = chest_width
        self.slit_height = slit_height
        self.collar_type = collar_type
        self.sleeve_length = sleeve_length

        # 参数范围校验
        self._validate_params()

    # ── 参数校验 ─────────────────────────────────────────────────

    def _validate_params(self) -> None:
        """校验参数范围，超出范围时给出警告但不中断构建。"""
        checks: List[Tuple[float, float, float, str]] = [
            (self.garment_length, 80.0, 140.0, "衣长"),
            (self.shoulder_width, 32.0, 48.0, "肩宽"),
            (self.chest_width, 45.0, 75.0, "胸宽"),
            (self.slit_height, 25.0, 80.0, "开衩高"),
            (self.sleeve_length, 45.0, 85.0, "袖长"),
        ]
        for val, lo, hi, label in checks:
            if val < lo or val > hi:
                print(
                    f"[{self.name}] 警告: {label} {val:.1f}cm "
                    f"超出范围 [{lo:.0f}, {hi:.0f}]cm"
                )

        if self.garment_length > 0 and self.slit_height >= self.garment_length * 0.85:
            print(
                f"[{self.name}] 警告: 开衩高度 ({self.slit_height:.0f}cm) "
                f"超过衣长 ({self.garment_length:.0f}cm) 的 85%，"
                f"可能导致裁片结构不稳"
            )

    # ── 辅助属性 ─────────────────────────────────────────────────

    @property
    def collar_type_name(self) -> str:
        """获取领型中文名称。"""
        return COLLAR_TYPE_MAP.get(self.collar_type, "对襟")

    @property
    def slit_height_ratio(self) -> float:
        """开衩高度占衣长的比例。"""
        if self.garment_length <= 0:
            return 0.0
        return self.slit_height / self.garment_length

    @property
    def summary(self) -> str:
        """生成参数摘要字符串。"""
        return (
            f"褙子（{self.collar_type_name}） | "
            f"衣长{self.garment_length:.0f}cm | "
            f"胸宽{self.chest_width:.0f}cm | "
            f"肩宽{self.shoulder_width:.0f}cm | "
            f"袖长{self.sleeve_length:.0f}cm | "
            f"开衩高{self.slit_height:.0f}cm "
            f"({self.slit_height_ratio:.0%})"
        )

    # ── 面板构建 ─────────────────────────────────────────────────

    def build_panels(self) -> List[Panel]:
        """
        构建褙子裁片面板。

        褙子裁片结构（共5片）：
        1. 后身片 — 一片式后身，自肩至下摆，含后领窝
        2. 左前身片 — 左半前身，对襟开口，左侧开衩
        3. 右前身片 — 右半前身，对襟开口，右侧开衩
        4. 左袖片 — 直袖/窄袖，袖山弧线与袖窿缝合
        5. 右袖片 — 镜像左袖

        坐标系说明：
        (0, 0) 位于后领中点，x轴向右为正，y轴向下为正。
        """
        panels: List[Panel] = []

        # 读参
        L = self.garment_length
        SW = self.shoulder_width
        CW = self.chest_width
        slit = self.slit_height
        SL = self.sleeve_length
        sa = self.seam_allowance

        # 派生尺寸
        half_shoulder = SW / 2            # 半肩宽
        half_chest = CW / 2               # 半胸宽
        body_width = half_chest + 4.0     # 衣身半宽（含松量）
        neck_width = half_shoulder * 0.35 # 后领半宽
        neck_depth_back = 2.5             # 后领深
        neck_depth_front = 8.0            # 前领深
        armhole_depth = 20.0              # 袖窿深（肩点至腋下）
        sleeve_cap_height = 6.0           # 袖山高

        # ============================================================
        # 1. 后身片 (Back Body Panel)
        # ============================================================
        # 轮廓逆时针：后领窝左→右→右肩→右袖窿→右侧缝→右侧开衩→
        #             下摆右→左→左侧开衩→左侧缝→左袖窿→左肩→后领窝左
        back_outline: List[Point2D] = []

        # 后领窝弧线（左→右），2次贝塞尔
        back_outline.extend(
            bezier_curve([
                Point2D(-neck_width, 0),
                Point2D(0, -neck_depth_back),
                Point2D(neck_width, 0),
            ], num_points=20)
        )
        # 右肩线（领点→肩点）
        back_outline.extend(line(Point2D(neck_width, 0), Point2D(half_shoulder, 0)))
        # 右袖窿弧线（肩点→腋下），3次贝塞尔
        back_outline.extend(
            bezier_curve([
                Point2D(half_shoulder, 0),
                Point2D(half_shoulder + 3, armhole_depth * 0.35),
                Point2D(body_width, armhole_depth * 0.65),
                Point2D(body_width, armhole_depth),
            ], num_points=24)
        )
        # 右侧缝上段（腋下→开衩顶）
        back_outline.extend(
            line(Point2D(body_width, armhole_depth), Point2D(body_width, L - slit))
        )
        # 右侧开衩边（开衩顶→下摆，开口不缝合）
        back_outline.extend(
            line(Point2D(body_width, L - slit), Point2D(body_width, L))
        )
        # 后下摆（右→左）
        back_outline.extend(
            line(Point2D(body_width, L), Point2D(-body_width, L))
        )
        # 左侧开衩边（下摆→开衩顶）
        back_outline.extend(
            line(Point2D(-body_width, L), Point2D(-body_width, L - slit))
        )
        # 左侧缝上段（开衩顶→腋下）
        back_outline.extend(
            line(Point2D(-body_width, L - slit), Point2D(-body_width, armhole_depth))
        )
        # 左袖窿弧线（腋下→肩点），3次贝塞尔
        back_outline.extend(
            bezier_curve([
                Point2D(-body_width, armhole_depth),
                Point2D(-body_width, armhole_depth * 0.65),
                Point2D(-half_shoulder - 3, armhole_depth * 0.35),
                Point2D(-half_shoulder, 0),
            ], num_points=24)
        )
        # 左肩线（肩点→领点）
        back_outline.extend(
            line(Point2D(-half_shoulder, 0), Point2D(-neck_width, 0))
        )

        # 构建后身片缝边
        back_sewing_edges: List[SewingEdge] = [
            SewingEdge(
                name="后领窝",
                points=bezier_curve([
                    Point2D(-neck_width, 0),
                    Point2D(0, -neck_depth_back),
                    Point2D(neck_width, 0),
                ], num_points=20),
                stitch_type=StitchType.BINDING,
                seam_allowance=sa,
                is_hem=False,
            ),
            SewingEdge(
                name="右肩线",
                points=line(Point2D(neck_width, 0), Point2D(half_shoulder, 0)),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="右前肩线",
                is_hem=False,
            ),
            SewingEdge(
                name="右袖窿弧线",
                points=bezier_curve([
                    Point2D(half_shoulder, 0),
                    Point2D(half_shoulder + 3, armhole_depth * 0.35),
                    Point2D(body_width, armhole_depth * 0.65),
                    Point2D(body_width, armhole_depth),
                ], num_points=24),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="右袖山弧线",
                is_hem=False,
            ),
            SewingEdge(
                name="右侧缝",
                points=line(
                    Point2D(body_width, armhole_depth), Point2D(body_width, L - slit)
                ),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="右前侧缝",
                is_hem=False,
            ),
            SewingEdge(
                name="右侧开衩",
                points=line(Point2D(body_width, L - slit), Point2D(body_width, L)),
                stitch_type=StitchType.HEM,
                seam_allowance=sa * 1.5,
                is_hem=False,
            ),
            SewingEdge(
                name="后下摆",
                points=line(Point2D(body_width, L), Point2D(-body_width, L)),
                stitch_type=StitchType.HEM,
                seam_allowance=sa * 2.0,
                is_hem=True,
            ),
            SewingEdge(
                name="左侧开衩",
                points=line(Point2D(-body_width, L), Point2D(-body_width, L - slit)),
                stitch_type=StitchType.HEM,
                seam_allowance=sa * 1.5,
                is_hem=False,
            ),
            SewingEdge(
                name="左侧缝",
                points=line(
                    Point2D(-body_width, L - slit), Point2D(-body_width, armhole_depth)
                ),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="左前侧缝",
                is_hem=False,
            ),
            SewingEdge(
                name="左袖窿弧线",
                points=bezier_curve([
                    Point2D(-body_width, armhole_depth),
                    Point2D(-body_width, armhole_depth * 0.65),
                    Point2D(-half_shoulder - 3, armhole_depth * 0.35),
                    Point2D(-half_shoulder, 0),
                ], num_points=24),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="左袖山弧线",
                is_hem=False,
            ),
            SewingEdge(
                name="左肩线",
                points=line(Point2D(-half_shoulder, 0), Point2D(-neck_width, 0)),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="左前肩线",
                is_hem=False,
            ),
        ]

        back_panel = Panel(
            name="后身片",
            component_type=ComponentType.ACCESSORY,
            outline=back_outline,
            sewing_edges=back_sewing_edges,
            metadata={
                "panel_type": "身片",
                "side": "后",
                "half_chest": half_chest,
                "has_slit": True,
                "slit_height": slit,
            },
        )
        panels.append(back_panel)

        # ============================================================
        # 2. 左前身片 (Left Front Body Panel)
        # ============================================================
        # 轮廓逆时针：肩点→前领窝→前中对襟→前下摆→侧开衩→侧缝→袖窿→肩点
        left_front_outline: List[Point2D] = []

        # 前领窝弧线（肩点→前中对襟顶），3次贝塞尔
        left_front_outline.extend(
            bezier_curve([
                Point2D(-half_shoulder, 0),
                Point2D(-half_shoulder * 0.6, neck_depth_front * 0.4),
                Point2D(-neck_width * 0.3, neck_depth_front * 0.8),
                Point2D(0, neck_depth_front),
            ], num_points=24)
        )
        # 前中对襟边缘（上段→下段，至下摆）
        left_front_outline.extend(
            line(Point2D(0, neck_depth_front), Point2D(0, L * 0.15))
        )
        left_front_outline.extend(
            line(Point2D(0, L * 0.15), Point2D(0, L))
        )
        # 前下摆（中→左）
        left_front_outline.extend(
            line(Point2D(0, L), Point2D(-body_width, L))
        )
        # 左侧开衩边
        left_front_outline.extend(
            line(Point2D(-body_width, L), Point2D(-body_width, L - slit))
        )
        # 左侧缝上段
        left_front_outline.extend(
            line(Point2D(-body_width, L - slit), Point2D(-body_width, armhole_depth))
        )
        # 左袖窿弧线（腋下→肩点）
        left_front_outline.extend(
            bezier_curve([
                Point2D(-body_width, armhole_depth),
                Point2D(-body_width, armhole_depth * 0.65),
                Point2D(-half_shoulder - 3, armhole_depth * 0.35),
                Point2D(-half_shoulder, 0),
            ], num_points=24)
        )

        left_front_sewing_edges: List[SewingEdge] = [
            SewingEdge(
                name="前领窝弧线",
                points=bezier_curve([
                    Point2D(-half_shoulder, 0),
                    Point2D(-half_shoulder * 0.6, neck_depth_front * 0.4),
                    Point2D(-neck_width * 0.3, neck_depth_front * 0.8),
                    Point2D(0, neck_depth_front),
                ], num_points=24),
                stitch_type=StitchType.BINDING,
                seam_allowance=sa,
                is_hem=False,
            ),
            SewingEdge(
                name="对襟前中边缘",
                points=(
                    line(Point2D(0, neck_depth_front), Point2D(0, L * 0.15))
                    + line(Point2D(0, L * 0.15), Point2D(0, L))[1:]
                ),
                stitch_type=StitchType.HEM,
                seam_allowance=sa * 1.5,
                is_hem=False,
            ),
            SewingEdge(
                name="前下摆",
                points=line(Point2D(0, L), Point2D(-body_width, L)),
                stitch_type=StitchType.HEM,
                seam_allowance=sa * 2.0,
                is_hem=True,
            ),
            SewingEdge(
                name="左侧开衩",
                points=line(Point2D(-body_width, L), Point2D(-body_width, L - slit)),
                stitch_type=StitchType.HEM,
                seam_allowance=sa * 1.5,
                is_hem=False,
            ),
            SewingEdge(
                name="左前侧缝",
                points=line(
                    Point2D(-body_width, L - slit), Point2D(-body_width, armhole_depth)
                ),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="左侧缝",
                is_hem=False,
            ),
            SewingEdge(
                name="左前袖窿弧线",
                points=bezier_curve([
                    Point2D(-body_width, armhole_depth),
                    Point2D(-body_width, armhole_depth * 0.65),
                    Point2D(-half_shoulder - 3, armhole_depth * 0.35),
                    Point2D(-half_shoulder, 0),
                ], num_points=24),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="左袖山弧线",
                is_hem=False,
            ),
            SewingEdge(
                name="左前肩线",
                points=line(Point2D(-half_shoulder, 0), Point2D(-neck_width, 0)),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="左肩线",
                is_hem=False,
            ),
        ]

        left_front_panel = Panel(
            name="左前身片",
            component_type=ComponentType.ACCESSORY,
            outline=left_front_outline,
            sewing_edges=left_front_sewing_edges,
            metadata={
                "panel_type": "身片",
                "side": "左前",
                "has_slit": True,
                "slit_height": slit,
            },
        )
        panels.append(left_front_panel)

        # ============================================================
        # 3. 右前身片 (Right Front Body Panel)
        # ============================================================
        # 右前片为左前片的镜像
        right_front_outline: List[Point2D] = []

        right_front_outline.extend(
            bezier_curve([
                Point2D(half_shoulder, 0),
                Point2D(half_shoulder * 0.6, neck_depth_front * 0.4),
                Point2D(neck_width * 0.3, neck_depth_front * 0.8),
                Point2D(0, neck_depth_front),
            ], num_points=24)
        )
        right_front_outline.extend(
            line(Point2D(0, neck_depth_front), Point2D(0, L * 0.15))
        )
        right_front_outline.extend(
            line(Point2D(0, L * 0.15), Point2D(0, L))
        )
        right_front_outline.extend(
            line(Point2D(0, L), Point2D(body_width, L))
        )
        right_front_outline.extend(
            line(Point2D(body_width, L), Point2D(body_width, L - slit))
        )
        right_front_outline.extend(
            line(Point2D(body_width, L - slit), Point2D(body_width, armhole_depth))
        )
        right_front_outline.extend(
            bezier_curve([
                Point2D(body_width, armhole_depth),
                Point2D(body_width, armhole_depth * 0.65),
                Point2D(half_shoulder + 3, armhole_depth * 0.35),
                Point2D(half_shoulder, 0),
            ], num_points=24)
        )

        right_front_sewing_edges: List[SewingEdge] = [
            SewingEdge(
                name="前领窝弧线",
                points=bezier_curve([
                    Point2D(half_shoulder, 0),
                    Point2D(half_shoulder * 0.6, neck_depth_front * 0.4),
                    Point2D(neck_width * 0.3, neck_depth_front * 0.8),
                    Point2D(0, neck_depth_front),
                ], num_points=24),
                stitch_type=StitchType.BINDING,
                seam_allowance=sa,
                is_hem=False,
            ),
            SewingEdge(
                name="对襟前中边缘",
                points=(
                    line(Point2D(0, neck_depth_front), Point2D(0, L * 0.15))
                    + line(Point2D(0, L * 0.15), Point2D(0, L))[1:]
                ),
                stitch_type=StitchType.HEM,
                seam_allowance=sa * 1.5,
                is_hem=False,
            ),
            SewingEdge(
                name="前下摆",
                points=line(Point2D(0, L), Point2D(body_width, L)),
                stitch_type=StitchType.HEM,
                seam_allowance=sa * 2.0,
                is_hem=True,
            ),
            SewingEdge(
                name="右侧开衩",
                points=line(Point2D(body_width, L), Point2D(body_width, L - slit)),
                stitch_type=StitchType.HEM,
                seam_allowance=sa * 1.5,
                is_hem=False,
            ),
            SewingEdge(
                name="右前侧缝",
                points=line(
                    Point2D(body_width, L - slit), Point2D(body_width, armhole_depth)
                ),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="右侧缝",
                is_hem=False,
            ),
            SewingEdge(
                name="右前袖窿弧线",
                points=bezier_curve([
                    Point2D(body_width, armhole_depth),
                    Point2D(body_width, armhole_depth * 0.65),
                    Point2D(half_shoulder + 3, armhole_depth * 0.35),
                    Point2D(half_shoulder, 0),
                ], num_points=24),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="右袖山弧线",
                is_hem=False,
            ),
            SewingEdge(
                name="右前肩线",
                points=line(Point2D(neck_width, 0), Point2D(half_shoulder, 0)),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="右肩线",
                is_hem=False,
            ),
        ]

        right_front_panel = Panel(
            name="右前身片",
            component_type=ComponentType.ACCESSORY,
            outline=right_front_outline,
            sewing_edges=right_front_sewing_edges,
            metadata={
                "panel_type": "身片",
                "side": "右前",
                "has_slit": True,
                "slit_height": slit,
            },
        )
        panels.append(right_front_panel)

        # ============================================================
        # 4. 左袖片 (Left Sleeve Panel)
        # ============================================================
        sleeve_root_width = armhole_depth * 1.2
        half_root = sleeve_root_width / 2

        left_sleeve_outline: List[Point2D] = []
        # 轮廓逆时针：袖口底→袖外侧→袖山外侧→袖山顶→袖山内侧→袖内侧→袖口顶
        cuff_outer = Point2D(-half_shoulder - half_root, SL)
        cap_outer = Point2D(-half_shoulder - half_root, sleeve_cap_height)
        cap_inner = Point2D(-half_shoulder + half_root * 0.6, 0)
        cuff_inner = Point2D(-half_shoulder + half_root * 0.6, SL)

        left_sleeve_outline.extend(line(cuff_outer, cap_outer))
        left_sleeve_outline.extend(
            bezier_curve([
                cap_outer,
                Point2D(-half_shoulder - half_root * 0.7, -sleeve_cap_height * 0.3),
                Point2D(-half_shoulder + half_root * 0.3, -sleeve_cap_height * 0.2),
                cap_inner,
            ], num_points=28)
        )
        left_sleeve_outline.extend(line(cap_inner, cuff_inner))
        left_sleeve_outline.extend(line(cuff_inner, cuff_outer))

        left_sleeve_sewing_edges: List[SewingEdge] = [
            SewingEdge(
                name="左袖口",
                points=line(cuff_inner, cuff_outer),
                stitch_type=StitchType.HEM,
                seam_allowance=sa * 2.0,
                is_hem=True,
            ),
            SewingEdge(
                name="左袖外侧缝",
                points=line(cuff_outer, cap_outer),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                is_hem=False,
            ),
            SewingEdge(
                name="左袖山弧线",
                points=bezier_curve([
                    cap_outer,
                    Point2D(-half_shoulder - half_root * 0.7, -sleeve_cap_height * 0.3),
                    Point2D(-half_shoulder + half_root * 0.3, -sleeve_cap_height * 0.2),
                    cap_inner,
                ], num_points=28),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="左袖窿弧线",
                is_hem=False,
            ),
            SewingEdge(
                name="左袖内侧缝",
                points=line(cap_inner, cuff_inner),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                is_hem=False,
            ),
        ]

        left_sleeve_panel = Panel(
            name="左袖片",
            component_type=ComponentType.SLEEVE,
            outline=left_sleeve_outline,
            sewing_edges=left_sleeve_sewing_edges,
            metadata={
                "panel_type": "袖片",
                "side": "左",
                "sleeve_length": SL,
            },
        )
        panels.append(left_sleeve_panel)

        # ============================================================
        # 5. 右袖片 (Right Sleeve Panel)
        # ============================================================
        r_cuff_outer = Point2D(half_shoulder + half_root, SL)
        r_cap_outer = Point2D(half_shoulder + half_root, sleeve_cap_height)
        r_cap_inner = Point2D(half_shoulder - half_root * 0.6, 0)
        r_cuff_inner = Point2D(half_shoulder - half_root * 0.6, SL)

        right_sleeve_outline: List[Point2D] = []
        right_sleeve_outline.extend(line(r_cuff_outer, r_cap_outer))
        right_sleeve_outline.extend(
            bezier_curve([
                r_cap_outer,
                Point2D(half_shoulder + half_root * 0.7, -sleeve_cap_height * 0.3),
                Point2D(half_shoulder - half_root * 0.3, -sleeve_cap_height * 0.2),
                r_cap_inner,
            ], num_points=28)
        )
        right_sleeve_outline.extend(line(r_cap_inner, r_cuff_inner))
        right_sleeve_outline.extend(line(r_cuff_inner, r_cuff_outer))

        right_sleeve_sewing_edges: List[SewingEdge] = [
            SewingEdge(
                name="右袖口",
                points=line(r_cuff_inner, r_cuff_outer),
                stitch_type=StitchType.HEM,
                seam_allowance=sa * 2.0,
                is_hem=True,
            ),
            SewingEdge(
                name="右袖外侧缝",
                points=line(r_cuff_outer, r_cap_outer),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                is_hem=False,
            ),
            SewingEdge(
                name="右袖山弧线",
                points=bezier_curve([
                    r_cap_outer,
                    Point2D(half_shoulder + half_root * 0.7, -sleeve_cap_height * 0.3),
                    Point2D(half_shoulder - half_root * 0.3, -sleeve_cap_height * 0.2),
                    r_cap_inner,
                ], num_points=28),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="右袖窿弧线",
                is_hem=False,
            ),
            SewingEdge(
                name="右袖内侧缝",
                points=line(r_cap_inner, r_cuff_inner),
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                is_hem=False,
            ),
        ]

        right_sleeve_panel = Panel(
            name="右袖片",
            component_type=ComponentType.SLEEVE,
            outline=right_sleeve_outline,
            sewing_edges=right_sleeve_sewing_edges,
            metadata={
                "panel_type": "袖片",
                "side": "右",
                "sleeve_length": SL,
            },
        )
        panels.append(right_sleeve_panel)

        return panels

    # ── DSL 导出 ───────────────────────────────────────────────────

    def to_garment_code(self) -> str:
        """
        导出为 GarmentCode DSL 格式。

        生成的代码声明褙子配饰，包含全部参数、裁片与缝合关系。
        """
        lines: List[str] = []
        lines.append("# ==========================================")
        lines.append("# 褙子 (Beizi / 背子)")
        lines.append(f"# 朝代: {', '.join(d.value for d in self.compatible_dynasties)}")
        lines.append(f"# 领型: {self.collar_type_name}")
        lines.append(f"# 宋制对襟长背心，无扣敞开，两侧高开衩")
        lines.append("# ==========================================")
        lines.append("")

        # 参数块
        lines.append("beizi = Accessory(")
        lines.append(f"    name=\"{self.name}\",")
        lines.append(f"    garment_length={self.garment_length},   # 衣长 (cm)")
        lines.append(f"    shoulder_width={self.shoulder_width},   # 肩宽 (cm)")
        lines.append(f"    chest_width={self.chest_width},         # 胸宽 (cm)")
        lines.append(f"    slit_height={self.slit_height},         # 开衩高 (cm)")
        lines.append(f"    collar_type=\"{self.collar_type_name}\", # 领型")
        lines.append(f"    sleeve_length={self.sleeve_length},     # 袖长 (cm)")
        lines.append(f"    seam_allowance={self.seam_allowance},   # 缝份 (cm)")
        lines.append(f"    dynasty={[d.value for d in self.compatible_dynasties]},")
        lines.append(f"    type='beizi',")
        lines.append(")")
        lines.append("")

        # 裁片块
        for panel in self.panels:
            lines.append(f"# ── 裁片: {panel.name} ──")
            lines.append(f"panel_{panel.name} = Panel(")
            lines.append(f"    name='{panel.name}',")
            lines.append(f"    component_type='{panel.component_type.name}',")
            lines.append(f"    outline_points={len(panel.outline)},")
            lines.append(f"    sewing_edge_count={len(panel.sewing_edges)},")
            if panel.metadata:
                for k, v in panel.metadata.items():
                    lines.append(f"    {k}={v!r},")
            lines.append(")")
            lines.append("")

            for edge in panel.sewing_edges:
                lines.append(f"    # {edge.name} "
                           f"(stitch={edge.stitch_type.name}, "
                           f"sa={edge.seam_allowance}cm"
                           f"{', mate=' + edge.mate_edge_name if edge.mate_edge_name else ''}"
                           f"{', hem' if edge.is_hem else ''})")

            lines.append("")

        # 缝合关系汇总
        all_mates = [
            (e.name, e.mate_edge_name)
            for panel in self.panels
            for e in panel.sewing_edges
            if e.mate_edge_name
        ]
        if all_mates:
            lines.append("# ── 缝合关系 ──")
            for edge_name, mate_name in all_mates:
                lines.append(f"stitch(\"{edge_name}\", \"{mate_name}\")")
            lines.append("")

        return "\n".join(lines)

    # ── 验证 ──────────────────────────────────────────────────────

    def validate(self) -> List[str]:
        """验证参数合理性，返回警告/错误信息列表。"""
        issues = super().validate()

        if self.garment_length < 80 or self.garment_length > 140:
            issues.append(
                f"[{self.name}] 衣长 {self.garment_length}cm "
                f"超出推荐范围 [80, 140]cm"
            )
        if self.shoulder_width < 32 or self.shoulder_width > 48:
            issues.append(
                f"[{self.name}] 肩宽 {self.shoulder_width}cm "
                f"超出推荐范围 [32, 48]cm"
            )
        if self.chest_width < 45 or self.chest_width > 75:
            issues.append(
                f"[{self.name}] 胸宽 {self.chest_width}cm "
                f"超出推荐范围 [45, 75]cm"
            )
        if self.slit_height < 25 or self.slit_height > 80:
            issues.append(
                f"[{self.name}] 开衩高 {self.slit_height}cm "
                f"超出推荐范围 [25, 80]cm"
            )
        if self.sleeve_length < 45 or self.sleeve_length > 85:
            issues.append(
                f"[{self.name}] 袖长 {self.sleeve_length}cm "
                f"超出推荐范围 [45, 85]cm"
            )
        if self.garment_length > 0 and self.slit_height > self.garment_length * 0.85:
            issues.append(
                f"[{self.name}] 开衩高 {self.slit_height}cm "
                f"超过衣长 {self.garment_length}cm 的 85%，"
                f"可能导致结构不稳"
            )
        if self.collar_type not in COLLAR_TYPE_MAP:
            issues.append(
                f"[{self.name}] 未知领型编码 {self.collar_type}"
            )

        return issues
