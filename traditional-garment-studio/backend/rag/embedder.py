"""文本向量化封装：复用项目 system.json 里的 DashScope OpenAI 兼容接口。"""

import json
from pathlib import Path
from openai import OpenAI


def load_config(system_json_path: str = None) -> dict:
    """读取演示项目的 system.json，复用 api_key 和 base_url。"""
    if system_json_path is None:
        # 默认指向演示项目的 system.json
        system_json_path = (
            Path(__file__).resolve().parents[3]
            / "design2garmentcode-impl-main"
            / "system.json"
        )
    with open(system_json_path, "r", encoding="utf-8") as f:
        return json.load(f)


class DashScopeEmbedder:
    """通过 OpenAI 兼容接口调用 DashScope text-embedding。"""

    def __init__(self, model: str = "text-embedding-v3", config: dict = None):
        cfg = config or load_config()
        self.client = OpenAI(
            api_key=cfg["api_keys"],
            base_url=cfg["base_urls"],
        )
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        # DashScope text-embedding 单次最多 10 条，需分批
        batch_size = 10
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            resp = self.client.embeddings.create(model=self.model, input=batch)
            all_embeddings.extend(d.embedding for d in resp.data)
        return all_embeddings

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]
