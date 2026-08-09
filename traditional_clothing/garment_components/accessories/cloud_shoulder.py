"""
cloud_shoulder - 云肩（Cloud Shoulder / Yunjian）配饰部件

云肩是中国传统服饰中极具辨识度的装饰性肩部配饰，由数片云朵形瓣片
环绕领口层叠排列而成，常见于明清时期的礼服、婚服及戏曲服饰中。

结构特征：
  - 中心为圆形领口开口
  - 4~8 片云朵形瓣片辐射状排列
  - 相邻瓣片以覆盖比（overlap_ratio）叠合
  - 内圈设有小型立领（collar_stand）
  - 外轮廓呈云纹波浪造型
"""

from __future__ import annotations

import math
from typing import List, Tuple, Dict, Any

from ..base import (
    GarmentComponent,
    ComponentType,
    Dynasty,
    Panel,
    SewingEdge,
    Point2D,
    StitchType,
)
from ..curves import arc, bezier_curve, cloud_scallop


# ─── 常量 ────────────────────────────────────────────────────────

# 弧线采样密度
_ARC_POINTS = 30
# 云纹波浪采样密度
_SCALLOP_POINTS = 24


# ─── CloudShoulder ───────────────────────────────────────────────

class CloudShoulder(GarmentComponent):
    """云肩（Cloud Shoulder / Yunjian）配饰。

    云肩由多片云朵形瓣片环绕领口叠合而成，兼具实用（护肩）
    与装饰功能，是明清礼服的标志性配饰之一。

    Attributes:
        neck_circumference: 颈围（厘米），默认 38cm
        num_petals: 云片数量（4~8），默认 4
        petal_radius: 云片径向长度（厘米），默认 18cm
        collar_stand_height: 内领立领高度（厘米），默认 2cm
        overlap_ratio: 相邻云片叠合比例（0~1），默认 0.15
        seam_allowance: 缝份宽度（厘米），默认 1.0cm
    """

    compatible_dynasties: List[Dynasty] = [Dynasty.MING, Dynasty.QING]

    def __init__(
        self,
        name: str = "云肩",
        neck_circumference: float = 38.0,
        num_petals: int = 4,
        petal_radius: float = 18.0,
        collar_stand_height: float = 2.0,
        overlap_ratio: float = 0.15,
        seam_allowance: float = 1.0,
    ):
        """初始化云肩参数。

        Args:
            name: 部件名称
            neck_circumference: 颈围（厘米），用于确定领口大小
            num_petals: 云片数量，取值范围 4~8
            petal_radius: 云片径向长度（厘米），从领口外沿到云片尖端
            collar_stand_height: 内领立领高度（厘米）
            overlap_ratio: 相邻云片叠合比例，0 表示不叠合，1 表示完全覆盖
            seam_allowance: 缝份宽度（厘米）
        """
        super().__init__(
            name=name,
            component_type=ComponentType.CLOUD_SHOULDER,
            seam_allowance=seam_allowance,
        )
        self.neck_circumference = max(20.0, neck_circumference)
        self.num_petals = max(4, min(8, num_petals))
        self.petal_radius = max(5.0, petal_radius)
        self.collar_stand_height = max(0.0, collar_stand_height)
        self.overlap_ratio = max(0.0, min(0.5, overlap_ratio))

    # ─── 派生几何参数 ─────────────────────────────────────────────

    @property
    def neck_radius(self) -> float:
        """领口半径（厘米）。"""
        return self.neck_circumference / (2.0 * math.pi)

    @property
    def inner_radius(self) -> float:
        """内圈半径 = 领口半径 + 立领高度。"""
        return self.neck_radius + self.collar_stand_height

    @property
    def outer_radius(self) -> float:
        """外圈半径 = 内圈半径 + 瓣片径向长。"""
        return self.inner_radius + self.petal_radius

    @property
    def angular_span(self) -> float:
        """单片云片的基础角跨度（弧度）。"""
        return 2.0 * math.pi / self.num_petals

    @property
    def effective_span(self) -> float:
        """含叠合的角跨度（弧度）。"""
        return self.angular_span * (1.0 + self.overlap_ratio)

    @property
    def half_overlap(self) -> float:
        """单侧叠合半角（弧度）。"""
        return self.angular_span * self.overlap_ratio / 2.0

    # ─── 单瓣轮廓生成 ─────────────────────────────────────────────

    def _petal_base_angle(self, petal_index: int) -> float:
        """返回第 i 片云片的基准角（弧度），基准角对应瓣片中心线方向。"""
        return petal_index * self.angular_span

    def _petal_angle_range(self, petal_index: int) -> Tuple[float, float]:
        """返回第 i 片云片的 [起始角, 终止角]（弧度），按逆时针方向。"""
        base = self._petal_base_angle(petal_index)
        half_eff = self.effective_span / 2.0
        return (base - half_eff, base + half_eff)

    def _petal_inner_arc(self, center: Point2D, angle_start: float, angle_end: float) -> List[Point2D]:
        """生成云片内侧弧线（沿立领外沿）。

        Args:
            center: 云肩中心点（领口圆心）
            angle_start: 起始角（弧度）
            angle_end: 终止角（弧度）

        Returns:
            内侧弧线的采样点列表，从 angle_start 到 angle_end。
        """
        return arc(center, self.inner_radius, angle_start, angle_end, _ARC_POINTS)

    def _petal_outer_contour(
        self,
        center: Point2D,
        angle_start: float,
        angle_end: float,
    ) -> List[Point2D]:
        """生成云片外轮廓云纹波浪线。

        外轮廓由若干扇形起伏构成云朵形态：
          - 瓣片尖端位于角度范围中央，径向延伸至 outer_radius
          - 两侧分别有两个副凸起（侧瓣），形成云纹的多层波浪效果
          - 使用 bezier_curve 和 cloud_scallop 组合生成圆润的云形轮廓

        Args:
            center: 云肩中心点
            angle_start: 瓣片起始角
            angle_end: 瓣片终止角

        Returns:
            外轮廓采样点列表，从 angle_end 方向行进到 angle_start 方向
            （注意：返回的是逆时针方向的轮廓段，与内侧弧线一致）。
        """
        span = angle_end - angle_start
        mid_angle = (angle_start + angle_end) / 2.0

        # 五个关键角度节点（从 start 到 end 均匀分布），定义轮廓的波峰波谷
        # 波峰（外凸）：mid_angle 主尖端, mid_angle ± 0.35*span 侧凸
        # 波谷（内凹）：mid_angle ± 0.65*span, 以及两端

        num_waves = max(2, min(5, self.num_petals // 2 + 1))  # 2~5 个波浪

        # 在角度跨度上均匀采样节点
        node_angles = []
        for k in range(num_waves * 2 + 1):
            t = k / (num_waves * 2)
            node_angles.append(angle_start + t * span)

        # 交替波峰/波谷（从 start 开始为波谷）
        contour_points: List[Point2D] = []
        for idx, ang in enumerate(node_angles):
            is_peak = (idx % 2 == 1)  # 奇数索引为波峰
            if is_peak:
                # 波峰：最外层凸起
                peak_factor = 1.0
                # 靠近中心的波峰（主尖端）最高
                dist_to_mid = abs(ang - mid_angle)
                if dist_to_mid < 0.05 * span:
                    peak_factor = 1.0   # 主尖端
                elif dist_to_mid < 0.3 * span:
                    peak_factor = 0.85  # 次尖端
                else:
                    peak_factor = 0.65  # 边缘小凸起
                r = self.inner_radius + self.petal_radius * peak_factor
            else:
                # 波谷：瓣片连接处的凹入
                r = self.inner_radius + self.petal_radius * 0.35

            contour_points.append(Point2D(
                center.x + r * math.cos(ang),
                center.y + r * math.sin(ang),
            ))

        # 使用贝塞尔曲线平滑插值各节点之间的弧段
        # 每个相邻节点对之间插入控制点以产生圆润过渡
        smoothed: List[Point2D] = []
        n = len(contour_points)
        for i in range(n - 1):
            p0 = contour_points[i]
            p1 = contour_points[i + 1]
            ang0 = node_angles[i]
            ang1 = node_angles[i + 1]

            # 计算控制点：在 p0 和 p1 连线的基础上向径向偏移以增加弧度
            mid_r = (self._point_radius(p0, center) + self._point_radius(p1, center)) / 2.0
            mid_ang = (ang0 + ang1) / 2.0

            # 控制点向外微调
            bulge = self.petal_radius * 0.08
            cp_rad = mid_r + bulge
            cp = Point2D(
                center.x + cp_rad * math.cos(mid_ang),
                center.y + cp_rad * math.sin(mid_ang),
            )

            seg = bezier_curve(
                [p0, cp, p1],
                num_points=max(8, _SCALLOP_POINTS // max(1, num_waves)),
            )
            if smoothed:
                # 避免重复点
                smoothed.extend(seg[1:])
            else:
                smoothed.extend(seg)

        return smoothed

    def _point_radius(self, pt: Point2D, center: Point2D) -> float:
        """计算点相对于中心的径向距离。"""
        return math.hypot(pt.x - center.x, pt.y - center.y)

    def _petal_side_edge(
        self,
        center: Point2D,
        inner_point: Point2D,
        outer_point: Point2D,
    ) -> List[Point2D]:
        """生成云片侧边（从内侧弧端点到外侧轮廓端点）。

        侧边略带 S 形曲线，模拟真实云肩瓣片之间的叠层过渡。

        Args:
            center: 云肩中心点
            inner_point: 内侧弧上的端点
            outer_point: 外侧轮廓上的端点

        Returns:
            侧边线采样点列表，从 inner_point 到 outer_point。
        """
        # 计算径向方向角和两点间方向
        ang_inner = math.atan2(inner_point.y - center.y, inner_point.x - center.x)
        r_inner = self._point_radius(inner_point, center)
        r_outer = self._point_radius(outer_point, center)

        # 中间控制点：径向中点处稍作偏移，形成 S 形
        mid_r = (r_inner + r_outer) / 2.0
        # 偏移方向垂直于径向
        perp_ang = ang_inner + math.pi / 2.0
        offset = (r_outer - r_inner) * 0.12

        cp = Point2D(
            center.x + mid_r * math.cos(ang_inner) + offset * math.cos(perp_ang),
            center.y + mid_r * math.sin(ang_inner) + offset * math.sin(perp_ang),
        )

        return bezier_curve([inner_point, cp, outer_point], num_points=16)

    # ─── 完整单瓣面板构建 ──────────────────────────────────────────

    def _build_petal_panel(self, petal_index: int, center: Point2D) -> Panel:
        """构建单片云片面板。

        面板轮廓（逆时针）：
          1. 内侧弧线（从左到右）
          2. 右侧边线（从内到外）
          3. 外侧云纹轮廓（从右到左）
          4. 左侧边线（从外到内，闭合）

        Args:
            petal_index: 云片索引（0-based）
            center: 云肩中心点

        Returns:
            单瓣 Panel 对象。
        """
        ang_start, ang_end = self._petal_angle_range(petal_index)

        # 各段轮廓
        inner_arc_pts = self._petal_inner_arc(center, ang_start, ang_end)
        outer_contour_pts = self._petal_outer_contour(center, ang_start, ang_end)
        # 注意：outer_contour 从 ang_end 侧行进到 ang_start 侧（保持逆时针）
        # 实际上 outer_contour 应该是从 ang_end 到 ang_start
        # 内侧弧线是从 ang_start 到 ang_end
        # 所以整体逆时针顺序：
        #   inner_start → (inner_arc) → inner_end → (right_edge) → outer_start → (outer_contour) → outer_end → (left_edge) → inner_start

        # inner_arc 从 ang_start 到 ang_end
        inner_start = inner_arc_pts[0]
        inner_end = inner_arc_pts[-1]

        # outer_contour 从 ang_end 侧的端点开始，到 ang_start 侧的端点结束
        outer_start = outer_contour_pts[0]   # 在 ang_end 侧
        outer_end = outer_contour_pts[-1]    # 在 ang_start 侧

        # 右侧边线：inner_end → outer_start
        right_edge = self._petal_side_edge(center, inner_end, outer_start)

        # 左侧边线：outer_end → inner_start（闭合）
        left_edge = self._petal_side_edge(center, inner_start, outer_end)

        # 组装轮廓（逆时针）：inner → right_edge → outer(reversed) → left_edge(reversed)
        # 实际上 outer 的方向可能是从 end 到 start（也就是从 ang_end 到 ang_start），
        # 在逆时针轮廓中，外侧应该从右向左走，与内侧从左到右形成闭环。
        #
        # 让我们重新理清：
        # 内侧弧线 inner_arc: ang_start → ang_end (逆时针沿内圈走)
        # 右侧边 right_edge: inner_end → outer_start (向外走)
        # 外侧轮廓 outer_contour: outer_start(ang_end侧) → outer_end(ang_start侧) (逆时针沿外圈走回)
        # 左侧边 left_edge(reversed): outer_end → inner_start (向内走闭合)
        #
        # 但是 outer_contour 生成的方向也是从 ang_end 侧到 ang_start 侧，
        # 而内侧弧线从 ang_start 到 ang_end，所以整个轮廓形成了一个逆时针闭合环。

        outline: List[Point2D] = []
        # 1. 内侧弧线（从左到右）
        outline.extend(inner_arc_pts)
        # 2. 右侧边线（去掉与内侧弧线重合的首点）
        outline.extend(right_edge[1:])
        # 3. 外侧轮廓（从右到左，注意 outer_contour 方向）
        outline.extend(outer_contour_pts[1:])
        # 4. 左侧边线逆向（从外到内，去掉与外侧重合的首点，以及闭合到起点的末点）
        left_rev = list(reversed(left_edge))
        outline.extend(left_rev[1:-1])

        # 构建缝边
        n_inner = len(inner_arc_pts)
        n_right = len(right_edge) - 1  # 减去重合点
        n_outer = len(outer_contour_pts) - 1
        n_left = len(left_rev) - 2  # 减去两端重合点

        idx_end_inner = n_inner - 1  # 内侧弧段结束索引
        idx_end_right = idx_end_inner + n_right
        idx_end_outer = idx_end_right + n_outer

        inner_edge = SewingEdge(
            name=f"{self.name}_瓣{petal_index + 1}_内侧",
            points=outline[:n_inner],
            stitch_type=StitchType.PLAIN_SEAM,
            seam_allowance=self.seam_allowance,
            mate_edge_name=f"{self.name}_领座外侧",
        )

        right_side = SewingEdge(
            name=f"{self.name}_瓣{petal_index + 1}_右侧",
            points=outline[idx_end_inner : idx_end_right + 1],
            stitch_type=StitchType.NONE,
            seam_allowance=0.0,
            is_hem=True,
        )

        outer_edge = SewingEdge(
            name=f"{self.name}_瓣{petal_index + 1}_外缘",
            points=outline[idx_end_right : idx_end_outer + 1],
            stitch_type=StitchType.HEM,
            seam_allowance=self.seam_allowance,
            is_hem=True,
        )

        left_side = SewingEdge(
            name=f"{self.name}_瓣{petal_index + 1}_左侧",
            points=outline[idx_end_outer:],
            stitch_type=StitchType.NONE,
            seam_allowance=0.0,
            is_hem=True,
        )

        return Panel(
            name=f"{self.name}_云片{petal_index + 1}",
            component_type=ComponentType.CLOUD_SHOULDER,
            outline=outline,
            sewing_edges=[inner_edge, right_side, outer_edge, left_side],
            grain_angle_rad=self._petal_base_angle(petal_index),
            fabric_layers=1,
            metadata={
                "petal_index": petal_index,
                "base_angle_deg": math.degrees(self._petal_base_angle(petal_index)),
                "num_petals": self.num_petals,
            },
        )

    # ─── 领座面板 ─────────────────────────────────────────────────

    def _build_collar_stand_panel(self, center: Point2D) -> Panel:
        """构建内圈立领（领座）面板。

        领座为圆环形，内侧与领口相连，外侧与云片内侧缝合。

        Args:
            center: 云肩中心点

        Returns:
            领座 Panel 对象。
        """
        # 领座由两部分组成：内圆（领口）和外圆（立领上沿）
        # 实际上领座是一圈矩形条带弯成环形
        # 为简化，将其表示为环形面板的展开形式：一个矩形
        # 矩形宽度 = 领座高度(collar_stand_height)
        # 矩形长度 = 内圈周长 = 2π * (neck_radius + collar_stand_height/2)

        mid_radius = self.neck_radius + self.collar_stand_height / 2.0
        band_length = 2.0 * math.pi * mid_radius
        band_height = self.collar_stand_height

        # 矩形轮廓（局部坐标系，原点在矩形左下角）
        # 逆时针：左下 → 右下 → 右上 → 左上
        outline = [
            Point2D(0, 0),
            Point2D(band_length, 0),
            Point2D(band_length, band_height),
            Point2D(0, band_height),
        ]

        # 底边 = 与领口接合边，顶边 = 与云片内侧缝合边
        bottom_edge = SewingEdge(
            name=f"{self.name}_领座内侧",
            points=[outline[0], outline[1]],
            stitch_type=StitchType.PLAIN_SEAM,
            seam_allowance=self.seam_allowance,
            mate_edge_name=f"{self.name}_领口",
        )

        top_edge = SewingEdge(
            name=f"{self.name}_领座外侧",
            points=[outline[2], outline[3]],
            stitch_type=StitchType.PLAIN_SEAM,
            seam_allowance=self.seam_allowance,
            mate_edge_name=f"{self.name}_瓣*_内侧",
        )

        return Panel(
            name=f"{self.name}_领座",
            component_type=ComponentType.COLLAR,
            outline=outline,
            sewing_edges=[bottom_edge, top_edge],
            grain_angle_rad=0.0,
            fabric_layers=1,
            metadata={
                "neck_circumference": self.neck_circumference,
                "collar_stand_height": self.collar_stand_height,
                "band_length": band_length,
            },
        )

    # ─── build_panels ────────────────────────────────────────────

    def build_panels(self) -> List[Panel]:
        """构建云肩的全部裁片面板。

        Returns:
            包含 1 个领座面板 + num_petals 个云片面板的列表。
        """
        panels: List[Panel] = []
        # 云肩中心点（原点）
        center = Point2D(0, 0)

        # 先构建领座
        collar_panel = self._build_collar_stand_panel(center)
        panels.append(collar_panel)

        # 构建各云片
        for i in range(self.num_petals):
            petal_panel = self._build_petal_panel(i, center)
            panels.append(petal_panel)

        return panels

    # ─── to_garment_code ──────────────────────────────────────────

    def to_garment_code(self) -> str:
        """导出服装 DSL 代码。

        DSL 格式示例:
            ACCESSORY 云肩 {
                TYPE CloudShoulder
                DYNASTY 明,清
                NECK_CIRCUMFERENCE 38.0
                PETALS 4 {
                    PETAL 1 { INNER_R 8.05 OUTER_R 26.05 ANGLE 0.0 }
                    ...
                }
                COLLAR_STAND { HEIGHT 2.0 INNER_R 6.05 OUTER_R 8.05 }
                SEAM_ALLOWANCE 1.0
            }

        Returns:
            DSL 代码字符串。
        """
        lines: List[str] = []
        lines.append(f"ACCESSORY {self.name} {{")
        lines.append(f"    TYPE CloudShoulder")
        # 兼容朝代
        dynasty_names = "，".join(d.value for d in self.compatible_dynasties)
        lines.append(f"    DYNASTY {dynasty_names}")
        lines.append(f"    NECK_CIRCUMFERENCE {self.neck_circumference:.1f}")
        lines.append(f"    OVERLAP_RATIO {self.overlap_ratio:.2f}")
        lines.append(f"    PETALS {self.num_petals} {{")

        for i in range(self.num_petals):
            base_angle = math.degrees(self._petal_base_angle(i))
            ang_start, ang_end = self._petal_angle_range(i)
            lines.append(
                f"        PETAL {i + 1} {{"
                f" INNER_R {self.inner_radius:.2f}"
                f" OUTER_R {self.outer_radius:.2f}"
                f" ANGLE {base_angle:.1f}"
                f" ANGLE_START {math.degrees(ang_start):.1f}"
                f" ANGLE_END {math.degrees(ang_end):.1f}"
                f" }}"
            )

        lines.append("    }")
        lines.append(f"    COLLAR_STAND {{")
        lines.append(f"        HEIGHT {self.collar_stand_height:.1f}")
        lines.append(f"        INNER_R {self.neck_radius:.2f}")
        lines.append(f"        OUTER_R {self.inner_radius:.2f}")
        lines.append(f"    }}")
        lines.append(f"    SEAM_ALLOWANCE {self.seam_allowance:.1f}")
        lines.append(f"}}")

        return "\n".join(lines)

    # ─── validate ─────────────────────────────────────────────────

    def validate(self) -> List[str]:
        """验证参数合理性。"""
        issues = super().validate()
        if self.num_petals < 4:
            issues.append(f"[{self.name}] 云片数过少（{self.num_petals}），建议至少 4 片")
        if self.num_petals > 8:
            issues.append(f"[{self.name}] 云片数过多（{self.num_petals}），建议不超过 8 片")
        if self.petal_radius < self.collar_stand_height:
            issues.append(
                f"[{self.name}] 云片径向长（{self.petal_radius}cm）应大于领座高度"
                f"（{self.collar_stand_height}cm）"
            )
        if self.overlap_ratio < 0:
            issues.append(f"[{self.name}] 叠合比例不能为负值")
        if self.overlap_ratio > 0.5:
            issues.append(f"[{self.name}] 叠合比例过大（{self.overlap_ratio}），可能导致云片严重重叠")
        if self.petal_radius > 40:
            issues.append(f"[{self.name}] 云片径向长较大（{self.petal_radius}cm），请确认是否为预期尺寸")
        return issues

    # ─── 工具方法 ─────────────────────────────────────────────────

    def get_flat_layout(self) -> Dict[str, Any]:
        """获取云肩平铺布局信息（用于可视化或排版）。

        Returns:
            包含直径、云片角度、轮廓点等布局数据的字典。
        """
        return {
            "name": self.name,
            "type": "CloudShoulder",
            "neck_radius": self.neck_radius,
            "inner_radius": self.inner_radius,
            "outer_radius": self.outer_radius,
            "total_diameter": self.outer_radius * 2,
            "num_petals": self.num_petals,
            "overlap_ratio": self.overlap_ratio,
            "collar_stand_height": self.collar_stand_height,
            "dynasties": [d.value for d in self.compatible_dynasties],
            "petal_angles_deg": [
                math.degrees(self._petal_base_angle(i))
                for i in range(self.num_petals)
            ],
        }

    def __repr__(self) -> str:
        return (
            f"CloudShoulder(name='{self.name}', petals={self.num_petals}, "
            f"neck={self.neck_circumference:.0f}cm, radius={self.petal_radius:.0f}cm, "
            f"dynasties={[d.value for d in self.compatible_dynasties]})"
        )
