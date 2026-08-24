"""GarmentComposer — 将多个 GarmentComponent 组合为完整服装"""
from ..base import GarmentComponent, Dynasty, Panel
from ..collars import CrossCollar, StandCollar, RoundCollar, DuijinCollar
from ..sleeves import WideSleeve, NarrowSleeve, PipaSleeve
from ..skirts import MamianSkirt, RuqunSkirt
from ..accessories import CloudShoulder, Beizi, Banbi

class GarmentComposer:
    """服装组合器 — 添加部件并组合为完整服装"""
    def __init__(self, name="定制服装", dynasty=Dynasty.MING):
        self.name = name
        self.dynasty = dynasty if isinstance(dynasty, Dynasty) else Dynasty(dynasty)
        self.components = []
        # 语义化部件引用（供校验引擎等按属性访问）
        self.collar = None
        self.sleeve = None
        self.skirt = None
        self.accessories = []

    def _register(self, comp):
        """按部件类型登记语义化引用。"""
        from ..base import ComponentType
        ctype = getattr(comp, "component_type", None)
        if ctype == ComponentType.COLLAR:
            self.collar = comp
        elif ctype == ComponentType.SLEEVE:
            self.sleeve = comp
        elif ctype == ComponentType.SKIRT:
            self.skirt = comp
        else:
            self.accessories.append(comp)
        self.components.append(comp)
        return comp

    def add_collar(self, collar_type="cross_collar", **params):
        collar_map = {"cross_collar": CrossCollar, "stand_collar": StandCollar,
                      "round_collar": RoundCollar, "duijin_collar": DuijinCollar}
        comp = collar_map[collar_type]()
        for k, v in params.items():
            if hasattr(comp, k):
                setattr(comp, k, v)
            elif hasattr(comp, 'set_param'):
                comp.set_param(k, v)
        self._register(comp)
        return self

    def _add_with_params(self, cls, **params):
        comp = cls()
        for k, v in params.items():
            if hasattr(comp, k): setattr(comp, k, v)
            elif hasattr(comp, 'set_param'): comp.set_param(k, v)
        return self._register(comp)

    def add_sleeve(self, sleeve_type="wide_sleeve", **params):
        m = {"wide_sleeve": WideSleeve, "narrow_sleeve": NarrowSleeve, "pipa_sleeve": PipaSleeve}
        self._add_with_params(m[sleeve_type], **params)
        return self

    def add_skirt(self, skirt_type="mamian_skirt", **params):
        m = {"mamian_skirt": MamianSkirt, "ruqun_skirt": RuqunSkirt}
        self._add_with_params(m[skirt_type], **params)
        return self

    def add_accessory(self, acc_type="cloud_shoulder", **params):
        m = {"cloud_shoulder": CloudShoulder, "beizi": Beizi, "banbi": Banbi}
        self._add_with_params(m[acc_type], **params)
        return self

    def compose(self):
        """组合并返回所有面板和部件"""
        return self

    @property
    def all_panels(self):
        panels = []
        for comp in self.components:
            panels.extend(comp.panels)
        return panels
