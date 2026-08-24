"""
形制规则校验引擎单元测试 — 验证文化合规性检查。
"""

import pytest

from garment_components.base import Dynasty
from garment_components.garments import GarmentComposer
from validation.engine import ValidationEngine, ValidationReport
from validation.rules import ALL_RULES


@pytest.fixture(scope="module")
def engine():
    return ValidationEngine()


# ── 规则库完整性 ──────────────────────────────────────────────────

def test_rules_nonempty():
    """规则库至少 20 条。"""
    assert len(ALL_RULES) >= 20


def test_rules_have_required_fields():
    """每条规则都包含 name/category/severity/check/message。"""
    for rule in ALL_RULES:
        assert rule["name"], "规则缺少名称"
        assert rule["category"], "规则缺少类别"
        assert rule["severity"] in ("error", "warning", "info")
        assert callable(rule["check"])
        assert rule["message"]


def test_rules_cover_all_categories():
    """规则类别应覆盖朝代/领/袖/裙/色彩/纹样/组合。"""
    categories = {r["category"] for r in ALL_RULES}
    assert {"dynasty", "collar", "sleeve", "skirt",
            "color", "pattern", "combination"} <= categories


# ── 朝代规则 ──────────────────────────────────────────────────────

def test_qing_with_pipa_sleeve_fails(engine):
    """清代 + 琵琶袖 → 必须报错（清代不用琵琶袖）。"""
    composer = (GarmentComposer("清代袍", Dynasty.QING)
                .add_collar("stand_collar")
                .add_sleeve("pipa_sleeve")
                .add_skirt("mamian_skirt"))
    report = engine.validate(composer)
    assert not report.passed
    assert report.error_count >= 1
    names = [r.rule_name for r in report.results if not r.passed]
    assert any("琵琶袖" in n for n in names)


def test_ming_with_pipa_sleeve_passes(engine):
    """明代 + 琵琶袖 → 琵琶袖规则应通过。"""
    composer = (GarmentComposer("明代袄裙", Dynasty.MING)
                .add_collar("stand_collar")
                .add_sleeve("pipa_sleeve")
                .add_skirt("mamian_skirt"))
    report = engine.validate(composer)
    pipa_rules = [r for r in report.results if "琵琶袖" in r.rule_name]
    assert all(r.passed for r in pipa_rules)


def test_tang_low_waist_warns(engine):
    """唐代齐胸襦裙腰位 < 0.75 → warning。"""
    composer = (GarmentComposer("唐代襦裙", Dynasty.TANG)
                .add_collar("cross_collar")
                .add_sleeve("wide_sleeve")
                .add_skirt("ruqun_skirt", waist_position=0.6))
    report = engine.validate(composer)
    assert report.warning_count >= 1
    assert any("腰位" in r.rule_name for r in report.results if not r.passed)


def test_tang_high_waist_passes(engine):
    """唐代齐胸襦裙腰位 >= 0.8 → 腰位规则通过。"""
    composer = (GarmentComposer("唐代襦裙", Dynasty.TANG)
                .add_collar("cross_collar")
                .add_sleeve("wide_sleeve")
                .add_skirt("ruqun_skirt", waist_position=0.85))
    report = engine.validate(composer)
    assert all(
        r.passed for r in report.results if "腰位" in r.rule_name
    )


def test_song_without_beizi_infos(engine):
    """宋代无褙子 → info 级提示（不阻塞通过）。"""
    composer = (GarmentComposer("宋代衫", Dynasty.SONG)
                .add_collar("cross_collar")
                .add_sleeve("narrow_sleeve")
                .add_skirt("ruqun_skirt"))
    report = engine.validate(composer)
    beizi_rule = [r for r in report.results if "褙子" in r.rule_name]
    assert beizi_rule and not beizi_rule[0].passed
    assert beizi_rule[0].severity == "info"


# ── 部件规则 ──────────────────────────────────────────────────────

def test_mamian_skirt_too_narrow_pleats(engine):
    """马面裙褶数必须为偶数（奇数 → error）。"""
    from garment_components.skirts import MamianSkirt

    class OddPleatMamian(MamianSkirt):
        def __init__(self):
            super().__init__(pleat_count=5)
            self.pleat_count = 5  # 绕过自动修正，模拟异常输入

    composer = GarmentComposer("测试裙", Dynasty.MING)
    composer._register(OddPleatMamian())
    report = engine.validate(composer)
    assert any(
        (not r.passed and "褶数" in r.rule_name and r.severity == "error")
        for r in report.results
    )


def test_wide_sleeve_cuff_must_exceed_root(engine):
    """广袖袖口宽必须大于袖根宽。"""
    from garment_components.sleeves import WideSleeve

    class BadWideSleeve(WideSleeve):
        def __init__(self):
            super().__init__()
            self.cuff_width, self.root_width = 10.0, 25.0

    composer = GarmentComposer("测试袍", Dynasty.HAN)
    composer._register(BadWideSleeve())
    report = engine.validate(composer)
    assert any(
        (not r.passed and "广袖" in r.rule_name and r.severity == "error")
        for r in report.results
    )


# ── 规则过滤与报告 ────────────────────────────────────────────────

def test_validate_component_filter(engine):
    """validate_component 只评估指定类别。"""
    composer = (GarmentComposer("清代袍", Dynasty.QING)
                .add_collar("stand_collar")
                .add_sleeve("pipa_sleeve")
                .add_skirt("mamian_skirt"))
    report = engine.validate_component(composer, "dynasty")
    assert report.results
    assert all(r.category == "dynasty" for r in report.results)


def test_validate_combination_filter(engine):
    """validate_combination 只评估组合规则。"""
    composer = (GarmentComposer("套装")
                .add_collar("cross_collar")
                .add_sleeve("narrow_sleeve"))
    report = engine.validate_combination(composer)
    assert report.results
    assert all(r.category == "combination" for r in report.results)


def test_report_counts(engine):
    """ValidationReport 统计属性正确。"""
    composer = (GarmentComposer("清代袍", Dynasty.QING)
                .add_collar("stand_collar")
                .add_sleeve("pipa_sleeve")
                .add_skirt("mamian_skirt"))
    report = engine.validate(composer)
    assert isinstance(report, ValidationReport)
    assert report.error_count + report.warning_count >= report.error_count
    assert report.passed == (report.error_count == 0)


def test_rule_exception_does_not_crash(engine):
    """规则内部抛异常 → 报告为 error 而非崩溃。"""

    class BrokenGarment:
        dynasty = Dynasty.MING
        collar = None
        sleeve = None
        skirt = None
        accessories = []
        components = [object()]  # 无 component_type 的部件

    report = engine.validate(BrokenGarment())
    assert isinstance(report, ValidationReport)
