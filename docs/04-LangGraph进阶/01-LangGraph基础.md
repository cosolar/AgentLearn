# 4.1 LangGraph 基础 —— 从线性链到图工作流

> 📅 更新至 2026-10 · 技术栈基线见 [知识库大纲](../知识库大纲.md)

## 📖 导读

> **现实世界的工作流不是线性的——它有分支、有循环、有条件判断，需要一个更强大的编排工具。**

前面学习的 Chain 是线性结构（A → B → C），适合确定性的简单流程。但很多复杂的 Agent 场景需要**条件分支**（如果 X 则走分支 A，否则走分支 B）、**循环**（不断重试直到成功）、**并行**等能力。这正是 **LangGraph** 的用武之地——它用**图（Graph）** 来描述工作流。

LangGraph 是**低层编排运行时（orchestration runtime）**。LangChain v1 的 `create_agent` 就构建在它之上；当你需要更细粒度的控制（分支、循环、并行、持久化、人机协同）时，直接使用 LangGraph。

> 📌 本章基线：`langgraph>=1.2.15`、`langgraph-checkpoint>=4.3.0`、Python >= 3.12、`uv`。新路径统一为 `from langgraph.checkpoint.memory import InMemorySaver`。
>
> ⚠️ **1.2+ 的两个包结构变化**（最容易踩的坑）：
> 1. **`langgraph` 顶层不再导出 `StateGraph` 等符号**——必须从子模块导入：`from langgraph.graph import StateGraph, START, END`，**不能**写 `from langgraph import StateGraph`。
> 2. **`langgraph.prebuilt` 已拆为独立发行包 `langgraph-prebuilt`**（它是 `langgraph` 的硬依赖，会自动装上）。`from langgraph.prebuilt import ToolNode, tools_condition` 写法不变；但如果你用 `--no-deps` 安装，需手动补 `langgraph-prebuilt`。

---

## 一、前置知识

| 概念 | 章节 | 说明 |
|------|------|------|
| Chain | 2.2 | 线性组件连接 |
| Agent 架构 | 2.3 | Agent 的"思考→行动→观察"循环 |
| State | 2.4 | 工作流中的共享数据状态 |
| Runnable | 3.1 | LangChain 的可运行组件 |
| `create_agent` | 3.4 | 构建在 LangGraph 之上的标准 Agent |

---

## 二、为什么需要 LangGraph？

### 2.1 Chain 的局限

```text
线性 Chain 能做的：
A → B → C → D
✅ 简单的顺序处理

线性 Chain 做不到的：
      ┌── B ──┐
A ────┤       ├─── D
      └── C ──┘
❌ 并行分支

A → B → C
     ↑    │
     └────┘
❌ 循环

A → 判断 → B (如果是)
         → C (如果不是)
❌ 条件分支
```

### 2.2 LangGraph 能做什么

```text
LangGraph 是一个"图计算框架"，能表达：

1. 顺序执行：A → B → C （和 Chain 一样）
2. 条件分支：A → 判断 → [条件1] → B / [条件2] → C
3. 循环：A → B → 判断 → 回到 B / 结束
4. 并行：A → [B, C] (同时执行)
5. 子图：主图中嵌入一个完整的子工作流
6. 动态分发：根据状态在运行时决定生成多少个下游任务（Send）
```

---

## 三、核心概念

### 3.1 图的三要素

```text
┌─────────────────────────────────────────────────────┐
│                      StateGraph                      │
│                                                      │
│   ┌─────────┐      ┌─────────┐      ┌─────────┐    │
│   │  Node A  │─────▶│  Node B  │─────▶│  Node C  │    │
│   │ (处理)   │ Edge │ (处理)   │ Edge │ (处理)   │    │
│   └─────────┘      └─────────┘      └─────────┘    │
│         ▲                                            │
│         │         ┌─────────────┐                    │
│   __START__ ─────▶│  Conditional │                    │
│                   │   Edge (判断) │                    │
│                   └──────┬───────┘                    │
│                          ▼                            │
│                   ┌──────────┐                        │
│                   │  __END__  │  (终止节点)            │
│                   └──────────┘                        │
│                                                      │
│  ┌─────────────────────┐                             │
│  │  State (共享状态)    │ ← 所有节点都可以读写       │
│  └─────────────────────┘                             │
└─────────────────────────────────────────────────────┘
```

| 概念 | 类比 | 说明 |
|------|------|------|
| **State（状态）** | 白板 | 所有节点共享的数据容器 |
| **Node（节点）** | 工人 | 处理状态的函数单元 |
| **Edge（边）** | 传送带 | 控制节点间的执行顺序 |
| **Conditional Edge** | 分拣员 | 根据状态决定下一步走向 |
| **START / END** | 出入口 | 特殊节点，分别代表图入口与终止 |

### 3.2 状态（State）

State 是图工作流的核心——**所有节点共享同一个状态对象**，用 `TypedDict` 定义。

```python
from typing import TypedDict, Annotated, List
import operator

# 定义状态类型
class GraphState(TypedDict):
    input: str                                  # 输入
    output: str                                 # 输出
    messages: Annotated[List, operator.add]     # 消息列表（自动追加）
    steps: int                                  # 已执行步数
    is_complete: bool                           # 是否完成
```

> **注意**：`Annotated[List, operator.add]` 表示多个节点可以往同一个列表追加元素，而不是覆盖。细节见 [4.2 状态管理与节点](./02-状态管理与节点.md)。

---

## 四、创建第一个图

### 4.1 最简单的图：两个节点顺序执行

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END


# 1. 定义状态
class SimpleState(TypedDict):
    input: str
    processed: str
    output: str


# 2. 定义节点函数（接收状态，返回"部分更新"的 dict）
def process_input(state: SimpleState) -> dict:
    """节点 A：处理输入"""
    print(f"  [节点A] 处理输入: {state['input']}")
    return {"processed": f"已处理: {state['input']}"}


def generate_output(state: SimpleState) -> dict:
    """节点 B：生成输出"""
    print(f"  [节点B] 基于处理结果生成输出: {state['processed']}")
    return {"output": f"最终结果: {state['processed']}"}


# 3. 构建图
builder = StateGraph(SimpleState)
builder.add_node("process", process_input)      # 添加节点
builder.add_node("generate", generate_output)
builder.add_edge(START, "process")              # 入口：START → process
builder.add_edge("process", "generate")         # process → generate
builder.add_edge("generate", END)               # generate → 结束

# 4. 编译图（编译后可调用）
app = builder.compile()

# 5. 可视化拓扑结构
print("图结构:")
app.get_graph().print_ascii()

# 6. 执行
result = app.invoke({
    "input": "你好，LangGraph！",
    "processed": "",
    "output": "",
})

print(f"\n最终结果: {result['output']}")
```

**输出**：

```text
图结构:
    +-----------+
    | __start__ |
    +-----------+
          *
          *
          *
    +---------+
    | process |
    +---------+
          *
          *
          *
    +----------+
    | generate |
    +----------+
          *
          *
          *
     +---------+
     | __end__ |
     +---------+

  [节点A] 处理输入: 你好，LangGraph！
  [节点B] 基于处理结果生成输出: 已处理: 你好，LangGraph！

最终结果: 最终结果: 已处理: 你好，LangGraph！
```

> ✅ `app.invoke(input)` 返回的是**执行结束后的完整状态**。初始输入是"部分状态"，未提供的字段按 schema 初始化（列表用空列表、字符串用默认值等）。

### 4.2 执行流程可视化

```text
invoke({"input": "你好"})
    │
    ▼
┌─────────────────────┐
│  START → "process"   │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Node "process"      │
│  state["processed"]  │  ← 返回 {"processed": ...}
│  = "已处理: 你好"    │
└────────┬────────────┘
         │  Edge: process → generate
         ▼
┌─────────────────────┐
│  Node "generate"     │
│  state["output"]     │
│  = "最终结果: ..."   │
└────────┬────────────┘
         │  Edge: generate → END
         ▼
     返回完整状态
```

---

## 五、编译后的三种调用方式

`builder.compile()` 返回的对象（习惯命名为 `app`）同时支持同步与异步调用：

```python
# 1. invoke：一次性拿到最终状态
result = app.invoke({"input": "你好", "processed": "", "output": ""})

# 2. batch：批量并发执行多组输入
results = app.batch([
    {"input": "问题1", "processed": "", "output": ""},
    {"input": "问题2", "processed": "", "output": ""},
])

# 3. stream：流式观察每一步（详见 4.3 的类型化流式）
for chunk in app.stream(
    {"input": "你好", "processed": "", "output": ""},
    stream_mode="updates",
):
    print(chunk)   # 形如 {"process": {"processed": "..."}}
```

> 💡 生产环境更常用 `ainvoke` / `astream`（异步版本），避免阻塞事件循环。

---

## 六、LangGraph vs LangChain Chain

| 维度 | LangChain Chain | LangGraph |
|------|----------------|-----------|
| **结构** | 线性管道（A→B→C） | 有向图（支持分支/循环） |
| **状态管理** | 隐式传递 | **显式共享状态** |
| **条件分支** | 需要 RunnableBranch | **原生条件边** |
| **循环** | 不支持 | **原生支持** |
| **并行** | RunnableParallel | 节点天然并行 |
| **持久化 / HITL** | 无 | **原生支持** |
| **复杂度** | 低 | 中-高 |
| **适用场景** | 确定性的简单流程 | 复杂的 Agent 工作流 |

### 什么时候用 Chain，什么时候用 Graph？

```text
✅ 用 Chain（简单确定）：
输入 → 翻译 → 总结 → 输出

✅ 用 Graph（复杂多变）：
输入 → 判断是否需要搜索
     → 是：搜索 → 分析 → 回答
     → 否：直接回答
     → 如果回答不够好，再搜索一次（循环）
```

---

## 七、LangGraph v1 核心能力全景（2026）

LangGraph 已发布 **v1 / v1.1**，官方定位是**低层编排运行时**。四大核心能力：

| 能力 | 说明 | 关键词 |
|------|------|--------|
| **持久化（Persistence）** | 每一步状态自动落盘，支持断点恢复 | `checkpointer`、`store` |
| **持久执行（Durable Execution）** | 进程崩溃后可从中断处续跑 | 长时任务、可靠性 |
| **流式（Streaming）** | 实时输出 token / 工具调用 / 推理轨迹 | `stream_mode`、typed streaming v2 |
| **人机协同（Human-in-the-Loop）** | 关键节点暂停，等待人工审批/修改 | `interrupt`、`Command` |

### 7.1 v1.1 的类型化流式（typed streaming v2）

向 `stream()` / `astream()` 传入 `version="v2"`，输出会被统一为 **`StreamPart`** 格式，每个分片包含 `type`、`ns`、`data` 字段：

```python
for part in app.stream(
    {"input": "你好", "processed": "", "output": ""},
    stream_mode=["messages", "updates"],
    version="v2",
):
    # part 形如: {"type": "updates", "ns": (), "data": {...}}
    print(part["type"], part["ns"], part["data"])
```

> 💡 类型化流式让前端/网关可以**稳定地解析**多路流（消息、状态更新、自定义事件），是生产级流式接口的首选。

### 7.2 持久化与断点恢复

```python
from langgraph.checkpoint.memory import InMemorySaver

builder = StateGraph(SimpleState)
# ... 添加节点与边 ...
app = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "task-1"}}
app.invoke({"input": "开始", "processed": "", "output": ""}, config)  # 中途崩溃也不怕
app.invoke({"input": "继续", "processed": "", "output": ""}, config)  # 从上次状态续跑
```

| Checkpointer | 场景 |
|--------------|------|
| `InMemorySaver` | 开发调试 |
| `SqliteSaver` | 单机持久化 |
| `PostgresSaver` | 生产、多实例 |

### 7.3 人机协同（HITL）

```python
from langgraph.types import interrupt, Command

def review_node(state):
    # 在此处暂停，把决策权交给人类
    decision = interrupt({"question": "是否批准这笔转账？", "amount": state["amount"]})
    return {"approved": decision}

# 恢复执行时传入人工决策
app.invoke(Command(resume=True), config)
```

### 7.4 与 LangChain v1 的关系

| 你的需求 | 选择 |
|----------|------|
| 快速构建标准 Agent（工具循环） | LangChain `create_agent` |
| 精细控制分支/循环/并行 | LangGraph 自定义图 |
| 需要持久化/HITL/时间旅行 | 两者皆可，LangGraph 更底层灵活 |

> 📌 本教程 [3.4 构建聊天 Agent](../03-LangChain实战/04-构建聊天Agent.md) 用 `create_agent` + `checkpointer` 构建聊天 Agent，其实已经在用 LangGraph 的能力了。

---

## 八、常见问题

### ❌ State 类型错误：返回了未定义的字段

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

class MyState(TypedDict):
    output: str

# ❌ 错误：返回的 key 在 State 中未定义 → 抛出 InvalidUpdateError
def bad_node(state: MyState) -> dict:
    return {"unknown_key": "value"}

# ✅ 正确：返回的 key 必须在 State 定义中
def good_node(state: MyState) -> dict:
    return {"output": "value"}
```

### ❌ 忘记连接入口

```python
# ❌ 错误：没有任何边从 START 出发 → 编译/执行时报"缺少入口"
builder = StateGraph(MyState)
builder.add_node("a", node_a)
builder.add_node("b", node_b)
builder.add_edge("a", "b")
builder.add_edge("b", END)
app = builder.compile()          # ❌ 没有 START → "a"

# ✅ 正确：显式从 START 连到入口节点
builder.add_edge(START, "a")
```

### ❌ 边连接了不存在的节点

```python
# ❌ 错误：node_x 不存在
builder.add_edge("a", "node_x")   # 编译时报错

# ✅ 正确：确保添加了所有节点
builder.add_node("a", node_a)
builder.add_node("b", node_b)
builder.add_edge("a", "b")
```

---

## 九、本章小结

| 概念 | 一句话说明 |
|------|------------|
| **StateGraph** | 基于状态共享的图工作流框架 |
| **State** | 所有节点共享的数据，定义为 `TypedDict` |
| **Node** | 处理函数，接收 state 返回部分更新 dict |
| **Edge** | 节点间的连接线 |
| **START / END** | 图的入口 / 终止特殊节点 |
| **compile** | 把 builder 编译成可调用的 `app` |
| **invoke / stream** | 一次性执行 / 流式观察每一步 |
| **print_ascii()** | 打印图的拓扑结构，便于调试 |

---

## 📝 课后练习

1. **✅ 基础**：创建一个 3 个节点的顺序执行图（START→A→B→C→END），每个节点输出一句话
2. **💡 观察**：使用 `app.get_graph().print_ascii()` 打印图的拓扑结构，并尝试 `draw_mermaid()` 生成 Mermaid 图
3. **🚀 扩展**：在 State 中添加一个 `counter` 字段，每个节点将其值 +1，观察最终结果
4. **🔍 探索**：用 `app.stream(..., stream_mode="updates")` 逐节点观察状态变化，再对比 `invoke` 的返回
