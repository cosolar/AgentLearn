# RAG 知识库示例（05-rag-kb）

一个**可运行、可离线自检**的检索增强生成（RAG）示例，对应教程 [第五部分：RAG 系统](../../docs/05-RAG系统/)。

它把第五部分的核心概念串成一条完整链路：**加载 → 切分 → 父块/子块 → 混合检索（向量 + BM25）→ 父块回溯 → Agentic RAG 问答**，并额外演示 **GraphRAG 多跳检索**。

## 设计要点

| 模块 | 文件 | 说明 | 是否需要 API Key |
|:-----|:-----|:-----|:----------------:|
| 配置 | `config.py` | 集中管理切分/检索/模型参数 | 否 |
| 切分 | `chunking.py` | 标题切分 + 定长切分 + **父子块** | 否 |
| 关键词检索 | `bm25.py` | 纯标准库 BM25 + RRF 融合 | 否 |
| 知识图谱 | `graph.py` | 极简图 + 多跳遍历 + 规则/LLM 三元组抽取 | 否（LLM 抽取需） |
| GraphRAG | `graph_rag.py` | 识别→扩展→取证→生成 的完整链路 | 仅生成步骤需 |
| 向量库 | `store.py` | `langchain_chroma` + OpenAI Embeddings（延迟导入） | 是 |
| 混合检索 | `retrieval.py` | 向量 + BM25 → RRF → 父块回溯 | 否（降级为 BM25） |
| Agentic RAG | `agent.py` | `create_agent` + 检索/图谱工具 | 是 |
| 命令行 | `main.py` | `ingest` / `search` / `graph` / `ask` | 部分 |
| 自检 | `smoke_test.py` | 18 项离线断言 | 否 |

> 💡 **离线可用**：除 `store.py` / `agent.py` 外，全部模块**零第三方依赖**，因此 `search`、`graph` 与 `smoke_test.py` 无需任何 API Key 即可运行。

## 快速开始

```bash
# 1) 离线自检（推荐先跑，确认环境 OK）
python smoke_test.py
#   → 通过 18/18

# 2) 离线关键词检索（无需 API Key）
python main.py search "Atlas 由谁负责"

# 3) 图谱多跳查询（无需 API Key）
python main.py graph "Atlas"

# 4) GraphRAG 完整链路（识别/扩展/取证离线，生成需 LLM）
python main.py graph-rag "Atlas 受什么约束，由谁制定？"

# 5) 建向量库（需要 Embedding，写入 .chroma/）
python main.py ingest

# 6) Agentic RAG 问答（需要 LLM API Key）
python main.py ask "Atlas 受什么政策约束"
```

配置 LLM：在仓库根目录 `.env` 中设置

```bash
LLM_MODEL_NAME=gpt-5.5
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
```

## 数据

`data/` 下是 3 篇示例文档（公司产品、合规政策、技术栈），可直接替换为你自己的 `.md` / `.txt`。

## 与教程章节的对应

| 教程 | 本示例对应实现 |
|:-----|:---------------|
| [5.1 RAG 原理](../../docs/05-RAG系统/01-RAG原理.md) | 最小闭环、Agentic RAG（`agent.py`）、GraphRAG（`graph_rag.py`） |
| [5.2 文档处理](../../docs/05-RAG系统/02-文档处理.md) | 标题切分与父子块（`chunking.py`） |
| [5.3 向量数据库](../../docs/05-RAG系统/03-向量数据库.md) | `langchain_chroma` 建库与持久化（`store.py`） |
| [5.4 优化策略](../../docs/05-RAG系统/04-优化策略.md) | 混合检索 + RRF + 父块回溯（`bm25.py` / `retrieval.py`） |
| [5.6 RAG 评估](../../docs/05-RAG系统/06-RAG评估.md) | 检索侧指标与黄金集（`eval.py`） |
| [5.5 企业级知识库](../../docs/05-RAG系统/05-企业级知识库.md) | 多源加载、来源标注、增量重建的思路骨架 |

## 注意事项

- 向量库写入即落盘（`langchain_chroma`），**不要**调用已弃用的 `vectorstore.persist()`。
- 未安装 `langchain-chroma` 时，`search` 会自动降级为纯 BM25，不影响自检。
- 规则版三元组抽取（`graph.py`）仅用于教学与离线演示；生产应改用 LLM 抽取或成熟 GraphRAG 框架。
- `.chroma/` 为本地持久化目录，已被 `.gitignore` 忽略。
