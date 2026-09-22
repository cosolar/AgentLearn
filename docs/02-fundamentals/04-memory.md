# 2.4 记忆机制 —— 让 Agent 拥有"记性"

## 📖 导读

> **一个没有记忆的 Agent，就像一个人面对你说过的每句话都当作第一次听到。**

记忆是 Agent 从"工具"进化为"伙伴"的关键能力。有了记忆，Agent 才能**记住用户说过的话、记住之前任务的结果、持续优化自己的行为**。本文将从记忆的底层原理讲到 2026 年的工程实现，带你建立完整的记忆体系认知。

> 🆕 **2026 版更新**：旧的 `langchain.memory`（`ConversationBufferMemory` 等）已在 **LangChain v1** 中迁至 [`langchain-classic`](https://pypi.org/project/langchain-classic/)。本教程改用 **LangGraph 的 `checkpointer` / `store`** 与 **LangChain v1 中间件**来构建记忆，这也是当前的生产级做法。

---

## 一、前置知识

| 概念 | 说明 |
|------|------|
| **LLM 的无状态性** | 每次调用都是独立的，模型本身不保留任何对话 |
| **Context Window** | 一次能处理的最大 token 数（GPT-5.x 约 128K–400K） |
| **Token 成本** | 每次调用按输入/输出 token 计费，历史越长越贵 |
| **消息类型** | `SystemMessage` / `HumanMessage` / `AIMessage` / `ToolMessage` |
| **Checkpointer** | 保存 Agent 图状态的持久化组件（会话级记忆） |
| **Store** | 跨会话的长期键值存储（长期记忆） |

---

## 二、为什么需要记忆？

### 2.1 没有记忆 vs 有记忆

```text
❌ 没有记忆：
用户：我叫小明
Agent：好的

用户：我刚才说了我叫什么？
Agent：我不记得了 ❌（每次调用都是全新的）

✅ 有记忆：
用户：我叫小明
Agent：好的，小明

用户：我刚才说了我叫什么？
Agent：你叫小明 ✅
```

### 2.2 记忆为 Agent 带来的核心能力

| 能力 | 说明 | 价值 |
|------|------|------|
| **上下文连贯** | 能跟上多轮对话 | 自然的人机交互 |
| **用户画像** | 记住用户的偏好、习惯 | 个性化服务 |
| **任务跟踪** | 记住当前任务的进度 | 断点续执行 |
| **知识积累** | 跨会话记住学到的知识 | 持续进化 |
| **错误学习** | 记住之前的错误，避免重复 | 自愈能力 |

---

## 三、记忆的分类体系

在工程上，记忆通常按"**存多久 + 存哪里**"分为三类：

| 类型 | 生命周期 | 典型载体 | 用途 |
|------|----------|----------|------|
| **工作记忆（Working）** | 单次任务内 | 图状态 / 变量 | 当前任务的中间结果 |
| **短期记忆（Short-term）** | 单个会话内 | 消息列表 + checkpointer | 多轮对话上下文 |
| **长期记忆（Long-term）** | 跨会话、长期 | 向量库 / KV store / 记忆框架 | 用户画像、经验沉淀 |

```
┌──────────────────────────────────────────────────────┐
│  长期记忆 (Store / 向量库 / Mem0 · Letta · Zep)        │  跨会话
├──────────────────────────────────────────────────────┤
│  短期记忆 (消息列表 + Checkpointer)                    │  单个会话
├──────────────────────────────────────────────────────┤
│  工作记忆 (当前图状态 / 中间变量)                       │  单次任务
└──────────────────────────────────────────────────────┘
```

---

## 四、短期记忆：会话内的上下文

### 4.1 最朴素的实现：消息列表

LLM 无状态，所谓"记忆"其实是我们**每次把历史消息重新传进去**：

```python
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

messages = [SystemMessage(content="你是一个友好的助手。")]

def chat(user_input: str) -> str:
    messages.append(HumanMessage(content=user_input))
    reply = llm.invoke(messages)   # 每次带上完整历史
    messages.append(reply)
    return reply.content
```

**优点**：实现简单、100% 准确。  
**缺点**：对话越长，token 消耗越大（成本线性增长），最终撑爆上下文窗口。

### 4.2 控制长度：`trim_messages`

LangChain 提供了按 **token / 消息条数** 裁剪上下文的工具：

```python
from langchain_core.messages import trim_messages, HumanMessage

messages = [...]  # 很长的历史

# 只保留最近、且总量不超过 max_tokens 的消息
trimmed = trim_messages(
    messages,
    max_tokens=2000,
    strategy="last",          # 从最新的开始保留
    token_counter=llm,        # 用模型自带的计数器精确计数
    include_system=True,      # 保留 SystemMessage
)
```

### 4.3 生产级做法：LangGraph Checkpointer

`trim_messages` 仍需自己管理列表。**LangGraph 的 `checkpointer` 能自动持久化每一步的对话状态**，并支持断点恢复、时间旅行：

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import create_react_agent   # 或用 langchain 的 create_agent

# 开发用内存版；生产可换 Postgres / SQLite
checkpointer = SqliteSaver.from_conn_string("checkpoints.db")

agent = create_react_agent(
    model="gpt-5.5",
    tools=[],
    checkpointer=checkpointer,
)

# 用 thread_id 区分不同会话
config = {"configurable": {"thread_id": "user-001"}}

agent.invoke({"messages": [HumanMessage("我叫小明")]}, config)
result = agent.invoke({"messages": [HumanMessage("我叫什么？")]}, config)
print(result["messages"][-1].content)   # → 你叫小明
```

| 记忆载体 | 适用场景 | 持久化 |
|----------|----------|--------|
| `InMemorySaver` | 本地开发、单进程 | ❌ 重启即丢 |
| `SqliteSaver` | 单机、中小规模 | ✅ 文件 |
| `PostgresSaver` | 生产、多实例 | ✅ 数据库 |
| `AsyncPostgresSaver` | 异步高并发生产 | ✅ 数据库 |

> 📌 Checkpointer 的完整用法见 [2.2 状态管理与节点](../04-langgraph/02-state-nodes.md)。

### 4.4 自动摘要压缩：SummarizationMiddleware

当历史过长时，与其粗暴截断，不如**让模型自动摘要**。LangChain v1 内置了 `SummarizationMiddleware`：

```python
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware

agent = create_agent(
    model="gpt-5.5",
    tools=[],
    middleware=[
        # 当上下文超过 4000 token 时，自动把历史压缩成摘要
        SummarizationMiddleware(trigger={"tokens": 4000}),
    ],
)
```

**工作原理**：

```
原始对话（1000 tokens）→ 摘要（100 tokens）
↓
下次对话：摘要 + 最新消息（150 tokens）
↓
再摘要 → 持续迭代，token 稳定在低位
```

---

## 五、长期记忆：跨会话的知识沉淀

### 5.1 向量记忆（语义召回）

把重要信息存入向量库，需要时按语义检索回来：

```python
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

vectorstore = Chroma(
    collection_name="long_term_memory",
    embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"),
    persist_directory="./memory_db",
)

# 写入记忆
vectorstore.add_documents([
    Document(page_content="用户叫小明，北京人，喜欢 Python 和咖啡。")
])

# 语义召回：问"用户来自哪"也能命中
hits = vectorstore.similarity_search("用户的家乡在哪里？", k=2)
```

### 5.2 LangGraph Store（跨会话长期记忆）

`store` 是 LangGraph 提供的**跨线程（跨会话）**键值存储，天然适合用户画像：

```python
from langgraph.store.memory import InMemoryStore
from langgraph.prebuilt import create_react_agent

store = InMemoryStore()

agent = create_react_agent(
    model="gpt-5.5",
    tools=[],
    store=store,
)

# 不同 thread_id（会话）共享同一个 namespace 下的长期记忆
config = {"configurable": {"user_id": "u-001"}}
```

> 💡 `checkpointer` 管**会话内**，`store` 管**跨会话**，二者可以组合使用。

### 5.3 专用记忆框架（2026 生态）

当长期记忆需求变复杂（抽取、去重、遗忘、图谱化），可以引入专门的记忆层：

| 框架 | 特点 | 适合 |
|------|------|------|
| **Mem0** | 开箱即用，自动抽取/更新用户记忆，支持向量+图 | 通用个性化 Agent |
| **Letta**（原 MemGPT） | 把记忆当作"操作系统"分页管理 | 长时自主 Agent |
| **Zep** | 时序知识图谱，专注对话记忆 | 客服/助手类 |
| **LangMem** | LangChain 官方记忆 SDK，与 LangGraph 无缝集成 | LangChain 技术栈 |

```python
# 以 Mem0 为例（示意）
from mem0 import Memory

m = Memory()
m.add("我喜欢喝美式咖啡", user_id="u-001")          # 写入
hits = m.search("用户喜欢喝什么？", user_id="u-001")  # 召回
```

### 5.4 模型原生记忆工具

2026 年，主流模型厂商也开始提供**原生记忆能力**。例如 Anthropic 的 Claude 提供了 memory tool，允许模型在客户端读写 `/memories` 目录，把"记忆"变成模型可以直接操作的工具，而不是纯靠提示词拼接。

---

## 六、记忆类型对比总结

| 类型 | 存储方式 | 检索方式 | Token 消耗 | 适合场景 |
|------|----------|----------|-----------|----------|
| **完整消息列表** | 内存中的 messages | 全量传入 | 高（线性增长） | 短对话 |
| **截断/窗口** | 最近 N 条/条数上限 | 截取最新 | 可控 | 客服、常规对话 |
| **摘要压缩** | 模型生成的摘要 | 读取摘要 | 中（稳定） | 长对话 |
| **向量长期记忆** | 向量数据库 | 语义搜索 | 低（按需） | 跨会话、海量记忆 |
| **记忆框架** | 向量 + 图 + KV | 混合检索 | 低 | 复杂个性化 |

---

## 七、实战：构建带记忆的对话 Agent

### 7.1 用 LangGraph Checkpointer 实现会话记忆

```python
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage

checkpointer = InMemorySaver()

agent = create_agent(
    model="gpt-5.5",
    tools=[],
    system_prompt="你是一个友好的 AI 助手，记住用户说过的重要信息。",
    checkpointer=checkpointer,
)

def chat(session_id: str, text: str) -> str:
    config = {"configurable": {"thread_id": session_id}}
    result = agent.invoke(
        {"messages": [HumanMessage(content=text)]},
        config,
    )
    return result["messages"][-1].content

print(chat("s1", "你好，我叫小明"))          # → 你好，小明！
print(chat("s1", "我喜欢喝美式咖啡"))        # → 记住了
print(chat("s1", "我叫什么？喜欢喝什么？"))  # → 你叫小明，喜欢美式咖啡
print(chat("s2", "我叫什么？"))              # → 新会话，不知道
```

> ✅ 同一个 `thread_id` = 同一个会话，跨调用自动保持记忆；不同 `thread_id` 之间互不干扰。

### 7.2 记忆管理最佳实践

```python
class MemoryManager:
    """一个简单的记忆分层管理器（示意）"""

    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens
        self.short_term: list = []   # 会话内消息
        self.long_term: dict = {}    # 跨会话关键信息

    def add(self, message):
        self.short_term.append(message)
        self._prune_if_needed()

    def remember(self, key: str, value: str):
        """沉淀长期记忆（真实项目应写入向量库/Store）"""
        self.long_term[key] = value

    def _prune_if_needed(self):
        # 用 trim_messages 做精确裁剪
        from langchain_core.messages import trim_messages
        self.short_term = trim_messages(
            self.short_term, max_tokens=self.max_tokens, strategy="last"
        )
```

**实践清单**：

1. **分层**：工作记忆 ≠ 短期记忆 ≠ 长期记忆，分别存储；
2. **裁剪**：始终用 `trim_messages` 控制上下文；
3. **摘要**：长对话用 `SummarizationMiddleware` 自动压缩；
4. **持久化**：生产环境把 checkpointer 换成 Postgres；
5. **隔离**：按 `thread_id` / `user_id` 隔离，防止串记忆；
6. **可遗忘**：提供删除/过期机制，尊重用户隐私。

---

## 八、常见问题与排查

### ❌ 记忆丢失（重启后消失）

```python
# 原因：使用了 InMemorySaver / InMemoryStore
# 解决：生产环境换成持久化后端
from langgraph.checkpoint.postgres import PostgresSaver

with PostgresSaver.from_conn_string("postgresql://...") as checkpointer:
    checkpointer.setup()
    agent = create_agent(model="gpt-5.5", tools=[], checkpointer=checkpointer)
```

### ❌ Token 超限（上下文溢出）

```python
# 解决：裁剪 + 摘要双保险
trimmed = trim_messages(messages, max_tokens=3000, strategy="last")
# 并配置 SummarizationMiddleware(trigger={"tokens": 4000})
```

### ❌ 记忆混淆（多用户串记忆）

```python
# 原因：所有用户共用一个 thread_id
# 解决：用 session_id / user_id 隔离
config = {"configurable": {"thread_id": f"user-{user_id}"}}
```

### ❌ 记忆污染（记错/记串）

- 长期记忆写入前做**去重与冲突检测**；
- 给记忆条目加**时间戳与来源**，检索时优先近期；
- 引入**人工审核**处理敏感记忆（可用 `HumanInTheLoopMiddleware`）。

---

## 九、本章总结

| 知识点 | 一句话说明 |
|--------|------------|
| **记忆的本质** | LLM 无状态，记忆靠"把历史重新喂回去" |
| **短期记忆** | 消息列表 + `checkpointer`，会话内保持连贯 |
| **上下文裁剪** | `trim_messages` 控制 token，避免溢出 |
| **摘要压缩** | `SummarizationMiddleware` 自动压缩长历史 |
| **长期记忆** | 向量库 / LangGraph `store` / Mem0 等框架 |
| **隔离与持久化** | 用 thread_id 隔离，生产用数据库后端 |

---

## 📝 课后练习

1. **✅ 基础**：用 `InMemorySaver` + `create_agent` 实现一个带会话记忆的聊天 Agent，运行多轮对话验证记忆生效
2. **💡 对比**：分别用"完整列表"、"`trim_messages` 裁剪"、"`SummarizationMiddleware` 摘要"三种方式实现长对话，对比回答质量与 token 消耗
3. **🚀 挑战**：实现"关键信息提取"——在对话中自动抽取用户的姓名、偏好，用 LangGraph `store` 或向量库沉淀为长期记忆，并在后续会话中正确使用
4. **🔍 探索**：调研 Mem0 / Letta / Zep / LangMem 四个记忆框架的差异，写出你的选型结论
