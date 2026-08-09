"""
ValidationEngine — 加载 rules/ 中全部规则，对 FullGarment 进行评估并生成验证报告。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from validation.rules import ALL_RULES


@dataclass
class RuleResult:
    """单条规则评估结果。"""
    rule_name: str
    category: str
    passed: bool
    severity: str         # "error" | "warning" | "info"
    message: str = ""


@dataclass
class ValidationReport:
    """验证报告，包含全部规则的评估结果。"""
    results: List[RuleResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """error 级别的规则是否全部通过。"""
        return all(r.passed or r.severity != "error" for r in self.results)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if not r.passed and r.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.results if not r.passed and r.severity == "warning")


class ValidationEngine:
    """加载 rules/ 全部规则，针对 FullGarment 执行合规性验证。"""

    def __init__(self):
        self._rules: List[Dict[str, Any]] = ALL_RULES

    # ── 公开 API ────────────────────────────────────────────────

    def validate(self, garment) -> ValidationReport:
        """对 garment 执行全部规则，返回 ValidationReport。"""
        return self._run_rules(self._build_context(garment))

    def validate_component(self, garment, component_type: str) -> ValidationReport:
        """仅评估指定 component_type 类别的规则（如 "collar"、"sleeve"）。"""
        return self._run_rules(self._build_context(garment),
                               category_filter=component_type)

    def validate_combination(self, garment) -> ValidationReport:
        """仅评估部件组合（"combination" 类别）规则。"""
        return self._run_rules(self._build_context(garment),
                               category_filter="combination")

    def get_rules_summary(self) -> None:
        """按类别打印已加载规则的数量统计。"""
        counts = Counter(r.get("category", "general") for r in self._rules)
        print("规则汇总（按类别）:")
        for cat in sorted(counts):
            print(f"  {cat}: {counts[cat]} 条")
        print(f"  总计: {len(self._rules)} 条")

    # ── 内部实现 ────────────────────────────────────────────────

    def _build_context(self, garment) -> Dict[str, Any]:
        """从 FullGarment 实例提取评估所需的上下文字典。"""
        return {
            "dynasty":      getattr(garment, "dynasty", None),
            "collar":       getattr(garment, "collar", None),
            "sleeve":       getattr(garment, "sleeve", None),
            "skirt":        getattr(garment, "skirt", None),
            "accessories":  getattr(garment, "accessories", []),
            "colors":       getattr(garment, "colors", []),
            "patterns":     getattr(garment, "patterns", []),
            "fabric":       getattr(garment, "fabric", None),
            "components":   getattr(garment, "components", []),
            "garment":      garment,
        }

    def _run_rules(self, ctx: Dict[str, Any],
                   category_filter: Optional[str] = None) -> ValidationReport:
        """遍历 rules 并执行，可选按 category 过滤。"""
        results: List[RuleResult] = []
        for rule in self._rules:
            if category_filter and rule.get("category", "") != category_filter:
                continue
            results.append(self._eval(rule, ctx))
        return ValidationReport(results=results)

    def _eval(self, rule: Dict[str, Any], ctx: Dict[str, Any]) -> RuleResult:
        """执行单条规则的 check 回调，捕获异常并返回 RuleResult。"""
        try:
            ok = rule["check"](ctx)
            return RuleResult(
                rule_name=rule["name"],
                category=rule.get("category", "general"),
                passed=ok,
                severity=rule.get("severity", "warning"),
                message="" if ok else rule.get("message",
                                               f"{rule['name']} 未通过"),
            )
        except Exception as exc:
            return RuleResult(
                rule_name=rule["name"],
                category=rule.get("category", "general"),
                passed=False,
                severity="error",
                message=f"规则执行异常: {exc}",
            )
