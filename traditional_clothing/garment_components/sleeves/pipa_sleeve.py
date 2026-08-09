"""
琵琶袖 (Pipa Sleeve) — 明代独有的袖型 ⭐
名称源于琵琶乐器造型：袖口窄小、袖身中部膨起如琵琶共鸣箱、袖根宽度适中。
明代女装最具代表性的袖型，常见于袄裙、道袍、披风等。
"""

from __future__ import annotations

from typing import List

from ..base import (
    GarmentComponent, ComponentType, Dynasty,
    Panel, SewingEdge, Point2D, StitchType,
)
from ..curves import bezier_curve


class PipaSleeve(GarmentComponent):
    """琵琶袖 — 形似琵琶，窄口、膨身、适中根。明代独有袖型。

    轮廓由两条贝塞尔曲线勾勒：上缘与下缘各自从袖根经膨起处延伸至袖口，
    形成优美的琵琶形弧线。关键尺寸约束：袖口宽 < 袖根宽 < 膨起宽。
    """

    compatible_dynasties: List[Dynasty] = [Dynasty.MING]  # ⭐ 仅明代使用

    # ── 参数范围常量 ──
    _SL_RANGE = (60.0, 100.0)      # 袖长 (cm)
    _CW_RANGE = (10.0, 20.0)       # 袖口宽 (cm)
    _RW_RANGE = (18.0, 28.0)       # 袖根宽 (cm)
    _BW_RANGE = (25.0, 45.0)       # 膨起宽 (cm)
    _BP_RANGE = (0.30, 0.55)       # 膨起位置（占袖长比例）
    _SH_RANGE = (8.0, 16.0)        # 袖山高 (cm)

    def __init__(
        self,
        sleeve_length: float = 80.0,
        cuff_width: float = 15.0,
        root_width: float = 22.0,
        bulge_width: float = 35.0,
        bulge_position: float = 0.45,
        sleeve_cap_height: float = 12.0,
        seam_allowance: float = 1.0,
    ):
        """初始化琵琶袖部件。

        Args:
            sleeve_length: 袖长，从袖根到袖口 (cm)，范围 60-100
            cuff_width: 袖口宽度 (cm)，范围 10-20，为四角点中最窄处
            root_width: 袖根宽度 (cm)，范围 18-28，接衣身袖窿处
            bulge_width: 袖身膨起最大宽度 (cm)，范围 25-45，形似琵琶琴箱
            bulge_position: 膨起位置，占袖长的比例 (0.3-0.55)
            sleeve_cap_height: 袖山高 (cm)，范围 8-16，影响上缘弧度
            seam_allowance: 缝份宽度 (cm)，默认 1.0
        """
        super().__init__(
            name="琵琶袖",
            component_type=ComponentType.SLEEVE,
            seam_allowance=seam_allowance,
        )
        # 参数钳位存储
        self.sleeve_length = self._clamp(sleeve_length, *self._SL_RANGE)
        self.cuff_width = self._clamp(cuff_width, *self._CW_RANGE)
        self.root_width = self._clamp(root_width, *self._RW_RANGE)
        self.bulge_width = self._clamp(bulge_width, *self._BW_RANGE)
        self.bulge_position = self._clamp(bulge_position, *self._BP_RANGE)
        self.sleeve_cap_height = self._clamp(sleeve_cap_height, *self._SH_RANGE)

    @staticmethod
    def _clamp(value: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, value))

    # ── 面板构建 ──────────────────────────────────────────────────────

    def build_panels(self) -> List[Panel]:
        """构建琵琶袖裁片面板。

        单侧袖片（右侧），外部通过 mirrored=True 镜像得到左侧。
        外轮廓为琵琶形：袖根→膨起→袖口，由两条贝塞尔曲线勾勒上下缘。

        Returns:
            包含一片琵琶袖裁片的列表。
        """
        L = self.sleeve_length
        cw, rw = self.cuff_width, self.root_width
        bw = self.bulge_width
        bp_x = L * self.bulge_position          # 膨起处 X 坐标
        sh = self.sleeve_cap_height
        sa = self.seam_allowance

        # ── 关键约束：袖口 < 袖根 < 膨起 ──
        if not (cw < rw < bw):
            raise ValueError(
                f"琵琶袖尺寸约束不满足："
                f"袖口宽({cw:.1f}) < 袖根宽({rw:.1f}) < 膨起宽({bw:.1f})"
            )

        # ── 四个角点（局部坐标系，原点=袖根中心）──
        rt = Point2D(0, rw / 2)                 # 袖根上角
        rb = Point2D(0, -rw / 2)                # 袖根下角
        ct = Point2D(L, cw / 2)                 # 袖口上角
        cb = Point2D(L, -cw / 2)                # 袖口下角
        bt = Point2D(bp_x, bw / 2)              # 膨起上缘点
        bb = Point2D(bp_x, -bw / 2)             # 膨起下缘点

        # ── 上缘贝塞尔曲线（两段 cubic 拼接）：袖根上角 → 膨起上缘 → 袖口上角 ──
        top_to_bulge = bezier_curve([
            rt,
            Point2D(bp_x * 0.40, rw / 2 + sh * 0.55),   # 袖山弧度：从根部向上隆起
            Point2D(bp_x * 0.75, bw / 2 + 3),            # 接近膨起处，微高于膨起线
            bt,
        ], num_points=30)
        top_to_cuff = bezier_curve([
            bt,
            Point2D(bp_x + (L - bp_x) * 0.25, bw / 2 - 1),  # 从膨起开始缓慢下降
            Point2D(bp_x + (L - bp_x) * 0.70, cw / 2 + 2),  # 趋近袖口，平滑收拢
            ct,
        ], num_points=30)

        # ── 下缘贝塞尔曲线（两段 cubic 拼接）：袖口下角 → 膨起下缘 → 袖根下角 ──
        bot_to_bulge = bezier_curve([
            cb,
            Point2D(bp_x + (L - bp_x) * 0.70, -cw / 2 - 2),  # 从袖口向外微扩
            Point2D(bp_x + (L - bp_x) * 0.25, -bw / 2 + 1),  # 接近膨起处
            bb,
        ], num_points=30)
        bot_to_root = bezier_curve([
            bb,
            Point2D(bp_x * 0.75, -bw / 2 - 3),               # 从膨起保持宽度
            Point2D(bp_x * 0.40, -rw / 2 - sh * 0.55),       # 向袖根收拢
            rb,
        ], num_points=30)

        # ── 拼接完整外轮廓（逆时针 CCW）──
        root_edge = [rb, rt]                          # 左：袖根竖边
        top_edge = top_to_bulge[:-1] + top_to_cuff    # 上：去重合的 bt
        cuff_edge = [ct, cb]                          # 右：袖口竖边
        bottom_edge = bot_to_bulge[:-1] + bot_to_root # 下：去重合的 bb
        outline = root_edge + top_edge + cuff_edge + bottom_edge

        # ── 缝边 ──
        sewing_edges = [
            SewingEdge(
                name="琵琶袖-袖根", points=root_edge,
                stitch_type=StitchType.PLAIN_SEAM, seam_allowance=sa,
                mate_edge_name="衣身-袖窿",
            ),
            SewingEdge(
                name="琵琶袖-袖口", points=cuff_edge,
                stitch_type=StitchType.HEM, seam_allowance=sa, is_hem=True,
            ),
            SewingEdge(
                name="琵琶袖-上缘", points=top_edge,
                stitch_type=StitchType.PLAIN_SEAM, seam_allowance=sa,
            ),
            SewingEdge(
                name="琵琶袖-下缘", points=bottom_edge,
                stitch_type=StitchType.PLAIN_SEAM, seam_allowance=sa,
            ),
        ]

        panel = Panel(
            name="琵琶袖裁片",
            component_type=ComponentType.SLEEVE,
            outline=outline,
            sewing_edges=sewing_edges,
            grain_angle_rad=0.0,     # 纹理平行于袖长方向
            fabric_layers=1,
            mirrored=True,           # 左右对称，仅定义一侧，使用时可镜像
            metadata={
                "dynasty": "明",
                "sleeve_type": "琵琶袖",
                "sleeve_length": self.sleeve_length,
                "cuff_width": self.cuff_width,
                "bulge_width": self.bulge_width,
                "bulge_position": self.bulge_position,
            },
        )
        return [panel]

    # ── DSL 导出 ──────────────────────────────────────────────────────

    def to_garment_code(self) -> str:
        """将琵琶袖导出为服装 DSL 描述代码。"""
        return "\n".join([
            "# 琵琶袖 (Pipa Sleeve) — 明代独有袖型 ⭐",
            "pipa_sleeve = SleevePanel(",
            f"    sleeve_length={self.sleeve_length:.1f},      # 袖长 (cm)",
            f"    cuff_width={self.cuff_width:.1f},            # 袖口宽 (cm)",
            f"    root_width={self.root_width:.1f},            # 袖根宽 (cm)",
            f"    bulge_width={self.bulge_width:.1f},          # 膨起宽 (cm)",
            f"    bulge_position={self.bulge_position:.2f},    # 膨起位置比例",
            f"    sleeve_cap_height={self.sleeve_cap_height:.1f},  # 袖山高 (cm)",
            f"    seam_allowance={self.seam_allowance:.1f},    # 缝份 (cm)",
            "    type='pipa',",
            "    dynasty='明',",
            "    mirrored=True,  # 左右袖对称",
            ")",
        ])

    # ── 验证 ──────────────────────────────────────────────────────────

    def validate(self) -> List[str]:
        """验证参数合理性，返回警告/错误信息列表。"""
        issues = super().validate()
        cw, rw, bw = self.cuff_width, self.root_width, self.bulge_width
        if not (cw < rw < bw):
            issues.append(
                f"[{self.name}] 尺寸约束不满足：袖口({cw:.1f}) < "
                f"袖根({rw:.1f}) < 膨起({bw:.1f})"
            )
        if bw > self.sleeve_length * 0.6:
            issues.append(
                f"[{self.name}] 膨起宽({bw:.1f})相对袖长"
                f"({self.sleeve_length:.1f})过大，呈灯笼袖而非琵琶袖形态"
            )
        if self.bulge_position < 0.3 or self.bulge_position > 0.55:
            issues.append(
                f"[{self.name}] 膨起位置({self.bulge_position:.2f})超出合理范围"
            )
        return issues

    # ── 显示 ──────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"PipaSleeve(袖长={self.sleeve_length:.0f}cm, "
            f"袖口={self.cuff_width:.0f}cm, 袖根={self.root_width:.0f}cm, "
            f"膨起={self.bulge_width:.0f}cm@{self.bulge_position:.2f})"
        )
