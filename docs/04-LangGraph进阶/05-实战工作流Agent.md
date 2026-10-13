# 4.5 实战：工作流 Agent —— 构建带人工审批的生产级系统

> 📅 更新至 2026-10 · 技术栈基线见 [知识库大纲](../知识库大纲.md)

## 📖 导读

> **本章把前四节综合起来，构建一个真正可用于生产的"内容创作工作流 Agent"——它包含子图、循环、持久化，并在发布前引入人工审批（HITL）。**

我们要做的系统能：接收主题 → 自动调研 → 生成大纲 → 逐节写作 → 质量审查 → **暂停等待人工批准** → 输出最终内容。核心新增能力是 **中断/恢复（interrupt/resume）** 与 **持久化**，这正是 LangGraph 区别于普通 Chain 的地方。

---

## 一、前置知识

| 概念 | 章节 | 说明 |
|------|------|------|
| 状态管理 | 4.2 | `TypedDict` + reducer |
| checkpointer / store | 4.2 | 会话持久化与长期记忆 |
| 条件路由与循环 | 4.3 | 分支、迭代 |
| 子图 | 4.4 | 模块化 |
| `create_agent` | 3.4 | 标准 Agent 入口 |

---

## 二、需求与流程设计

### 2.1 功能清单

| 阶段 | 功能 | 说明 |
|------|------|------|
| 调研 | 用 Agent 搜索资料 | 由一个 `create_agent` 构建的研究员完成 |
| 规划 | 生成内容大纲 | 结构化组织 |
| 写作 | 逐节写作（循环） | 直到写完所有章节 |
| 审查 | 质量评估 | 打分 + 反馈 |
| **审批** | **人工确认（HITL）** | **中断等待批准，可驳回返工** |
| 输出 | 格式化输出 | 生成最终版本 |

### 2.2 流程图

```text
START
  │
  ▼
research ──▶ outline ──▶ write_section ◀──┐
                              │  (continue)│
                              ▼            │
                         route_writing ────┘
                              │ (complete)
                              ▼
                           review ──▶ approval  ◀──┐
                                         │         │
                             ┌───────────┴─────┐   │
                      (approved)          (rejected)
                             │                 │
                             ▼                 ▼
                          finalize          revise ──▶（回到 review）
                             │
                             ▼
                            END
```

---

## 三、状态定义

```python
from typing import TypedDict


class WorkflowState(TypedDict):
    # 输入
    topic: str

    # 研究阶段
    research_summary: str

    # 写作阶段
    outline: list[str]
    draft: str
    current_section: int
    total_sections: int

    # 审查阶段
    quality_score: int
    feedback: str
    revision_count: int
    max_revisions: int

    # 审批阶段（HITL）
    approved: bool

    # 输出
    final_content: str
```

> ⚠️ **纪律**：后面每个节点读写的字段都必须在此处声明，否则运行时报 `KeyError` / `InvalidUpdateError`。

---

## 四、研究节点：用 `create_agent` 做调研

调研这种"需要工具循环"的任务，直接交给 LangChain v1 的 `create_agent`，再把它包进图的节点里。

```python
import os

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI


def get_llm(temperature: float = 0.0) -> ChatOpenAI:
    """统一从环境变量读取模型配置"""
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL_NAME", "gpt-5.5"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        temperature=temperature,
    )


@tool
def search_web(query: str) -> str:
    """搜索互联网获取与主题相关的资料。"""
    # 实际项目接入 Tavily / Bing / SerpAPI；此处为可运行的占位实现
    return f"关于「{query}」的资料：\n1. 核心概念\n2. 最新进展\n3. 实践案例"


# 研究 Agent：内置"模型 → 工具 → 回传模型"循环
research_agent = create_agent(
    model=get_llm(),
    tools=[search_web],
    system_prompt="你是资深研究员。围绕给定主题检索资料，输出结构化的中文研究摘要。",
)


def research_node(state: WorkflowState) -> dict:
    """图节点：调用研究 Agent"""
    result = research_agent.invoke({
        "messages": [{"role": "user", "content": f"请研究主题：{state['topic']}"}]
    })
    return {"research_summary": result["messages"][-1].content}
```

> 📌 完整的研究 Agent 示例见 [examples/04-research-agent](../../examples/04-research-agent/)，多 Agent 协作见 [examples/06-multi-agent](../../examples/06-multi-agent/)。

---

## 五、写作 / 审查 / 审批节点

```python
from langgraph.types import interrupt, Command


def outline_node(state: WorkflowState) -> dict:
    """规划：生成大纲"""
    outline = [
        f"1. {state['topic']} 概述",
        f"2. {state['topic']} 核心概念",
        f"3. {state['topic']} 实践案例",
        "4. 总结与展望",
    ]
    return {"outline": outline, "total_sections": len(outline), "current_section": 0}


def write_section_node(state: WorkflowState) -> dict:
    """写作：写一节（循环执行）"""
    idx = state["current_section"]
    section = state["outline"][idx]
    chunk = f"\n## {section}\n\n本节围绕「{section}」展开……\n"
    return {
        "draft": state["draft"] + chunk,
        "current_section": idx + 1,
    }


def route_writing(state: WorkflowState) -> str:
    """写作循环路由"""
    return "complete" if state["current_section"] >= state["total_sections"] else "continue"


def review_node(state: WorkflowState) -> dict:
    """审查：打分 + 反馈"""
    score = min(10, max(1, len(state["draft"]) // 100))
    feedback = "内容长度充足" if len(state["draft"]) > 300 else "建议补充内容"
    return {"quality_score": score, "feedback": feedback}


def approval_node(state: WorkflowState) -> dict:
    """审批：中断并等待人工决策（HITL）"""
    decision = interrupt({
        "question": f"是否批准发布？质量评分：{state['quality_score']}/10",
        "feedback": state["feedback"],
        "draft_preview": state["draft"][:200],
    })
    # decision 是人工通过 Command(resume=...) 传回的值
    return {
        "approved": bool(decision.get("approved")),
        "feedback": decision.get("feedback", state["feedback"]),
    }


def route_after_approval(state: WorkflowState) -> str:
    """审批后路由：通过→输出；驳回且未超限→返工；超限→强制输出"""
    if state["approved"]:
        return "finalize"
    if state["revision_count"] >= state["max_revisions"]:
        return "finalize"
    return "revise"


def revise_node(state: WorkflowState) -> dict:
    """返工：根据反馈优化"""
    return {
        "draft": state["draft"] + f"\n\n> 根据审批意见优化：{state['feedback']}\n",
        "revision_count": state["revision_count"] + 1,
    }


def finalize_node(state: WorkflowState) -> dict:
    """输出：组装最终内容"""
    content = (
        f"# {state['topic']}\n\n"
        f"{state['research_summary']}\n\n---\n"
        f"{state['draft']}\n\n---\n"
        f"*质量评分：{state['quality_score']}/10 · 返工 {state['revision_count']} 次*"
    )
    return {"final_content": content}
```

---

## 六、组装主图（含持久化）

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver


def create_workflow():
    builder = StateGraph(WorkflowState)

    builder.add_node("research", research_node)
    builder.add_node("outline", outline_node)
    builder.add_node("write_section", write_section_node)
    builder.add_node("review", review_node)
    builder.add_node("approval", approval_node)
    builder.add_node("revise", revise_node)
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "research")
    builder.add_edge("research", "outline")
    builder.add_edge("outline", "write_section")

    # 写作循环
    builder.add_conditional_edges(
        "write_section",
        route_writing,
        {"continue": "write_section", "complete": "review"},
    )

    builder.add_edge("review", "approval")

    # 审批后的分支
    builder.add_conditional_edges(
        "approval",
        route_after_approval,
        {"finalize": "finalize", "revise": "revise"},
    )
    builder.add_edge("revise", "review")     # 返工后重新审查
    builder.add_edge("finalize", END)

    # 持久化：HITL 必须依赖 checkpointer
    return builder.compile(checkpointer=InMemorySaver())


app = create_workflow()
app.get_graph().print_ascii()
```

---

## 七、运行：中断 → 人工审批 → 恢复

```python
from langgraph.types import Command


def run():
    config = {"configurable": {"thread_id": "content-001"}}

    initial = {
        "topic": "AI Agent 开发指南",
        "research_summary": "",
        "outline": [],
        "draft": "",
        "current_section": 0,
        "total_sections": 0,
        "quality_score": 0,
        "feedback": "",
        "revision_count": 0,
        "max_revisions": 2,
        "approved": False,
        "final_content": "",
    }

    # 第一次执行：会停在 approval 的 interrupt 处
    result = app.invoke(initial, config)
    interrupts = result.get("__interrupt__")
    if interrupts:
        payload = interrupts[0].value
        print("⏸️ 等待人工审批：", payload["question"])
        print("草稿预览：", payload["draft_preview"][:60], "...")

        # —— 模拟人工决策 ——
        human_decision = {"approved": False, "feedback": "请补充实践案例"}

        # 恢复执行：把决策传回去
        result = app.invoke(Command(resume=human_decision), config)
        print("返工后质量评分：", result["quality_score"])

    # 再次审批（此时模拟批准）
    interrupts = result.get("__interrupt__")
    if interrupts:
        result = app.invoke(
            Command(resume={"approved": True, "feedback": "通过"}),
            config,
        )

    print("\n✅ 最终内容：")
    print(result["final_content"][:300], "...")


if __name__ == "__main__":
    run()
```

**关键点**：

1. `app.invoke(...)` 第一次返回时，结果里带 `__interrupt__`，说明图**暂停**了；
2. 用**同一个 `thread_id`** + `Command(resume=...)` 恢复，`interrupt()` 的返回值就是 `resume` 的内容；
3. 图状态全程由 `checkpointer` 保存，即使进程重启，只要 `thread_id` 不变就能续跑。

---

## 八、生产级持久化

```python
# 开发：内存
from langgraph.checkpoint.memory import InMemorySaver
app = builder.compile(checkpointer=InMemorySaver())

# 单机：SQLite（跨重启保留）
# uv add langgraph-checkpoint-sqlite
from langgraph.checkpoint.sqlite import SqliteSaver
with SqliteSaver.from_conn_string("checkpoints.db") as cp:
    app = builder.compile(checkpointer=cp)

# 生产：PostgreSQL（多实例、高可用）
# uv add langgraph-checkpoint-postgres
from langgraph.checkpoint.postgres import PostgresSaver
with PostgresSaver.from_conn_string("postgresql://user:pass@localhost/agent") as cp:
    cp.setup()
    app = builder.compile(checkpointer=cp)
```

| 存储 | 适用 | 特性 |
|------|------|------|
| `InMemorySaver` | 开发调试 | 进程结束即丢失 |
| `SqliteSaver` | 单机 / 桌面应用 | 文件持久化 |
| `PostgresSaver` | 生产 / 多实例 | 高可用、可横向扩展 |

---

## 九、另一种 HITL：工具级人工审批（`create_agent` + 中间件）

若你用的是 `create_agent`（而非手写图），LangChain v1 提供了**中间件**来实现"敏感工具调用前暂停等待审批"：

```python
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.checkpoint.memory import InMemorySaver


@tool
def send_email(to: str, body: str) -> str:
    """发送邮件。"""
    return f"邮件已发送至 {to}"


guarded_agent = create_agent(
    model=get_llm(),
    tools=[send_email],
    system_prompt="你是行政助手。",
    checkpointer=InMemorySaver(),                 # HITL 依赖 checkpointer
    middleware=[
        HumanInTheLoopMiddleware(tools=["send_email"]),   # 调用前暂停等待审批
    ],
)

config = {"configurable": {"thread_id": "mail-1"}}
result = guarded_agent.invoke(
    {"messages": [{"role": "user", "content": "给 boss@corp.com 发一封周报邮件"}]},
    config,
)
# 触发中断后，用 Command(resume=...) 批准或拒绝
result = guarded_agent.invoke(Command(resume=True), config)
```

| 方案 | 粒度 | 适用 |
|------|------|------|
| 手写图 + `interrupt()` | 节点级 / 流程级 | 复杂工作流、多阶段审批 |
| `create_agent` + `HumanInTheLoopMiddleware` | 工具级 | 标准 Agent 的敏感操作 |

---

## 十、扩展方向

| 扩展 | 实现 |
|------|------|
| **真实检索** | 把 `search_web` 换成 Tavily / Bing / SerpAPI |
| **LLM 写作** | 用 `get_llm().invoke(...)` 替换占位文案 |
| **并行写作** | 用 `Send` 把各章节并行分发给 `write_section`（见 4.3） |
| **长期记忆** | `compile(store=...)` 记住用户偏好（见 4.2） |
| **可观测** | 接入 LangSmith 追踪每一步与中断 |

---

## 十一、本章小结

| 要点 | 说明 |
|------|------|
| **子图 / 循环** | 研究、写作、审查各司其职，写作用循环逐节推进 |
| **`create_agent`** | 调研节点直接复用标准 Agent（工具循环内置） |
| **中断/恢复** | `interrupt()` 暂停，`Command(resume=...)` 恢复 |
| **人工审批（HITL）** | 审批节点暂停，把决策权交给人类 |
| **持久化** | `InMemorySaver` / `SqliteSaver` / `PostgresSaver` |
| **`thread_id`** | 同一线程才能恢复中断现场 |
| **工具级 HITL** | `create_agent` + `HumanInTheLoopMiddleware` |

---

## 📝 课后练习

1. **✅ 基础**：运行本章工作流，观察 `__interrupt__` 的输出与恢复后的结果
2. **💡 改进**：把 `write_section` 的占位文案换成真实 LLM 生成（提示词包含研究摘要）
3. **🚀 挑战**：用 `Send` 把各章节写作改为**并行**，并用 `operator.add` 汇总草稿
4. **🔍 探索**：把 `InMemorySaver` 换成 `SqliteSaver`，中断后**重启程序**再用同一 `thread_id` 恢复，验证状态是否还在
