"""config.py —— RAG 知识库示例的集中配置

设计原则：把"可调参数"与"逻辑"分离，方便对照 docs/05-RAG系统/ 各章做实验。
依赖：仅标准库。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


@dataclass
class RAGConfig:
    """RAG 全链路配置"""

    # ---- 数据与存储 ----
    data_dir: Path = BASE_DIR / "data"                 # 原始文档目录
    persist_dir: Path = BASE_DIR / ".chroma"           # Chroma 落盘目录（已加入 .gitignore）
    collection: str = "agentlearn_kb"

    # ---- 切分参数（对应 5.2 文档处理）----
    chunk_size: int = 220          # 子块目标长度（字符）
    chunk_overlap: int = 40        # 相邻子块重叠
    parent_size: int = 600         # 父块长度（父块喂给 LLM，子块用于检索）

    # ---- 检索参数（对应 5.3 / 5.4）----
    top_k: int = 4                 # 召回条数
    hybrid_alpha: float = 0.5      # 混合检索权重：0=纯 BM25，1=纯向量
    rerank_top_n: int = 3          # 重排后保留条数

    # ---- 模型 ----
    chat_model: str = "gpt-5.5"
    embedding_model: str = "text-embedding-3-small"

    # ---- 生成 ----
    system_prompt: str = (
        "你是企业知识库问答助手。回答规则：\n"
        "1) 回答前必须先检索，不要凭记忆作答；\n"
        "2) 证据不足时换关键词再次检索，最多检索 3 轮；\n"
        "3) 最终回答必须基于检索到的原文，并标注来源文件名；\n"
        "4) 确实检索不到时，明确回答「未找到相关信息」。"
    )

    def ensure_dirs(self) -> None:
        self.persist_dir.mkdir(parents=True, exist_ok=True)


DEFAULT = RAGConfig()


def load_documents(cfg: RAGConfig = DEFAULT) -> list[dict]:
    """加载 data/ 下的所有 .md / .txt 文档，返回 [{source, text}]。

    纯标准库实现，离线可用；生产可替换为 LangChain 的各类 Loader（见 5.2）。
    """
    docs: list[dict] = []
    for path in sorted(cfg.data_dir.glob("*")):
        if path.suffix.lower() not in (".md", ".txt"):
            continue
        docs.append({"source": path.name, "text": path.read_text(encoding="utf-8")})
    return docs
