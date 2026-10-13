"""agent.py —— Agentic RAG：让 Agent 自主决定检索策略

对应 docs/05-RAG系统/01-RAG原理.md 的 5.4 Agentic RAG：
    把「检索」与「图谱查询」封装成工具，交给 create_agent 自主调用——
    由模型决定检索几次、换什么关键词、是否用图谱做多跳推理。

依赖：langchain v1 / langchain-openai（延迟导入，仅在实际调用时加载）。
"""

from __future__ import annotations

import os

from config import RAGConfig, load_documents
from graph import build_graph_from_docs


def _get_llm(cfg: RAGConfig):
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=cfg.chat_model,
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        temperature=0,
    )


def build_tools(cfg: RAGConfig, retriever, graph) -> list:
    """构造 Agent 可调用的工具集。"""
    from langchain.tools import tool

    from retrieval import format_hits

    @tool
    def search_kb(query: str) -> str:
        """在知识库中做混合检索（向量 + BM25）。可用不同关键词多次调用。"""
        return format_hits(retriever.search(query))

    @tool
    def graph_query(entity: str, hops: int = 2) -> str:
        """查询知识图谱中某个实体 N 跳内的关联实体，用于跨文档多跳推理。"""
        related = graph.multi_hop(entity, hops=hops)
        if len(related) <= 1:
            return f"（图谱中未找到「{entity}」的关联实体）"
        return f"「{entity}」在 {hops} 跳内的关联实体：{'、'.join(related)}"

    return [search_kb, graph_query]


def build_agent(cfg: RAGConfig = None):  # type: ignore[assignment]
    """构建 Agentic RAG Agent。"""
    from langchain.agents import create_agent

    from config import DEFAULT
    from retrieval import HybridRetriever
    from store import load_vectorstore

    cfg = cfg or DEFAULT

    # 向量库可选：没有 Embedding 依赖时降级为纯 BM25
    try:
        vectorstore = load_vectorstore(cfg)
    except Exception:  # noqa: BLE001 - 依赖缺失 / 未建库时降级
        vectorstore = None

    retriever = HybridRetriever.from_disk(cfg, vectorstore=vectorstore)
    graph = build_graph_from_docs(load_documents(cfg))

    return create_agent(
        model=_get_llm(cfg),
        tools=build_tools(cfg, retriever, graph),
        system_prompt=cfg.system_prompt,
    )


def ask(question: str, cfg: RAGConfig = None) -> str:  # type: ignore[assignment]
    """单轮问答入口。"""
    agent = build_agent(cfg)
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    return result["messages"][-1].content
