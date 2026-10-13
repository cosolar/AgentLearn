"""main.py —— RAG 知识库示例的命令行入口

用法：
    python main.py ingest                  # 建库（需要 Embedding，写入 .chroma/）
    python main.py search "Atlas 由谁负责"   # 离线混合检索（纯 BM25，无需 API Key）
    python main.py graph "Atlas"           # 图谱多跳查询（离线）
    python main.py graph-rag "问题"         # GraphRAG 完整链路（前 3 步离线，生成需 LLM）
    python main.py ask "Atlas 受什么政策约束" # Agentic RAG 问答（需要 LLM API Key）
"""

from __future__ import annotations

import sys

from config import DEFAULT, load_documents
from graph import build_graph_from_docs
from retrieval import HybridRetriever, format_hits


def cmd_ingest() -> None:
    from store import build_vectorstore

    DEFAULT.ensure_dirs()
    store = build_vectorstore(DEFAULT)
    print(f"✅ 建库完成，集合「{DEFAULT.collection}」已写入 {DEFAULT.persist_dir}")
    print(f"   向量库对象：{type(store).__name__}（写入即落盘，无需 persist()）")


def cmd_search(query: str) -> None:
    """离线混合检索：只用 BM25（向量部分自动跳过）。"""
    retriever = HybridRetriever.from_disk(DEFAULT, vectorstore=None)
    hits = retriever.search(query)
    print(f"🔍 查询：{query}\n")
    print(format_hits(hits))


def cmd_graph(entity: str) -> None:
    graph = build_graph_from_docs(load_documents(DEFAULT))
    print(f"🕸️  实体：{entity}")
    print(f"   实体总数：{len(graph.entities())}，边数：{len(graph.edges)}")
    print(f"   2 跳内关联：{'、'.join(graph.multi_hop(entity, hops=2))}")


def cmd_graph_rag(question: str) -> None:
    """GraphRAG 完整链路：识别 → 扩展 → 取证（离线），再交给 LLM 生成。"""
    from graph_rag import GraphRAG

    rag = GraphRAG()
    entities = rag.find_entities(question)
    related = rag.expand(entities, hops=2)
    context = rag.collect_context(related)

    print(f"🕸️  问题：{question}")
    print(f"   ① 识别实体：{entities}")
    print(f"   ② 2 跳扩展：{related}")
    print(f"   ③ 证据片段（{len(context)} 字符）：\n{context}\n")

    try:
        print("🤖 生成回答：")
        print(rag.answer(question, hops=2))
    except Exception as exc:  # noqa: BLE001 - 无 API Key 时降级为只展示证据
        print(f"（跳过 LLM 生成：{type(exc).__name__}。设置 LLM_API_KEY 后可生成答案）")


def cmd_ask(question: str) -> None:
    from agent import ask

    print("🤖 正在检索并生成回答...\n")
    print(ask(question))


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 0
    cmd, *rest = argv[1:]
    if cmd == "ingest":
        cmd_ingest()
    elif cmd == "search" and rest:
        cmd_search(" ".join(rest))
    elif cmd == "graph" and rest:
        cmd_graph(" ".join(rest))
    elif cmd == "graph-rag" and rest:
        cmd_graph_rag(" ".join(rest))
    elif cmd == "ask" and rest:
        cmd_ask(" ".join(rest))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
