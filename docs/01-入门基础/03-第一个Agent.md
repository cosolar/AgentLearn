# 1.3 第一个 Agent —— 用 create_agent 构建你的第一个智能体

> 📅 更新至 2026-10 · 技术栈基线见 [知识库大纲](../知识库大纲.md)

## 📖 导读

> **一句话结论**：在 LangChain v1 中，构建一个会调用工具、能自主决策的 Agent，**只需要一个函数 `create_agent`**——它把"模型 → 调用工具 → 把结果回传模型 → 直到不再需要工具"的循环全部封装好了。

- **前置阅读**：[1.2 开发环境搭建](./02-开发环境搭建.md)（必须已能运行 `uv run`）。
- **本章你将学到**：
  1. 用 `create_agent` 写一个**最小可运行**的 Agent（约 15 行）；
  2. `create_agent` 的参数含义与返回结构；
  3. **流式输出**（`stream` / `stream_mode="messages"`）；
  4. LangChain 的**消息模型**（`SystemMessage` / `HumanMessage` / `AIMessage` / `ToolMessage`）；
  5. 常见错误排查。

> 📌 **关于 API**：本教程**唯一**的 Agent 入口是 `from langchain.agents import create_agent`。你可能会在网上看到旧的 `AgentExecutor` / `create_react_agent` 写法，它们已不再是推荐方式（迁移对照见 [2.3 Agent 核心架构](../02-核心概念/03-Agent核心架构.md)）。
>
> 📎 **配套示例**：本章的"消息 + invoke"底层机制版见 [`examples/01-hello-agent/main.py`](../../examples/01-hello-agent/main.py)；完整的 `create_agent` 实战见 [`examples/04-research-agent/main.py`](../../examples/04-research-agent/main.py)。

---

## 一、前置知识：消息模型

Agent 与 LLM 之间的一切交互，都是**消息（Message）**。LangChain 的消息都是 `BaseMessage` 的子类：

| 消息类型 | 来源 | 作用 |
|----------|------|------|
| `SystemMessage` | 系统 | 设定角色与规则，**通常只有第一条** |
| `HumanMessage` | 用户 | 用户输入 |
| `AIMessage` | 模型 | 模型回复；**可能携带 `tool_calls`（工具调用请求）** |
| `ToolMessage` | 工具 | 工具执行结果，回传给模型 |

Agent 的循环，本质上就是这些消息在模型与工具之间来回追加的过程：

```
HumanMessage
  → AIMessage(tool_calls=[...])     ← 模型决定调用工具
  → ToolMessage(...)                ← 工具执行结果
  → AIMessage(content="最终回答")   ← 模型给出最终答案
```

> 💡 `create_agent` 的输入输出都是 `{"messages": [...]}` 这种字典结构，内部维护的正是上面这条消息序列。

---

## 二、最小可运行 Agent

新建 `hello_agent.py`（或在项目里直接运行下面这段），这是一个**能查天气**的 Agent：

```python
"""
第一个 Agent —— 最小可运行的 create_agent 示例

运行：uv run hello_agent.py
"""

import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain.tools import tool

# 1. 加载 .env（读取 LLM_MODEL_NAME / LLM_API_KEY / LLM_BASE_URL）
load_dotenv()


# 2. 定义一个工具：Agent 可以自主决定是否调用它
@tool
def get_weather(city: str) -> str:
    """查询指定城市的天气。"""
    # 实际项目里这里会调用真实天气 API，此处用模拟数据
    fake = {"北京": "晴，25℃", "上海": "多云，22℃", "广州": "小雨，28℃"}
    return f"{city}：{fake.get(city, '暂无数据')}"


# 3. 用统一约定初始化模型（缺省回退 OPENAI_*）
model = ChatOpenAI(
    model=os.getenv("LLM_MODEL_NAME", "gpt-5.5"),
    api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_API_BASE"),
    temperature=0,
)

# 4. 创建 Agent —— 这就是全部
agent = create_agent(
    model=model,                              # 也可直接传字符串 "gpt-5.5"
    tools=[get_weather],                      # 可调用的工具列表
    system_prompt="你是一个贴心的出行助手，用中文简洁回答。",
)

# 5. 调用：输入输出都是 {"messages": [...]}
result = agent.invoke(
    {"messages": [{"role": "user", "content": "北京今天要带伞吗？"}]}
)

# 6. 最后一条消息就是最终回答
print(result["messages"][-1].content)
```

运行：

```bash
uv run hello_agent.py
# 预期输出（示意）：
# 北京今天晴，25℃，不用带伞，出行很舒适。
```

> 🎯 **注意 Agent 和"普通聊天"的区别**：你问的是"要不要带伞"，模型自己判断出**需要先查天气**，于是调用 `get_weather("北京")`，拿到结果后再组织回答。这个"判断 → 调用 → 再回答"的过程，就是 Agent 的核心。

---

## 三、代码逐段拆解

### 3.1 导入

```python
import os
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain.tools import tool
```

| 导入 | 作用 |
|------|------|
| `load_dotenv` | 从 `.env` 加载环境变量 |
| `create_agent` | **v1 标准 Agent 构建入口** |
| `ChatOpenAI` | OpenAI 兼容模型客户端 |
| `tool` | 把普通函数变成 Agent 可调用的工具 |

### 3.2 `@tool`：把函数变成工具

```python
@tool
def get_weather(city: str) -> str:
    """查询指定城市的天气。"""
    ...
```

- 函数名 = 工具名，**docstring = 工具描述**，模型靠描述判断"这个工具能干什么、什么时候用"；
- 类型标注（`city: str`）会被转换成参数 schema，模型据此正确传参；
- ⚠️ **docstring 写得越清楚，模型选工具越准**（详见 [2.3 决策机制](../02-核心概念/03-Agent核心架构.md)）。

### 3.3 `create_agent` 的关键参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `model` | `str` 或 ChatModel 实例 | 模型名（如 `"gpt-5.5"`）或已初始化的模型对象 |
| `tools` | `list` | 工具列表（`@tool` 函数、`BaseTool` 实例均可） |
| `system_prompt` | `str` | 系统提示，设定角色与行为规则 |
| `middleware` | `list` | 中间件：摘要压缩、人工审批、PII 脱敏等（见 [2.3](../02-核心概念/03-Agent核心架构.md)） |
| `checkpointer` | 对象 | 持久化/记忆（见 [2.4 记忆机制](../02-核心概念/04-记忆机制.md)） |
| `response_format` | 策略 | 结构化输出（见 [2.1](../02-核心概念/01-Prompt与上下文工程.md)） |

### 3.4 返回结构

```python
result = agent.invoke({"messages": [{"role": "user", "content": "北京今天要带伞吗？"}]})
```

`result` 是一个字典，键为 `"messages"`，值是**完整的消息序列**（含中间的 `AIMessage(tool_calls)` 与 `ToolMessage`）：

```python
result["messages"]
# [HumanMessage("北京今天要带伞吗？"),
#  AIMessage(tool_calls=[{"name": "get_weather", "args": {"city": "北京"}}]),
#  ToolMessage("北京：晴，25℃"),
#  AIMessage("北京今天晴，25℃，不用带伞。")]
```

因此最终回答永远是 **`result["messages"][-1].content`**。

---

## 四、流式输出（stream）

一次性等待完整回复体验较差，Agent 支持**逐 token 流式输出**。用 `stream` + `stream_mode="messages"`：

```python
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

load_dotenv()

model = ChatOpenAI(
    model=os.getenv("LLM_MODEL_NAME", "gpt-5.5"),
    api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_API_BASE"),
)
agent = create_agent(model=model, tools=[], system_prompt="你是一个中文写作助手。")

print("🤖 ", end="")
for chunk, metadata in agent.stream(
    {"messages": [{"role": "user", "content": "写一首关于秋天的五言绝句"}]},
    stream_mode="messages",          # 逐 token 产出 (message_chunk, metadata)
):
    if chunk.content:                # chunk 是 AIMessageChunk
        print(chunk.content, end="", flush=True)
print()
```

`stream` 的常用 `stream_mode`：

| `stream_mode` | 产出 | 用途 |
|---------------|------|------|
| `"updates"`（默认） | 每个节点执行后的状态增量 | 观察 Agent 的每一步 |
| `"values"` | 每个节点执行后的完整状态 | 调试整体状态 |
| `"messages"` | `(消息块, 元数据)` 元组 | **前端打字机效果** |

> 💡 异步场景用 `async for ... in agent.astream(...)`，参数一致。生产级流式前端见 [07-生产部署](../07-生产部署/01-API服务部署.md)。

---

## 五、消息模型详解

### 5.1 两种构造方式

```python
from langchain_core.messages import HumanMessage, SystemMessage

# 方式一：字典（简单，推荐用于快速调用）
{"role": "user", "content": "你好"}
{"role": "system", "content": "你是一个助手"}

# 方式二：消息对象（可访问更多字段，推荐用于复杂逻辑）
SystemMessage(content="你是一个助手")
HumanMessage(content="你好")
```

两种方式可以混用，`create_agent` 会自动规范化。

### 5.2 消息对象的关键字段

| 字段 | 说明 |
|------|------|
| `.content` | 文本内容（也可能是内容块列表） |
| `.tool_calls` | 仅 `AIMessage`：模型请求调用的工具列表 |
| `.tool_call_id` | 仅 `ToolMessage`：对应哪一次工具调用 |
| `.usage_metadata` | 可选：token 用量（用于成本统计） |

### 5.3 手动观察 Agent 的思考过程

把消息序列打出来，就能看到 Agent"思考 → 调用工具 → 回答"的全过程：

```python
result = agent.invoke({"messages": [{"role": "user", "content": "北京今天要带伞吗？"}]})

for msg in result["messages"]:
    kind = type(msg).__name__
    if getattr(msg, "tool_calls", None):
        calls = [c["name"] for c in msg.tool_calls]
        print(f"[{kind}] 调用工具: {calls}")
    else:
        print(f"[{kind}] {msg.content}")
```

---

## 六、进阶：给 Agent 加上记忆

上面的 Agent **每次调用都是独立的**——它不记得上一轮说过什么。只需传入一个 `checkpointer`，并用 `thread_id` 标识会话：

```python
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver   # 注意：新路径

agent = create_agent(
    model="gpt-5.5",
    tools=[],
    system_prompt="你是一个友好的助手。",
    checkpointer=InMemorySaver(),
)

config = {"configurable": {"thread_id": "user-001"}}

agent.invoke({"messages": [{"role": "user", "content": "我叫小明"}]}, config)
result = agent.invoke({"messages": [{"role": "user", "content": "我叫什么？"}]}, config)
print(result["messages"][-1].content)   # → 你叫小明
```

> 📌 `InMemorySaver` 只适合本地开发（重启即丢）；生产环境换成 `SqliteSaver` / `PostgresSaver`。完整讲解见 [2.4 记忆机制](../02-核心概念/04-记忆机制.md)。

---

## 七、常见错误排查

### ❌ `AuthenticationError` / `401`

```python
# 排查：确认 .env 存在、Key 完整、load_dotenv() 已调用
import os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
print("API Key 是否存在:", bool(key))
```

### ❌ `ModuleNotFoundError: No module named 'langchain'`

原因：未安装依赖，或用错解释器。

```bash
uv sync
uv run hello_agent.py
```

### ❌ `TypeError: create_agent() got an unexpected keyword argument ...`

原因：**用了旧版 API 的参数**。v1 的 `create_agent` 不接受 `max_iterations`、`agent_type` 等旧参数；限制轮次请改用中间件或 LangGraph（见 [2.3](../02-核心概念/03-Agent核心架构.md)）。

### ❌ 模型不调用工具

- 检查 `@tool` 函数的 **docstring** 是否清楚描述了用途；
- 检查 `tools=[...]` 是否真的传入了工具；
- 用 `temperature=0` 降低随机性；
- 用 [五、5.3](#53-手动观察-agent-的思考过程) 的方法打印消息，确认模型是否产生了 `tool_calls`。

### ❌ 网络连接失败

```bash
# 检查 Base URL 是否可达、结尾是否为 /v1
curl -s "$LLM_BASE_URL/models" -H "Authorization: Bearer $LLM_API_KEY" | head
```

---

## 本章小结

| 要点 | 说明 |
|------|------|
| **Agent 入口** | `from langchain.agents import create_agent`（v1 唯一推荐入口） |
| **最小结构** | 模型 + 工具 + `system_prompt`，三行即可创建 |
| **调用方式** | `agent.invoke({"messages": [...]})`，返回 `{"messages": [...]}` |
| **最终答案** | `result["messages"][-1].content` |
| **流式输出** | `agent.stream(..., stream_mode="messages")` 逐 token 产出 |
| **消息类型** | System / Human / AI / Tool 四种 `BaseMessage` |
| **记忆** | 传入 `checkpointer=InMemorySaver()` + `thread_id` |
| **工具描述** | docstring 质量直接决定模型选工具是否准确 |

---

## 📝 课后练习

**基础**
1. 运行本章的最小示例，把 `get_weather` 换成你自己的工具（如"查汇率""算 BMI"），让 Agent 自主调用。

**进阶**
2. 给 Agent 加两个工具（如"查天气"+"算折扣"），提出一个**需要连续调用两个工具**的问题（如"北京气温打个 8 折是多少度"），打印消息序列，观察 Agent 的两轮工具调用。

**挑战**
3. 结合 `stream_mode="messages"` 与 `checkpointer`，写一个**带记忆的流式命令行 Agent**：支持多轮对话，每轮回复逐字打印，输入 `exit` 退出。
4. 阅读 [`examples/04-research-agent/main.py`](../../examples/04-research-agent/main.py)，指出它与本章示例相比多了哪些能力（提示：工具数量、结构化输出、报告落盘）。
