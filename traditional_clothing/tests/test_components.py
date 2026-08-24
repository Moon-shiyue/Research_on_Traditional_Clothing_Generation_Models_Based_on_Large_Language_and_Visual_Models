"""
组件库单元测试 — 验证传统服饰参数化组件库的全部部件。
覆盖：领型、袖型、下裳、配饰、组合器。
"""

import pytest

from garment_components.base import Dynasty, Panel, Point2D, ComponentType
from garment_components.collars import (
    CrossCollar, RoundCollar, StandCollar, DuijinCollar,
)
from garment_components.sleeves import WideSleeve, NarrowSleeve, PipaSleeve
from garment_components.skirts import MamianSkirt, RuqunSkirt
from garment_components.accessories import CloudShoulder, Beizi, Banbi
from garment_components.garments import GarmentComposer


# ── 全部部件实例化与面板构建 ──────────────────────────────────────

ALL_COMPONENTS = [
    CrossCollar, RoundCollar, StandCollar, DuijinCollar,
    WideSleeve, NarrowSleeve, PipaSleeve,
    MamianSkirt, RuqunSkirt,
    CloudShoulder, Beizi, Banbi,
]


@pytest.mark.parametrize("cls", ALL_COMPONENTS, ids=lambda c: c.__name__)
def test_component_builds_panels(cls):
    """每个部件都能构建出至少 1 个面板。"""
    comp = cls()
    panels = comp.panels
    assert len(panels) >= 1, f"{cls.__name__} 未生成任何面板"
    for panel in panels:
        assert isinstance(panel, Panel)
        assert len(panel.outline) >= 3, f"{cls.__name__} 面板 '{panel.name}' 轮廓点不足"
        assert panel.area > 0, f"{cls.__name__} 面板 '{panel.name}' 面积为 0"


@pytest.mark.parametrize("cls", ALL_COMPONENTS, ids=lambda c: c.__name__)
def test_component_exports_garment_code(cls):
    """每个部件都能导出 GarmentCode DSL。"""
    comp = cls()
    code = comp.to_garment_code()
    assert isinstance(code, str) and len(code) > 20
    assert comp.name in code or cls.__name__ in code


@pytest.mark.parametrize("cls", ALL_COMPONENTS, ids=lambda c: c.__name__)
def test_component_validate_returns_list(cls):
    """每个部件的 validate() 返回问题列表。"""
    comp = cls()
    issues = comp.validate()
    assert isinstance(issues, list)


@pytest.mark.parametrize("cls", ALL_COMPONENTS, ids=lambda c: c.__name__)
def test_component_declares_dynasties(cls):
    """每个部件都声明了兼容朝代（形制溯源要求）。"""
    comp = cls()
    assert comp.compatible_dynasties, f"{cls.__name__} 未声明兼容朝代"


# ── 基础几何 ──────────────────────────────────────────────────────

def test_point2d_ops():
    p = Point2D(1, 2)
    assert (p + Point2D(3, 4)) == Point2D(4, 6)
    assert (p - Point2D(1, 1)) == Point2D(0, 1)
    assert (p * 2) == Point2D(2, 4)
    assert p.distance_to(Point2D(1, 5)) == pytest.approx(3.0)


# ── 领型 ──────────────────────────────────────────────────────────

def test_cross_collar_right_lapel():
    """交领应为三片式，且左前领片为外层（右衽）。"""
    collar = CrossCollar()
    panels = collar.panels
    assert len(panels) == 3
    labels = [p.metadata.get("panel_side") for p in panels]
    assert "left" in labels and "right" in labels and "back" in labels


def test_stand_collar_height():
    """立领高度应被正确存储。"""
    collar = StandCollar()
    collar.set_param("collar_height", 5.0)
    assert collar.get_param("collar_height") == pytest.approx(5.0)


def test_round_collar_depths():
    """圆领前领深应大于后领深。"""
    collar = RoundCollar(front_depth=10.0, back_depth=4.0)
    assert collar.front_depth > collar.back_depth


# ── 袖型 ──────────────────────────────────────────────────────────

def test_wide_sleeve_cuff_gt_root():
    """广袖袖口宽必须大于袖根宽（规则前提）。"""
    sleeve = WideSleeve()
    assert sleeve.cuff_width > sleeve.root_width


def test_pipa_sleeve_ming_only():
    """琵琶袖是明代独有袖型。"""
    assert PipaSleeve.compatible_dynasties == [Dynasty.MING]


def test_narrow_sleeve_general():
    """窄袖历代通用。"""
    assert Dynasty.QING in NarrowSleeve.compatible_dynasties
    assert Dynasty.HAN in NarrowSleeve.compatible_dynasties


# ── 下裳 ──────────────────────────────────────────────────────────

def test_mamian_skirt_structure():
    """马面裙应构建出 2 片马面 + 左右褶裥片 + 腰头 + 左右系带。"""
    skirt = MamianSkirt(num_mamian=2)
    panels = skirt.panels
    assert len(panels) == 7, f"马面裙应生成 7 片，实际 {len(panels)}"
    names = [p.name for p in panels]
    assert "前马面片" in names and "后马面片" in names
    assert "腰头片" in names
    assert "左系带" in names and "右系带" in names


def test_mamian_skirt_mamian_width_min():
    """马面宽低于 15cm 时自动修正（形制硬性要求）。"""
    skirt = MamianSkirt(mamian_width=10.0)
    assert skirt.mamian_width >= 15.0


def test_mamian_skirt_pleat_even():
    """褶数为奇数时自动修正为偶数。"""
    skirt = MamianSkirt(pleat_count=7)
    assert skirt.pleat_count % 2 == 0


def test_mamian_skirt_validate_catches_bad_params():
    """校验应捕获非法参数（腰围过小无法容纳马面）。"""
    skirt = MamianSkirt(waist_circumference=30.0, mamian_width=28.0)
    issues = skirt.validate()
    assert any("错误" in i for i in issues)


def test_mamian_skirt_fabric_math():
    """面料数学关系：总展开宽 = N×马面宽 + 2×侧片展开宽。"""
    skirt = MamianSkirt(num_mamian=2)
    expected = (2 * skirt.mamian_width
                + 2 * (skirt.side_visible_width + skirt.pleat_count * 2 * skirt.pleat_depth))
    assert skirt.total_fabric_width == pytest.approx(expected)


def test_ruqun_skirt_builds():
    """襦裙可构建。"""
    skirt = RuqunSkirt()
    assert len(skirt.panels) >= 1


# ── 配饰 ──────────────────────────────────────────────────────────

def test_accessory_types():
    """三类配饰的 component_type 均为 ACCESSORY 或 CLOUD_SHOULDER。"""
    for cls in (CloudShoulder, Beizi, Banbi):
        comp = cls()
        assert comp.component_type in (
            ComponentType.ACCESSORY, ComponentType.CLOUD_SHOULDER,
        )


# ── 组合器 ────────────────────────────────────────────────────────

def test_composer_ming_aoqun():
    """组合器：明代袄裙 = 立领 + 琵琶袖 + 马面裙。"""
    composer = (GarmentComposer("明代袄裙", Dynasty.MING)
                .add_collar("stand_collar")
                .add_sleeve("pipa_sleeve")
                .add_skirt("mamian_skirt"))
    assert len(composer.components) == 3
    assert composer.collar is not None
    assert composer.sleeve is not None
    assert composer.skirt is not None
    assert len(composer.all_panels) >= 8


def test_composer_tang_style():
    """组合器：唐代齐胸襦裙 = 交领 + 广袖 + 襦裙。"""
    composer = (GarmentComposer("唐代襦裙", Dynasty.TANG)
                .add_collar("cross_collar")
                .add_sleeve("wide_sleeve")
                .add_skirt("ruqun_skirt"))
    assert len(composer.components) == 3
    assert isinstance(composer.collar, CrossCollar)
    assert isinstance(composer.sleeve, WideSleeve)


def test_composer_song_style_with_beizi():
    """组合器：宋代褙子裙 = 对襟 + 窄袖 + 襦裙 + 褙子。"""
    composer = (GarmentComposer("宋代褙子裙", Dynasty.SONG)
                .add_collar("duijin_collar")
                .add_sleeve("narrow_sleeve")
                .add_skirt("ruqun_skirt")
                .add_accessory("beizi"))
    assert len(composer.components) == 4
    assert len(composer.accessories) == 1


def test_composer_unknown_collar_raises():
    """不支持的领型应抛出 KeyError。"""
    composer = GarmentComposer()
    with pytest.raises(KeyError):
        composer.add_collar("not_a_collar")
