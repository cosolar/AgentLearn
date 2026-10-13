"""chunking.py —— 文档切分与「父子块」构建

对应 docs/05-RAG系统/02-文档处理.md：
    - 先按标题切「父块」（喂给 LLM，保证语义完整）
    - 再把父块切成更小的「子块」（用于向量检索，保证命中精准）
    - 检索命中子块 → 回溯其父块 → 把父块交给 LLM

依赖：仅标准库。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass
class Chunk:
    """一个文本块。parent_id 为空表示它本身就是父块。"""

    text: str
    source: str
    parent_id: str | None = None
    chunk_id: str = ""

    def with_meta(self, **extra) -> dict:
        return {"source": self.source, "parent_id": self.parent_id, **extra}


def split_by_heading(text: str) -> list[str]:
    """按 Markdown 标题切分为若干「段」，标题保留在段首。"""
    sections: list[str] = []
    buf: list[str] = []
    for line in text.splitlines():
        if HEADING_RE.match(line) and buf:
            sections.append("\n".join(buf).strip())
            buf = [line]
        else:
            buf.append(line)
    if buf:
        sections.append("\n".join(buf).strip())
    return [s for s in sections if s]


def chunk_text(text: str, size: int = 220, overlap: int = 40) -> list[str]:
    """定长滑动窗口切分（带重叠），按段落边界尽量对齐。

    size/overlap 以字符计（对中英文都适用；生产可换成 token 计数，见 5.2）。
    """
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []

    step = max(1, size - overlap)
    chunks: list[str] = []
    for start in range(0, len(text), step):
        piece = text[start:start + size].strip()
        if piece:
            chunks.append(piece)
        if start + size >= len(text):
            break
    return chunks


def build_parent_child(
    text: str,
    source: str,
    parent_size: int = 600,
    child_size: int = 220,
    overlap: int = 40,
) -> list[Chunk]:
    """构建父子块：每个父块包含若干子块，子块记录 parent_id。"""
    chunks: list[Chunk] = []
    parents = split_by_heading(text)
    # 若没有标题，退化为按长度切父块
    if not parents:
        parents = chunk_text(text, size=parent_size, overlap=0)

    for pi, parent_text in enumerate(parents):
        if len(parent_text) > parent_size:
            parent_text = parent_text[:parent_size]
        parent_id = f"{source}#p{pi}"
        chunks.append(Chunk(text=parent_text, source=source, parent_id=None,
                            chunk_id=parent_id))
        for ci, child_text in enumerate(chunk_text(parent_text, child_size, overlap)):
            chunks.append(Chunk(text=child_text, source=source, parent_id=parent_id,
                                chunk_id=f"{parent_id}#c{ci}"))
    return chunks


def children_only(chunks: list[Chunk]) -> list[Chunk]:
    """取出所有子块（用于建向量索引）。"""
    return [c for c in chunks if c.parent_id is not None]


def parent_index(chunks: list[Chunk]) -> dict[str, Chunk]:
    """父块 id → 父块对象，便于检索命中子块后回溯父块。"""
    return {c.chunk_id: c for c in chunks if c.parent_id is None}
