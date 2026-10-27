"""RAG 管线总入口：入库 + 检索。

用法：
    from backend.rag.pipeline import RagPipeline

    rag = RagPipeline(persist_dir="./backend/rag/chroma_db")

    # 入库（语料准备好后执行一次）
    rag.ingest([("标题", "正文..."), ...])

    # 检索
    sources = rag.search("交领右衽长袍是什么形制", top_k=3)
"""

from pathlib import Path
from .chunker import chunk_doc
from .embedder import DashScopeEmbedder
from .store import VectorStore


class RagPipeline:
    def __init__(self, persist_dir: str = None, embedder: DashScopeEmbedder = None):
        if persist_dir is None:
            persist_dir = str(Path(__file__).parent / "chroma_db")
        self.embedder = embedder or DashScopeEmbedder()
        self.store = VectorStore(persist_dir=persist_dir)

    def ingest(self, docs: list[tuple[str, str]]):
        """docs: [(title, text), ...]"""
        all_chunks = []
        for title, text in docs:
            all_chunks.extend(chunk_doc(text, title))
        if not all_chunks:
            return
        embeddings = self.embedder.embed([c["text"] for c in all_chunks])
        self.store.add(all_chunks, embeddings)

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        q_emb = self.embedder.embed_one(query)
        return self.store.query(q_emb, top_k=top_k)
