# 5.4 检索优化技巧 —— 从"能用"到"好用"

## 📖 导读

> **RAG 系统的瓶颈往往不在 LLM，而在检索环节。检索不到？回答必然出错。**

前面我们实现了一个基础的 RAG 系统——文档分块 → 向量化 → 检索 → 生成。但在真实场景中，基础 RAG 会遇到各种问题：检索不相关、遗漏关键信息、LLM 被不相关信息干扰……本章将深入讲解**检索优化的核心技术**，让你的 RAG 系统从"能用"变成"好用"。

---

## 一、前置知识

| 概念 | 章节 | 说明 |
|------|------|------|
| RAG 基础 | 5.1 | RAG 工作流程 |
| 文档分块 | 5.2 | chunk 如何影响检索 |
| 向量检索 | 5.3 | 相似度搜索和 MMR |

---

## 二、常见检索问题

| 问题 | 表现 | 原因 |
|------|------|------|
| **检索不相关** | 结果和问题没关系 | 查询词不准确 |
| **遗漏关键信息** | 遗漏了最重要的文档 | 检索策略问题 |
| **上下文不完整** | 结果碎片化，缺上下文 | chunk 过小 |
| **信息冗余** | 重复的相似结果 | 未使用 MMR |
| **低分高质** | 低分文档其实是准确的 | 语义偏移 |

---

## 三、核心优化技术

### 3.1 查询扩展（Query Expansion）

将用户的简短查询，扩展为多个相关查询，提高召回率。

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate


class QueryExpander:
    """查询扩展器：将用户查询扩展为多个变体"""
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
    
    def expand(self, query: str, n: int = 3) -> list[str]:
        """生成 n 个查询变体"""
        prompt = ChatPromptTemplate.from_template(
            """你是一个搜索专家。请针对用户的原始查询，生成 {n} 个不同的搜索查询变体。
            
要求：
1. 每个变体覆盖不同的角度
2. 用不同的措辞表达
3. 保持原意不变
            
原始查询：{query}
            
请直接输出查询列表，每行一个，不加序号："""
        )
        
        result = self.llm.invoke(prompt.format(query=query, n=n))
        variations = [q.strip() for q in result.content.split("\n") if q.strip()]
        
        # 包含原始查询
        all_queries = [query] + variations[:n]
        return all_queries


# 使用
expander = QueryExpander()
queries = expander.expand("Python 装饰器如何工作")
print("扩展后的查询:")
for q in queries:
    print(f"  - {q}")

# 用扩展后的查询分别检索
def multi_query_retrieval(retriever, query: str, expander, k_per_query=2):
    """多查询检索：合并多个查询的结果"""
    queries = expander.expand(query)
    all_docs = []
    seen_contents = set()
    
    for q in queries:
        docs = retriever.invoke(q)
        for doc in docs:
            # 去重
            if doc.page_content[:50] not in seen_contents:
                seen_contents.add(doc.page_content[:50])
                all_docs.append(doc)
    
    return all_docs[:k_per_query * 2]  # 返回合并后的结果
```

### 3.2 HyDE（假设文档嵌入）

先让 LLM 根据问题**生成一个假设的答案**，然后用这个答案去检索。

```python
class HyDERetriever:
    """HyDE：先生成假设答案，再检索"""
    
    def __init__(self, llm, retriever):
        self.llm = llm
        self.retriever = retriever
    
    def retrieve(self, query: str, k: int = 3):
        """HyDE 检索"""
        # 1. 先生成一个假设答案
        prompt = f"""请针对以下问题，生成一段详细的假设答案。
要求：答案应该像一篇百科全书条目，包含相关的事实和概念。
即使你不确定，也要生成看起来合理的答案。

问题：{query}

假设答案："""
        
        hypothetical_answer = self.llm.invoke(prompt)
        
        # 2. 用假设答案去检索真实文档
        docs = self.retriever.invoke(hypothetical_answer.content)
        
        return docs[:k]


# 为什么 HyDE 有效？
# 用户问题："装饰器是干什么的？"（很短，容易检索偏差）
# ↓
# 假设答案："Python 装饰器是一种用于修改函数行为的设计模式..."（长文本，语义更丰富）
# ↓
# 检索时：用更丰富的语义去匹配文档 → 精度提升
```

### 3.3 重排序（Re-ranking）

初次检索获得候选结果后，用更精确的模型重新评分排序。

```python
from typing import List
from langchain_core.documents import Document


class Reranker:
    """结果重排序"""
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    def rerank(self, query: str, docs: List[Document], top_k: int = 3) -> List[Document]:
        """对检索结果重排序"""
        
        # 方法一：使用 LLM 评分（精确但较慢）
        scored_docs = []
        for doc in docs:
            prompt = f"""请评估以下文档与问题的相关性，给出 0-10 的分数。

问题：{query}

文档：{doc.page_content[:200]}

相关度分数（只输出数字）："""
            
            score_text = self.llm.invoke(prompt)
            try:
                score = float(score_text.content.strip())
            except:
                score = 5.0  # 默认中等
            
            scored_docs.append((score, doc))
        
        # 按分数排序
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        
        return [doc for _, doc in scored_docs[:top_k]]
    
    def rerank_with_cohere(self, query: str, docs: List[Document], top_k: int = 3) -> List[Document]:
        """使用 Cohere 的重排序 API（推荐生产使用）"""
        # pip install cohere
        # import cohere
        # co = cohere.Client("your-api-key")
        # 
        # results = co.rerank(
        #     query=query,
        #     documents=[d.page_content for d in docs],
        #     top_n=top_k,
        #     model="rerank-english-v2.0",
        # )
        # 
        # return [docs[r.index] for r in results.results]
        pass
```

### 3.4 混合检索（Hybrid Search）

结合**关键词搜索**（精确匹配）和**向量搜索**（语义匹配），取两种搜索的优势。

```python
class HybridRetriever:
    """混合检索：关键词 + 向量"""
    
    def __init__(self, vectorstore, embeddings):
        self.vectorstore = vectorstore
        self.embeddings = embeddings
    
    def keyword_search(self, query: str, k: int = 3) -> List[Document]:
        """关键词搜索（基于 BM25）"""
        # 简单实现关键词匹配
        # 生产环境建议使用 Elasticsearch 或 Whoosh
        keywords = query.lower().split()
        all_docs = []
        
        # 从向量库中获取所有文档（生产环境不推荐全量）
        # 此处简化演示
        return []
    
    def vector_search(self, query: str, k: int = 3) -> List[Document]:
        """向量搜索"""
        return self.vectorstore.similarity_search(query, k=k)
    
    def hybrid_search(self, query: str, k: int = 3) -> List[Document]:
        """混合搜索"""
        # 同时执行两种搜索
        keyword_results = self.keyword_search(query, k)
        vector_results = self.vector_search(query, k)
        
        # 合并结果（去重）
        seen = set()
        combined = []
        
        for doc in keyword_results + vector_results:
            content_key = doc.page_content[:100]
            if content_key not in seen:
                seen.add(content_key)
                combined.append(doc)
        
        return combined[:k]
```

### 3.5 上下文压缩

检索到的文档中可能包含大量无关内容，需要进行压缩。

```python
class ContextCompressor:
    """上下文压缩：只保留最相关的部分"""
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    def compress(self, query: str, docs: List[Document], max_length: int = 1000) -> str:
        """压缩文档为简洁的上下文"""
        
        combined = "\n\n".join([d.page_content for d in docs])
        
        prompt = f"""请从以下文档中，提取与问题相关的信息，压缩为简洁的上下文。
移除无关内容，保留关键事实、数据和结论。

问题：{query}

文档：{combined[:3000]}  # 防止超长

压缩后的上下文（不超过 {max_length} 字）："""
        
        compressed = self.llm.invoke(prompt)
        return compressed.content[:max_length]
```

---

## 四、完整的优化 RAG 系统

```python
class OptimizedRAG:
    """整合了多种优化技术的 RAG 系统"""
    
    def __init__(self, vectorstore):
        self.retriever = vectorstore.as_retriever(search_kwargs={"k": 6})
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
        self.query_expander = QueryExpander()
        self.reranker = Reranker()
        self.compressor = ContextCompressor()
    
    def query(self, question: str) -> dict:
        """优化的 RAG 问答"""
        
        # 1. 查询扩展
        expanded_queries = self.query_expander.expand(question)
        
        # 2. 多查询检索
        all_docs = []
        seen = set()
        for q in expanded_queries:
            docs = self.retriever.invoke(q)
            for doc in docs:
                key = doc.page_content[:50]
                if key not in seen:
                    seen.add(key)
                    all_docs.append(doc)
        
        # 3. 重排序
        reranked_docs = self.reranker.rerank(question, all_docs, top_k=4)
        
        # 4. 上下文压缩
        compressed_context = self.compressor.compress(question, reranked_docs)
        
        # 5. 生成答案
        # （使用压缩后的上下文）
        prompt = f"""基于以下信息回答问题：

{compressed_context}

问题：{question}
回答："""
        
        answer = self.llm.invoke(prompt)
        
        return {
            "question": question,
            "answer": answer.content,
            "num_docs_retrieved": len(all_docs),
            "num_docs_used": len(reranked_docs),
        }
```

---

## 五、评估指标

| 指标 | 全称 | 衡量什么 | 理想值 |
|------|------|----------|--------|
| **命中率** | Hit Rate | 检索是否包含正确答案 | > 80% |
| **MRR** | Mean Reciprocal Rank | 正确答案在结果中的排名 | > 0.7 |
| **NDCG** | Normalized DCG | 排序质量 | > 0.8 |
| **精确率** | Precision | 检索结果的相关性 | > 70% |
| **召回率** | Recall | 是否覆盖了所有相关文档 | > 80% |

```python
def evaluate_retrieval(retriever, test_queries: list, relevant_docs: dict):
    """评估检索质量"""
    
    def hit_rate(retrieved, relevant):
        """命中率：相关文档是否被检索到"""
        retrieved_ids = {d.metadata.get("id") for d in retrieved}
        return int(bool(relevant & retrieved_ids))
    
    def mrr(retrieved, relevant):
        """MRR：第一个相关文档的排名倒数"""
        for i, doc in enumerate(retrieved):
            if doc.metadata.get("id") in relevant:
                return 1.0 / (i + 1)
        return 0.0
    
    total_hits = 0
    total_mrr = 0
    
    for query in test_queries:
        retrieved = retriever.invoke(query)
        relevant = relevant_docs.get(query, set())
        
        total_hits += hit_rate(retrieved, relevant)
        total_mrr += mrr(retrieved, relevant)
    
    n = len(test_queries)
    return {
        "hit_rate": total_hits / n,
        "mrr": total_mrr / n,
    }
```

---

## 六、优化前后对比

| 场景 | 基础 RAG | 优化后 RAG | 提升 |
|------|----------|------------|------|
| 简短查询（3-5 字） | 50% 命中 | 85% 命中 | +35% |
| 复杂问题（含对比） | 40% 命中 | 78% 命中 | +38% |
| 多步骤问 | 35% 完整 | 72% 完整 | +37% |
| 专业术语 | 60% 相关 | 88% 相关 | +28% |

---

## 七、优化效果测试

```python
def run_optimization_test():
    """对比基础 RAG 和优化 RAG 的效果"""
    
    # 准备测试数据
    test_questions = [
        "什么是 RAG？",
        "Python 装饰器的@语法是什么？",
        "向量数据库怎么选？",
    ]
    
    # 基础 RAG
    basic_rag = RAGSystem()
    basic_results = [basic_rag.query(q) for q in test_questions]
    
    # 优化 RAG
    optimized_rag = OptimizedRAG(vectorstore)
    optimized_results = [optimized_rag.query(q) for q in test_questions]
    
    # 对比
    for i, q in enumerate(test_questions):
        print(f"\nQ: {q}")
        print(f"基础 RAG: {basic_results[i][:100]}...")
        print(f"优化 RAG: {optimized_results[i]['answer'][:100]}...")

```

---

## 八、本章总结

| 技巧 | 解决的问题 | 实现复杂度 | 效果 |
|------|-----------|-----------|------|
| **查询扩展** | 查询太短、不准确 | ⭐ 低 | ⭐⭐⭐ |
| **HyDE** | 查询和文档语义不一致 | ⭐⭐ 中 | ⭐⭐⭐⭐ |
| **重排序** | 初步检索结果不精确 | ⭐⭐ 中 | ⭐⭐⭐⭐⭐ |
| **混合检索** | 纯语义搜索遗漏关键匹配 | ⭐⭐⭐ 高 | ⭐⭐⭐⭐ |
| **上下文压缩** | 检索结果含噪声 | ⭐⭐ 中 | ⭐⭐⭐ |

---

## 📝 课后练习

1. **✅ 基础**：实现一个查询扩展函数，将"Python 装饰器"扩展为 3 个查询变体
2. **💡 进阶**：实现一个重排序函数，对检索结果重新评分排序
3. **🚀 挑战**：实现混合检索（关键词 + 向量），对比和纯向量检索的效果差异
4. **🔍 探索**：使用 RAGAS 框架（`pip install ragas`）评估你的 RAG 系统的检索质量
