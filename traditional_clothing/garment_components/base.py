"""
base - 传统服饰部件生成系统的基础数据类型

定义二维几何、面板、缝边以及朝代/部件类型枚举等核心抽象层。
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple, Dict, Any


# ─── 二维几何原语 ────────────────────────────────────────────────

@dataclass
class Point2D:
    """二维点，所有几何计算的原子单位。单位为厘米。"""
    x: float = 0.0
    y: float = 0.0

    def __add__(self, other: Point2D) -> Point2D:
        return Point2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Point2D) -> Point2D:
        return Point2D(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Point2D:
        return Point2D(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: float) -> Point2D:
        return self.__mul__(scalar)

    def __truediv__(self, scalar: float) -> Point2D:
        return Point2D(self.x / scalar, self.y / scalar)

    def distance_to(self, other: Point2D) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def rotate(self, angle_rad: float, origin: Optional[Point2D] = None) -> Point2D:
        """绕指定原点逆时针旋转。"""
        ox, oy = (origin.x, origin.y) if origin else (0.0, 0.0)
        dx, dy = self.x - ox, self.y - oy
        cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
        return Point2D(
            ox + dx * cos_a - dy * sin_a,
            oy + dx * sin_a + dy * cos_a,
        )

    def polar(self, radius: float, angle_rad: float) -> Point2D:
        """返回从自身出发，极坐标 (r, θ) 处的点。"""
        return Point2D(
            self.x + radius * math.cos(angle_rad),
            self.y + radius * math.sin(angle_rad),
        )

    def as_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y}


# ─── 枚举 ────────────────────────────────────────────────────────

class Dynasty(Enum):
    """中国历史朝代枚举。"""
    HAN = "汉"
    WEI_JIN = "魏晋"
    TANG = "唐"
    SONG = "宋"
    YUAN = "元"
    MING = "明"
    QING = "清"


class ComponentType(Enum):
    """服饰部件类型。"""
    UPPER_GARMENT = auto()       # 上衣
    LOWER_GARMENT = auto()       # 下裳
    COLLAR = auto()              # 领
    SLEEVE = auto()              # 袖
    SKIRT = auto()               # 裙
    ACCESSORY = auto()           # 配饰
    CLOUD_SHOULDER = auto()      # 云肩


class StitchType(Enum):
    """缝纫方式枚举。"""
    PLAIN_SEAM = 1           # 平缝
    FRENCH_SEAM = 2          # 来去缝
    FLAT_FELLED = 3          # 外包缝
    OVERLOCK = 4             # 拷边
    BINDING = 5              # 滚边
    HEM = 6                  # 卷边
    NONE = 7                 # 无缝合
    # 兼容旧 API 别名
    REGULAR = 1              # = PLAIN_SEAM
    FRENCH = 2               # = FRENCH_SEAM
    BIAS_BINDING = 5         # = BINDING
    PIPING = 5               # = BINDING


# ─── 缝边 ────────────────────────────────────────────────────────

@dataclass
class SewingEdge:
    """面板的一条可缝合边。"""
    name: str = ""                               # 边名称
    points: List[Point2D] = field(default_factory=list)
    stitch_type: StitchType = StitchType.PLAIN_SEAM
    seam_allowance: float = 1.0
    mate_edge_name: Optional[str] = None
    is_hem: bool = False
    # 兼容旧 API 属性的存储
    _extra: Dict[str, Any] = field(default_factory=dict)

    def __init__(self, name="", points=None, stitch_type=None,
                 seam_allowance=1.0, mate_edge_name=None, is_hem=False,
                 **kwargs):
        """兼容旧 API：接受 edge_id, panel_id, curve, label 等参数。"""
        self.name = name or kwargs.pop('edge_id', '') or kwargs.pop('label', '')
        # 旧 API：curve 参数为点列表，转换为 points
        if points is None:
            points = kwargs.pop('curve', None) or []
        self.points = points
        self.stitch_type = stitch_type or StitchType.PLAIN_SEAM
        self.seam_allowance = seam_allowance
        self.mate_edge_name = mate_edge_name or kwargs.pop('mate_edge_id', None)
        self.is_hem = is_hem
        self._extra = kwargs  # 存储兼容参数

    @property
    def length(self) -> float:
        """曲线长度（折线近似）。"""
        if len(self.points) < 2:
            return 0.0
        return sum(
            self.points[i - 1].distance_to(self.points[i])
            for i in range(1, len(self.points))
        )

    def reversed(self) -> SewingEdge:
        """返回逆向边（缝合方向相反时使用）。"""
        return SewingEdge(
            name=self.name,
            points=list(reversed(self.points)),
            stitch_type=self.stitch_type,
            seam_allowance=self.seam_allowance,
            mate_edge_name=self.mate_edge_name,
            is_hem=self.is_hem,
        )

    def offset(self, distance: float, side: str = "left") -> SewingEdge:
        """沿边法向偏移产生缝份线。

        side: 'left' 或 'right'，相对于边的行进方向。
        """
        if len(self.points) < 2:
            return SewingEdge(name=f"{self.name}_offset", points=list(self.points))
        offset_points = []
        for i, pt in enumerate(self.points):
            if i == 0:
                dx = self.points[1].x - pt.x
                dy = self.points[1].y - pt.y
            elif i == len(self.points) - 1:
                dx = pt.x - self.points[i - 1].x
                dy = pt.y - self.points[i - 1].y
            else:
                dx = self.points[i + 1].x - self.points[i - 1].x
                dy = self.points[i + 1].y - self.points[i - 1].y
            length = math.hypot(dx, dy) or 1.0
            # 法向量：对于行进方向，左法向为 (-dy, dx)
            sign = 1.0 if side == "left" else -1.0
            nx = sign * (-dy) / length
            ny = sign * dx / length
            offset_points.append(Point2D(pt.x + nx * distance, pt.y + ny * distance))
        return SewingEdge(
            name=f"{self.name}_offset",
            points=offset_points,
            stitch_type=self.stitch_type,
            seam_allowance=0.0,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "points": [p.to_dict() for p in self.points],
            "stitch_type": self.stitch_type.name,
            "seam_allowance": self.seam_allowance,
            "mate_edge_name": self.mate_edge_name,
            "is_hem": self.is_hem,
        }


# ─── 面板 ────────────────────────────────────────────────────────

def _join_curves(curves: List[List[Point2D]]) -> List[Point2D]:
    """将多条曲线按顺序首尾相接拼接为一个闭合轮廓点列表。

    跳过相邻曲线间的重复端点，保证轮廓连续。
    """
    outline: List[Point2D] = []
    for curve in curves:
        pts = list(curve)
        if not pts:
            continue
        if outline and outline[-1] == pts[0]:
            pts = pts[1:]
        outline.extend(pts)
    return outline


@dataclass
class Panel:
    """一块裁片/面板 — 由外轮廓和缝边组成。"""
    name: str = ""
    component_type: ComponentType = ComponentType.UPPER_GARMENT
    outline: List[Point2D] = field(default_factory=list)
    sewing_edges: List[SewingEdge] = field(default_factory=list)
    internal_lines: List[List[Point2D]] = field(default_factory=list)
    grain_angle_rad: float = 0.0
    fabric_layers: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    mirrored: bool = False
    _extra: Dict[str, Any] = field(default_factory=dict)

    def __init__(self, name="", component_type=None, outline=None,
                 sewing_edges=None, internal_lines=None, grain_angle_rad=0.0,
                 fabric_layers=1, metadata=None, mirrored=False, **kwargs):
        """兼容旧 API：接受 panel_id, curves, fabric_type 等参数。"""
        self.name = name or kwargs.pop('panel_id', '')
        self.component_type = component_type or kwargs.pop('comp_type', None) or ComponentType.UPPER_GARMENT
        # 旧 API：curves 为曲线点列表，首尾相接拼接为 outline
        if outline is None:
            curves = kwargs.pop('curves', None) or []
            if curves:
                outline = _join_curves(curves)
        self.outline = outline if outline is not None else []
        self.sewing_edges = sewing_edges if sewing_edges is not None else []
        self.internal_lines = internal_lines if internal_lines is not None else []
        self.grain_angle_rad = grain_angle_rad
        self.fabric_layers = fabric_layers
        self.metadata = metadata if metadata is not None else {}
        self.mirrored = mirrored
        self._extra = kwargs

    @property
    def bounding_box(self) -> Tuple[Point2D, Point2D]:
        """返回 (min_pt, max_pt) 包围盒。"""
        if not self.outline:
            return Point2D(0, 0), Point2D(0, 0)
        xs = [p.x for p in self.outline]
        ys = [p.y for p in self.outline]
        return Point2D(min(xs), min(ys)), Point2D(max(xs), max(ys))

    @property
    def area(self) -> float:
        """Shoelace 公式计算多边形面积。"""
        n = len(self.outline)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += self.outline[i].x * self.outline[j].y
            area -= self.outline[j].x * self.outline[i].y
        return abs(area) / 2.0

    def translate(self, delta: Point2D) -> Panel:
        """平移整个面板。"""
        self.outline = [p + delta for p in self.outline]
        for edge in self.sewing_edges:
            edge.points = [p + delta for p in edge.points]
        for line in self.internal_lines:
            line[:] = [p + delta for p in line]
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "component_type": self.component_type.name,
            "outline": [p.to_dict() for p in self.outline],
            "sewing_edges": [e.to_dict() for e in self.sewing_edges],
            "grain_angle_rad": self.grain_angle_rad,
            "fabric_layers": self.fabric_layers,
            "mirrored": self.mirrored,
            "metadata": self.metadata,
        }


# ─── 服饰部件基类 ─────────────────────────────────────────────────

class GarmentComponent(ABC):
    """所有传统服饰部件的抽象基类。

    子类需实现：
      - build_panels() → List[Panel]
      - to_garment_code() → str
    """

    # 兼容朝代列表，子类覆盖
    compatible_dynasties: List[Dynasty] = []

    def __init__(
        self,
        name: str = "",
        component_type: ComponentType = ComponentType.ACCESSORY,
        seam_allowance: float = 1.0,
        **kwargs,  # 兼容旧 API: comp_type, component_id, etc.
    ):
        self.name = name
        # 兼容 comp_type 旧参数名
        if 'comp_type' in kwargs:
            component_type = kwargs['comp_type']
        self.component_type = component_type
        self.seam_allowance = seam_allowance
        self._panels: List[Panel] = []
        self._params: Dict[str, Any] = {}  # 兼容旧 API 的参数存储
        self.component_id = kwargs.get('component_id', f"{component_type.name}_{name}")  # 兼容旧 API
        # 自动调用 define_params() 初始化参数（兼容旧版组件）
        self.define_params()

    @property
    def panels(self) -> List[Panel]:
        """获取已构建的面板列表。"""
        if not self._panels:
            self._panels = self.build_panels()
        return self._panels

    @abstractmethod
    def build_panels(self) -> List[Panel]:
        """构建组成该部件的所有裁片面板。

        Returns:
            Panel 对象列表。
        """
        ...

    @abstractmethod
    def to_garment_code(self) -> str:
        """将部件导出为 DSL 服装描述代码。

        Returns:
            服装 DSL 代码字符串。
        """
        ...

    def is_compatible_with(self, dynasty: Dynasty) -> bool:
        """判断该部件是否兼容指定朝代。"""
        return dynasty in self.compatible_dynasties

    def validate(self) -> List[str]:
        """验证参数合理性，返回警告/错误信息列表。"""
        issues: List[str] = []
        if self.seam_allowance <= 0:
            issues.append(f"[{self.name}] 缝份应大于 0，当前值 {self.seam_allowance}cm")
        if not self.compatible_dynasties:
            issues.append(f"[{self.name}] 未声明兼容朝代")
        return issues

    # ── 兼容旧 API (define_params / add_param / get_param) ──────

    def define_params(self) -> None:
        """旧 API 兼容钩子 — 子类可在此调用 add_param() 定义参数。"""
        pass

    @property
    def params(self) -> Dict[str, Any]:
        """兼容旧 API — 返回参数字典。"""
        return self._params

    def add_param(self, name: str, default: Any, min_val: Any = None,
                  max_val: Any = None, unit: str = "cm",
                  description: str = "", step: Any = None) -> None:
        """兼容旧 API — 添加参数。"""
        self._params[name] = {
            'value': default, 'min_val': min_val, 'max_val': max_val,
            'unit': unit, 'description': description, 'step': step,
        }
        # 同时设为实例属性方便直接访问
        if not hasattr(self, name):
            setattr(self, name, default)

    def get_param(self, name: str) -> Any:
        """兼容旧 API — 获取参数值。先查实例属性，再查 _params。"""
        if hasattr(self, name) and not name.startswith('_'):
            val = getattr(self, name)
            if not callable(val):
                return val
        if name in self._params:
            return self._params[name]['value']
        raise KeyError(f"参数 '{name}' 不存在于 '{self.name}'")

    def set_param(self, name: str, value: Any) -> None:
        """兼容旧 API — 设置参数值，同时更新实例属性和 _params。"""
        if name in self._params:
            self._params[name]['value'] = value
        if hasattr(self, name):
            setattr(self, name, value)

    def validate_params(self):
        """兼容旧 API — 校验参数合法性。"""
        ok, errs = True, []
        for pname, pdict in self._params.items():
            if pdict['min_val'] is not None and pdict['value'] < pdict['min_val']:
                ok, errs = False, errs + [f"参数'{pname}'={pdict['value']} < min({pdict['min_val']})"]
            if pdict['max_val'] is not None and pdict['value'] > pdict['max_val']:
                ok, errs = False, errs + [f"参数'{pname}'={pdict['value']} > max({pdict['max_val']})"]
        return ok, errs

    def rebuild(self) -> None:
        """兼容旧 API — 重建面板。"""
        self._panels = []
        self._panels = self.build_panels()
