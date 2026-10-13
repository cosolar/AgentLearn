# 3.1 LangChain v1 核心组件 —— 框架全景、create_agent 与 Middleware

> 📅 更新至 2026-10 · 技术栈基线见 [知识库大纲](../知识库大纲.md)

## 📖 导读

LangChain 是当前最流行的 LLM 应用开发框架，也是构建 AI Agent 最常用的基础设施。**它不是一个大而全的"黑盒"，而是一组精心设计的可组合模块。**

> 🆕 **2026 版重点**：**LangChain v1**（与 LangGraph v1 同步 GA）带来了三大变化，它们构成本章的骨架：
> 1. **`create_agent`** —— 统一的、标准的 Agent 构建方式，取代 `langgraph.prebuilt.create_react_agent` 与 `AgentExecutor`；
> 2. **标准内容块（content blocks）** —— 通过 `content_blocks` 跨厂商统一访问推理轨迹、引用、内置工具调用；
> 3. **简化的命名空间** —— `langchain` 只保留 Agent 核心构建块，旧功能（chains / retrievers / hub / memory）迁往 `langchain-classic`。
>
> 本章将围绕这三条主线，带你建立对 LangChain v1 的完整认知。**记住一条铁律：v1 里创建 Agent 只有一个入口 —— `create_agent`。**

**本节基线**：Python ≥ 3.12 · `uv` · `langchain>=1.4.5` · `langchain-core>=1.6.10` · `langgraph>=1.2.15`。

---

## 一、前置知识

学习本章前，建议你已完成：

| 前置章节 | 为什么需要 |
|----------|------------|
| 1.2 开发环境搭建 | `uv` 工作流、Python 3.12、`LLM_*` 环境变量配置 |
| 1.3 第一个 Agent | 消息模型、`invoke` / `stream` 基本调用 |
| 2.1 Prompt 与上下文工程 | 系统提示词与上下文管理 |
| 2.2 Chain 模式（LCEL） | `\|` 声明式编排 |
| 2.3 Agent 核心架构 | ReAct / TAO 循环、终止条件 |
| 2.4 记忆机制 | checkpointer、store 的概念 |

> 📎 **配套示例**：[`examples/01-hello-agent/`](../../examples/01-hello-agent/)（最小对话 Agent）。

---

## 二、LangChain v1 架构全景

### 2.1 整体架构

LangChain v1 的定位从"大而全的工具箱"收窄为**"聚焦、可用于生产的 Agent 构建基础"**：

```
┌──────────────────────────────────────────────────────────────────┐
│                    LangChain v1（聚焦的 Agent 基础）               │
│                                                                   │
│  ┌────────────────────┐   ┌───────────────────────────────────┐  │
│  │  langchain.agents  │   │  Middleware（中间件 = 控制面）      │  │
│  │  ┌──────────────┐  │   │  • Summarization  历史压缩          │  │
│  │  │ create_agent │  │   │  • HumanInTheLoop 人工审批          │  │
│  │  │ AgentState   │  │   │  • PII 脱敏 / 调用限额 / 模型回退    │  │
│  │  └──────────────┘  │   │  • 自定义 before/after/wrap hooks   │  │
│  └────────────────────┘   └───────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐ │
│  │  chat_models   │  │    tools       │  │     messages        │ │
│  │  init_chat_    │  │  @tool         │  │  消息类型/内容块     │ │
│  │  model         │  │  ToolRuntime   │  │  content_blocks     │ │
│  └────────────────┘  └────────────────┘  └─────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  底层由 LangGraph 提供：持久化 / 流式 / 人机协同 / 时间旅行  │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

> 💡 **重要**：v1 中 Agent 的持久化、流式、Human-in-the-Loop、时间旅行等能力**由 LangGraph 提供，但你无需直接学习 LangGraph** —— `create_agent` 已开箱即用（想深入则看[第 4 章 LangGraph 基础](../04-LangGraph进阶/01-LangGraph基础.md)）。

### 2.2 架构分层

| 层级 | 说明 | 核心 API | 导入路径 |
|------|------|----------|----------|
| **Agents** | Agent 创建与状态 | `create_agent`, `AgentState` | `langchain.agents` |
| **Middleware** | 上下文工程控制面 | `AgentMiddleware`, `SummarizationMiddleware` 等 | `langchain.agents.middleware` |
| **Messages** | 消息与内容块 | `HumanMessage`, `AIMessage`, `content_blocks`, `trim_messages` | `langchain.messages` |
| **Models** | 统一模型接口 | `init_chat_model`, `BaseChatModel` | `langchain.chat_models` |
| **Tools** | 工具定义与运行时注入 | `@tool`, `BaseTool`, `ToolRuntime` | `langchain.tools` |
| **Embeddings** | 嵌入模型 | `init_embeddings`, `Embeddings` | `langchain.embeddings` |
| **LangGraph（底层）** | 编排运行时 | 持久化 / 流式 / HITL | `langgraph.*`（第 4 章） |

> 📌 `langchain.*` 的这些模块大多是 `langchain-core` 的**再导出**。你也会在 `examples/` 里看到 `from langchain_core.messages import ...` —— 两者等价，本教程统一使用 v1 的 `langchain.*` 短路径。

---

## 三、`create_agent`：v1 唯一的 Agent 入口

### 3.1 核心思想

`create_agent` 的底层是一个标准的 **Agent 循环**：

```
调用模型 → 模型选择工具 → 执行工具 → 结果回传模型 → …… 直到模型不再调用工具时结束
```

你只需声明 **模型、工具、系统提示词**，循环由框架负责。

### 3.2 完整签名

```python
# doc-check: skip —— 参数签名示意，非可运行代码
from langchain.agents import create_agent

create_agent(
    model,                      # str | BaseChatModel（必填）
    tools=None,                 # 工具列表（None 则退化为纯模型节点）
    *,
    system_prompt=None,         # str | SystemMessage
    middleware=(),              # 中间件序列
    response_format=None,       # ToolStrategy | ProviderStrategy | Pydantic 模型
    state_schema=None,          # 扩展 AgentState（加自定义字段）
    context_schema=None,        # 运行时上下文 schema（配合 invoke(context=...)）
    checkpointer=None,          # 会话级记忆（LangGraph checkpointer）
    store=None,                 # 跨会话长期记忆（LangGraph store）
    interrupt_before=None,      # 在这些节点前中断
    interrupt_after=None,       # 在这些节点后中断
    debug=False,
    name=None,
    cache=None,
)
```

### 3.3 最小可运行示例

```python
"""3.1 最小 Agent —— 模型 + 两个工具 + 系统提示词"""
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool

load_dotenv()


def build_model(temperature: float = 0):
    """从环境变量构建模型，便于在 OpenAI / Anthropic / DeepSeek 之间切换。"""
    return init_chat_model(
        os.getenv("LLM_MODEL_NAME", "gpt-5.5"),
        model_provider="openai",
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        temperature=temperature,
    )


@tool
def search_web(query: str) -> str:
    """搜索互联网获取实时信息。当需要最新知识或不确定答案时使用。"""
    return f"关于「{query}」的搜索结果：AI Agent 市场持续增长……"


@tool
def calculate(expression: str) -> str:
    """执行数学计算，支持 +、-、*、/、**、() 等运算。"""
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:  # 工具内部兜底，避免异常打断 Agent 循环
        return f"计算失败：{e}"


agent = create_agent(
    model=build_model(),                       # 也可直接传字符串，如 "openai:gpt-5.5"
    tools=[search_web, calculate],
    system_prompt="你是一个严谨的助理，需要数据时先搜索，需要计算时用计算工具。",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "算一下 (1234 + 5678) * 3，顺便说说 AI Agent 趋势"}]}
)
print(result["messages"][-1].content)
```

> 💡 **模型参数**：`model` 既可传字符串（如 `"openai:gpt-5.5"`），也可传 `ChatOpenAI` / `ChatAnthropic` 实例。当你需要自定义 `base_url` / `api_key` 时，构造实例再传入更直观。

### 3.4 `create_agent` 与旧 API 的对照

| 能力 | v0.x 旧写法 | v1 新写法 |
|------|-------------|-----------|
| 创建 ReAct Agent | `langgraph.prebuilt.create_react_agent` | `langchain.agents.create_agent` |
| 工具调用执行器 | `AgentExecutor` | 内置（无需手动配置） |
| 多轮记忆 | `ConversationBufferMemory` | `checkpointer`（LangGraph） |
| 上下文压缩 | 手写摘要 | `SummarizationMiddleware` |
| 人工审批 | 自己实现中断 | `HumanInTheLoopMiddleware` |
| 解析错误兜底 | `handle_parsing_errors=True` | `ToolRetryMiddleware` / `@wrap_tool_call` |
| 死循环防护 | `max_iterations` | `ModelCallLimitMiddleware` / `ToolCallLimitMiddleware` |

---

## 四、Middleware：v1 的上下文工程控制面

中间件用于**上下文工程与运行治理**：动态提示词、对话摘要、工具选择性访问、状态管理、护栏（guardrails）、调用限额、失败重试与模型回退。

### 4.1 内置中间件

全部从 `langchain.agents.middleware` 导入：

| 中间件 | 作用 | 关键参数 |
|--------|------|----------|
| `SummarizationMiddleware` | 接近上下文窗口时自动摘要历史 | `model`, `trigger={"tokens": 4000}`, `keep=("messages", 20)` |
| `HumanInTheLoopMiddleware` | 敏感工具调用前暂停等待人工审批 | `interrupt_on={"send_email": True}` |
| `PIIMiddleware` | 发送给模型前脱敏/拦截 | `pii_type="email"`, `strategy="redact"\|"mask"\|"hash"\|"block"` |
| `ModelCallLimitMiddleware` | 限制模型调用次数（防成本失控） | `thread_limit`, `run_limit`, `exit_behavior="end"` |
| `ToolCallLimitMiddleware` | 限制工具调用次数（防死循环） | `tool_name`, `thread_limit`, `run_limit` |
| `ModelFallbackMiddleware` | 主模型失败时回退到备用模型 | `ModelFallbackMiddleware("openai:gpt-5.5", "anthropic:...")` |
| `ToolRetryMiddleware` | 工具失败自动重试（指数退避） | `max_retries=2`, `on_failure="continue"` |
| `LLMToolSelectorMiddleware` | 工具过多时先用 LLM 筛出相关工具 | `max_tools` |
| `ContextEditingMiddleware` | 清理/裁剪历史工具结果以控上下文 | `ClearToolUsesEdit` |
| `TodoListMiddleware` | 给 Agent 注入任务清单能力 | — |

```python
from langchain.agents import create_agent
from langchain.agents.middleware import (
    SummarizationMiddleware,
    HumanInTheLoopMiddleware,
    PIIMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    ToolRetryMiddleware,
)

agent = create_agent(
    model="openai:gpt-5.5",
    tools=[search_web, send_email],
    middleware=[
        # 1) 上下文超过 4000 token 时自动摘要，保留最近 20 条消息
        SummarizationMiddleware(model="openai:gpt-5.5", trigger={"tokens": 4000}),
        # 2) 用户输入里的邮箱在发给模型前脱敏
        PIIMiddleware("email", strategy="redact"),
        # 3) 发邮件属于敏感操作，执行前暂停等待人工批准
        HumanInTheLoopMiddleware(interrupt_on={"send_email": True}),
        # 4) 兜底：限制模型/工具调用次数 + 工具失败重试
        ModelCallLimitMiddleware(thread_limit=20, run_limit=10, exit_behavior="end"),
        ToolCallLimitMiddleware(tool_name="search_web", run_limit=5),
        ToolRetryMiddleware(max_retries=2, on_failure="continue"),
    ],
)
```

### 4.2 自定义中间件：两种写法

**写法一：装饰器（轻量，推荐）**

```python
from langchain.agents.middleware import before_model, after_model, wrap_tool_call
from langchain.messages import SystemMessage


@before_model
def inject_time(state, runtime):
    """每次调用模型前，把当前时间注入系统提示词。"""
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {"messages": [SystemMessage(content=f"当前时间：{now}")] + state["messages"]}


@after_model
def log_response(state, runtime):
    """每次模型返回后打印长度，便于调试。"""
    print(f"[log] 本次响应长度: {len(state['messages'][-1].content)}")
    return None
```

**写法二：继承 `AgentMiddleware`（需要携带状态或复杂逻辑时）**

```python
from langchain.agents.middleware import AgentMiddleware


class TokenCounterMiddleware(AgentMiddleware):
    """统计模型调用次数（示意）。"""

    def __init__(self):
        super().__init__()
        self.calls = 0

    def before_model(self, state, runtime):
        self.calls += 1
        return None

    def after_model(self, state, runtime):
        print(f"[token-counter] 第 {self.calls} 次模型调用完成")
        return None
```

### 4.3 Hook 一览

| Hook | 运行时机 | 典型用途 |
|------|----------|----------|
| `before_agent` | 调用 Agent 前 | 加载记忆、校验输入 |
| `before_model` | 每次 LLM 调用前 | 更新提示词、裁剪消息 |
| `wrap_model_call` | 包裹每次 LLM 调用 | 动态换模型/换工具集、拦截请求与响应 |
| `wrap_tool_call` | 包裹每次工具调用 | 统一错误处理、重试、审计 |
| `after_model` | 每次 LLM 响应后 | 校验输出、应用护栏 |
| `after_agent` | Agent 完成后 | 保存结果、清理资源 |

> 📌 装饰器与类方法都有对应的异步版本（如 `abefore_model`、`awrap_tool_call`）。

---

## 五、标准内容块（content_blocks）

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
| **向后兼容** | 标准内容惰性加载，`.content` 原始字段依然可用 |

> 目前支持内容块的集成：`langchain-anthropic`、`langchain-aws`、`langchain-openai`、`langchain-google-genai`、`langchain-ollama`。

---

## 六、其余核心组件速览

### 6.1 Models（模型）

```python
from langchain.chat_models import init_chat_model

# 一行切换任意厂商（provider 前缀或 model_provider 参数）
llm = init_chat_model("openai:gpt-5.5", temperature=0)
llm = init_chat_model("anthropic:claude-sonnet-4-6")
llm = init_chat_model("deepseek:deepseek-chat")
```

### 6.2 Messages（消息）

```python
from langchain.messages import HumanMessage, SystemMessage, AIMessage, trim_messages

messages = [
    SystemMessage(content="你是一个 AI 助手。"),
    HumanMessage(content="你好"),
]

# 按 token 上限裁剪历史（配合 checkpointer 使用）
trimmed = trim_messages(messages, max_tokens=2000, strategy="last")
```

### 6.3 Tools（工具）

```python
from langchain.tools import tool


@tool
def search_knowledge_base(query: str) -> str:
    """搜索企业知识库，返回与问题最相关的资料片段。"""
    docs = vectorstore.similarity_search(query, k=3)
    return "\n\n".join(d.page_content for d in docs)
```

### 6.4 Embeddings（嵌入模型）

```python
from langchain.embeddings import init_embeddings

embeddings = init_embeddings("openai:text-embedding-3-small")
vector = embeddings.embed_query("什么是 AI Agent？")
print(f"向量维度: {len(vector)}")  # 1536
```

### 6.5 LCEL（声明式流程编排）

LCEL 用 `|` 编排**确定性**工作流，适合"步骤固定"的场景：

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

prompt = ChatPromptTemplate.from_template("用一句话解释：{topic}")
chain = prompt | llm | StrOutputParser()
print(chain.invoke({"topic": "什么是 RAG"}))
```

> 🆕 **v1 定位**：LCEL 负责"确定流程"；一旦涉及**自主决策、循环、人工介入**，请用 `create_agent` 或 LangGraph。

---

## 七、v0.x → v1 迁移对照（重点）

### 7.1 概念级对照

| 主题 | v0.x 旧写法 | v1 新写法 | 备注 |
|------|-------------|-----------|------|
| 构建 Agent | `create_react_agent` / `AgentExecutor` | **`create_agent`** | v1 唯一入口 |
| 工具循环 | 执行器自动跑 / 手写循环 | 内置 | 无需 `max_iterations` |
| 多轮记忆 | `ConversationBufferMemory` | **`checkpointer`** | `InMemorySaver` / `SqliteSaver` / `PostgresSaver` |
| 长期记忆 | `ConversationSummaryMemory` 等 | **`store`** 或向量库 | 跨会话 |
| 上下文压缩 | 手写摘要链 | `SummarizationMiddleware` | 声明式 |
| 结构化输出 | `PydanticOutputParser` | `response_format=ToolStrategy(Model)` | 主循环内生成 |
| 解析错误 | `handle_parsing_errors=True` | `ToolRetryMiddleware` / `@wrap_tool_call` | 按错误分类处理 |
| 敏感操作审批 | 自己实现 | `HumanInTheLoopMiddleware` | `interrupt_on=...` |
| 观测 | Callbacks | Middleware + LangSmith | 见 [7.3 可观测性](../07-生产部署/03-可观测性与监控.md) |
| 向量库 | `langchain_community.vectorstores.*` | 专用包（如 `langchain-chroma`） | 已拆分 |
| 持久化 | `vectorstore.persist()` | 写入自动落盘 | `persist()` 已弃用 |

### 7.2 导入迁移对照

```python
# doc-check: skip —— 旧→新 迁移对照，非可运行代码
# —— 旧（v0.x）→ 新（v1）——
from langchain import ...               →  from langchain_classic import ...
from langchain.chains import ...         →  from langchain_classic.chains import ...
from langchain.retrievers import ...     →  from langchain_classic.retrievers import ...
from langchain import hub                →  from langchain_classic import hub
from langchain.memory import ...         →  from langchain_classic.memory import ...（或改用 checkpointer/store）
from langchain_community.vectorstores import Chroma  →  from langchain_chroma import Chroma
```

### 7.3 命名空间一览

| 模块 | 可用内容 |
|------|----------|
| `langchain.agents` | `create_agent`, `AgentState` |
| `langchain.agents.middleware` | 内置中间件、`AgentMiddleware`、hook 装饰器 |
| `langchain.messages` | 消息类型、内容块、`trim_messages` |
| `langchain.tools` | `@tool`, `BaseTool`, `ToolRuntime` |
| `langchain.chat_models` | `init_chat_model`, `BaseChatModel` |
| `langchain.embeddings` | `Embeddings`, `init_embeddings` |
| `langchain-classic` | 旧 chains / retrievers / hub / memory |
| `langchain-community` | 社区集成（仍在，但向量库等已陆续拆分） |

### 7.4 依赖安装

```bash
uv add langchain                 # v1 核心（含 create_agent / middleware）
uv add langchain-openai          # OpenAI 集成
uv add langchain-anthropic       # Anthropic 集成
uv add langgraph                 # 底层运行时（create_agent 依赖）
uv add langchain-classic         # 需要旧 chains / retrievers / hub 时
```

---

## 八、常见问题

### ❌ 导入报错（找不到某个类）

```python
# ❌ 旧版本导入（v0.x）
from langchain.chains import LLMChain
from langchain.agents import AgentExecutor

# ✅ v1：旧链式 API 已迁移到 langchain-classic
from langchain_classic.chains import LLMChain

# ✅ 更推荐：Agent 改用 create_agent
from langchain.agents import create_agent
```

### ❌ "找不到 AgentExecutor" 怎么办

v1 里 **没有** `AgentExecutor`。所有"执行器 + 工具循环 + 记忆"的能力都由 `create_agent` + `checkpointer` + Middleware 承担。迁移时不要试图找回它，而是重构为 `create_agent`。

### ❌ 异步调用与流式

```python
# 异步
result = await agent.ainvoke({"messages": [{"role": "user", "content": "你好"}]})

# 流式（逐 token）
async for chunk in agent.astream(
    {"messages": [{"role": "user", "content": "你好"}]},
    stream_mode="messages",
):
    message_chunk, metadata = chunk
    if message_chunk.content:
        print(message_chunk.content, end="", flush=True)
```

### ❌ 结构化输出解析失败

- 优先用 `response_format=ToolStrategy(Model, handle_errors=True)`，让失败自动重试；
- 若走 Parser，务必在 Prompt 中明确输出格式（见 [3.2 结构化输出](./02-模型调用与工具.md)）。

---

## 本章小结

| 组件 | 一句话说明 |
|------|------------|
| **`create_agent`** | v1 唯一的标准 Agent 构建入口，内置工具循环 |
| **Middleware** | 上下文工程与运行治理的控制面：压缩、审批、脱敏、限额、重试、回退 |
| **`content_blocks`** | 跨厂商统一访问推理、引用、工具调用 |
| **Models** | `init_chat_model` 一行切换任意厂商 |
| **Messages** | `langchain.messages` 提供消息类型与 `trim_messages` |
| **Tools** | `@tool` 把函数变成 Agent 的能力，`ToolRuntime` 读取运行时上下文 |
| **LCEL** | 声明式编排确定性工作流 |
| **`langchain-classic`** | v0.x 旧功能（chains / retrievers / hub / memory）的迁移去向 |
| **迁移铁律** | Agent 只有一个入口：`create_agent` |

---

## 📝 课后练习

1. **✅ 基础**：用 `create_agent` + 两个工具（搜索、计算）构建一个 Agent，并让它完成一个需要"先搜索、再计算"的多步任务。
2. **💡 进阶**：为 Agent 加上 `SummarizationMiddleware(model=..., trigger={"tokens": 4000})`，构造一段长对话，观察上下文被压缩前后 `len(result["messages"])` 的变化。
3. **🚀 挑战**：用 `response_format=ToolStrategy(Model)` 让 Agent 返回一个 Pydantic 结构（例如 `{title, summary, confidence}`），并读取 `result["structured_response"]`。
4. **🔍 探索**：写一个自定义 `AgentMiddleware`，在 `before_model` 中动态注入当前时间；再对比用 `@before_model` 装饰器实现同一功能的代码差异。
