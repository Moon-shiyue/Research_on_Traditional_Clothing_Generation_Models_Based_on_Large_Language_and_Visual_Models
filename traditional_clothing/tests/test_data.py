"""
数据集完整性单元测试 — 验证标注数据、索引与 DSL 训练数据。
"""

import json
import os

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
ANNOTATIONS_DIR = os.path.join(DATA_DIR, "annotations")


# ── dataset_index.json ────────────────────────────────────────────

def _load_index():
    with open(os.path.join(DATA_DIR, "dataset_index.json"),
              encoding="utf-8") as f:
        return json.load(f)


def test_index_loads():
    idx = _load_index()
    assert idx["version"] == "1.0"
    assert idx["total_count"] >= 28


def test_index_statistics_consistent():
    """统计字段与标注条目数一致。"""
    idx = _load_index()
    annotations = idx["annotations"]
    assert len(annotations) == idx["total_count"]
    assert len(annotations) == sum(idx["statistics"]["by_dynasty"].values())


def test_index_annotations_have_required_fields():
    """每条标注都有核心字段（朝代/形制/来源），纹样条目用 pattern_name。"""
    idx = _load_index()
    for ann in idx["annotations"]:
        assert ann["image_id"]
        assert ann["dynasty"]
        assert ann.get("garment_type") or ann.get("pattern_name")
        assert ann["source"]
        assert ann["annotator"]
        assert ann["review_status"]


def test_index_covers_all_dynasties():
    """标注数据覆盖汉/魏晋/唐/宋/明/清全部朝代。"""
    idx = _load_index()
    dynasties = set(idx["statistics"]["by_dynasty"].keys())
    assert {"汉", "魏晋", "唐", "宋", "明", "清"} <= dynasties


# ── training_data.jsonl（文本训练数据）────────────────────────────

def _read_jsonl(name):
    path = os.path.join(ANNOTATIONS_DIR, name)
    assert os.path.exists(path), f"缺少文件: {name}"
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def test_training_data_nonempty():
    rows = _read_jsonl("training_data.jsonl")
    assert len(rows) >= 100


def test_training_data_fields():
    """核心字段存在；知识库条目（带 dynasty）与图文条目（带 classification）并存。"""
    rows = _read_jsonl("training_data.jsonl")
    knowledge = [r for r in rows if "dynasty" in r]
    image_text = [r for r in rows if "classification" in r]
    assert knowledge, "缺少知识库条目"
    assert image_text, "缺少图文条目"
    for row in rows:
        assert row["id"]
        assert row["text"]
        assert row["source"]
        assert row["data_type"]


def test_training_data_ids_unique():
    rows = _read_jsonl("training_data.jsonl")
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "存在重复 id"


# ── dsl_training.jsonl（DSL 训练数据）─────────────────────────────

def test_dsl_training_nonempty():
    rows = _read_jsonl("dsl_training.jsonl")
    assert len(rows) >= 100


def test_dsl_training_has_dsl():
    rows = _read_jsonl("dsl_training.jsonl")
    for row in rows:
        assert row["dsl"]
        assert row["text"]
        # DSL 以 GARMENT 或部件声明开头
        assert row["dsl"].startswith(("GARMENT", "COLLAR", "SLEEVE",
                                      "SKIRT", "ACCESSORY"))


def test_dsl_mentions_component_tags():
    """DSL 应包含部件标记（与组件库对应）。"""
    rows = _read_jsonl("dsl_training.jsonl")
    dsl_text = " ".join(r["dsl"] for r in rows)
    for tag in ("duijin", "narrow", "ruqun", "beizi", "mamian", "pipa"):
        assert tag in dsl_text, f"DSL 数据缺少部件标记 {tag}"


# ── 文本数据目录 ──────────────────────────────────────────────────

def test_texts_readmes_exist():
    for sub in ("literature", "craft", "culture"):
        path = os.path.join(DATA_DIR, "texts", sub, "README.md")
        assert os.path.exists(path), f"缺少 {sub}/README.md"
        with open(path, encoding="utf-8") as f:
            assert len(f.read()) > 50
