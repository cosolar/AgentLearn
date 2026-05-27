# 3.3 向量存储与检索 —— 为 Agent 装上"语义搜索引擎"

## 📖 导读

> **传统搜索靠关键词匹配，向量搜索靠语义理解。**

向量存储（Vector Store）是 RAG（检索增强生成）技术的核心基础设施。它让 Agent 能在海量文本中找到**语义上最相关**的内容——即使关键词不完全匹配。本文将深入讲解向量嵌入的原理、向量数据库的使用、以及检索策略的优化。

---

## 一、前置知识

| 概念 | 说明 |
|------|------|
| **Embedding** | 将文本转换为数值向量的技术 |
| **语义相似度** | 向量空间中两个文本距离的远近 |
| **最近邻搜索** | 在向量库中找到与查询向量最相似的 K 个向量 |
| **Token** | LLM 的处理单元，也是 Embedding 的计费单位 |

---

## 二、什么是向量嵌入？

### 2.1 直观理解

```text
传统搜索：
用户搜"猫" → 只匹配包含"猫"字的文档 → 错过"猫咪""小猫""feline"

向量搜索：
用户搜"猫" → 转换为向量 [0.1, 0.5, -0.3, ...]
           → 找到向量空间中最接近的内容
           → "猫咪" [0.12, 0.48, -0.28, ...] ✅ 匹配
           → "宠物" [0.15, 0.45, -0.20, ...] ✅ 相关
           → "汽车" [-0.1, 0.1, 0.6, ...]    ❌ 无关
```

### 2.2 文本 → 向量的过程

```python
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# 文本 → 向量
text_1 = "猫是一种可爱的动物"
text_2 = "猫咪很讨人喜欢"
text_3 = "汽车需要定期保养"

vector_1 = embeddings.embed_query(text_1)
vector_2 = embeddings.embed_query(text_2)
vector_3 = embeddings.embed_query(text_3)

print(f"向量维度: {len(vector_1)}")  # 1536
print(f"向量 (前5个): {vector_1[:5]}")  # [0.012, -0.023, 0.045, ...]

# 语义相似度（余弦相似度）
import numpy as np

def cosine_similarity(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

sim_1_2 = cosine_similarity(vector_1, vector_2)  # 高相似度（都是关于猫）
sim_1_3 = cosine_similarity(vector_1, vector_3)  # 低相似度（猫 vs 汽车）

print(f"猫 vs 猫咪: {sim_1_2:.3f}")  # ~0.85
print(f"猫 vs 汽车: {sim_1_3:.3f}")  # ~0.30
```

### 2.3 Embedding 模型对比

| 模型 | 维度 | 特点 | 适用场景 |
|------|------|------|----------|
| `text-embedding-3-small` | 1536 | 性价比高，速度快 | **默认推荐** |
| `text-embedding-3-large` | 3072 | 精度更高（但更贵） | 对精度要求极高的场景 |
| `text-embedding-ada-002` | 1536 | 上一代模型 | 兼容旧项目 |

> 💡 **选择建议**：没有特殊需求时，直接使用 `text-embedding-3-small`。它在大多数场景下已经足够好，且成本只有 large 版本的 1/5。

---

## 三、向量数据库实战

### 3.1 主流向量数据库对比

| 数据库 | 部署方式 | 特点 | 适用场景 |
|--------|----------|------|----------|
| **Chroma** | 本地/嵌入式 | 零配置、轻量级 | **开发测试、小型项目** |
| **FAISS** | 本地库 | Meta 出品，极快 | 本地应用、批量处理 |
| **Pinecone** | 云服务 | 全托管、高可用 | 生产环境 |
| **Milvus** | 自托管/云 | 分布式、大规模 | 企业级 |
| **Weaviate** | 自托管/云 | 内置向量化 | 需要内置 NLP 能力 |
| **Qdrant** | 自托管/云 | Rust 实现，性能好 | 高吞吐场景 |

### 3.2 Chroma 实战（推荐用于学习）

#### 安装

```bash
uv add chromadb
```

#### 完整流程

```python
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# 1. 准备文档
documents = [
    Document(
        page_content="AI Agent 是一种能够自主感知环境、理解意图、做出决策并采取行动的智能软件系统。",
        metadata={"source": "agent_intro", "page": 1}
    ),
    Document(
        page_content="LangChain 是一个用于构建 LLM 应用的开发框架，提供了模型调用、链式组合、Agent 等能力。",
        metadata={"source": "langchain_intro", "page": 2}
    ),
    Document(
        page_content="向量数据库将文本转换为向量进行存储，支持基于语义相似度的检索。",
        metadata={"source": "vector_db", "page": 3}
    ),
]

# 2. 初始化 Embedding 模型
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# 3. 创建向量存储（自动计算向量并索引）
vectorstore = Chroma.from_documents(
    documents=documents,
    embedding=embeddings,
    persist_directory="./chroma_db",  # 持久化到磁盘
)

# 4. 持久化
vectorstore.persist()

# 5. 检索测试
query = "什么是 AI Agent？"
results = vectorstore.similarity_search(query, k=2)

print(f"查询：{query}\n")
for i, doc in enumerate(results, 1):
    print(f"结果 {i}:")
    print(f"  内容：{doc.page_content}")
    print(f"  来源：{doc.metadata}")
    print()
```

#### 基本检索方式

```python
# 1. 基础相似度搜索
results = vectorstore.similarity_search("AI Agent 是什么？", k=3)

# 2. 带分数的相似度搜索
results_with_scores = vectorstore.similarity_search_with_relevance_scores(
    "AI Agent 是什么？",
    k=3,
)
for doc, score in results_with_scores:
    print(f"分数：{score:.3f} | 内容：{doc.page_content[:50]}...")

# 3. 根据向量直接检索
query_vector = embeddings.embed_query("AI Agent 是什么？")
results = vectorstore.similarity_search_by_vector(query_vector, k=3)

# 4. MMR（最大边际相关性，增加结果多样性）
results = vectorstore.max_marginal_relevance_search(
    "AI Agent 是什么？",
    k=3,
    fetch_k=10,  # 先取 10 个候选，再从中选 3 个多样化的
)
```

---

### 3.3 FAISS 实战（高性能本地检索）

```python
# 安装
# uv add faiss-cpu  # 或 faiss-gpu

from langchain_community.vectorstores import FAISS

# 创建 FAISS 索引（API 与 Chroma 几乎一致）
vectorstore = FAISS.from_documents(
    documents=documents,
    embedding=embeddings,
)

# 保存和加载
vectorstore.save_local("./faiss_index")
loaded_vectorstore = FAISS.load_local(
    "./faiss_index",
    embeddings,
    allow_dangerous_deserialization=True,  # v0.2+ 需要显式确认
)
```

### 3.4 异步操作（生产环境推荐）

```python
# 异步创建和检索
async def async_vector_ops():
    # 异步创建（适合批量处理大量文档）
    vectorstore = await Chroma.afrom_documents(
        documents=documents,
        embedding=embeddings,
    )
    
    # 异步检索
    results = await vectorstore.asimilarity_search(
        "AI Agent 是什么？",
        k=3,
    )
    
    return results
```

---

## 四、检索策略详解

### 4.1 相似度搜索 vs MMR

| 策略 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| **相似度搜索** | 选和查询最像的 K 个 | 相关度高 | 结果可能重复 |
| **MMR** | 选相关+多样化的 K 个 | 结果覆盖广 | 可能遗漏最相关项 |

```python
# 对比示例
query = "Python 编程"

# 相似度搜索：结果都围绕 Python
similar_results = vectorstore.similarity_search(query, k=3)
# 1. Python 基础语法
# 2. Python 函数式编程
# 3. Python 面向对象

# MMR：覆盖不同角度
mmr_results = vectorstore.max_marginal_relevance_search(query, k=3)
# 1. Python 基础语法
# 2. Java 和 Python 对比  ← 新角度
# 3. 编程入门指南        ← 新角度
```

### 4.2 检索参数调优

```python
def tune_retrieval_params(vectorstore, query: str):
    """对比不同参数的效果"""
    
    # 不同的 k 值
    for k in [1, 3, 5, 10]:
        results = vectorstore.similarity_search(query, k=k)
        print(f"k={k}: 找到 {len(results)} 个结果")
    
    # 不同的分数阈值
    results = vectorstore.similarity_search_with_relevance_scores(
        query, k=10
    )
    for doc, score in results:
        if score > 0.7:  # 只取高置信度结果
            print(f"✅ {score:.3f}: {doc.page_content[:30]}")
        else:
            print(f"❌ {score:.3f}: {doc.page_content[:30]}")
```

| 参数 | 说明 | 推荐值 | 效果 |
|------|------|--------|------|
| **k** | 返回结果数 | 3-5 | k 越大信息越多，但噪声也越多 |
| **score_threshold** | 分数阈值 | 0.5-0.7 | 过滤低质量结果 |
| **fetch_k** | MMR 候选数 | k * 2-3 | 增加多样性 |
| **lambda_mult** | MMR 多样性权重 | 0.5 | 0=纯多样，1=纯相关 |

---

## 五、构建检索器

```python
from langchain_core.vectorstores import VectorStoreRetriever

# 从向量存储创建检索器
retriever = vectorstore.as_retriever(
    search_type="similarity",  # 或 "mmr"
    search_kwargs={
        "k": 3,
        "score_threshold": 0.5,
    }
)

# 检索
docs = retriever.invoke("什么是 AI Agent？")

# 在 Chain 中使用
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

rag_chain = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough(),
    }
    | ChatPromptTemplate.from_template(
        "基于以下上下文回答问题：\n\n{context}\n\n问题：{question}"
    )
    | ChatOpenAI(model="gpt-4o")
    | StrOutputParser()
)

answer = rag_chain.invoke("AI Agent 有哪些核心能力？")
```

---

## 六、元数据过滤

```python
# 添加元数据：为文档标记来源、日期、分类等
documents = [
    Document(
        page_content="Python 3.12 发布说明",
        metadata={
            "source": "official",
            "date": "2023-10-02",
            "category": "release",
            "language": "en",
        }
    ),
    Document(
        page_content="2024 年 AI 趋势报告",
        metadata={
            "source": "research",
            "date": "2024-01-15",
            "category": "report",
            "language": "zh",
        }
    ),
]

# 创建带元数据的向量存储
vectorstore = Chroma.from_documents(documents, embeddings)

# 使用元数据过滤检索
results = vectorstore.similarity_search(
    "AI 趋势",
    k=3,
    filter={"category": "report"},  # 只查报告类
)

# 复合过滤（部分数据库支持）
results = vectorstore.similarity_search(
    "Python 新特性",
    k=3,
    filter={
        "$and": [
            {"category": {"$eq": "release"}},
            {"date": {"$gte": "2023-01-01"}},
        ]
    }
)
```

---

## 七、最佳实践与优化建议

### 7.1 文档预处理

```python
def prepare_documents_for_vectorstore(raw_docs: list) -> list:
    """文档预处理流水线"""
    
    # 1. 清洗：去除无关内容
    cleaned_docs = clean_irrelevant_content(raw_docs)
    
    # 2. 分块：将长文档切成合适大小
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", "。", ".", " "],
    )
    chunks = splitter.split_documents(cleaned_docs)
    
    # 3. 添加元数据
    for chunk in chunks:
        chunk.metadata["chunk_id"] = hash(chunk.page_content)
        chunk.metadata["length"] = len(chunk.page_content)
    
    return chunks
```

### 7.2 常见性能问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| **检索结果不相关** | 查询词太短/模糊 | 使用查询扩展（HyDE 技术） |
| **结果重复度高** | 分块重叠或语义相似 | 使用 MMR 检索 |
| **检索速度慢** | 数据量太大 | 使用 FAISS 或索引优化 |
| **内存占用高** | 全量加载 | 分片存储或使用远程服务 |

---

## 八、本章总结

| 概念 | 一句话说明 |
|------|------------|
| **向量嵌入** | 将文本转为数值向量，语义相近的文本向量距离近 |
| **向量数据库** | 存储向量并支持相似度搜索 |
| **Chroma** | 轻量级向量库，适合学习和开发测试 |
| **相似度搜索** | 找到和查询最像的 K 个结果 |
| **MMR** | 找相关+多样化的结果 |
| **检索器** | 封装向量存储的统一检索接口 |
| **元数据过滤** | 按来源、日期等维度筛选检索范围 |

---

## 📝 课后练习

1. **✅ 基础**：使用 Chroma 创建一个包含 10 个文档的向量库，对 3 个不同查询进行检索
2. **💡 对比**：分别用 Chroma 和 FAISS 创建向量库，对比检索速度和精度
3. **🚀 进阶**：实现一个带元数据过滤的知识库，支持按"类别"和"日期"筛选
4. **🔍 探索**：使用 `similarity_search_with_relevance_scores` 观察不同查询的分数分布
