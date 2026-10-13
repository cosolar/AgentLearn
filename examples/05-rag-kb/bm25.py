"""bm25.py —— 纯标准库的 BM25 关键词检索

对应 docs/05-RAG系统/04-优化策略.md 的「混合检索」：
    向量检索擅长语义相似，BM25 擅长精确关键词（型号、专有名词、编号）。
    两者融合（RRF 或加权）能显著提升召回质量。

本实现零依赖，便于离线测试与教学；生产可换成 rank_bm25 / Elasticsearch。
"""

from __future__ import annotations

import math
import re
from collections import Counter

_ASCII_WORD = re.compile(r"[a-zA-Z0-9_]+")
_CJK = re.compile(r"[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    """中英混合分词：
    - 英文/数字：按词切分并小写
    - 中文：切成单字 + 相邻双字（bigram），无需外部分词器也能获得不错的召回
    """
    text = text.lower()
    tokens: list[str] = _ASCII_WORD.findall(text)
    cjk = _CJK.findall(text)
    tokens.extend(cjk)
    # 中文 bigram：从原文中抽取连续汉字对
    runs = re.findall(r"[\u4e00-\u9fff]+", text)
    for run in runs:
        for i in range(len(run) - 1):
            tokens.append(run[i:i + 2])
    return tokens


class BM25:
    """Okapi BM25 检索器（内存版）"""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.docs: list[dict] = []          # 每个 doc: {"source", "text", "tokens"}
        self.df: Counter = Counter()
        self.avg_len: float = 0.0

    def fit(self, docs: list[dict]) -> "BM25":
        self.docs = []
        self.df = Counter()
        total_len = 0
        for d in docs:
            toks = tokenize(d["text"])
            self.docs.append({"source": d["source"], "text": d["text"], "tokens": toks})
            total_len += len(toks)
            for term in set(toks):
                self.df[term] += 1
        self.avg_len = total_len / len(self.docs) if self.docs else 0.0
        return self

    def _idf(self, term: str) -> float:
        n = len(self.docs)
        df = self.df.get(term, 0)
        # BM25 常用的平滑 IDF
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def score(self, query: str, doc_idx: int) -> float:
        doc = self.docs[doc_idx]
        tf = Counter(doc["tokens"])
        dl = len(doc["tokens"]) or 1
        score = 0.0
        for term in tokenize(query):
            if term not in tf:
                continue
            idf = self._idf(term)
            freq = tf[term]
            denom = freq + self.k1 * (1 - self.b + self.b * dl / (self.avg_len or 1))
            score += idf * freq * (self.k1 + 1) / denom
        return score

    def search(self, query: str, k: int = 4) -> list[tuple[float, dict]]:
        scored = [(self.score(query, i), self.docs[i]) for i in range(len(self.docs))]
        scored = [s for s in scored if s[0] > 0]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:k]


def rrf_fuse(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion：把多路检索结果按「排名」融合（无需归一化分数）。

    rankings 是若干条「id 列表」（各自已按相关性降序）。返回融合后的 (id, 分数)。
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
