"""retrieval.py —— 混合检索 + 父子块回溯

对应 docs/05-RAG系统/04-优化策略.md：
    向量检索（语义）+ BM25（关键词）→ RRF 融合 → 回溯父块 → 交给 LLM。

其中 BM25 与融合部分为纯标准库实现，可离线测试；向量部分需要 Embedding。
"""

from __future__ import annotations

from dataclasses import dataclass

from bm25 import BM25, rrf_fuse
from chunking import Chunk, children_only, parent_index
from config import RAGConfig, load_documents


@dataclass
class Hit:
    text: str            # 最终给 LLM 的文本（通常是父块）
    source: str
    score: float


class HybridRetriever:
    """混合检索器：BM25 +（可选）向量，RRF 融合，父块回溯。"""

    def __init__(self, cfg: RAGConfig, all_chunks: list[Chunk],
                 vectorstore=None) -> None:
        self.cfg = cfg
        self.parents = parent_index(all_chunks)
        self.children = children_only(all_chunks)
        self.by_id = {c.chunk_id: c for c in self.children}
        # BM25 索引建立在子块上
        self.bm25 = BM25().fit([
            {"source": c.chunk_id, "text": c.text} for c in self.children
        ])
        self.vectorstore = vectorstore

    # ---- 单路检索 ----
    def bm25_search(self, query: str, k: int) -> list[str]:
        return [doc["source"] for _score, doc in self.bm25.search(query, k)]

    def vector_search(self, query: str, k: int) -> list[str]:
        if self.vectorstore is None:
            return []
        hits = self.vectorstore.similarity_search(query, k=k)
        return [h.metadata.get("chunk_id", "") for h in hits]

    # ---- 混合检索 ----
    def search(self, query: str, k: int | None = None) -> list[Hit]:
        k = k or self.cfg.top_k
        rankings = [r for r in (self.vector_search(query, k * 2),
                                self.bm25_search(query, k * 2)) if r]
        fused = rrf_fuse(rankings)

        hits: list[Hit] = []
        seen_parents: set[str] = set()
        for chunk_id, score in fused:
            child = self.by_id.get(chunk_id)
            if child is None:
                continue
            parent_id = child.parent_id or chunk_id
            if parent_id in seen_parents:      # 同一父块只保留一次
                continue
            seen_parents.add(parent_id)
            parent = self.parents.get(parent_id)
            text = parent.text if parent else child.text
            hits.append(Hit(text=text, source=child.source, score=score))
            if len(hits) >= self.cfg.rerank_top_n:
                break
        return hits

    @classmethod
    def from_disk(cls, cfg: RAGConfig, vectorstore=None) -> "HybridRetriever":
        """从 data/ 直接构建（不依赖向量库也能跑 BM25 部分）。"""
        from store import build_chunks
        all_chunks, _ = build_chunks(cfg)
        return cls(cfg, all_chunks, vectorstore=vectorstore)


def format_hits(hits: list[Hit]) -> str:
    """把检索结果格式化为给 LLM / 用户看的文本。"""
    if not hits:
        return "（未检索到相关内容）"
    return "\n\n".join(f"[{h.source}] {h.text}" for h in hits)


__all__ = ["Hit", "HybridRetriever", "format_hits", "load_documents"]
