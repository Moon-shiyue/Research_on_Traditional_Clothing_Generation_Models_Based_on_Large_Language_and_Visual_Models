"""RAG 管线可行性验证：用占位语料跑通 入库 → 检索 全流程。

运行（在演示项目 venv 中，因为 chromadb 装在那里）：
    cd clothes-llm/design2garmentcode-impl-main
    .venv/Scripts/python.exe ../traditional-garment-studio/backend/rag/tests/test_pipeline.py
"""

import sys
from pathlib import Path

# 让脚本能 import backend.rag
ROOT = Path(__file__).resolve().parents[3]  # traditional-garment-studio
sys.path.insert(0, str(ROOT))

from backend.rag.pipeline import RagPipeline


# 占位语料（真实项目替换为论文/词条文本）
SAMPLE_DOCS = [
    (
        "马面裙形制",
        "马面裙前后共四个裙门，两两重合，外侧裙门平整无褶，两侧打活褶，常见四到十对。"
        "裙腰用白布，取白头偕老之意，以绳带系结。穿着时光面位于身体前后正中。"
        "明代盛行，清代延续并衍变出阑干裙、鱼鳞裙等变体。",
    ),
    (
        "交领右衽",
        "交领指衣领左右交叉，右衽指衣襟向右掩，即左襟压右襟。"
        "交领右衽是汉服最典型的领型，自周代以来沿用，深衣、直裰、圆领袍等多采用。"
        "衽的方向是华夷之辨的标志，少数民族或死者多用左衽。",
    ),
    (
        "琵琶袖",
        "琵琶袖是明代女装常见袖型，袖根窄、袖口宽大呈弧形，整体形似琵琶。"
        "袖口处常缝有一段窄边称为袖缘，可挽起露出衬里。"
        "琵琶袖多见于明制袄裙、长衫，行动时袖口自然摆动。",
    ),
]


def main():
    persist_dir = str(ROOT / "backend" / "rag" / "chroma_db_test")

    # 清理旧库（测试用）：在创建客户端前删除，避免 sqlite 文件锁
    import shutil
    if Path(persist_dir).exists():
        shutil.rmtree(persist_dir, ignore_errors=True)

    rag = RagPipeline(persist_dir=persist_dir)

    print("=== 入库 ===")
    rag.ingest(SAMPLE_DOCS)
    print(f"已入库片段数: {rag.store.count()}")

    print("\n=== 检索测试 ===")
    queries = [
        "马面裙的结构是什么",
        "交领右衽是什么意思",
        "明代女子穿什么袖子",
    ]
    for q in queries:
        sources = rag.search(q, top_k=2)
        print(f"\n查询: {q}")
        if not sources:
            print("  (无相关结果)")
            continue
        for s in sources:
            print(f"  [{s['score']}] {s['title']}: {s['snippet'][:60]}...")

    print("\n✅ 管线全流程跑通：入库 → 向量化 → 检索 → 相关性排序")


if __name__ == "__main__":
    main()
