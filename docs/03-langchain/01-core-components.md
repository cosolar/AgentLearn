# 3.1 LangChain v1 核心组件 —— 框架全景与组件详解

## 📖 导读

LangChain 是当前最流行的 LLM 应用开发框架，也是构建 AI Agent 最常用的基础设施。**它不是一个大而全的"黑盒"，而是一组精心设计的可组合模块。**

> 🆕 **2026 版重点**：**LangChain v1** 已于 2025 年 10 月正式 GA（与 LangGraph v1 同步），带来了三大变化：
> 1. **`create_agent`** —— 统一的、标准的 Agent 构建方式（取代 `create_react_agent`）；
> 2. **标准内容块（content blocks）** —— 跨厂商统一访问推理轨迹、引用、内置工具；
> 3. **简化命名空间** —— `langchain` 只保留核心构建块，旧功能迁往 `langchain-classic`。
>
> 本章将围绕这三条主线，带你建立对 LangChain v1 的完整认知。

---

## 一、前置知识

学习本章前，建议你已完成：

- ✅ 环境搭建（第 1.2 节）
- ✅ 第一个 Agent（第 1.3 节）
- ✅ Prompt 与上下文工程（第 2.1 节）
- ✅ Chain 模式（第 2.2 节）

---

## 二、LangChain v1 架构全景

### 2.1 整体架构

LangChain v1 的定位从"大而全的工具箱"收窄为**"聚焦、可用于生产的 Agent 构建基础"**：

```
┌──────────────────────────────────────────────────────────────────┐
│                    LangChain v1（聚焦的 Agent 基础）               │
│                                                                   │
│  ┌────────────────────┐   ┌───────────────────────────────────┐  │
│  │  langchain.agents  │   │  Middleware（中间件 = 上下文工程）  │  │
│  │  ┌──────────────┐  │   │  • Summarization  历史压缩          │  │
│  │  │ create_agent │  │   │  • HumanInTheLoop 人工审批          │  │
│  │  │ AgentState   │  │   │  • PII 脱敏                         │  │
│  │  └──────────────┘  │   │  • 自定义 before/after/wrap hooks   │  │
│  └────────────────────┘   └───────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐ │
│  │  chat_models   │  │    tools       │  │     messages        │ │
│  │  init_chat_    │  │  @tool         │  │  消息类型/内容块     │ │
│  │  model         │  │  BaseTool      │  │  trim_messages      │ │
│  └────────────────┘  └────────────────┘  └─────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  底层由 LangGraph 提供：持久化 / 流式 / 人机协同 / 时间旅行  │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

> 💡 **重要**：v1 中 Agent 的持久化、流式、Human-in-the-Loop、时间旅行等能力**由 LangGraph 提供，但你无需直接学习 LangGraph** —— `create_agent` 已开箱即用（想深入则看第 4 章）。

### 2.2 架构分层

| 层级 | 说明 | 核心 API |
|------|------|----------|
| **Agents** | Agent 创建与状态 | `create_agent`, `AgentState` |
| **Middleware** | 上下文工程钩子 | `AgentMiddleware`, `SummarizationMiddleware` 等 |
| **Messages** | 消息与内容块 | `HumanMessage`, `AIMessage`, `content_blocks`, `trim_messages` |
| **Models** | 统一模型接口 | `init_chat_model`, `BaseChatModel` |
| **Tools** | 工具定义与注入 | `@tool`, `BaseTool` |
| **Embeddings** | 嵌入模型 | `init_embeddings`, `Embeddings` |
| **LangGraph（底层）** | 编排运行时 | 持久化 / 流式 / HITL（第 4 章） |

---

## 三、核心组件详解

### 3.1 `create_agent`：标准 Agent 构建方式（v1 核心）

`create_agent` 的底层是一个标准的 **Agent 循环**：调用模型 → 模型选择工具执行 → 直到不再调用工具时结束。

```python
from langchain.agents import create_agent
from langchain.tools import tool


@tool
def search_web(query: str) -> str:
    """搜索互联网获取实时信息。"""
    return f"关于 {query} 的搜索结果..."


@tool
def analyze_data(data: str) -> str:
    """对给定的数据进行分析。"""
    return f"分析结论：{data} 表现出上升趋势。"


agent = create_agent(
    model="gpt-5.5",                 # 字符串或 ChatModel 实例
    tools=[search_web, analyze_data],
    system_prompt="你是一个专业的研究助手，必要时先搜索再分析。",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "分析一下 2026 年 AI Agent 趋势"}]}
)
print(result["messages"][-1].content)
```

**`create_agent` 与旧 API 的对照**：

| 能力 | v0.x 旧写法 | v1 新写法 |
|------|-------------|-----------|
| 创建 ReAct Agent | `langgraph.prebuilt.create_react_agent` | `langchain.agents.create_agent` |
| 工具调用执行器 | `AgentExecutor` | 内置（无需手动配置） |
| 多轮记忆 | `ConversationBufferMemory` | `checkpointer`（LangGraph） |
| 上下文压缩 | 手写摘要 | `SummarizationMiddleware` |
| 人工审批 | 自己实现中断 | `HumanInTheLoopMiddleware` |

### 3.2 中间件（Middleware）：v1 的标志性特性

中间件用于**上下文工程**：动态提示词、对话摘要、工具选择性访问、状态管理、护栏（guardrails）。

**内置中间件**：

| 中间件 | 作用 | 关键参数 |
|--------|------|----------|
| `SummarizationMiddleware` | 历史过长时压缩对话 | `trigger={"tokens": 500}` |
| `HumanInTheLoopMiddleware` | 敏感工具调用需人工审批 | 决策：approve / edit / reject |
| `PIIMiddleware` | 发送给模型前脱敏 | `strategy="redact" \| "block"` |

```python
from langchain.agents import create_agent
from langchain.agents.middleware import (
    SummarizationMiddleware,
    HumanInTheLoopMiddleware,
    PIIMiddleware,
)

agent = create_agent(
    model="gpt-5.5",
    tools=[search_web],
    middleware=[
        SummarizationMiddleware(trigger={"tokens": 4000}),
        PIIMiddleware(strategy="redact"),
        HumanInTheLoopMiddleware(tools=["send_email"]),  # 发邮件前需审批
    ],
)
```

**自定义中间件 Hook**：

| Hook | 运行时机 | 典型用途 |
|------|----------|----------|
| `before_agent` | 调用 Agent 前 | 加载记忆、校验输入 |
| `before_model` | 每次 LLM 调用前 | 更新提示词、裁剪消息 |
| `wrap_model_call` | 包裹每次 LLM 调用 | 拦截/修改请求与响应 |
| `wrap_tool_call` | 包裹每次工具调用 | 拦截/修改工具执行 |
| `after_model` | 每次 LLM 响应后 | 校验输出、应用护栏 |
| `after_agent` | Agent 完成后 | 保存结果、清理 |

```python
from langchain.agents.middleware import AgentMiddleware


class TokenCounterMiddleware(AgentMiddleware):
    """统计每次模型调用的 token（示意）"""

    def before_model(self, state, runtime):
        # 可在此裁剪消息、注入上下文
        return None

    def after_model(self, state, runtime):
        msg = state["messages"][-1]
        print(f"本次响应长度: {len(msg.content)}")
        return None
```

### 3.3 标准内容块（content_blocks）

不同厂商对"推理过程""引用""内置工具"的返回格式各不相同。v1 引入 **`content_blocks`** 统一访问：

```python
from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(model="claude-sonnet-4-6")
response = model.invoke("法国的首都是哪里？")

for block in response.content_blocks:
    if block["type"] == "reasoning":
        print("推理:", block["reasoning"])
    elif block["type"] == "text":
        print("回答:", block["text"])
    elif block["type"] == "tool_call":
        print("工具调用:", block["name"], block["args"])
```

| 优势 | 说明 |
|------|------|
| **提供商无关** | 推理轨迹、引用、内置工具（网页搜索/代码解释器）用同一套 API |
| **类型安全** | 所有内容块类型均有完整类型提示 |
| **向后兼容** | 标准内容惰性加载，无破坏性变更 |

> 目前支持内容块的集成：`langchain-anthropic`、`langchain-aws`、`langchain-openai`、`langchain-google-genai`、`langchain-ollama`。

### 3.4 Models（模型）

LangChain 提供统一的模型接口，推荐用 `init_chat_model` 动态初始化：

```python
from langchain.chat_models import init_chat_model

# 一行切换任意厂商
llm = init_chat_model("gpt-5.5", model_provider="openai")
llm = init_chat_model("claude-sonnet-4-6", model_provider="anthropic")
llm = init_chat_model("gemini-3-pro", model_provider="google_genai")
```

也可以直接用厂商包：

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

chat = ChatOpenAI(model="gpt-5.5")
result = chat.invoke([
    SystemMessage(content="你是一个 AI 助手。"),
    HumanMessage(content="你好"),
])
print(result.content)
```

#### Embedding 模型

```python
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vector = embeddings.embed_query("什么是 AI Agent？")
print(f"向量维度: {len(vector)}")  # 1536
```

### 3.5 Prompts（提示管理）

```python
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder

# 1. 基本字符串模板
template = PromptTemplate.from_template("请用{language}回答：{question}")

# 2. 聊天消息模板（推荐）
chat_template = ChatPromptTemplate.from_messages([
    ("system", "你是一个{role}专家。"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="history"),
])

prompt = chat_template.invoke({
    "role": "Python",
    "input": "什么是装饰器？",
    "history": [],
})
```

> 📌 在 v1 中，对于简单场景你也可以**直接用字符串/消息列表**，不必再强制套 Prompt Template；模板的价值在于**复用与变量注入**。

### 3.6 OutputParser（输出解析）

```python
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from pydantic import BaseModel, Field


class Movie(BaseModel):
    title: str = Field(description="电影名称")
    year: int = Field(description="上映年份")


str_parser = StrOutputParser()      # AIMessage → str
json_parser = JsonOutputParser()    # AIMessage → dict
```

> 🆕 **更推荐**：需要结构化输出时，用 `create_agent` 的 `response_format` 直接在**主循环**里生成，无需额外一次 LLM 调用：

```python
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from pydantic import BaseModel


class Weather(BaseModel):
    temperature: float
    condition: str


agent = create_agent(
    "gpt-5.5",
    tools=[weather_tool],
    response_format=ToolStrategy(Weather),
)
result = agent.invoke({"messages": [{"role": "user", "content": "旧金山天气如何？"}]})
print(repr(result["structured_response"]))  # Weather(temperature=21.0, condition='sunny')
```

### 3.7 Chains（LCEL 流程编排）

LCEL（LangChain Expression Language）用 `|` 声明式编排**确定性**流程：

```python
from langchain_core.runnables import RunnablePassthrough, RunnableParallel

chain = prompt | chat | str_parser

# 通过 RunnablePassthrough 传递上下文
rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | chat
    | str_parser
)

# 并行执行
parallel_chain = RunnableParallel(
    summary=summarize_chain,
    keywords=keywords_chain,
)
```

> 🆕 **v1 定位**：LCEL 适合"步骤固定"的工作流；一旦涉及**自主决策、循环、人工介入**，请用 `create_agent` 或 LangGraph。

### 3.8 Retrieval（检索系统）

```python
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

loader = TextLoader("document.txt")
documents = loader.load()

splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(documents)

vectorstore = Chroma.from_documents(documents=chunks, embedding=OpenAIEmbeddings())
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
results = retriever.invoke("用户问题")
```

### 3.9 Callbacks（回调系统）

用于**日志记录、监控、调试**等场景：

```python
from langchain_core.callbacks import BaseCallbackHandler


class MyCallbackHandler(BaseCallbackHandler):
    def on_llm_start(self, serialized, prompts, **kwargs):
        print(f"🚀 LLM 调用开始，prompts: {len(prompts)}")

    def on_tool_start(self, serialized, input_str, **kwargs):
        print(f"🛠️ 工具调用: {serialized.get('name')}")


chain = prompt | chat | str_parser
result = chain.invoke({"input": "你好"}, config={"callbacks": [MyCallbackHandler()]})
```

> 📌 生产环境建议直接接入 **LangSmith / Langfuse** 做全链路追踪（见 [7.3 可观测性](../07-deployment/03-monitoring.md)）。

---

## 四、组件组合实战

### 4.1 用 create_agent 构建 RAG Agent

```python
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings


vectorstore = Chroma(
    collection_name="kb",
    embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"),
    persist_directory="./kb_db",
)


@tool
def search_knowledge_base(query: str) -> str:
    """搜索企业知识库，返回与问题最相关的资料片段。"""
    docs = vectorstore.similarity_search(query, k=3)
    return "\n\n".join(d.page_content for d in docs)


agent = create_agent(
    model="gpt-5.5",
    tools=[search_knowledge_base],
    system_prompt="你是企业知识助手，回答前先检索知识库；找不到依据就直说不知道。",
)

result = agent.invoke({"messages": [{"role": "user", "content": "我们的报销流程是什么？"}]})
print(result["messages"][-1].content)
```

### 4.2 带会话记忆的 Agent

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
agent = create_agent(model="gpt-5.5", tools=[], checkpointer=checkpointer)

config = {"configurable": {"thread_id": "user-1"}}
agent.invoke({"messages": [{"role": "user", "content": "我叫小明"}]}, config)
```

---

## 五、组件选择指南

| 需求 | 推荐 | 替代方案 |
|------|------|----------|
| 构建 Agent | `create_agent` | LangGraph 自定义图 |
| 调用模型 | `init_chat_model` | `ChatOpenAI` / `ChatAnthropic` |
| 定义工具 | `@tool` | `BaseTool` 类 |
| 结构化输出 | `response_format=ToolStrategy(...)` | `PydanticOutputParser` |
| 确定性工作流 | LCEL（`\|`） | 普通 Python 函数 |
| 上下文压缩 | `SummarizationMiddleware` | `trim_messages` |
| 文档分块 | `RecursiveCharacterTextSplitter` | `TokenTextSplitter` |
| 向量存储 | `Chroma` | `FAISS` / `Qdrant` / `Milvus` |
| 记忆 | LangGraph `checkpointer` / `store` | Mem0 / Letta / Zep |

---

## 六、版本兼容性与迁移（重要）

LangChain v1 精简了 `langchain` 命名空间，**旧功能迁往 `langchain-classic`**：

```bash
uv add langchain                 # v1 核心
uv add langchain-classic         # 需要旧 chains / retrievers / hub 时
uv add langchain-community       # 社区集成
```

**导入迁移对照**：

```python
# v0.x 旧写法 → v1
from langchain import ...              →  from langchain_classic import ...
from langchain.chains import ...        →  from langchain_classic.chains import ...
from langchain.retrievers import ...    →  from langchain_classic.retrievers import ...
from langchain import hub               →  from langchain_classic import hub
```

**v1 中 `langchain` 的核心模块**：

| 模块 | 可用内容 |
|------|----------|
| `langchain.agents` | `create_agent`, `AgentState` |
| `langchain.messages` | 消息类型、内容块、`trim_messages` |
| `langchain.tools` | `@tool`, `BaseTool`, 注入辅助 |
| `langchain.chat_models` | `init_chat_model`, `BaseChatModel` |
| `langchain.embeddings` | `Embeddings`, `init_embeddings` |

---

## 七、常见问题

### ❌ 导入报错（找不到某个类）

```python
# ❌ 旧版本导入（v0.x）
from langchain.chains import LLMChain

# ✅ v1：旧链式 API 已迁移
from langchain_classic.chains import LLMChain

# ✅ 更推荐：改用 create_agent / LCEL
```

### ❌ 异步调用与流式

```python
# 异步
result = await chain.ainvoke({"input": "你好"})

# 流式
async for chunk in chain.astream({"input": "你好"}):
    print(chunk, end="", flush=True)
```

### ❌ 结构化输出解析失败

- 优先用 `response_format=ToolStrategy(Model)`，并配置 `handle_errors`；
- 若走 Parser，务必在 Prompt 中明确输出格式。

---

## 八、本章总结

| 组件 | 一句话说明 |
|------|------------|
| **`create_agent`** | v1 标准的 Agent 构建方式，内置工具循环 |
| **Middleware** | 上下文工程钩子：压缩、审批、脱敏、护栏 |
| **content_blocks** | 跨厂商统一访问推理、引用、工具调用 |
| **Models** | `init_chat_model` 一行切换任意厂商 |
| **Tools** | `@tool` 把函数变成 Agent 的能力 |
| **LCEL** | 声明式编排确定性工作流 |
| **langchain-classic** | v0.x 旧功能的迁移去向 |

---

## 📝 课后练习

1. **✅ 基础**：用 `create_agent` + 两个工具构建一个能搜索、能计算的 Agent
2. **💡 进阶**：为 Agent 加上 `SummarizationMiddleware`，观察长对话下的上下文压缩效果
3. **🚀 挑战**：用 `response_format=ToolStrategy(Model)` 让 Agent 返回结构化结果
4. **🔍 探索**：写一个自定义 `AgentMiddleware`，在 `before_model` 中动态注入当前时间
