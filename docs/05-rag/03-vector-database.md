# 5.3 向量数据库实战 —— 从 Chroma 到生产级部署

## 📖 导读

> **向量数据库是 RAG 系统的"记忆库"。选择一个合适的向量数据库，直接决定了 RAG 系统的检索效率、维护成本和扩展能力。**

前面我们学习了向量嵌入和文档处理。现在我们要把这些"处理好的文档块"存入向量数据库，并实现高效的检索。本节将从**开发环境（Chroma）到生产环境（FAISS/Pinecone）**，带你全面掌握向量数据库的实战用法。

---

## 一、前置知识

| 概念 | 章节 | 说明 |
|------|------|------|
| Embedding | 3.3 | 文本→向量的转换 |
| 文档分块 | 5.2 | 将长文档切分为检索单元 |
| 余弦相似度 | 3.3 | 向量相似度的衡量方式 |

---

## 二、向量数据库选型对比

### 2.1 主流方案

| 数据库 | 部署方式 | 性能 | 易用性 | 成本 | 最佳场景 |
|--------|----------|------|--------|------|----------|
| **Chroma** | 本地嵌入 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 免费 | 开发测试、个人项目 |
| **FAISS** | 本地库 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 免费 | 大规模本地检索 |
| **Pinecone** | 云托管 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 按量付费 | 生产级、无需运维 |
| **Milvus** | 自托管 | ⭐⭐⭐⭐⭐ | ⭐⭐ | 自建成本 | 企业级大规模 |
| **Weaviate** | 自托管/云 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 按量付费 | 混合搜索需求 |
| **Qdrant** | 自托管/云 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 按量付费 | 高性能需求 |

### 2.2 如何选择？

```text
开发阶段？ 
→ Chroma（零配置，快速上手）

个人项目/低流量？
→ Chroma 或 FAISS（免费，够用）

生产环境／高并发？
→ Pinecone 或 Qdrant（托管，省心）

企业级／海量数据（千万级+）？
→ Milvus 或 Elasticsearch（分布式，可扩展）
```

---

## 三、Chroma 完全实战

### 3.1 安装

```bash
uv add chromadb
```

### 3.2 基础操作

```python
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

# 1. 初始化 Embedding
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# 2. 准备文档
documents = [
    Document(
        page_content="AI Agent 是一种能够自主感知环境的智能系统。",
        metadata={"source": "doc1", "page": 1}
    ),
    Document(
        page_content="LangChain 是一个构建 LLM 应用的框架。",
        metadata={"source": "doc2", "page": 2}
    ),
]

# 3. 创建向量存储（方式一：从文档创建）
vectorstore = Chroma.from_documents(
    documents=documents,
    embedding=embeddings,
    persist_directory="./chroma_db",  # 持久化目录
)

# 4. 创建向量存储（方式二：从已有集合加载）
vectorstore = Chroma(
    embedding_function=embeddings,
    persist_directory="./chroma_db",
)

# 5. 添加文档（增量）
vectorstore.add_documents([
    Document(
        page_content="向量数据库可以将文本转换为向量进行检索。",
        metadata={"source": "doc3", "page": 3}
    ),
])

# 6. 持久化到磁盘
vectorstore.persist()
```

### 3.3 检索操作

```python
# 1. 基础相似度搜索
results = vectorstore.similarity_search("什么是 AI Agent？", k=2)

# 2. 带分数（置信度）
results_with_score = vectorstore.similarity_search_with_relevance_scores(
    "什么是 AI Agent？", k=3
)
for doc, score in results_with_score:
    print(f"分数: {score:.3f} → {doc.page_content[:30]}...")

# 3. 通过向量直接搜索
query_vector = embeddings.embed_query("什么是 AI Agent？")
results = vectorstore.similarity_search_by_vector(query_vector, k=3)

# 4. MMR（最大边际相关性）
mmr_results = vectorstore.max_marginal_relevance_search(
    "什么是 AI Agent？",
    k=3,
    fetch_k=10,  # 候选数
    lambda_mult=0.5,  # 0=纯多样, 1=纯相关
)
```

### 3.4 高级功能

```python
# 1. 元数据过滤
filtered_results = vectorstore.similarity_search(
    "AI Agent",
    k=3,
    filter={"source": "doc1"},  # 只查 doc1
)

# 2. 复合过滤（Chroma 支持 $and/$or）
filtered_results = vectorstore.similarity_search(
    "AI Agent",
    k=3,
    filter={
        "$and": [
            {"source": {"$eq": "doc1"}},
            {"page": {"$gte": 1}},
        ]
    },
)

# 3. 批量检索
queries = ["AI Agent", "LangChain", "向量数据库"]
all_results = []
for q in queries:
    results = vectorstore.similarity_search(q, k=2)
    all_results.append(results)

# 4. 更新文档
vectorstore.update_document(
    document_id="doc1",
    document=Document(
        page_content="更新的内容...",
        metadata={"source": "doc1", "version": 2},
    ),
)

# 5. 删除文档
vectorstore.delete(["doc1", "doc2"])

# 6. 获取集合信息
collection = vectorstore._collection
print(f"文档数: {collection.count()}")
print(f"集合名: {collection.name}")
```

---

## 四、FAISS 实战

### 4.1 安装

```bash
uv add faiss-cpu  # CPU 版
# 或
uv add faiss-gpu  # GPU 版（需要 CUDA）
```

### 4.2 使用 FAISS

```python
from langchain_community.vectorstores import FAISS

# 创建索引
vectorstore = FAISS.from_documents(
    documents=documents,
    embedding=embeddings,
)

# 本地保存
vectorstore.save_local("./faiss_index")

# 加载索引（v0.2+ 需要 allow_dangerous_deserialization）
loaded_vectorstore = FAISS.load_local(
    "./faiss_index",
    embeddings,
    allow_dangerous_deserialization=True,
)

# 检索（API 与 Chroma 完全一致）
results = loaded_vectorstore.similarity_search("AI Agent", k=3)

# FAISS 特有的功能：合并索引
db1 = FAISS.from_documents(docs1, embeddings)
db2 = FAISS.from_documents(docs2, embeddings)

db1.merge_from(db2)  # 合并两个索引
```

### FAISS vs Chroma 性能对比

```python
import time

def benchmark_retrieval(vectorstore, queries, k=3):
    """检索性能基准测试"""
    times = []
    for q in queries:
        start = time.time()
        _ = vectorstore.similarity_search(q, k=k)
        times.append(time.time() - start)
    
    return {
        "avg_time_ms": sum(times) / len(times) * 1000,
        "min_time_ms": min(times) * 1000,
        "max_time_ms": max(times) * 1000,
    }
```

---

## 五、Pinecone（生产级云服务）

### 5.1 安装和初始化

```bash
pip install pinecone-client langchain-pinecone
```

```python
from langchain_pinecone import PineconeVectorStore
import pinecone

# 初始化 Pinecone
pinecone.init(
    api_key="your-api-key",
    environment="us-west1-gcp",
)

# 创建索引（只需执行一次）
index_name = "agent-guide"
if index_name not in pinecone.list_indexes():
    pinecone.create_index(
        name=index_name,
        dimension=1536,  # text-embedding-3-small 的维度
        metric="cosine",
    )

# 使用
vectorstore = PineconeVectorStore.from_documents(
    documents=documents,
    embedding=embeddings,
    index_name=index_name,
)

# 检索
results = vectorstore.similarity_search("AI Agent", k=3)
```

---

## 六、构建完整的 RAG 检索系统

```python
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough


class RAGSystem:
    """完整的 RAG 检索问答系统"""
    
    def __init__(self, persist_dir="./chroma_db"):
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
        self.vectorstore = self._init_vectorstore(persist_dir)
        self.retriever = self._init_retriever()
        self.chain = self._build_chain()
    
    def _init_vectorstore(self, persist_dir):
        """初始化或加载向量存储"""
        import os
        if os.path.exists(persist_dir):
            print(f"📦 从 {persist_dir} 加载已有向量库")
            return Chroma(
                embedding_function=self.embeddings,
                persist_directory=persist_dir,
            )
        else:
            print(f"🆕 创建新的向量库")
            return Chroma(
                embedding_function=self.embeddings,
                persist_directory=persist_dir,
            )
    
    def _init_retriever(self):
        """配置检索器"""
        return self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": 4,                    # 返回 4 个结果
                "score_threshold": 0.5,    # 仅返回 > 0.5 的结果
            },
        )
    
    def _build_chain(self):
        """构建 RAG 链"""
        template = """你是一个知识库问答助手。请基于以下信息回答问题。

参考信息：
{context}

问题：{question}

要求：
- 只基于参考信息回答
- 如果参考信息没有相关内容，请说"未找到相关信息"
- 引用信息来源（文件名）

回答："""
        
        prompt = ChatPromptTemplate.from_template(template)
        
        def format_docs(docs):
            """格式化检索结果"""
            formatted = []
            for i, doc in enumerate(docs, 1):
                source = doc.metadata.get("source", "未知来源")
                formatted.append(f"[来源 {i}: {source}]\n{doc.page_content}")
            return "\n\n".join(formatted)
        
        return (
            {
                "context": self.retriever | format_docs,
                "question": RunnablePassthrough(),
            }
            | prompt
            | self.llm
            | StrOutputParser()
        )
    
    def add_documents(self, documents):
        """添加文档到知识库"""
        self.vectorstore.add_documents(documents)
        self.vectorstore.persist()
        print(f"✅ 已添加 {len(documents)} 个文档")
    
    def query(self, question: str) -> str:
        """问答"""
        return self.chain.invoke(question)
    
    def query_with_sources(self, question: str) -> dict:
        """问答（含来源信息）"""
        # 获取检索结果
        docs = self.retriever.invoke(question)
        
        # 获取 LLM 回答
        answer = self.chain.invoke(question)
        
        return {
            "question": question,
            "answer": answer,
            "sources": [
                {
                    "content": d.page_content[:100] + "...",
                    "source": d.metadata.get("source", "未知"),
                    "score": getattr(d, "_score", None),
                }
                for d in docs
            ],
        }


# 使用
if __name__ == "__main__":
    rag = RAGSystem()
    
    # 添加文档
    rag.add_documents([
        Document(
            page_content="AI Agent 的核心能力包括感知、推理、行动和记忆。",
            metadata={"source": "agent_intro.md"},
        ),
        Document(
            page_content="RAG 是检索增强生成的缩写，用于提升 LLM 的回答质量。",
            metadata={"source": "rag_intro.md"},
        ),
    ])
    
    # 问答
    result = rag.query_with_sources("什么是 AI Agent？")
    print(f"\nQ: {result['question']}")
    print(f"A: {result['answer']}")
    print("\n📚 参考来源:")
    for s in result["sources"]:
        print(f"  - {s['source']}")
```

---

## 七、性能优化技巧

```python
# 1. 批量添加文档（避免频繁 persist）
def batch_add_documents(vectorstore, docs, batch_size=100):
    """批量添加文档"""
    for i in range(0, len(docs), batch_size):
        batch = docs[i:i + batch_size]
        vectorstore.add_documents(batch)
        print(f"  已添加 {i + len(batch)}/{len(docs)}")
    vectorstore.persist()

# 2. 使用异步检索
async def async_search(vectorstore, query):
    results = await vectorstore.asimilarity_search(query, k=3)
    return results

# 3. 限制检索范围（指定目录或类别）
def create_filtered_retriever(vectorstore, category: str):
    """创建只检索特定类别的检索器"""
    return vectorstore.as_retriever(
        search_kwargs={
            "k": 3,
            "filter": {"category": category},
        }
    )
```

---

## 八、常见问题

### ❌ 维度过高导致存储膨胀

```python
# text-embedding-3-small: 1536 维, 每个向量约 6KB
# 100 万个文档 → 约 6GB

# 优化：使用降维
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    dimensions=256,  # 支持降维（OpenAI 特有）
)
```

### ❌ 检索结果为空

```python
# 原因：查询和文档语义差异大
# 解决方案：使用查询扩展

def expand_query(query: str) -> list[str]:
    """生成多个查询变体"""
    variations = [
        query,
        f"什么是{query}",
        f"{query}的定义",
        f"{query}的应用",
    ]
    return variations
```

### ❌ 跨会话持久化

```python
# Chroma 默认是内存模式，程序重启后数据丢失
# 必须指定 persist_directory 并调用 persist()
vectorstore = Chroma.from_documents(
    documents=docs,
    embedding=embeddings,
    persist_directory="./persistent_db",  # 必须指定
)
vectorstore.persist()  # 保存到磁盘
```

---

## 九、本章总结

| 概念 | 说明 |
|------|------|
| **Chroma** | 开发首选，零配置，支持持久化 |
| **FAISS** | 高性能本地检索，适合大规模数据 |
| **Pinecone** | 生产级托管服务，无需运维 |
| **检索参数** | k（数量）、score_threshold（质量）、filter（过滤） |
| **优化** | 批量添加、异步检索、查询扩展 |

---

## 📝 课后练习

1. **✅ 基础**：使用 Chroma 创建一个包含 10 个文档的知识库，执行 3 次检索
2. **💡 对比**：分别用 Chroma 和 FAISS 存储同样的文档，对比检索速度和结果
3. **🚀 挑战**：实现一个带"元数据过滤"的知识库，让用户可以选择只检索某类文档
4. **🔍 探索**：使用 `similarity_search_with_relevance_scores` 观察不同查询的分数分布，找到合适的 score_threshold
