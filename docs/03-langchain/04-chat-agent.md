# 3.4 构建聊天 Agent —— 从对话到自主行动

## 📖 导读

前几节我们学习了 Chain、Prompt、记忆、工具等独立概念。现在是时候**把它们组合成一个完整的聊天 Agent**——既能自然对话，又能使用工具，还有记忆能力。

> 🆕 **2026 版重点**：在 **LangChain v1** 中，构建一个"带工具 + 带记忆 + 带流式"的聊天 Agent，不再需要手写 `AgentExecutor` 与工具循环，而是**一个 `create_agent` + 一个 `checkpointer`** 就能搞定。本节的代码全部基于 v1。

---

## 一、前置知识

| 概念 | 章节 | 说明 |
|------|------|------|
| Prompt 与上下文工程 | 2.1 | 控制 Agent 行为 |
| Chain（链） | 2.2 | 用 `\|` 连接多个组件 |
| Agent 架构 | 2.3 | 思考 → 行动 → 观察 循环 |
| 记忆（Memory） | 2.4 | 会话记忆与长期记忆 |
| 工具（Tool） | 3.2 | Agent 调用的外部功能 |
| `create_agent` | 3.1 | v1 标准 Agent 构建方式 |

---

## 二、基础聊天 Agent

### 2.1 最简单版本（纯对话）

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatOpenAI(model="gpt-5.5", temperature=0.7)

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个友好的 AI 助手，名叫 AgentBot。用中文回答用户的问题。"),
    ("human", "{input}"),
])

chat_chain = prompt | llm | StrOutputParser()
print(chat_chain.invoke({"input": "你好，你是谁？"}))
```

### 2.2 多轮对话：用 LangGraph Checkpointer 做记忆

在 v1 中，多轮记忆不再用 `ConversationBufferMemory`，而是交给 **checkpointer**——它会自动把每一步的对话状态持久化：

```python
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver


class ChatAgent:
    """支持多轮对话的聊天 Agent（LangChain v1）"""

    def __init__(self, model: str = "gpt-5.5", system_prompt: str | None = None):
        self.checkpointer = InMemorySaver()          # 生产环境换成 PostgresSaver
        self.agent = create_agent(
            model=model,
            tools=[],
            system_prompt=system_prompt or "你是一个友好的 AI 助手。",
            checkpointer=self.checkpointer,
        )

    def chat(self, session_id: str, user_input: str) -> str:
        config = {"configurable": {"thread_id": session_id}}
        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config,
        )
        return result["messages"][-1].content


# 使用
agent = ChatAgent(system_prompt="你是一个 Python 编程助手。")
print(agent.chat("s1", "我叫小明"))
print(agent.chat("s1", "我叫什么名字？"))   # → 你叫小明
```

> ✅ 同一个 `thread_id` = 同一个会话，跨调用自动保持记忆；不同 `thread_id` 之间完全隔离。

---

## 三、添加流式输出

流式（逐字显示）能显著提升体验。`create_agent` 支持按 `stream_mode` 流式输出：

```python
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver


agent = create_agent(
    model="gpt-5.5",
    tools=[],
    system_prompt="你是一个友好的 AI 助手。",
    checkpointer=InMemorySaver(),
)

config = {"configurable": {"thread_id": "s1"}}

# messages 模式：逐条消息流式；updates 模式：逐节点更新流式
for chunk in agent.stream(
    {"messages": [{"role": "user", "content": "给我讲一个程序员的笑话"}]},
    config,
    stream_mode="messages",
):
    message_chunk, metadata = chunk
    if message_chunk.content:
        print(message_chunk.content, end="", flush=True)
```

> 💡 面向 Web 服务时，可进一步使用 LangGraph 的 **typed streaming（`version="v2"`）**，输出统一为 `StreamPart` 格式（含 `type` / `ns` / `data`），便于前端解析（见 [4.1 LangGraph 基础](../04-langgraph/01-basics.md)）。

---

## 四、添加工具调用能力

这是 Agent 从"聊天"进化为"行动"的关键一步。v1 中，工具循环由 `create_agent` 内置：

```python
from langchain.agents import create_agent
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from datetime import datetime


@tool
def search_web(query: str) -> str:
    """搜索互联网信息，获取最新知识和资料。"""
    return f"关于'{query}'的搜索结果：\n1. AI Agent 是一种...\n2. 相关技术有..."


@tool
def calculate(expression: str) -> str:
    """执行数学计算，支持加减乘除等运算。"""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"计算错误: {e}"


@tool
def get_time(timezone: str = "Asia/Shanghai") -> str:
    """获取指定时区的当前时间。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


agent = create_agent(
    model="gpt-5.5",
    tools=[search_web, calculate, get_time],
    system_prompt="你是一个有用的 AI 助手。需要时主动使用工具回答问题。",
    checkpointer=InMemorySaver(),
)

config = {"configurable": {"thread_id": "s1"}}
result = agent.invoke(
    {"messages": [{"role": "user", "content": "计算 (1234 + 5678) * 3，并告诉我现在的时间"}]},
    config,
)
print(result["messages"][-1].content)
```

**对比旧写法**：

| 环节 | v0.x 旧写法 | v1 新写法 |
|------|-------------|-----------|
| 创建 Agent | `create_tool_calling_agent` + `AgentExecutor` | `create_agent` |
| 工具循环 | 执行器自动跑 | 内置 |
| 中间步骤 | `return_intermediate_steps` | `stream()` 观察每一步 |
| 记忆 | `ConversationBufferMemory` | `checkpointer` |

---

## 五、完整版：记忆 + 工具 + 流式 的聊天 Agent

```python
from datetime import datetime

from langchain.agents import create_agent
from langchain.tools import tool
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.memory import InMemorySaver


@tool
def search_web(query: str) -> str:
    """搜索互联网获取最新信息。当需要最新知识或不确定答案时使用。"""
    return f"【搜索结果】关于 '{query}' 的最新信息已获取..."


@tool
def calculate(expression: str) -> str:
    """数学计算工具。支持 +, -, *, /, **, () 等运算。"""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"计算失败：{e}"


@tool
def get_current_time() -> str:
    """获取当前日期和时间。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class FullChatAgent:
    """完整的聊天 Agent：对话 + 记忆 + 工具 + 流式 + 上下文压缩"""

    def __init__(self, model: str = "gpt-5.5", system_prompt: str | None = None):
        self.system_prompt = system_prompt or (
            "你是一个全能 AI 助手，具备以下能力：\n"
            "1. 自然对话：记住用户说过的重要信息\n"
            "2. 工具使用：搜索、计算、查时间\n"
            "3. 知识问答：基于你的知识回答\n\n"
            "回答规则：用中文、简洁明了；不确定时用工具查证；多步问题分步解决。"
        )
        self.agent = create_agent(
            model=model,
            tools=[search_web, calculate, get_current_time],
            system_prompt=self.system_prompt,
            checkpointer=InMemorySaver(),                 # 会话记忆
            middleware=[
                SummarizationMiddleware(trigger={"tokens": 4000}),  # 长对话自动压缩
            ],
        )

    def chat(self, session_id: str, user_input: str) -> str:
        config = {"configurable": {"thread_id": session_id}}
        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config,
        )
        return result["messages"][-1].content

    def stream_chat(self, session_id: str, user_input: str):
        config = {"configurable": {"thread_id": session_id}}
        for chunk in self.agent.stream(
            {"messages": [{"role": "user", "content": user_input}]},
            config,
            stream_mode="messages",
        ):
            message_chunk, _ = chunk
            if message_chunk.content:
                yield message_chunk.content


# ===== 使用示例 =====
def demo():
    agent = FullChatAgent()
    questions = [
        "你好，我是小明",
        "你能做什么？",
        "计算 25 的平方根乘以 3 的结果",
        "你还记得我叫什么吗？",
    ]
    for q in questions:
        print(f"\n👤 我: {q}")
        print(f"🤖 AI: {agent.chat('demo', q)}")


if __name__ == "__main__":
    demo()
```

---

## 六、会话管理（多用户支持）

`checkpointer` 用 `thread_id` 天然实现了会话隔离，无需自己维护字典：

```python
class SessionManager:
    """多会话管理：不同 thread_id 互相隔离"""

    def __init__(self):
        self.agent = create_agent(
            model="gpt-5.5",
            tools=[search_web, calculate, get_current_time],
            system_prompt="你是用户的私人助手。",
            checkpointer=InMemorySaver(),
        )

    def chat(self, session_id: str, message: str) -> str:
        config = {"configurable": {"thread_id": session_id}}
        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config,
        )
        return result["messages"][-1].content


manager = SessionManager()

# 用户 A
print(manager.chat("user_a", "我喜欢编程"))
print(manager.chat("user_a", "我最大的爱好是什么？"))   # → 编程

# 用户 B（独立记忆）
print(manager.chat("user_b", "我喜欢音乐"))
print(manager.chat("user_b", "我最大的爱好是什么？"))   # → 音乐

# 两用户互不干扰 ✅
```

> 🏭 **生产环境**：把 `InMemorySaver` 换成 `PostgresSaver`，即可获得**跨进程、跨重启**的持久化会话记忆。

```python
from langgraph.checkpoint.postgres import PostgresSaver

with PostgresSaver.from_conn_string("postgresql://user:pass@localhost/agent") as cp:
    cp.setup()
    agent = create_agent(model="gpt-5.5", tools=[...], checkpointer=cp)
```

---

## 七、常见问题与优化

### ❌ 记忆和工具中间步骤混在一起

```python
# 原因：把工具调用的中间消息也当成"对话记忆"
# 解决：v1 的 checkpointer 会区分消息类型，最终回答取最后一条：
final = result["messages"][-1].content
# 需要查看工具调用过程时，遍历 messages 过滤 ToolMessage
```

### ❌ Token 超限

```python
# 双重保险：中间件自动压缩 + 运行期裁剪
middleware=[SummarizationMiddleware(trigger={"tokens": 4000})]
```

### ❌ 工具调用失败 / 模型输出格式错误

- v1 的内置工具循环已能容忍大多数解析问题；
- 若工具本身报错，**在工具内部返回友好错误信息**，而不是抛出异常；
- 需要重试/兜底策略时，用中间件 `wrap_tool_call` 包裹工具调用。

### ❌ 敏感操作（如发邮件）希望人工确认

```python
from langchain.agents.middleware import HumanInTheLoopMiddleware

middleware=[
    HumanInTheLoopMiddleware(tools=["send_email"]),  # 调用前暂停等待审批
]
```

---

## 八、适用场景

| 场景 | 必须的功能 | 可选功能 |
|------|-----------|----------|
| **客服机器人** | 记忆、知识库(RAG) | 人工转接 |
| **编程助手** | 代码执行工具、长记忆 | 流式输出 |
| **个人助理** | 日历/天气/搜索工具 | 多模态 |
| **教育辅导** | 记忆、计算工具 | 结构化输出 |
| **数据分析助手** | 代码执行、文件读写 | 长时运行（durable execution） |

---

## 九、本章总结

| 功能 | v1 实现方式 | 关键代码 |
|------|-------------|----------|
| **基础对话** | Prompt + LLM | `prompt \| llm \| parser` |
| **多轮记忆** | LangGraph Checkpointer | `create_agent(checkpointer=...)` |
| **流式输出** | `agent.stream(..., stream_mode="messages")` | 逐块输出 |
| **工具调用** | `create_agent(tools=[...])` | 内置工具循环 |
| **上下文压缩** | `SummarizationMiddleware` | `trigger={"tokens": 4000}` |
| **人工审批** | `HumanInTheLoopMiddleware` | 敏感工具前暂停 |
| **会话隔离** | `thread_id` | `{"configurable": {"thread_id": ...}}` |

---

## 📝 课后练习

1. **✅ 基础**：用 `create_agent` 构建一个最简单的聊天 Agent，运行 3 轮对话
2. **💡 进阶**：加上 `InMemorySaver`，验证 Agent 能记住之前说过的话
3. **🚀 综合**：实现"记忆 + 工具 + 流式"三位一体的聊天 Agent（参考第五节）
4. **🔍 探索**：把 `InMemorySaver` 换成 `SqliteSaver`，重启程序后验证记忆是否还在
