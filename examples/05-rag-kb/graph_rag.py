"""graph_rag.py —— GraphRAG 完整链路（局部检索模式）

对应 docs/05-RAG系统/01-RAG原理.md 的 5.5 GraphRAG，以及 5.6 的评估思想。

链路（Local Search）：
    问题 → ① 识别实体 → ② 图上多跳扩展 → ③ 回溯原文证据 → ④ LLM 生成带来源的答案

其中 ①②③ 均为纯标准库、**可离线运行与自检**；只有 ④ 需要 LLM。

为什么需要 GraphRAG：向量检索擅长「找相似段落」，但「哪些产品同时受 A 政策约束
且由 B 部门负责」这类**跨文档多跳**问题，需要沿关系边遍历，而不是找相似文本。
"""

from __future__ import annotations

import re

from config import DEFAULT, RAGConfig, load_documents
from graph import build_graph_from_docs


class GraphRAG:
    """极简 GraphRAG（局部检索）：图谱负责「关系」，原文负责「证据」。"""

    def __init__(self, cfg: RAGConfig | None = None,
                 use_llm_extraction: bool = False, llm=None) -> None:
        self.cfg = cfg or DEFAULT
        self.docs = load_documents(self.cfg)
        self.graph = build_graph_from_docs(
            self.docs, use_llm=use_llm_extraction, llm=llm
        )

    # ---------- ① 识别实体（离线：字符串包含）----------
    def find_entities(self, question: str, min_len: int = 2) -> list[str]:
        """找出问题中出现的图谱实体（长实体优先，避免「产品」覆盖「Atlas」）。"""
        hits = [e for e in self.graph.entities() if e in question and len(e) >= min_len]
        return sorted(hits, key=len, reverse=True)

    # ---------- ② 图上多跳扩展 ----------
    def expand(self, entities: list[str], hops: int = 2) -> list[str]:
        visited: set[str] = set()
        for e in entities:
            visited.update(self.graph.multi_hop(e, hops=hops))
        return sorted(visited)

    # ---------- ③ 回溯原文证据 ----------
    def collect_context(self, entities: list[str], max_chars: int = 2000) -> str:
        """从原始文档中取「包含这些实体」的段落作为证据，并标注来源。"""
        parts: list[str] = []
        for d in self.docs:
            for para in re.split(r"\n\s*\n", d["text"]):
                para = para.strip()
                if para and any(e in para for e in entities):
                    parts.append(f"[{d['source']}] {para}")
        return "\n\n".join(parts)[:max_chars]

    # ---------- 关系描述（供 Agent 工具调用）----------
    def describe(self, entity: str, hops: int = 2) -> str:
        """把以 entity 为中心的子图渲染成文本。"""
        related = self.graph.multi_hop(entity, hops=hops)
        if len(related) <= 1:
            return f"（图谱中未找到「{entity}」的关联实体）"
        edges = [(s, r, o) for s, r, o in self.graph.edges
                 if s in related and o in related]
        lines = [f"{s} --{r}--> {o}" for s, r, o in edges]
        return f"与「{entity}」相关（{hops} 跳）：\n" + "\n".join(lines)

    # ---------- ④ 生成答案（需要 LLM）----------
    def answer(self, question: str, hops: int = 2, llm=None) -> str:
        """完整链路：识别 → 扩展 → 取证 → 生成。"""
        import os

        entities = self.find_entities(question)
        related = self.expand(entities, hops=hops)
        context = self.collect_context(related)

        if not context:
            return "未找到相关信息。"

        if llm is None:
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=self.cfg.chat_model,
                api_key=os.getenv("LLM_API_KEY"),
                base_url=os.getenv("LLM_BASE_URL"),
                temperature=0,
            )

        prompt = (
            "你是知识库问答助手。请**仅基于下面的证据**回答问题，"
            "并标注来源文件名；证据不足时明确说明。\n\n"
            f"【问题】{question}\n\n【证据】\n{context}\n\n【回答】"
        )
        return str(llm.invoke(prompt).content)


def main() -> int:
    """离线演示：不调用 LLM，只展示「识别 → 扩展 → 取证」三段。"""
    rag = GraphRAG()
    question = "Atlas 受什么约束，由谁制定？"
    entities = rag.find_entities(question)
    related = rag.expand(entities, hops=2)
    print(f"问题：{question}")
    print(f"① 识别实体：{entities}")
    print(f"② 2 跳扩展：{related}")
    print("③ 证据片段：")
    print(rag.collect_context(related, max_chars=400))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
