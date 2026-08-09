"""
马面裙 (Mamian Skirt / Horse-Face Skirt) ⭐ 核心交付件

明代至清代最具代表性的汉族女裙形制之一。因裙身前后各有一块
长方形的"马面"（又称"裙门"）而得名 —— 马面平整无褶，
两侧则密排对褶（箱褶 / 马面褶），整体呈现"前后平整、两侧打褶"
的独特廓形。穿着时马面居中，褶裥自然垂落，行走间裙摆摇曳。

============================================================================
历史源流
============================================================================
- 明制马面裙：马面较窄（约 20-28cm），褶裥细密规整，面料多采用
  织金/妆花，底襕（裙底横襕）明显，整体庄重华丽。
- 清制马面裙：马面渐宽（可达 30-38cm），褶裥相对疏朗，刺绣装饰
  更为繁复，裙门常饰以独立绣片（裙门绣）。

============================================================================
结构组成（共 5+ 片裁片）
============================================================================
  (1) N 片马面裁片 — 前后平整矩形，宽 W_mamian ≥ 15cm，
      长约及足踝（裙长），是马面裙区别于普通褶裙的关键特征。
  (2) 左侧褶裥侧片 — 密排对褶（箱褶），收拢时贴腰，
      展开后蓬松，形成裙摆量感。
  (3) 右侧褶裥侧片 — 与左侧对称。
  (4) 腰头裁片 — 横长矩形，覆盖整个腰围，两端延伸为系带。
  (5) 左/右系带 — 自腰头延伸或单独裁制。

============================================================================
核心数学关系
============================================================================
  腰围_总 = N_马面 × W_马面宽 + 2 × 侧片_收拢宽

  其中：
    - 侧片_收拢宽 = (腰围_总 - N_马面 × W_马面宽) / 2
    - 侧片_展开宽 = 侧片_收拢宽 + 褶数 × 2 × 褶深
    - 约束：W_马面 ≥ 15cm（马面裙硬性要求）
    - 约束：褶数必须为偶数（保证左右对称）

  褶裥为活褶（对褶/箱褶），每一褶消耗 2×褶深 的面料，
  褶裥分布均匀，从腰头向下自然散开。

============================================================================
参数说明
============================================================================
  skirt_length       裙长 (cm)，默认 95，范围 [75, 120]
  waist_circumference 腰围 (cm)，默认 70，范围 [55, 105]
  mamian_width       马面宽 (cm)，默认 28，范围 [18, 38]，必须 ≥15
  num_mamian         马面数量，默认 2，范围 [2, 4]
  pleat_count        褶数（每侧），默认 6，范围 [4, 12]，步长 2，必须为偶数
  pleat_depth        褶深 (cm)，默认 4.5，范围 [2, 8]
  pleat_direction    褶向，0=向外（常规），1=向内，范围 [0, 1]
  waistband_height   腰头高 (cm)，默认 6，范围 [3, 10]
  tie_length         系带长 (cm)，默认 80，范围 [50, 150]
  border_width       底襕宽 (cm)，默认 10，范围 [0, 25]
  seam_allowance     缝份 (cm)，默认 1.0
"""

from __future__ import annotations

import math
from typing import List, Optional, Dict, Any, Tuple

from ..base import (
    GarmentComponent, ComponentType, Dynasty,
    Panel, SewingEdge, Point2D, StitchType,
)
from ..curves import line


# ─── 马面裙各裁片位置名称映射 ──────────────────────────────────────

# num_mamian=2 时的命名
_MAMIAN_NAMES_2: Dict[int, str] = {
    0: "前马面片",
    1: "后马面片",
}

# num_mamian=4 时的命名（前后各两片，轻微对称）
_MAMIAN_NAMES_4: Dict[int, str] = {
    0: "前左马面片",
    1: "前右马面片",
    2: "后左马面片",
    3: "后右马面片",
}

_MAMIAN_NAME_MAPS: Dict[int, Dict[int, str]] = {
    2: _MAMIAN_NAMES_2,
    4: _MAMIAN_NAMES_4,
}


class MamianSkirt(GarmentComponent):
    """马面裙 — 明/清制女裙，前后马面平整、两侧密排对褶。

    这是整个传统服饰生成系统中裙类的核心组件。
    马面裙的几何关键在于：马面宽度（≥15cm）与褶裥深度
    共同决定了裙摆的展开量、穿着时的廓形蓬度以及历史断代
    的形制准确性。
    """

    # ── 朝代兼容性（类变量）──────────────────────────────────────
    compatible_dynasties: List[Dynasty] = [Dynasty.MING, Dynasty.QING]

    def __init__(
        self,
        name: str = "马面裙",
        skirt_length: float = 95.0,
        waist_circumference: float = 70.0,
        mamian_width: float = 28.0,
        num_mamian: int = 2,
        pleat_count: int = 6,
        pleat_depth: float = 4.5,
        pleat_direction: float = 0.0,
        waistband_height: float = 6.0,
        tie_length: float = 80.0,
        border_width: float = 10.0,
        seam_allowance: float = 1.0,
    ):
        """初始化马面裙部件。

        Args:
            name: 部件名称
            skirt_length: 裙长（从腰头下沿至裙底），默认 95cm
            waist_circumference: 腰围（沿腰头一圈的净尺寸），默认 70cm
            mamian_width: 单片马面宽度，默认 28cm，必须 ≥15cm
            num_mamian: 马面数量，默认 2（前后各一），可选 4
            pleat_count: 每侧褶裥数，默认 6，必须为偶数，步长 2
            pleat_depth: 每个褶的折叠深度，默认 4.5cm
            pleat_direction: 褶向 0=向外（常规），1=向内
            waistband_height: 腰头高度，默认 6cm
            tie_length: 系带长度（单条），默认 80cm
            border_width: 底襕（裙底横襕装饰带）宽度，0 表示无底襕
            seam_allowance: 缝份宽度，默认 1.0cm
        """
        super().__init__(
            name=name,
            component_type=ComponentType.SKIRT,
            seam_allowance=seam_allowance,
        )

        # ── 尺寸参数 ──
        self.skirt_length = skirt_length
        self.waist_circumference = waist_circumference
        self.mamian_width = mamian_width
        self.num_mamian = num_mamian
        self.pleat_count = pleat_count
        self.pleat_depth = pleat_depth
        self.pleat_direction = pleat_direction
        self.waistband_height = waistband_height
        self.tie_length = tie_length
        self.border_width = border_width

        # ── 参数校验与自动修正 ──
        self._validate_and_fix_params()

    # ═══════════════════════════════════════════════════════════════
    # 参数校验与自动修正
    # ═══════════════════════════════════════════════════════════════

    def _validate_and_fix_params(self) -> None:
        """校验参数合法性并自动修正明显异常值。

        修正策略：
          - 马面宽小于 15cm 时强制提升至 15cm
          - 褶数为奇数时自动 +1 调整为偶数
          - 侧片收拢宽为负时自动缩减马面宽
        """
        # 马面宽硬性约束
        if self.mamian_width < 15.0:
            print(
                f"[{self.name}] 警告: 马面宽 {self.mamian_width:.1f}cm "
                f"小于最低要求 15cm，已自动修正为 15cm"
            )
            self.mamian_width = 15.0

        # 褶数必须为偶数
        if self.pleat_count % 2 != 0:
            old = self.pleat_count
            self.pleat_count += 1
            print(
                f"[{self.name}] 警告: 褶数 {old} 为奇数，"
                f"已自动修正为 {self.pleat_count}"
            )

        # 侧片收拢宽 = (腰围 - N×马面宽) / 2
        side_visible = self._calc_side_visible()
        if side_visible < 3.0:
            # 马面占比过大，减小马面宽
            max_mamian = (self.waist_circumference - 6.0) / self.num_mamian
            if max_mamian >= 15.0:
                print(
                    f"[{self.name}] 警告: 马面宽 {self.mamian_width:.1f}cm "
                    f"过大导致侧片过窄，已自动缩减至 {max_mamian:.1f}cm"
                )
                self.mamian_width = max_mamian
            else:
                print(
                    f"[{self.name}] 警告: 腰围 {self.waist_circumference:.0f}cm "
                    f"不足以容纳 {self.num_mamian} 片马面（各 ≥15cm），"
                    f"请增大腰围或减少马面数量"
                )

        # 褶深比例检查：仅在展开/收拢比极端时警告
        side_visible_after = self._calc_side_visible()
        unfold_ratio = self.side_unfolded_width / max(side_visible_after, 0.01)
        if unfold_ratio > 15.0:
            print(
                f"[{self.name}] 警告: 侧片展开/收拢比 {unfold_ratio:.1f} "
                f"偏大（褶深 {self.pleat_depth:.1f}cm, "
                f"收拢宽 {side_visible_after:.1f}cm），"
                f"褶裥可能过于厚重"
            )

    # ═══════════════════════════════════════════════════════════════
    # 派生尺寸计算
    # ═══════════════════════════════════════════════════════════════

    def _calc_side_visible(self) -> float:
        """计算单侧褶裥收拢后的可见宽度（cm）。

        公式: (腰围 - N_马面 × W_马面宽) / 2
        """
        return (self.waist_circumference - self.num_mamian * self.mamian_width) / 2.0

    def _calc_side_unfolded(self) -> float:
        """计算单侧褶裥完全展开后的面料宽度（cm）。

        公式: 侧片收拢宽 + 褶数 × 2 × 褶深
        每个对褶消耗 2×褶深 的面料（一进一出）。
        """
        return self._calc_side_visible() + self.pleat_count * 2.0 * self.pleat_depth

    # ═══════════════════════════════════════════════════════════════
    # 辅助属性
    # ═══════════════════════════════════════════════════════════════

    @property
    def side_visible_width(self) -> float:
        """单侧褶裥收拢后的可见宽度（cm）。"""
        return self._calc_side_visible()

    @property
    def side_unfolded_width(self) -> float:
        """单侧褶裥完全展开后的面料宽度（cm）。"""
        return self._calc_side_unfolded()

    @property
    def total_fabric_width(self) -> float:
        """裙身一圈所需的总面料宽度（展开态，不含缝份，cm）。

        公式: N_马面 × W_马面 + 2 × 侧片展开宽
        """
        return (self.num_mamian * self.mamian_width
                + 2.0 * self._calc_side_unfolded())

    @property
    def pleat_direction_name(self) -> str:
        """褶向中文名称。"""
        return "向外（常规）" if self.pleat_direction <= 0.5 else "向内"

    @property
    def dynasty_range(self) -> str:
        """朝代适用性中文描述。"""
        return "明制/清制"

    @property
    def summary(self) -> str:
        """生成参数摘要字符串。"""
        return (
            f"马面裙 | 裙长{self.skirt_length:.0f}cm | "
            f"腰围{self.waist_circumference:.0f}cm | "
            f"马面{self.num_mamian}片×{self.mamian_width:.0f}cm | "
            f"褶{self.pleat_count}对×深{self.pleat_depth:.1f}cm | "
            f"展开围{self.total_fabric_width:.0f}cm"
        )

    # ═══════════════════════════════════════════════════════════════
    # 面板构建 — build_panels() 核心方法
    # ═══════════════════════════════════════════════════════════════

    def build_panels(self) -> List[Panel]:
        """构建马面裙所有裁片面板。

        构建顺序：
          1. N 片马面裁片（平整矩形，无褶）
          2. 左侧褶裥侧片（含褶位内线标记）
          3. 右侧褶裥侧片（含褶位内线标记）
          4. 腰头裁片
          5. 左系带
          6. 右系带

        Returns:
            Panel 对象列表，按构建顺序排列。
        """
        panels: List[Panel] = []

        # ── 读参 ──
        L = self.skirt_length          # 裙长
        Wm = self.mamian_width         # 马面宽
        Nm = self.num_mamian           # 马面数量
        Np = self.pleat_count          # 每侧褶数
        Dp = self.pleat_depth          # 褶深
        Wh = self.waistband_height     # 腰头高
        Lt = self.tie_length           # 系带长
        Bw = self.border_width         # 底襕宽
        sa = self.seam_allowance       # 缝份
        Sv = self.side_visible_width   # 侧片收拢宽
        Su = self.side_unfolded_width  # 侧片展开宽

        # ==========================================================
        # (1) N 片马面裁片
        # ==========================================================
        # 每一马面为矩形: 宽 Wm, 高 L
        # 坐标系: (0,0) 为马面左上角，x 轴向右（布幅方向），y 轴向下（裙长方向）
        #
        # 马面名称策略:
        #   Nm=2: "前马面片", "后马面片"
        #   Nm=4: "前左马面片", "前右马面片", "后左马面片", "后右马面片"
        #   其他: 数字编号
        name_map = _MAMIAN_NAME_MAPS.get(Nm, {})
        for i in range(Nm):
            mamian_name = name_map.get(i, f"马面片{i + 1}")

            # 马面轮廓: 逆时针矩形
            # (0,0) → (Wm,0) → (Wm,L) → (0,L) → (0,0)
            outline = [
                Point2D(0, 0),
                Point2D(Wm, 0),
                Point2D(Wm, L),
                Point2D(0, L),
                Point2D(0, 0),
            ]

            # 缝边
            # 注意: 上下边为水平缝边，左右边为竖直缝边（与侧片/相邻马面缝合）
            sewing_edges: List[SewingEdge] = [
                SewingEdge(
                    name="上腰口",
                    points=[Point2D(0, 0), Point2D(Wm, 0)],
                    stitch_type=StitchType.PLAIN_SEAM,
                    seam_allowance=sa,
                    mate_edge_name="腰头下沿",
                    is_hem=False,
                ),
                SewingEdge(
                    name="下摆",
                    points=[Point2D(Wm, L), Point2D(0, L)],
                    stitch_type=StitchType.HEM,
                    seam_allowance=sa * 2.0,
                    is_hem=True,
                ),
                SewingEdge(
                    name="左侧缝",
                    points=[Point2D(0, 0), Point2D(0, L)],
                    stitch_type=StitchType.PLAIN_SEAM,
                    seam_allowance=sa,
                    mate_edge_name=None,  # 与侧片或相邻马面缝合，运行时动态配对
                    is_hem=False,
                ),
                SewingEdge(
                    name="右侧缝",
                    points=[Point2D(Wm, 0), Point2D(Wm, L)],
                    stitch_type=StitchType.PLAIN_SEAM,
                    seam_allowance=sa,
                    mate_edge_name=None,
                    is_hem=False,
                ),
            ]

            # 底襕内线（如有）：距裙底 border_width 处沿水平方向标记
            internal_lines: List[List[Point2D]] = []
            if Bw > 0 and Bw < L:
                internal_lines.append([
                    Point2D(0, L - Bw),
                    Point2D(Wm, L - Bw),
                ])

            # 判断位置: 前后
            is_front = (i < Nm / 2)
            position = "前" if is_front else "后"

            panel = Panel(
                name=mamian_name,
                component_type=ComponentType.SKIRT,
                outline=outline,
                sewing_edges=sewing_edges,
                internal_lines=internal_lines,
                grain_angle_rad=0.0,          # 直纹（经向沿裙长）
                fabric_layers=1,
                metadata={
                    "panel_type": "马面",
                    "index": i,
                    "position": position,
                    "width": Wm,
                    "height": L,
                    "has_border": Bw > 0,
                    "border_width": Bw,
                },
            )
            panels.append(panel)

        # ==========================================================
        # (2) 左侧褶裥侧片
        # ==========================================================
        # 展开态矩形: 宽 Su, 高 L
        # 收拢后宽度为 Sv（即缝合后腰部可见宽度）
        # 含 Np 个对褶，每个褶消耗 2×Dp 的面料
        left_side_panel = self._build_pleated_side_panel(
            side_name="左侧褶裥片",
            side_label="左",
            unfolded_width=Su,
            visible_width=Sv,
        )
        panels.append(left_side_panel)

        # ==========================================================
        # (3) 右侧褶裥侧片
        # ==========================================================
        right_side_panel = self._build_pleated_side_panel(
            side_name="右侧褶裥片",
            side_label="右",
            unfolded_width=Su,
            visible_width=Sv,
        )
        panels.append(right_side_panel)

        # ==========================================================
        # (4) 腰头裁片
        # ==========================================================
        # 腰头为长矩形: 宽 waist_circumference, 高 Wh
        # 注意: 系带可以从腰头两端延伸，这里腰头不包含系带延伸，
        # 系带单独裁制（更符合现代汉服制版习惯）
        waistband_outline = [
            Point2D(0, 0),
            Point2D(self.waist_circumference, 0),
            Point2D(self.waist_circumference, Wh),
            Point2D(0, Wh),
            Point2D(0, 0),
        ]
        waistband_sewing_edges: List[SewingEdge] = [
            SewingEdge(
                name="腰头下沿",
                points=[
                    Point2D(0, Wh),
                    Point2D(self.waist_circumference, Wh),
                ],
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="上腰口",
                is_hem=False,
            ),
            SewingEdge(
                name="腰头上沿",
                points=[
                    Point2D(self.waist_circumference, 0),
                    Point2D(0, 0),
                ],
                stitch_type=StitchType.HEM,
                seam_allowance=sa,
                is_hem=False,
            ),
            SewingEdge(
                name="腰头左端",
                points=[Point2D(0, Wh), Point2D(0, 0)],
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="左系带根部",
                is_hem=False,
            ),
            SewingEdge(
                name="腰头右端",
                points=[Point2D(self.waist_circumference, 0),
                        Point2D(self.waist_circumference, Wh)],
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="右系带根部",
                is_hem=False,
            ),
        ]
        waistband_panel = Panel(
            name="腰头片",
            component_type=ComponentType.SKIRT,
            outline=waistband_outline,
            sewing_edges=waistband_sewing_edges,
            grain_angle_rad=0.0,
            fabric_layers=2,  # 腰头通常双层（对折或加衬）
            metadata={
                "panel_type": "腰头",
                "width": self.waist_circumference,
                "height": Wh,
                "fabric_layers": 2,
            },
        )
        panels.append(waistband_panel)

        # ==========================================================
        # (5) 左系带
        # ==========================================================
        left_tie_panel = self._build_tie_panel(
            tie_name="左系带",
            tie_label="左",
        )
        panels.append(left_tie_panel)

        # ==========================================================
        # (6) 右系带
        # ==========================================================
        right_tie_panel = self._build_tie_panel(
            tie_name="右系带",
            tie_label="右",
        )
        panels.append(right_tie_panel)

        return panels

    # ═══════════════════════════════════════════════════════════════
    # 面板构建辅助方法
    # ═══════════════════════════════════════════════════════════════

    def _build_pleated_side_panel(
        self,
        side_name: str,
        side_label: str,
        unfolded_width: float,
        visible_width: float,
    ) -> Panel:
        """构建一片褶裥侧片。

        侧片为矩形，宽 unfolded_width，高 skirt_length。
        内部包含 N_pleat 条垂直褶线（标记每个褶的折叠位置），
        用于指导后续的褶裥塑形。

        Args:
            side_name: 面板名称
            side_label: 侧别标签 "左"/"右"
            unfolded_width: 展开态面料宽度
            visible_width: 收拢后可见宽度

        Returns:
            侧片面 Panel 对象
        """
        L = self.skirt_length
        Np = self.pleat_count
        Dp = self.pleat_depth
        Bw = self.border_width
        sa = self.seam_allowance

        # 轮廓: 逆时针矩形
        outline = [
            Point2D(0, 0),
            Point2D(unfolded_width, 0),
            Point2D(unfolded_width, L),
            Point2D(0, L),
            Point2D(0, 0),
        ]

        # 缝边
        sewing_edges: List[SewingEdge] = [
            SewingEdge(
                name=f"{side_label}侧片上腰口",
                points=[Point2D(0, 0), Point2D(unfolded_width, 0)],
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name="腰头下沿",
                is_hem=False,
            ),
            SewingEdge(
                name=f"{side_label}侧片下摆",
                points=[Point2D(unfolded_width, L), Point2D(0, L)],
                stitch_type=StitchType.HEM,
                seam_allowance=sa * 2.0,
                is_hem=True,
            ),
            SewingEdge(
                name=f"{side_label}侧片前接边",
                points=[Point2D(0, 0), Point2D(0, L)],
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name=None,
                is_hem=False,
            ),
            SewingEdge(
                name=f"{side_label}侧片后接边",
                points=[Point2D(unfolded_width, 0), Point2D(unfolded_width, L)],
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name=None,
                is_hem=False,
            ),
        ]

        # ── 褶位内线标记 ──
        # 每个对褶在面料上占据 2×Dp 宽度（进深+回程）
        # 收拢段 visible_width 位于展开面料的一端（靠马面侧）
        # 褶区占据剩余宽度 Np × 2 × Dp
        #
        # 布局（从左→右）:
        #   [收拢区: visible_width] + [褶区: Np × 2 × Dp]
        # 或对称布置（将收拢区居中）取决于褶向
        #
        # 这里采用传统做法: 收拢区靠马面侧，褶区靠外侧
        # 即: 侧片一边是平整收拢区（接马面），另一边是密褶区（接后马面或侧后）
        internal_lines: List[List[Point2D]] = []

        # 垂直褶线：从收拢区结束位置开始，每隔 2×Dp 画一条垂直线
        fold_start_x = visible_width
        for fold_idx in range(Np + 1):  # Np+1 条线围出 Np 个褶位
            fold_x = fold_start_x + fold_idx * (2.0 * Dp)
            if fold_x <= unfolded_width + 0.01:
                line_end_y = L
                internal_lines.append([
                    Point2D(fold_x, 0),
                    Point2D(fold_x, line_end_y),
                ])

        # 底襕内线
        if Bw > 0 and Bw < L:
            internal_lines.append([
                Point2D(0, L - Bw),
                Point2D(unfolded_width, L - Bw),
            ])

        return Panel(
            name=side_name,
            component_type=ComponentType.SKIRT,
            outline=outline,
            sewing_edges=sewing_edges,
            internal_lines=internal_lines,
            grain_angle_rad=0.0,
            fabric_layers=1,
            metadata={
                "panel_type": "褶裥侧片",
                "side": side_label,
                "unfolded_width": unfolded_width,
                "visible_width": visible_width,
                "pleat_count": Np,
                "pleat_depth": Dp,
                "pleat_direction": self.pleat_direction_name,
                "has_border": Bw > 0,
                "border_width": Bw,
            },
        )

    def _build_tie_panel(
        self,
        tie_name: str,
        tie_label: str,
    ) -> Panel:
        """构建一片系带。

        系带为细长矩形: 宽 tie_length, 高 waistband_height。
        根部与腰头端部缝合。

        Args:
            tie_name: 系带面板名称
            tie_label: 侧别标签 "左"/"右"

        Returns:
            系带 Panel 对象
        """
        Wh = self.waistband_height
        Lt = self.tie_length
        sa = self.seam_allowance

        # 轮廓: 逆时针矩形 (长条: 宽 Lt, 高 Wh)
        outline = [
            Point2D(0, 0),
            Point2D(Lt, 0),
            Point2D(Lt, Wh),
            Point2D(0, Wh),
            Point2D(0, 0),
        ]

        sewing_edges: List[SewingEdge] = [
            SewingEdge(
                name=f"{tie_label}系带根部",
                points=[Point2D(0, Wh), Point2D(0, 0)],
                stitch_type=StitchType.PLAIN_SEAM,
                seam_allowance=sa,
                mate_edge_name=f"腰头{tie_label}端",
                is_hem=False,
            ),
            SewingEdge(
                name=f"{tie_label}系带尾部",
                points=[Point2D(Lt, 0), Point2D(Lt, Wh)],
                stitch_type=StitchType.HEM,
                seam_allowance=sa,
                is_hem=False,
            ),
            SewingEdge(
                name=f"{tie_label}系带上边",
                points=[Point2D(0, 0), Point2D(Lt, 0)],
                stitch_type=StitchType.HEM,
                seam_allowance=sa,
                is_hem=False,
            ),
            SewingEdge(
                name=f"{tie_label}系带下边",
                points=[Point2D(Lt, Wh), Point2D(0, Wh)],
                stitch_type=StitchType.HEM,
                seam_allowance=sa,
                is_hem=False,
            ),
        ]

        return Panel(
            name=tie_name,
            component_type=ComponentType.SKIRT,
            outline=outline,
            sewing_edges=sewing_edges,
            grain_angle_rad=0.0,
            fabric_layers=2,  # 系带通常双层对折
            metadata={
                "panel_type": "系带",
                "side": tie_label,
                "length": Lt,
                "height": Wh,
                "fabric_layers": 2,
            },
        )

    # ═══════════════════════════════════════════════════════════════
    # DSL 导出 — to_garment_code()
    # ═══════════════════════════════════════════════════════════════

    def to_garment_code(self) -> str:
        """将马面裙导出为 GarmentCode DSL 格式。

        导出内容包括:
          - 部件声明（类型、朝代、全部参数）
          - 各裁片几何定义
          - 缝合关系
          - 褶裥标记与底襕信息
        """
        lines: List[str] = []

        # ── 头部注释 ──
        lines.append("# ══════════════════════════════════════════════")
        lines.append("# 马面裙 (Mamian Skirt / Horse-Face Skirt)")
        lines.append(f"# 朝代: {', '.join(d.value for d in self.compatible_dynasties)}")
        lines.append(f"# 参数摘要: {self.summary}")
        lines.append("# ══════════════════════════════════════════════")
        lines.append("")

        # ── 部件声明 ──
        lines.append("mamian_skirt = Skirt(")
        lines.append(f"    name=\"{self.name}\",")
        lines.append(f"    skirt_length={self.skirt_length},           # 裙长 (cm)")
        lines.append(f"    waist_circumference={self.waist_circumference}, # 腰围 (cm)")
        lines.append(f"    mamian_width={self.mamian_width},           # 马面宽 (cm)")
        lines.append(f"    num_mamian={self.num_mamian},               # 马面数量")
        lines.append(f"    pleat_count={self.pleat_count},             # 每侧褶数(偶)")
        lines.append(f"    pleat_depth={self.pleat_depth},             # 褶深 (cm)")
        lines.append(f"    pleat_direction={self.pleat_direction},     # 褶向 (0=外)")
        lines.append(f"    waistband_height={self.waistband_height},   # 腰头高 (cm)")
        lines.append(f"    tie_length={self.tie_length},               # 系带长 (cm)")
        lines.append(f"    border_width={self.border_width},           # 底襕宽 (cm)")
        lines.append(f"    seam_allowance={self.seam_allowance},       # 缝份 (cm)")
        lines.append(f"    dynasty={[d.value for d in self.compatible_dynasties]},")
        lines.append("    type='mamian_skirt',")
        lines.append(")")
        lines.append("")

        # ── 派生尺寸块 ──
        lines.append("# ── 派生尺寸 ──")
        lines.append(f"# 侧片收拢宽(单侧): {self.side_visible_width:.1f} cm")
        lines.append(f"# 侧片展开宽(单侧): {self.side_unfolded_width:.1f} cm")
        lines.append(f"# 裙摆总展开围:     {self.total_fabric_width:.1f} cm")
        lines.append(f"# 展开/收拢比:      {self.total_fabric_width / self.waist_circumference:.2f}")
        lines.append("")

        # ── 裁片块 ──
        for panel in self.panels:
            lines.append(f"# ── 裁片: {panel.name} ──")
            lines.append(f"panel_{panel.name.replace(' ', '_')} = Panel(")
            lines.append(f"    name='{panel.name}',")
            lines.append(f"    component_type='{panel.component_type.name}',")
            # 包围盒尺寸
            lo, hi = panel.bounding_box
            lines.append(f"    width={hi.x - lo.x:.1f},")
            lines.append(f"    height={hi.y - lo.y:.1f},")
            lines.append(f"    outline_points={len(panel.outline)},")
            lines.append(f"    sewing_edge_count={len(panel.sewing_edges)},")
            lines.append(f"    internal_line_count={len(panel.internal_lines)},")
            lines.append(f"    fabric_layers={panel.fabric_layers},")
            lines.append(f"    grain='straight',  # 直纹，经向沿裙长")
            # 元数据
            for k, v in panel.metadata.items():
                lines.append(f"    {k}={v!r},")
            lines.append(")")
            lines.append("")

            # 缝边详情
            for edge in panel.sewing_edges:
                mate_str = f", mate='{edge.mate_edge_name}'" if edge.mate_edge_name else ""
                hem_str = ", hem" if edge.is_hem else ""
                lines.append(
                    f"    # {edge.name}: "
                    f"stitch={edge.stitch_type.name}, "
                    f"sa={edge.seam_allowance}cm, "
                    f"len={edge.length:.1f}cm"
                    f"{mate_str}{hem_str}"
                )

            # 内线详情（褶线）
            if panel.internal_lines:
                lines.append(f"    # 内部结构线（{len(panel.internal_lines)} 条）:")
                for idx, iline in enumerate(panel.internal_lines):
                    p0, p1 = iline[0], iline[1]
                    if abs(p0.y - p1.y) < 0.01:
                        # 水平线 → 底襕标记
                        lines.append(f"    #   线{idx}: 底襕标记 y={p0.y:.1f}cm")
                    else:
                        # 垂直线 → 褶位标记
                        lines.append(f"    #   线{idx}: 褶位标记 x={p0.x:.1f}cm")
            lines.append("")

        # ── 缝合关系汇总 ──
        all_mates = [
            (panel.name, e.name, e.mate_edge_name)
            for panel in self.panels
            for e in panel.sewing_edges
            if e.mate_edge_name
        ]
        if all_mates:
            lines.append("# ── 缝合关系 ──")
            for panel_name, edge_name, mate_name in all_mates:
                lines.append(
                    f"stitch(\"{panel_name}.{edge_name}\", "
                    f"\"{mate_name}\")"
                )
            lines.append("")

        # ── 褶裥说明块 ──
        lines.append("# ── 褶裥说明 ──")
        lines.append("# 褶裥类型: 对褶（箱褶 / Box Pleat）")
        lines.append(f"# 每侧褶数: {self.pleat_count}")
        lines.append(f"# 褶深: {self.pleat_depth} cm")
        lines.append(f"# 单褶面料消耗: {2 * self.pleat_depth:.1f} cm")
        lines.append(f"# 褶向: {self.pleat_direction_name}")
        lines.append(f"# 侧片收拢宽: {self.side_visible_width:.1f} cm → "
                     f"展开宽: {self.side_unfolded_width:.1f} cm "
                     f"(×{self.side_unfolded_width / max(self.side_visible_width, 0.01):.1f})")
        lines.append("# 穿着时所有褶裥向腰头方向收拢，"
                     "以系带固定，裙门居中平整。")
        lines.append("")

        # ── 底襕说明块 ──
        if self.border_width > 0:
            lines.append("# ── 底襕说明 ──")
            lines.append(f"# 底襕宽度: {self.border_width} cm")
            lines.append(f"# 底襕距裙底: 0 ~ {self.border_width} cm (裙底向上)")
            lines.append("# 底襕通常为独立面料横条缝于裙底，"
                         "可用织金/妆花/刺绣装饰。")
            lines.append("")

        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════════
    # 验证
    # ═══════════════════════════════════════════════════════════════

    def validate(self) -> List[str]:
        """验证参数合理性，返回警告/错误信息列表。

        覆盖:
          - 基础缝份检查（继承自基类）
          - 裙长范围
          - 腰围范围
          - 马面宽硬性 ≥15cm
          - 褶数偶数检查
          - 侧片几何可行性
        """
        issues = super().validate()

        # 裙长范围
        if self.skirt_length < 75 or self.skirt_length > 120:
            issues.append(
                f"[{self.name}] 裙长 {self.skirt_length}cm "
                f"超出推荐范围 [75, 120]cm"
            )

        # 腰围范围
        if self.waist_circumference < 55 or self.waist_circumference > 105:
            issues.append(
                f"[{self.name}] 腰围 {self.waist_circumference}cm "
                f"超出推荐范围 [55, 105]cm"
            )

        # 马面宽硬性约束
        if self.mamian_width < 15.0:
            issues.append(
                f"[{self.name}] 错误: 马面宽 {self.mamian_width}cm "
                f"小于最低要求 15cm！这不再是马面裙。"
            )

        # 马面宽上限检查
        if self.mamian_width > 38:
            issues.append(
                f"[{self.name}] 马面宽 {self.mamian_width}cm "
                f"超出推荐范围 [18, 38]cm"
            )

        # 马面数量约束
        if self.num_mamian not in (2, 4):
            issues.append(
                f"[{self.name}] 马面数量 {self.num_mamian} "
                f"不受支持，推荐 2 或 4"
            )

        # 褶数偶数检查
        if self.pleat_count % 2 != 0:
            issues.append(
                f"[{self.name}] 错误: 褶数 {self.pleat_count} "
                f"为奇数，必须为偶数以保证两侧对称"
            )

        # 侧片几何可行性
        sv = self.side_visible_width
        if sv <= 0:
            issues.append(
                f"[{self.name}] 错误: 侧片收拢宽 {sv:.1f}cm ≤ 0，"
                f"腰围 {self.waist_circumference}cm 无法容纳 "
                f"{self.num_mamian} 片各 {self.mamian_width}cm 宽的马面，"
                f"请增大腰围或减小马面宽"
            )
        elif sv < 3.0:
            issues.append(
                f"[{self.name}] 警告: 侧片收拢宽仅 {sv:.1f}cm，"
                f"褶裥空间不足，建议至少 3cm"
            )

        # 褶深范围
        if self.pleat_depth < 2.0 or self.pleat_depth > 8.0:
            issues.append(
                f"[{self.name}] 褶深 {self.pleat_depth}cm "
                f"超出推荐范围 [2, 8]cm"
            )

        # 腰头高度范围
        if self.waistband_height < 3.0 or self.waistband_height > 10.0:
            issues.append(
                f"[{self.name}] 腰头高 {self.waistband_height}cm "
                f"超出推荐范围 [3, 10]cm"
            )

        # 系带长度范围
        if self.tie_length < 50 or self.tie_length > 150:
            issues.append(
                f"[{self.name}] 系带长 {self.tie_length}cm "
                f"超出推荐范围 [50, 150]cm"
            )

        # 底襕合理性
        if self.border_width > 0 and self.border_width >= self.skirt_length * 0.4:
            issues.append(
                f"[{self.name}] 底襕宽 {self.border_width}cm "
                f"超过裙长 {self.skirt_length}cm 的 40%，"
                f"可能比例失调"
            )

        return issues


# ═══════════════════════════════════════════════════════════════════
# 快速构建入口
# ═══════════════════════════════════════════════════════════════════

def build_mamian_skirt(
    skirt_length: float = 95.0,
    waist_circumference: float = 70.0,
    mamian_width: float = 28.0,
    num_mamian: int = 2,
    pleat_count: int = 6,
    pleat_depth: float = 4.5,
    pleat_direction: float = 0.0,
    waistband_height: float = 6.0,
    tie_length: float = 80.0,
    border_width: float = 10.0,
    seam_allowance: float = 1.0,
) -> MamianSkirt:
    """快速构建马面裙实例的便捷函数。

    Args:
        skirt_length: 裙长 (cm)，默认 95
        waist_circumference: 腰围 (cm)，默认 70
        mamian_width: 马面宽 (cm)，默认 28，必须 ≥15
        num_mamian: 马面数量，默认 2
        pleat_count: 每侧褶数，默认 6，必须为偶数
        pleat_depth: 褶深 (cm)，默认 4.5
        pleat_direction: 褶向，默认 0（向外）
        waistband_height: 腰头高 (cm)，默认 6
        tie_length: 系带长 (cm)，默认 80
        border_width: 底襕宽 (cm)，默认 10
        seam_allowance: 缝份 (cm)，默认 1.0

    Returns:
        构建好的 MamianSkirt 实例。
    """
    return MamianSkirt(
        name="马面裙",
        skirt_length=skirt_length,
        waist_circumference=waist_circumference,
        mamian_width=mamian_width,
        num_mamian=num_mamian,
        pleat_count=pleat_count,
        pleat_depth=pleat_depth,
        pleat_direction=pleat_direction,
        waistband_height=waistband_height,
        tie_length=tie_length,
        border_width=border_width,
        seam_allowance=seam_allowance,
    )
