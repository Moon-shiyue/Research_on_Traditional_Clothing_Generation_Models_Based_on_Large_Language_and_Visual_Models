"""文本切分：按段落聚合，保持条目完整性。"""


def chunk_doc(text: str, title: str, chunk_size: int = 500, overlap: int = 80) -> list[dict]:
    """把一篇文档切成带元数据的片段。

    Args:
        text: 文档正文
        title: 文档标题（作为 metadata）
        chunk_size: 单片段大致字数上限
        overlap: 片段间重叠字数（取上一片尾）
    """
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    buf = ""
    for p in paras:
        if len(buf) + len(p) > chunk_size and buf:
            chunks.append({"text": buf, "title": title})
            buf = buf[-overlap:] if len(buf) > overlap else buf
        buf += ("\n" if buf else "") + p
    if buf:
        chunks.append({"text": buf, "title": title})
    return chunks
