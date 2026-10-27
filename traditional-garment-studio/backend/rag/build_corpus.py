"""
从队友数据集构建 RAG 语料并入库。

语料来源：memberCode1/01_数据/traditional_design_dataset.jsonl
策略：
  1. 按组件聚合 → 生成形制知识条目（主语料，参数范围/朝代/裁片数）
  2. 原始 instructions_cn → 参数实例条目（补充语料）
  3. 全部入库 Chroma

运行：
  cd traditional-garment-studio
  python backend/rag/build_corpus.py
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]  # traditional-garment-studio
sys.path.insert(0, str(ROOT))

from backend.rag.pipeline import RagPipeline

DATASET = Path(r"c:\Users\huang\Desktop\clothes-llm\memberCode1\01_数据\traditional_design_dataset.jsonl")


def load_dataset():
    rows = []
    with open(DATASET, encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def aggregate_by_component(rows):
    """按组件聚合，生成形制知识条目。"""
    groups = defaultdict(list)
    for r in rows:
        groups[r["component"]].append(r)

    docs = []
    for comp, items in groups.items():
        dynasties = set(r["dynasty"] for r in items)
        occasions = set(r.get("occasion", "") for r in items)
        panels = items[0]["pattern"]["panels"]
        panel_names = items[0]["pattern"]["panel_names"]

        # 收集该组件所有参数名 + 取值范围
        param_ranges = {}
        for r in items:
            for pname, pnode in r["design"].get(comp, {}).items():
                v = pnode.get("v")
                if v is None:
                    continue
                param_ranges.setdefault(pname, []).append(v)

        range_desc = []
        for pname, vals in param_ranges.items():
            if all(isinstance(v, (int, float)) for v in vals):
                range_desc.append(f"{pname}={min(vals)}~{max(vals)}")
            else:
                uniq = sorted(set(str(v) for v in vals))
                range_desc.append(f"{pname} in [{', '.join(uniq[:5])}{'...' if len(uniq) > 5 else ''}]")

        text = (
            f"{comp}（{items[0]['component_class']}）：\n"
            f"朝代覆盖：{', '.join(sorted(dynasties))}\n"
            f"场合：{', '.join(sorted(o for o in occasions if o))}\n"
            f"裁片数：{panels} 片（{', '.join(panel_names)}）\n"
            f"参数范围：{'; '.join(range_desc)}\n"
            f"样本数：{len(items)}（均经 GarmentCode 真实执行验证，可生成纸样）"
        )
        docs.append((f"{comp}_形制知识", text))
    return docs


def extract_raw_instructions(rows):
    """原始 instructions_cn 作为参数实例补充语料。"""
    docs = []
    seen = set()
    for r in rows:
        ins = r["instructions_cn"][0]
        key = (r["component"], r["dynasty"], ins)
        if key in seen:
            continue
        seen.add(key)
        title = f"{r['component']}_{r['dynasty']}_参数实例"
        docs.append((title, ins))
    return docs


def main():
    rows = load_dataset()
    print(f"数据集样本数: {len(rows)}")

    agg_docs = aggregate_by_component(rows)
    raw_docs = extract_raw_instructions(rows)
    print(f"聚合形制条目: {len(agg_docs)}")
    print(f"原始参数条目: {len(raw_docs)}")

    # 展示前 3 条聚合条目
    print("\n=== 聚合条目示例 ===")
    for title, text in agg_docs[:3]:
        print(f"\n【{title}】")
        print(text)

    # 入库
    persist_dir = str(ROOT / "backend" / "rag" / "chroma_db")
    rag = RagPipeline(persist_dir=persist_dir)

    # 清空旧库（重建）
    import shutil
    if Path(persist_dir).exists():
        shutil.rmtree(persist_dir, ignore_errors=True)
    rag = RagPipeline(persist_dir=persist_dir)

    all_docs = agg_docs + raw_docs
    rag.ingest(all_docs)
    print(f"\n✅ 入库完成，共 {rag.store.count()} 条片段")

    # 检索验证
    print("\n=== 检索验证 ===")
    queries = ["马面裙的结构", "交领右衽", "明代琵琶袖参数", "宋代褙子"]
    for q in queries:
        sources = rag.search(q, top_k=3)
        print(f"\n查询: {q}")
        for s in sources:
            print(f"  [{s['score']}] {s['title']}: {s['snippet'][:70]}...")


if __name__ == "__main__":
    main()
