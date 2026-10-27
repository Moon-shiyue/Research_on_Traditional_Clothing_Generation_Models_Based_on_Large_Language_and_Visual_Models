"""Chroma 向量库封装。

所有 add/query 都显式传入 embedding，不依赖 chroma 默认 embedding_function，
避免在线/默认模型回退问题（参见经验 2073543）。
"""

import chromadb
from chromadb.api.types import QueryResult


class VectorStore:
    def __init__(self, persist_dir: str, collection_name: str = "garment_docs"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        # 不指定 embedding_function，完全由调用方手动算向量
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def add(self, chunks: list[dict], embeddings: list[list[float]]):
        ids = [f"chunk_{i}" for i in range(len(chunks))]
        self.collection.add(
            ids=ids,
            documents=[c["text"] for c in chunks],
            metadatas=[{"title": c["title"]} for c in chunks],
            embeddings=embeddings,
        )

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 3,
        score_threshold: float = 0.3,
    ) -> list[dict]:
        result: QueryResult = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )
        sources = []
        for meta, doc, dist in zip(
            result["metadatas"][0], result["documents"][0], result["distances"][0]
        ):
            # chroma 默认用 L2 距离，转成相似度分数（粗略）
            score = round(1 / (1 + dist), 3)
            if score < score_threshold:
                continue
            sources.append(
                {"title": meta["title"], "snippet": doc[:300], "score": score}
            )
        return sources

    def count(self) -> int:
        return self.collection.count()
