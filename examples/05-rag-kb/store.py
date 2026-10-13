"""store.py —— 向量库封装（Chroma + OpenAI Embeddings）

对应 docs/05-RAG系统/03-向量数据库.md：
    - 使用 langchain_chroma（Chroma 已从 langchain-community 拆分）
    - 写入即落盘，**不要**调用已弃用的 vectorstore.persist()

注意：本模块依赖 langchain / langchain-openai / langchain-chroma，
均在函数内部**延迟导入**，因此未安装依赖时仍可运行纯离线的 BM25 / 图部分。
"""

from __future__ import annotations

from config import RAGConfig, load_documents
from chunking import Chunk, build_parent_child, children_only, parent_index


def build_chunks(cfg: RAGConfig) -> tuple[list[Chunk], dict[str, Chunk]]:
    """加载 data/ 文档并切分为父子块，返回 (全部块, 父块索引)。"""
    docs = load_documents(cfg)
    all_chunks: list[Chunk] = []
    for d in docs:
        all_chunks.extend(build_parent_child(
            d["text"], d["source"],
            parent_size=cfg.parent_size,
            child_size=cfg.chunk_size,
            overlap=cfg.chunk_overlap,
        ))
    return all_chunks, parent_index(all_chunks)


def get_embeddings(cfg: RAGConfig):
    """构造 Embedding 模型（延迟导入）。"""
    import os

    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=cfg.embedding_model,
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
    )


def build_vectorstore(cfg: RAGConfig = None):  # type: ignore[assignment]
    """用子块构建（并持久化）Chroma 向量库，返回向量库对象。"""
    from langchain_chroma import Chroma
    from langchain_core.documents import Document

    cfg = cfg or __import__("config").DEFAULT
    cfg.ensure_dirs()
    all_chunks, _ = build_chunks(cfg)
    children = children_only(all_chunks)

    documents = [
        Document(
            page_content=c.text,
            metadata={"source": c.source, "parent_id": c.parent_id, "chunk_id": c.chunk_id},
        )
        for c in children
    ]
    # langchain_chroma 写入即落盘，无需 persist()
    return Chroma.from_documents(
        documents=documents,
        embedding=get_embeddings(cfg),
        collection_name=cfg.collection,
        persist_directory=str(cfg.persist_dir),
    )


def load_vectorstore(cfg: RAGConfig = None):  # type: ignore[assignment]
    """加载已持久化的向量库。"""
    from langchain_chroma import Chroma

    cfg = cfg or __import__("config").DEFAULT
    return Chroma(
        collection_name=cfg.collection,
        embedding_function=get_embeddings(cfg),
        persist_directory=str(cfg.persist_dir),
    )
