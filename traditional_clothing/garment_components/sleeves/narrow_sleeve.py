"""
窄袖 (Narrow Sleeve) — 历代日常微锥形直袖

汉、唐、宋、明、清通用。袖根向袖口逐渐收窄，肘部微弧贴合手臂。
"""

from __future__ import annotations
from typing import List
from ..base import (
    GarmentComponent, ComponentType, Dynasty,
    Panel, SewingEdge, Point2D, StitchType,
)
from ..curves import line, bezier_curve


class NarrowSleeve(GarmentComponent):
    """窄袖：通袖78cm，袖口18cm，袖根20cm，肘宽22cm，袖山11cm，缝份1cm。

    肘部位置 0.45 处微扩以容纳肘关节，形成轻微锥度。
    裁片标记 mirrored=True 以生成左右对称袖片。
    """

    compatible_dynasties = [
        Dynasty.HAN, Dynasty.TANG, Dynasty.SONG, Dynasty.MING, Dynasty.QING,
    ]

    def __init__(self, name="窄袖",
                 sleeve_length=78.0, cuff_width=18.0, root_width=20.0,
                 elbow_width=22.0, elbow_position=0.45,
                 sleeve_cap_height=11.0, seam_allowance=1.0):
        super().__init__(name=name, component_type=ComponentType.SLEEVE,
                         seam_allowance=seam_allowance)
        self.sleeve_length = sleeve_length
        self.cuff_width = cuff_width
        self.root_width = root_width
        self.elbow_width = elbow_width
        self.elbow_position = elbow_position
        self.sleeve_cap_height = sleeve_cap_height

    def build_panels(self) -> List[Panel]:
        """构建逆时针外轮廓窄袖裁片。"""
        L   = self.sleeve_length
        ch  = self.cuff_width / 2
        rh  = self.root_width / 2
        eh  = self.elbow_width / 2
        ep  = self.elbow_position
        sch = self.sleeve_cap_height
        sa  = self.seam_allowance

        # 关键点坐标 — 袖根 y=0，袖口 y=L，袖山上凸
        cl = Point2D(-rh, 0)           # 左袖根
        cr = Point2D( rh, 0)           # 右袖根
        cp = Point2D(0, -sch)          # 袖山顶点
        ey = ep * L
        el = Point2D(-eh, ey)          # 左肘
        er = Point2D( eh, ey)          # 右肘
        cu = Point2D( ch, L)           # 右袖口
        cd = Point2D(-ch, L)           # 左袖口

        # 袖山弧线 — 贝塞尔曲线
        lc = bezier_curve([cl, Point2D(-rh * 0.85, -sch * 0.65), cp], 20)
        rc = bezier_curve([cp, Point2D( rh * 0.85, -sch * 0.65), cr], 20)

        # 右侧缝 — 肘部向外微凸
        ru = bezier_curve([cr, Point2D(eh + 0.6, ey * 0.65), er], 16)
        rl = line(er, cu)

        # 袖口 — 横线
        hm = line(cu, cd)

        # 左侧缝 — 肘部向外微凸
        ll = line(cd, el)
        lu = bezier_curve([el, Point2D(-eh - 0.6, ey * 0.65), cl], 16)

        # 逆时针外轮廓
        outline = (lc + rc[1:] + ru[1:] + rl[1:] +
                   hm[1:] + ll[1:] + lu[1:-1])

        panel = Panel(
            name=self.name,
            component_type=ComponentType.SLEEVE,
            outline=outline,
            sewing_edges=[
                SewingEdge("袖山弧线", lc + rc[1:],
                           stitch_type=StitchType.PLAIN_SEAM,
                           seam_allowance=sa, mate_edge_name="衣身袖窿"),
                SewingEdge("右侧缝", [cr] + ru[1:] + rl[1:],
                           stitch_type=StitchType.PLAIN_SEAM,
                           seam_allowance=sa),
                SewingEdge("袖口", hm,
                           stitch_type=StitchType.HEM,
                           seam_allowance=2.0, is_hem=True),
                SewingEdge("左侧缝", [cd] + ll[1:] + lu[1:] + [cl],
                           stitch_type=StitchType.PLAIN_SEAM,
                           seam_allowance=sa),
            ],
            mirrored=True,
            metadata={"袖型": "窄袖", "袖长cm": L, "袖口宽cm": self.cuff_width,
                      "袖根宽cm": self.root_width, "肘宽cm": self.elbow_width,
                      "肘位比例": ep, "袖山高cm": sch},
        )
        return [panel]

    def to_garment_code(self) -> str:
        dyn = ", ".join(d.value for d in self.compatible_dynasties)
        return (
            f"# 窄袖 (Narrow Sleeve)\n"
            f"narrow_sleeve = SleevePanel(\n"
            f"    sleeve_length={self.sleeve_length}, cuff_width={self.cuff_width},\n"
            f"    root_width={self.root_width}, elbow_width={self.elbow_width},\n"
            f"    elbow_position={self.elbow_position},\n"
            f"    sleeve_cap_height={self.sleeve_cap_height},\n"
            f"    seam_allowance={self.seam_allowance},\n"
            f"    dynasty_compatibility=[{dyn}],\n)"
        )

    def validate(self) -> List[str]:
        issues = super().validate()
        if self.sleeve_length <= 0:
            issues.append(f"[{self.name}] 袖长须 > 0，当前 {self.sleeve_length}cm")
        if self.cuff_width >= self.root_width:
            issues.append(f"[{self.name}] 窄袖袖口({self.cuff_width}cm)应小于袖根({self.root_width}cm)")
        if not (0.3 <= self.elbow_position <= 0.55):
            issues.append(f"[{self.name}] 肘位比例 {self.elbow_position} 异常 (典型 0.40~0.50)")
        if self.sleeve_cap_height <= 0:
            issues.append(f"[{self.name}] 袖山高须 > 0")
        return issues
