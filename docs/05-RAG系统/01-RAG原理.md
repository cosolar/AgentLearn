# 5.1 RAG 原理详解 —— 检索增强生成的核心机制

> 📅 更新至 2026-10 · 技术栈基线见 [教程大纲](../教程大纲.md)

## 📖 导读

> **LLM 的知识止于它的训练数据。RAG 让 LLM 能"看到"训练数据之外的世界。**

RAG（Retrieval-Augmented Generation，检索增强生成）是当前最主流的 LLM 应用范式。它通过**先检索相关信息，再基于检索结果生成答案**，解决了 LLM 的"知识截止日期"问题。本章不仅讲清原理，还要直面一个现实：**朴素 RAG 经常失败**，并给出 2026 年的解法——**Agentic RAG** 与 **GraphRAG**。

> 📌 本章基线：`langchain>=1.4.5`、`langchain-core>=1.6.10`、`langchain-openai>=1.7.1`、`langchain-chroma>=1.1.0`、`chromadb>=1.5.9`、`langgraph>=1.2.15`；Agent 入口统一用 `from langchain.agents import create_agent`。

---

## 一、前置知识

| 概念 | 章节 | 说明 |
|------|------|------|
| Embedding | 3.3 | 文本→向量的转换 |
| 向量数据库 | 3.3 | 存储和检索向量的系统 |
| Token | 1.1 | LLM 的输入/输出计量单位 |
| `create_agent` | 3.4 | 标准 Agent 入口 |

---

## 二、为什么需要 RAG？

### 2.1 LLM 的固有局限

```text
LLM 就像一个知识渊博但不更新的教授：
✅ 懂得很多（训练数据中的知识）
❌ 不知道新知识（训练后的新信息）
❌ 不知道你的私有数据（公司文档、个人信息）
❌ 会产生幻觉（编造不确定的信息）
```

### 2.2 解决方案对比

| 方案 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| **RAG** | 检索相关文档 + LLM 基于文档回答 | ✅ 实时更新 ✅ 可溯源 ✅ 低成本 | ❌ 依赖检索质量 |
| **微调** | 用新数据重新训练模型 | ✅ 深度融入模型 | ❌ 成本高 ❌ 更新慢 ❌ 可能遗忘 |
| **长上下文** | 把所有文档塞进 context | ✅ 简单直接 | ❌ 成本极高 ❌ 受窗口大小限制 |

---

## 三、RAG 核心工作流程

### 3.1 两大阶段

```text
阶段一：索引（Indexing）—— 建好知识库
原始文档 → 加载 → 分块 → Embedding → 存入向量库

阶段二：查询（Query）—— 回答问题
用户问题 → Embedding → 向量库检索 → 构建 Prompt（文档 + 问题）→ LLM 生成答案
```

```text
┌────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐
│ 文档   │    │ 文档分块  │    │ 生成向量  │    │ 存储到 │
│ 加载   │───▶│ (Chunk)  │───▶│(Embedding)│───▶│ 向量库  │
└────────┘    └──────────┘    └──────────┘    └───┬────┘
                                                  │
┌────────┐    ┌──────────┐    ┌──────────┐        │
│ 用户   │    │ 查询向量化 │    │ 相似度   │        │
│ 提问   │───▶│(Embedding)│───▶│ 检索     │◀───────┘
└────────┘    └──────────┘    └────┬─────┘
                                   ▼
                          ┌──────────────────┐
                          │ 构建 Prompt       │
                          │ 原文 + 问题 → LLM │
                          └────────┬─────────┘
                                   ▼
                          ┌──────────────────┐
                          │  生成答案 + 引用   │
                          └──────────────────┘
```

### 3.2 最小可运行 RAG（Naive RAG）

```python
import os

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL_NAME", "gpt-5.5"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        temperature=0,
    )


embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

docs = [
    Document(page_content="RAG 通过检索增强生成，缓解 LLM 幻觉。", metadata={"source": "rag.md"}),
    Document(page_content="LangGraph 是低层编排运行时，支持分支、循环与持久化。", metadata={"source": "lg.md"}),
]

# langchain-chroma 写入即落盘，无需（也不应）调用已弃用的 vectorstore.persist()
vectorstore = Chroma.from_documents(docs, embeddings, collection_name="naive_rag")
retriever = vectorstore.as_retriever(search_kwargs={"k": 2})


def format_docs(docs: list[Document]) -> str:
    return "\n\n".join(f"[{d.metadata.get('source', '?')}] {d.page_content}" for d in docs)


prompt = ChatPromptTemplate.from_template(
    "只依据参考信息回答，并标注来源。\n\n参考信息：\n{context}\n\n问题：{question}"
)

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | get_llm()
    | StrOutputParser()
)

print(rag_chain.invoke("RAG 能解决什么问题？"))
```

**特点**：简单、快速，适合文档质量高、问题明确、**单跳**的场景。

---

## 四、朴素 RAG 的失败模式（务必先看）

朴素 RAG 在实际系统中经常"看起来能用、实际不好用"。常见失败模式：

| 失败模式 | 表现 | 根因 | 对应解法 |
|----------|------|------|----------|
| **检索不到** | 明明有答案却答"未找到" | 查询与文档用词/语义差异大 | 查询改写、HyDE、多查询（见 5.4） |
| **检索到错的** | 引用了不相关文档 | 纯向量漏掉关键词精确匹配 | 混合检索（BM25 + 向量） |
| **上下文碎片化** | 只命中半句话 | chunk 太小 / 边界切断语义 | 增大 overlap、父子块（见 5.2） |
| **信息过载** | 关键信息被噪声淹没 | 召回太多、排序不准 | 重排序、上下文压缩（见 5.4） |
| **多跳推理失败** | 需要串联多个文档才能回答 | 单次检索无法跨文档连接 | GraphRAG / Agentic RAG |
| **时效性问题** | 引用了过期内容 | 索引未更新 | 增量索引（见 5.5） |
| **幻觉式引用** | 答案对但来源是编的 | 未强制"只依据检索内容" | 提示约束 + 证据校验 |

> 💡 一句话：**朴素 RAG 的瓶颈通常不在 LLM，而在检索**。RAG 的演进方向（Advanced / Modular / Agentic / GraphRAG）本质上都是在"补检索的短板"。

---

## 五、RAG 的四种架构

### 5.1 Naive RAG（基础版）

一次检索、一次生成。见上文 3.2。

### 5.2 Advanced RAG（进阶版）

在检索前后增加优化步骤：查询改写、混合检索、重排序、上下文压缩。详见 [5.4 检索优化技巧](./04-优化策略.md)。

### 5.3 Modular RAG（模块化版）

把 RAG 拆成可替换的独立模块，便于按需组合。

```python
class ModularRAG:
    """模块化 RAG：每个组件可独立替换"""

    def __init__(self, query_processor, retriever, reranker, generator, validator):
        self.query_processor = query_processor   # 查询处理
        self.retriever = retriever               # 混合检索
        self.reranker = reranker                 # 重排序
        self.generator = generator               # 生成
        self.validator = validator               # 答案校验

    def answer(self, query: str) -> dict:
        processed = self.query_processor.process(query)
        docs = self.retriever.retrieve(processed)
        ranked = self.reranker.rerank(query, docs)
        answer = self.generator.generate(query, ranked)
        return self.validator.validate(answer)
```

### 5.4 Agentic RAG（智能体化 RAG）—— 可运行示例

传统 RAG 是"检索一次 → 生成"，而 **Agentic RAG 把控制权交给 Agent**：它自己判断"要不要检索""检索几次""是否需要换查询词""答案是否足够好"。

```text
传统 RAG：  问题 → 检索 → 生成                     （固定单次）
Agentic RAG：问题 → 规划 → 检索 → 评估 → 再检索/改写 → ... → 生成
                        ↑__________________________|
```

下面是一个**完整可运行**的最小示例：把"检索"包装成工具，交给 `create_agent` 自主调用。

```python
"""Agentic RAG：让 Agent 自主决定检索策略"""
import os

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL_NAME", "gpt-5.5"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        temperature=0,
    )


# 1. 建一个小知识库
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma.from_documents(
    documents=[
        Document(page_content="LangGraph 用 StateGraph 描述工作流，支持条件边与循环。",
                 metadata={"source": "langgraph.md"}),
        Document(page_content="RAG 通过检索增强生成，缓解幻觉并支持溯源。",
                 metadata={"source": "rag.md"}),
        Document(page_content="Chroma 是轻量向量库，写入时自动持久化。",
                 metadata={"source": "chroma.md"}),
    ],
    embedding=embeddings,
    collection_name="agentic_rag",
)


# 2. 把检索封装成工具（Agent 可反复、换词调用）
@tool
def search_kb(query: str) -> str:
    """在企业知识库中检索。可以多次调用，用不同角度的关键词。"""
    hits = vectorstore.similarity_search(query, k=3)
    if not hits:
        return "（未检索到相关内容）"
    return "\n\n".join(f"[{d.metadata.get('source', '?')}] {d.page_content}" for d in hits)


# 3. 构建自主检索 Agent
agent = create_agent(
    model=get_llm(),
    tools=[search_kb],
    system_prompt=(
        "你是知识库问答助手。规则：\n"
        "1) 回答前必须先检索；\n"
        "2) 若证据不足，换关键词再次检索；\n"
        "3) 最终回答必须基于检索原文，并标注来源；\n"
        "4) 确实检索不到时，明确回答'未找到相关信息'。"
    ),
)

if __name__ == "__main__":
    result = agent.invoke({
        "messages": [{"role": "user", "content": "LangGraph 和 RAG 分别解决什么问题？"}]
    })
    print(result["messages"][-1].content)
```

**核心思想**：把 RAG 的每个环节（改写、检索、重排、校验）都变成 Agent 可自主调用的**工具**，让它像人一样"按需检索、反复验证"。

### 5.5 GraphRAG（图增强 RAG）—— 半可运行示例

向量检索擅长"找相似段落"，但不擅长"跨文档的多跳推理"（如"哪些产品同时受 A 政策影响且由 B 部门负责？"）。**GraphRAG** 用知识图谱补足。

| 维度 | 向量 RAG | GraphRAG |
|------|----------|----------|
| 数据结构 | 文本块向量 | 实体-关系图 + 向量 |
| 擅长 | 语义相似、局部细节 | 多跳推理、全局综述 |
| 典型问题 | "X 是什么？" | "X 和 Y 有什么联系？" |
| 代表实现 | Chroma / FAISS | Microsoft GraphRAG、Neo4j + 向量 |

下面的示例用 LLM 抽取"实体三元组"构建一张极简内存图，再做多跳遍历。**这是半可运行示例**——依赖 LLM 输出格式，生产应改用成熟 GraphRAG 框架。

```python
"""极简 GraphRAG：LLM 抽取三元组 → 内存图 → 多跳检索"""
import json
import os

from langchain_openai import ChatOpenAI


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL_NAME", "gpt-5.5"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        temperature=0,
    )


def extract_triples(text: str) -> list[tuple[str, str, str]]:
    """用 LLM 抽取 (主语, 关系, 宾语) 三元组"""
    prompt = (
        "从下面的文本中抽取实体关系三元组，"
        "严格输出 JSON 数组，每个元素为 [主语, 关系, 宾语]。\n\n"
        f"文本：{text}"
    )
    raw = get_llm().invoke(prompt).content
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [(str(s), str(r), str(o)) for s, r, o in data]


class SimpleGraph:
    """极简知识图谱（内存版）"""

    def __init__(self):
        self.edges: list[tuple[str, str, str]] = []

    def add(self, triples: list[tuple[str, str, str]]) -> None:
        self.edges.extend(triples)

    def neighbors(self, entity: str) -> list[tuple[str, str]]:
        """返回该实体的所有一跳邻居 (邻居, 关系)"""
        out = [(o, r) for s, r, o in self.edges if s == entity]
        out += [(s, r) for s, r, o in self.edges if o == entity]
        return out

    def multi_hop(self, entity: str, hops: int = 2) -> list[str]:
        """多跳遍历：收集 hops 跳内可达的实体"""
        visited = {entity}
        frontier = {entity}
        for _ in range(hops):
            nxt = set()
            for node in frontier:
                for neighbor, _rel in self.neighbors(node):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        nxt.add(neighbor)
            frontier = nxt
        return list(visited)


if __name__ == "__main__":
    texts = [
        "ACME 公司的 Atlas 产品由华东区负责，并受《数据合规政策》约束。",
        "《数据合规政策》由法务部制定，适用于所有面向欧盟的产品。",
    ]

    graph = SimpleGraph()
    for t in texts:
        graph.add(extract_triples(t))

    # 多跳检索：从 "Atlas" 出发，找到 2 跳内的相关实体
    related = graph.multi_hop("Atlas", hops=2)
    print("与 Atlas 相关的实体：", related)
    # 再把 related 作为线索，回向量库取原文交给 LLM 生成答案（略）
```

**混合做法（推荐）**：向量检索拿"局部细节"，图谱检索拿"关系/全局"，两者融合后交给 LLM。

> 💻 **完整可运行版本**：上面的 GraphRAG 已在 [`examples/05-rag-kb/graph_rag.py`](../../examples/05-rag-kb/) 中实现为**完整链路**（问题 → 识别实体 → 图上多跳扩展 → 回溯原文证据 → LLM 生成带来源的答案）。
>
> 其中**前三步（识别 / 扩展 / 取证）为纯标准库、可离线运行**，只有最后一步需要 LLM：
>
> ```bash
> cd examples/05-rag-kb
> python main.py graph-rag "Atlas 受什么约束，由谁制定？"   # 前三步离线，生成需 LLM
> python graph_rag.py                                      # 只看离线三段
> ```
>
> 此外 `graph.py` 同时提供**规则抽取**（离线，用于教学与自检）与 **LLM 抽取**（`extract_triples_llm`，覆盖面更广）两种建图方式。

---

## 六、RAG vs 微调 vs 纯 LLM

| 维度 | 纯 LLM | RAG | 微调 |
|------|--------|-----|------|
| **知识时效** | 训练截止日期 | ✅ 实时更新 | 训练截止日期 |
| **私有数据** | ❌ 看不到 | ✅ 可以访问 | ✅ 可以融入 |
| **可溯源** | ❌ 黑盒 | ✅ 可追溯来源 | ❌ 黑盒 |
| **幻觉控制** | ❌ 易产生 | ✅ 有据可依 | ⚠️ 略有改善 |
| **实施成本** | 低（直接调用） | 中（建向量库） | 高（需要算力） |
| **更新速度** | 快 | ✅ 秒级更新 | 慢（重新训练） |
| **维护复杂度** | 低 | 中 | 高 |

**什么时候选 RAG？** 需要回答**私有文档**、需要**实时**信息、需要**可追溯**来源、且没有资源/意愿去微调模型时。

---

## 七、应用场景

| 场景 | 知识来源 | 典型用户 |
|------|----------|----------|
| **企业知识库** | 内部文档、手册、政策 | 员工自助问答 |
| **客服系统** | 产品文档、FAQ、工单历史 | 客户自助服务 |
| **法务助手** | 法律法规、判例、合同 | 法律专业人员 |
| **医疗辅助** | 医学文献、诊疗指南、病历 | 临床医生 |
| **学术研究** | 论文库、技术报告 | 研究人员 |
| **代码助手** | API 文档、代码库、技术博客 | 开发者 |

---

## 八、2026 趋势与选型建议

| 趋势 | 说明 |
|------|------|
| **多模态 RAG** | 检索图片、表格、PDF 版面，而不仅是纯文本 |
| **上下文检索（Contextual Retrieval）** | 分块时用 LLM 为每块补充上下文，显著提升召回 |
| **自适应检索** | 简单问题不检索，复杂问题多轮检索 |
| **缓存与增量索引** | 只重新索引变化的文档，降低成本 |

```text
问答型、文档明确          → Advanced RAG（混合检索 + 重排）
多步推理、关系复杂        → GraphRAG 或 混合方案
问题开放、需要自主判断    → Agentic RAG
超大规模、企业级          → Modular RAG + 缓存 + 增量索引
```

---

## 九、本章小结

| 知识点 | 一句话说明 |
|--------|------------|
| **RAG** | 先检索相关文档，再基于文档生成答案 |
| **索引阶段** | 文档 → 分块 → 向量化 → 存储 |
| **查询阶段** | 问题 → 向量化 → 检索 → 增强 → 生成 |
| **失败模式** | 检索不到 / 检索到错的 / 碎片化 / 过载 / 多跳失败 |
| **Naive / Advanced / Modular** | 从"单次检索"到"可替换模块" |
| **Agentic RAG** | Agent 自主决定检索/改写/校验，适合开放复杂问题 |
| **GraphRAG** | 用知识图谱增强多跳推理与全局综述 |

---

> 💻 **配套代码**：本章的完整可运行实现见 [`examples/05-rag-kb/`](../../examples/05-rag-kb/)——含父子块切分、混合检索（向量 + BM25 + RRF）、Agentic RAG 与 GraphRAG 多跳。`python smoke_test.py` 可**离线自检 14 项**，`python main.py graph "Atlas"` 可离线跑图谱查询。

## 📝 课后练习

1. **📝 理解题**：用自己的话解释 RAG 为什么能缓解幻觉，并说明它**不能**解决什么
2. **💡 对比题**：针对"根据最新公司政策回答问题"，RAG 比微调好在哪里？
3. **🔍 实践题**：运行 5.4 的 Agentic RAG 示例，故意提一个知识库里没有的问题，观察 Agent 是否会"换关键词再检索"或如实说"未找到"
4. **🚀 挑战题**：给 5.5 的 `SimpleGraph` 增加一个 `to_context(entity)` 方法，把多跳结果拼成文本交给 LLM 生成带来源的答案
