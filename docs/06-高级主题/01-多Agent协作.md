# 6.1 多 Agent 协作 —— 从单打独斗到团队作战

> 📅 更新至 2026-10 · 技术栈基线见 [教程大纲](../教程大纲.md)

## 📖 导读

> **一个 Agent 是聪明的，一群分工明确的 Agent 可以是智能的——但前提是你真的需要一群人。**

在 LangChain v1 里，构建一个 Agent 只要一个 `create_agent`；当任务复杂到"一个 Agent 忙不过来"时，我们才会引入**多 Agent 协作**。本节聚焦工程实践：**什么时候该拆、怎么拆、用什么编排**。所有可运行代码均基于 `langchain.agents.create_agent` + **LangGraph**（supervisor / handoff / 群聊 / `Send` fan-out），不再依赖旧版手写执行器与 ReAct 构建方式。

---

## 一、前置知识

| 概念 | 章节 | 说明 |
|------|------|------|
| `create_agent` | 3.4 | v1 标准 Agent 构建方式（内置工具循环） |
| Checkpointer | 3.4 / 4.1 | 会话记忆与状态持久化 |
| StateGraph | 4.1 / 4.2 | 图工作流编排 |
| 路由与循环 | 4.3 | 条件边、循环、终止条件 |
| 子图 | 4.4 | 把 Agent 作为子图复用 |

---

## 二、先榨干单 Agent：什么时候**不该**拆

多 Agent 不是免费的午餐。每多一个 Agent，就多一次 LLM 调用、多一段上下文传递、多一处失败点。**在拆之前，先把单 Agent 做到极致。**

### 2.1 优先尝试的"单 Agent 增强"

| 手段 | 做法 | 说明 |
|------|------|------|
| **更好的 Prompt** | 明确角色、步骤、输出格式 | 大多数"能力不足"其实是 Prompt 不清 |
| **加工具** | 让单 Agent 调用检索 / 计算 / API | 工具弥补知识盲区 |
| **加中间件** | `SummarizationMiddleware` 压缩长对话 | 缓解上下文窗口压力 |
| **结构化输出** | `response_format` 约束结果 | 减少格式漂移 |
| **更强模型** | 复杂任务换旗舰模型 | 有时比拆成多 Agent 更便宜 |

### 2.2 该拆的 4 个信号

| 信号 | 说明 | 典型拆法 |
|------|------|----------|
| **上下文超限** | 单 Agent 要同时装下检索结果、历史、工具输出 | 拆出专职"检索 Agent"，只回传摘要 |
| **工具过多** | 工具数 > 10–15，选择准确率骤降 | 按领域拆成多个"工具子集 Agent" |
| **角色冲突** | 同一 Prompt 既要"大胆创作"又要"严格审查" | 拆成写作 / 审查两个 Agent |
| **需要并行** | 多个子任务互不依赖，可同时进行 | `Send` fan-out 并行 |

> ⚠️ **反模式**：为了"看起来高级"而拆——把一个简单问答拆成 5 个 Agent，结果延迟翻 3 倍、成本翻 5 倍，质量却没提升。**先量化单 Agent 的瓶颈，再决定是否拆。**

---

## 三、四种协作拓扑

```text
① Supervisor（主管调度）      ② Handoff（移交）
     ┌──────────┐                 A ──"接下来交给你"──▶ B
     │Supervisor│
     └┬───┬───┬─┘              ③ Group Chat（群聊）
      ▼   ▼   ▼                    A ⇄ B ⇄ C（轮流发言）
    A    B    C
                              ④ Send fan-out（扇出）
   成员做完都回到主管              ┌─▶ W1 ─┐
                                  输入 ─▶ W2 ─┼─▶ 汇总
                                  └─▶ W3 ─┘
```

| 拓扑 | 控制中心 | 适用场景 | LangGraph 实现 |
|------|----------|----------|----------------|
| **Supervisor** | 一个主管 Agent | 任务可分解、需要动态决策 | `StateGraph` + `Command` 路由 |
| **Handoff** | 无中心，Agent 互相移交 | 客服升级、专家转接 | `Command(goto=...)` |
| **Group Chat** | 轮流 / 选举发言 | 头脑风暴、辩论、评审 | 条件边 + 轮次上限 |
| **Send fan-out** | 无中心，一次性并行 | map-reduce、批量处理 | `Send` + reducer |

---

## 四、实战一：Supervisor 多 Agent 内容工厂

我们用 **LangGraph 的 supervisor 模式**搭建一个"研究 → 撰写 → 审查"的内容团队。核心是：**子 Agent 各自用 `create_agent` 构建，主管用一个 `Command` 决定下一个执行者**。

### 4.1 架构

```text
用户需求
   │
   ▼
┌────────────┐   Command(goto=...)   ┌──────────────┐
│ Supervisor │ ────────────────────▶ │ researcher   │
│  (主管)     │ ◀──────────────────── │ writer       │
└────────────┘   执行完回到主管        │ reviewer     │
                                      └──────────────┘
```

### 4.2 完整实现（`team.py`）

```python
"""LangGraph Supervisor 多 Agent 协作（LangChain v1 + LangGraph v1）"""
from __future__ import annotations

import os
from typing import Annotated, Literal, TypedDict

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command
from pydantic import BaseModel, Field

load_dotenv()


def build_llm(temperature: float = 0.3) -> ChatOpenAI:
    """统一从 LLM_* 环境变量读取模型配置"""
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL_NAME", "gpt-5.5"),
        api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_API_BASE"),
        temperature=temperature,
    )


llm = build_llm()


class TeamState(TypedDict):
    """团队共享状态：消息历史 + 当前决策"""

    messages: Annotated[list, add_messages]
    next: str


# ---- 1. 三个专业子 Agent：各自独立的 system prompt ----
researcher = create_agent(
    model=llm,
    tools=[],
    system_prompt="你是研究员，负责把主题拆解为结构化要点，输出简洁的要点列表。",
)
writer = create_agent(
    model=llm,
    tools=[],
    system_prompt="你是写手，负责把研究要点写成通顺、有条理的短文。",
)
reviewer = create_agent(
    model=llm,
    tools=[],
    system_prompt="你是审查员，负责指出文章的问题并给出 1-10 的评分。",
)


def run_subagent(agent, state: TeamState) -> dict:
    """运行子 Agent，只把【新增】消息写回状态，避免历史重复累积"""
    result = agent.invoke({"messages": state["messages"]})
    new_messages = result["messages"][len(state["messages"]):]
    return {"messages": new_messages}


def researcher_node(state: TeamState) -> dict:
    return run_subagent(researcher, state)


def writer_node(state: TeamState) -> dict:
    return run_subagent(writer, state)


def reviewer_node(state: TeamState) -> dict:
    return run_subagent(reviewer, state)


# ---- 2. 主管：用结构化输出决定下一个执行者 ----
class Route(BaseModel):
    """主管的路由决策"""

    next: Literal["researcher", "writer", "reviewer", "FINISH"] = Field(
        description="下一个要执行的成员；任务全部完成时返回 FINISH"
    )


router = llm.with_structured_output(Route)

SUPERVISOR_PROMPT = (
    "你是一个内容团队的主管，成员职责如下：\n"
    "- researcher：调研并输出要点\n"
    "- writer：根据要点撰写文章\n"
    "- reviewer：审查文章质量\n"
    "根据当前对话进展决定下一步交给谁；全部完成后返回 FINISH。\n"
    "避免让同一成员连续执行两次以上。"
)


def supervisor_node(state: TeamState) -> Command:
    """主管节点：返回 Command 实现动态移交（handoff）"""
    decision = router.invoke(
        [{"role": "system", "content": SUPERVISOR_PROMPT}, *state["messages"]]
    )
    goto = END if decision.next == "FINISH" else decision.next
    return Command(goto=goto, update={"next": decision.next})


# ---- 3. 组装图 ----
def build_team():
    graph = StateGraph(TeamState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("writer", writer_node)
    graph.add_node("reviewer", reviewer_node)

    graph.add_edge(START, "supervisor")
    # 每个成员执行完都回到主管，由主管决定下一步
    graph.add_edge("researcher", "supervisor")
    graph.add_edge("writer", "supervisor")
    graph.add_edge("reviewer", "supervisor")
    return graph.compile()


if __name__ == "__main__":
    team = build_team()
    final = team.invoke(
        {
            "messages": [
                {"role": "user", "content": "写一篇 200 字的短文，介绍 AI Agent 的典型用途。"}
            ]
        }
    )
    print(final["messages"][-1].content)
```

> 💡 **关键点**：
> - 子 Agent 用 `create_agent` 构建，天然是**可运行的 LangGraph 图**，可直接 `invoke`；
> - 主管用 `Command(goto=...)` 实现 **handoff**，无需为每条路径手写条件边；
> - `run_subagent` 只回写新增消息，否则 `add_messages` 会把整段历史重复追加。

---

## 五、实战二：`Send` fan-out 并行研究（map-reduce）

当子任务互不依赖时，**并行**能显著降低总延迟。LangGraph 用 `Send` 把一个任务扇出成多个并行分支，再用 reducer 汇总结果。

```python
"""Send fan-out：并行处理多个子主题后汇总（map-reduce）"""
from __future__ import annotations

import os
from operator import add
from typing import Annotated, TypedDict

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL_NAME", "gpt-5.5"),
    api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_API_BASE"),
    temperature=0.3,
)

worker = create_agent(
    model=llm,
    tools=[],
    system_prompt="你是研究助理，针对给定的子主题输出 3 条要点。",
)


class MapState(TypedDict):
    """map-reduce 状态：subtopics 被扇出，results 用 add 归并"""

    topic: str
    subtopics: list[str]
    results: Annotated[list[str], add]


def plan(state: MapState) -> dict:
    """把大主题拆成子主题（此处用规则演示，可替换为 LLM 规划）"""
    return {
        "subtopics": [f"{state['topic']} — 方向{i}" for i in range(1, 4)],
        "results": [],
    }


def fan_out(state: MapState):
    """为每个子主题生成一个 Send 任务，实现并行扇出"""
    return [Send("worker", {"topic": sub}) for sub in state["subtopics"]]


def worker_node(state: dict) -> dict:
    """处理单个子主题（输入是 Send 传入的局部状态）"""
    result = worker.invoke(
        {"messages": [{"role": "user", "content": state["topic"]}]}
    )
    return {"results": [result["messages"][-1].content]}


def reduce_node(state: MapState) -> dict:
    """汇总所有并行结果"""
    merged = "\n\n".join(state["results"])
    summary = llm.invoke(f"请把以下要点归纳成一段结论：\n{merged}")
    return {"results": [summary.content]}


def build_graph():
    graph = StateGraph(MapState)
    graph.add_node("plan", plan)
    graph.add_node("worker", worker_node)
    graph.add_node("reduce", reduce_node)

    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", fan_out, ["worker"])  # 扇出
    graph.add_edge("worker", "reduce")                        # 扇入
    graph.add_edge("reduce", END)
    return graph.compile()


if __name__ == "__main__":
    app = build_graph()
    out = app.invoke({"topic": "AI Agent 的企业落地", "subtopics": [], "results": []})
    print(out["results"][-1])
```

> 📌 `results` 使用 `Annotated[list[str], add]` 作为 reducer：多个 worker 并行写回时会被**自动拼接**，无需加锁。若不加 reducer，并发写入会报冲突。

---

## 六、实战三：群聊（Group Chat）

群聊让多个 Agent **轮流发言**，适合头脑风暴、辩论与评审。关键工程点是**终止条件**——必须限制轮次，否则 Agent 之间会无限对话。

```python
"""群聊：提案者 / 批评者 / 主持人轮流发言，达到轮次上限即结束"""
from __future__ import annotations

import os
from typing import Annotated, TypedDict

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

MAX_TURNS = 6  # 硬性轮次上限，防止无限对话

llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL_NAME", "gpt-5.5"),
    api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_API_BASE"),
    temperature=0.5,
)

proposer = create_agent(model=llm, tools=[], system_prompt="你是提案者，提出具体方案。")
critic = create_agent(model=llm, tools=[], system_prompt="你是批评者，指出方案的漏洞。")
moderator = create_agent(
    model=llm,
    tools=[],
    system_prompt="你是主持人，总结共识；当讨论可以结束时，回复中必须包含 DONE。",
)


class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
    turns: int


def speak(agent, state: ChatState) -> dict:
    """让某个 Agent 发言，并把轮次 +1"""
    result = agent.invoke({"messages": state["messages"]})
    new_messages = result["messages"][len(state["messages"]):]
    return {"messages": new_messages, "turns": state.get("turns", 0) + 1}


def proposer_node(state: ChatState) -> dict:
    return speak(proposer, state)


def critic_node(state: ChatState) -> dict:
    return speak(critic, state)


def moderator_node(state: ChatState) -> dict:
    return speak(moderator, state)


def route_after_moderator(state: ChatState):
    """终止条件：达到轮次上限，或主持人宣布 DONE"""
    last = state["messages"][-1].content
    if state["turns"] >= MAX_TURNS or "DONE" in last:
        return END
    return "proposer"


def build_chat():
    graph = StateGraph(ChatState)
    graph.add_node("proposer", proposer_node)
    graph.add_node("critic", critic_node)
    graph.add_node("moderator", moderator_node)

    graph.add_edge(START, "proposer")
    graph.add_edge("proposer", "critic")
    graph.add_edge("critic", "moderator")
    graph.add_conditional_edges("moderator", route_after_moderator, ["proposer", END])
    return graph.compile()


if __name__ == "__main__":
    chat = build_chat()
    final = chat.invoke(
        {"messages": [{"role": "user", "content": "讨论：客服 Agent 该不该接入退款能力？"}],
         "turns": 0}
    )
    print(final["messages"][-1].content)
```

> ⚠️ **群聊三条铁律**：① 必须有**轮次 / 预算上限**；② 主持人要有**明确的结束信号**（如 `DONE`）；③ 发言内容尽量**结构化精简**，避免"传话游戏"导致上下文爆炸。

---

## 七、工程要点

| 要点 | 建议 |
|------|------|
| **通信开销** | 消息结构化、精简；子 Agent 只回传摘要，不传全量中间过程 |
| **终止条件** | 明确轮次 / token / 时间预算上限，`Command` 与条件边都要能收敛 |
| **状态设计** | 用 reducer（如 `add_messages`、`operator.add`）处理并发写入 |
| **可观测性** | 用 OTel GenAI 语义约定追踪跨 Agent 链路（见 [7.3 可观测性与监控](../07-生产部署/03-可观测性与监控.md)） |
| **成本控制** | 子 Agent 用便宜模型，汇总 / 决策用旗舰模型（见 [6.3 成本控制](./03-成本控制.md)） |
| **降级策略** | 某个子 Agent 失败时，主管应能跳过或重试，而非整体崩溃 |

---

## 八、2026 多 Agent 生态与协议

多 Agent 已从"框架内协作"走向"跨框架、跨组织协作"。

### 8.1 主流框架格局

| 框架 | 定位 | 特点 |
|------|------|------|
| **LangGraph** | 图编排运行时 | 精细控制、持久化、HITL，本教程首选 |
| **AgentScope** | 消息驱动分布式 Agent | 多 Agent 通信、分布式部署（见 [8.13 AgentScope 教程](../08-生态与选型/AgentScope教程/index.md)） |
| **Microsoft Agent Framework** | 企业级 Agent 框架 | AutoGen + Semantic Kernel 合并 |
| **CrewAI** | 角色化协作 | 上手快，适合角色分工 |
| **OpenAI Agents SDK** | 轻量编排 | handoff、tracing |

> 💡 多 Agent 模式横向对比见 [8.2 多 Agent 模式](../08-生态与选型/生态调研/02-多Agent模式.md)。

### 8.2 用 A2A 协议实现跨组织协作

**A2A（Agent-to-Agent）** 让不同厂商、不同框架的 Agent 通过统一协议互相调用，突破了"同框架才能协作"的限制：

```text
你的 Agent ──A2A──▶ 合作方的 Agent ──▶ 完成任务并返回结果
```

> 📌 详见 [8.11 A2A 协议与互操作](../08-生态与选型/协议标准/02-A2A协议与互操作.md)；工具接入标准见 [8.10 MCP 协议完全指南](../08-生态与选型/协议标准/01-MCP协议完全指南.md)。

---

## 九、本章小结

| 知识点 | 一句话说明 |
|--------|------------|
| **先榨干单 Agent** | 大多数问题靠 Prompt / 工具 / 中间件就能解决，别急着拆 |
| **Supervisor** | 一个主管 Agent 动态决定下一个执行者，最实用的拓扑 |
| **Handoff** | 用 `Command(goto=...)` 在 Agent 间移交控制权 |
| **Group Chat** | 多 Agent 轮流发言，必须设轮次上限 |
| **Send fan-out** | 用 `Send` + reducer 并行处理互不依赖的子任务 |
| **子 Agent 构建** | 统一用 `create_agent`，各自独立 system prompt 与工具集 |

---

## 📝 课后练习

1. **✅ 基础**：运行 Supervisor 示例，把主管 Prompt 改为"最多调用一次 reviewer"，观察输出变化。
2. **💡 改进**：给 `researcher` 子 Agent 添加一个 `search_web` 工具（用 `create_agent(tools=[...])`），让研究基于真实检索。
3. **🚀 挑战**：把 `Send` fan-out 的 `plan` 节点换成 LLM 动态拆解子主题，并用 `reducer` 归并结果。
4. **🔍 探索**：为群聊加上"主持人选举下一位发言人"的机制（用 LLM 结构化输出决定 `next`），替代固定轮转。
