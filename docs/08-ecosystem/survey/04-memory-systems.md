# 8.4 记忆系统全景

## 📖 本章目标

- 了解不同类型的记忆系统及其关系
- 掌握向量数据库的选择策略
- 学会设计层级记忆架构

---

## 记忆系统分层架构

> 第 2.4 章学习了记忆的基础概念（短期/长期），第 3.3 章和 5.3 章学了向量存储。本章将这些整合到完整的记忆体系。

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent 记忆体系                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  1. 工作记忆 (Working Memory)                        │   │
│  │  • 当前对话上下文                                     │   │
│  │  • 内存中存储，容量有限                               │   │
│  │  • 对应：LangChain ChatMessageHistory                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                            │                                 │
│                            ▼                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  2. 短期记忆 (Short-term Memory)                     │   │
│  │  • 最近对话摘要/关键信息                              │   │
│  │  • 滑动窗口/摘要策略                                  │   │
│  │  • 对应：LangChain ConversationSummaryMemory          │   │
│  └──────────────────────────────────────────────────────┘   │
│                            │                                 │
│                            ▼                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  3. 长期记忆 (Long-term Memory)                      │   │
│  │  • 跨会话持久化存储                                   │   │
│  │  • 向量数据库 / 知识图谱                              │   │
│  │  • 对应：Chroma / Milvus / Neo4j                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                            │                                 │
│                            ▼                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  4. 全局记忆 (Global/Episodic Memory)                │   │
│  │  • Agent 学习到的通用知识                             │   │
│  │  • 技能/经验/偏好                                     │   │
│  │  • 高级特性：Hermes MemoryBank 三层系统                │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 向量数据库选型对比

> 第 5.3 章使用了 Chroma，这里是完整的选型参考。

| 数据库 | 类型 | 规模 | 部署 | 速度 | 特点 |
|--------|------|------|------|------|------|
| **Chroma** | 嵌入式 | 百万级 | 本地 | 快 | 零依赖，开发首选 |
| **FAISS** | 库 | 百万级 | 本地 | 极快 | 仅检索，无存储 |
| **Qdrant** | 服务 | 千万级 | Docker | 快 | Rust 实现，性能好 |
| **Milvus** | 分布式 | 十亿级 | K8s | 中 | 存储计算分离 |
| **Pinecone** | 云服务 | 十亿级 | SaaS | 快 | 托管，按量付费 |
| **Weaviate** | 服务 | 千万级 | Docker | 快 | 自带推理模块 |

**选型建议：**

```
开发/学习 → Chroma（最简单）
个人项目 → Qdrant（Docker 一键部署）
小团队 → Weaviate（自带推理，功能丰富）
企业级 → Milvus（十亿级扩展）
云服务 → Pinecone（零运维）
```

---

## 高级记忆架构

### MemoryBank — 三层记忆系统

受人类记忆机制启发，Hermes Agent 的 MemoryBank 实现：

```python
class MemoryBank:
    def __init__(self):
        self.working_memory = []       # 工作记忆：当前对话
        self.short_term = []           # 短期记忆：最近 N 轮
        self.long_term = VectorStore()  # 长期记忆：向量存储
        
    def add(self, experience: dict):
        """添加经验到记忆"""
        self.working_memory.append(experience)
        
        # 工作记忆 → 短期记忆
        if len(self.working_memory) > 10:
            self._consolidate_to_short_term()
        
        # 短期记忆 → 长期记忆（重要事件）
        if self._is_important(experience):
            self._consolidate_to_long_term(experience)
    
    def retrieve(self, query: str, k: int = 5) -> list:
        """按相关性检索记忆"""
        # 先查工作记忆
        working_results = self._search_working(query)
        
        # 再查短期记忆（最近上下文）
        short_results = self._search_short_term(query)
        
        # 最后查长期记忆（语义检索）
        long_results = self.long_term.similarity_search(query, k=k)
        
        # 合并排序
        return self._merge_results(working_results, short_results, long_results)
```

### Neo4j 图记忆 — 关系推理

对于知识密集型任务，图结构记忆比向量检索更适合：

```python
from neo4j import GraphDatabase
from langchain_community.graphs import Neo4jGraph

# 创建知识图谱
graph = Neo4jGraph(url="bolt://localhost:7687", username="neo4j", password="password")

# 存储实体关系
graph.query("""
    CREATE (a:Person {name: $name, birthday: $birthday})
    CREATE (b:Company {name: $company})
    CREATE (a)-[:WORKS_AT {since: $since}]->(b)
""", params={"name": "张三", "birthday": "1990-01-01", "company": "ABC Corp", "since": "2020"})

# 关系推理查询
result = graph.query("""
    MATCH (p:Person)-[:WORKS_AT]->(c:Company)
    WHERE c.name = $company
    RETURN p.name, p.birthday
""", params={"company": "ABC Corp"})
```

---

## 记忆优化策略

### 1. 分层缓存

```
查询 → 先查工作记忆（O(1)）→ 命中？→ 返回
                          ↓ 未命中
                  查短期记忆（O(n)）→ 命中？→ 返回
                          ↓ 未命中
                  查长期记忆（O(log n)）→ 返回
```

### 2. 遗忘机制

```python
def forget_old_memories(memories, max_age_days=30, max_count=1000):
    """定期清理过时记忆"""
    now = datetime.now()
    # 按时间衰减
    filtered = [m for m in memories 
                if (now - m.timestamp).days < max_age_days]
    # 按重要性保留 Top-K
    sorted_memories = sorted(filtered, key=lambda m: m.importance)
    return sorted_memories[:max_count]
```

### 3. 记忆压缩

```python
def compress_memory(memories, llm):
    """用 LLM 压缩相似记忆"""
    prompt = f"将以下记忆合并为简洁摘要：\n{memories}"
    summary = llm.invoke(prompt)
    return summary
```

---

## 记忆系统选型指南

| 场景 | 推荐方案 | 理由 |
|------|---------|------|
| 简单对话 | LangChain ChatMessageHistory | 内存存储，够用 |
| 客服系统 | Chroma + 短期摘要 | 快速检索常见问题 |
| 个人助手 | MemoryBank 三层架构 | 长期学习用户偏好 |
| 知识库问答 | Milvus + RAG | 海量文档检索 |
| 金融分析 | Neo4j 图记忆 | 实体关系推理 |
| 医疗诊断 | 混合：向量 + 图 + 规则 | 多维度知识 |

---

## 本章小结

| 要点 | 说明 |
|------|------|
| 🧠 | 记忆分四层：工作 → 短期 → 长期 → 全局 |
| 🗄️ | Chroma 开发最快，Milvus 最大规模 |
| 🔗 | 图记忆适合关系推理 |
| ⚡ | 分层缓存 + 遗忘机制提高性能 |

---

## 📝 课后练习

1. **实践题**：将项目中的简单记忆替换为 MemoryBank 三层架构
2. **对比题**：用 Chroma 和 Qdrant 分别实现同一条 RAG 链路，对比速度
3. **设计题**：设计一个 "Agent 学习用户偏好" 的记忆系统，至少包含三层

