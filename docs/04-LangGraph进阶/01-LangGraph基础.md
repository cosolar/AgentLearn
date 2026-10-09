# 4.1 LangGraph 基础 —— 从线性链到图工作流

## 📖 导读

> **现实世界的工作流不是线性的——它有分支、有循环、有条件判断，需要一个更强大的编排工具。**

前面学习的 Chain 是线性结构（A → B → C），适合确定性的简单流程。但很多复杂的 Agent 场景需要**条件分支**（如果 X 则走分支 A，否则走分支 B）、**循环**（不断重试直到成功）、**子任务并行**等能力。这就是 **LangGraph** 的用武之地——它用**图（Graph）** 来描述工作流，比线性链强大得多。

---

## 一、前置知识

| 概念 | 章节 | 说明 |
|------|------|------|
| Chain | 2.2 | 线性组件连接 |
| Agent 架构 | 2.3 | Agent 的"思考→行动→观察"循环 |
| State | 2.4 | 工作流中的共享数据状态 |
| Runnable | 3.1 | LangChain 的可运行组件 |

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
│         │                                            │
│         │         ┌─────────────┐                    │
│         └────────▶│  Conditional │                    │
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

### 3.2 状态（State）

State 是图工作流的核心——**所有节点共享同一个状态对象**。

```python
from typing import TypedDict, Annotated, List
import operator

# 定义状态类型
class GraphState(TypedDict):
    # 基础字段
    input: str                           # 输入
    output: str                          # 输出
    messages: Annotated[List, operator.add]  # 消息列表（自动追加）
    steps: int                           # 已执行步数
    is_complete: bool                    # 是否完成
```

> **注意**：`Annotated[List, operator.add]` 表示多个节点可以往同一个列表追加元素，而不是覆盖。

---

## 四、创建第一个图

### 4.1 最简单的图：两个节点顺序执行

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

# 1. 定义状态
class SimpleState(TypedDict):
    input: str
    processed: str
    output: str

# 2. 定义节点函数
def process_input(state: SimpleState) -> dict:
    """节点 A：处理输入"""
    print(f"  [节点A] 处理输入: {state['input']}")
    return {"processed": f"已处理: {state['input']}"}

def generate_output(state: SimpleState) -> dict:
    """节点 B：生成输出"""
    print(f"  [节点B] 基于处理结果生成输出: {state['processed']}")
    return {"output": f"最终结果: {state['processed']}"}

# 3. 构建图
workflow = StateGraph(SimpleState)

# 添加节点
workflow.add_node("process", process_input)
workflow.add_node("generate", generate_output)

# 添加边
workflow.add_edge("process", "generate")  # process → generate
workflow.add_edge("generate", END)         # generate → 结束

# 设置入口
workflow.set_entry_point("process")

# 4. 编译图
app = workflow.compile()

# 5. 执行
result = app.invoke({
    "input": "你好，LangGraph！",
    "processed": "",
    "output": "",
})

print(f"\n最终结果: {result['output']}")
```

**输出**：

```text
  [节点A] 处理输入: 你好，LangGraph！
  [节点B] 基于处理结果生成输出: 已处理: 你好，LangGraph！

最终结果: 最终结果: 已处理: 你好，LangGraph！
```

---

### 4.2 执行流程可视化

```
invoke({"input": "你好"})
    │
    ▼
┌─────────────────────┐
│  set_entry_point     │
│  → "process"         │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Node "process"      │
│  state["processed"]  │  ← 设置值
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
     返回结果
```

---

## 五、LangGraph vs LangChain Chain

| 维度 | LangChain Chain | LangGraph |
|------|----------------|-----------|
| **结构** | 线性管道（A→B→C） | 有向图（支持分支/循环） |
| **状态管理** | 隐式传递 | **显式共享状态** |
| **条件分支** | 需要 RunnableBranch | **原生条件边** |
| **循环** | 不支持 | **原生支持** |
| **并行** | RunnableParallel | Node 天然并行 |
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

## 六、LangGraph v1 核心能力全景（2026）

LangGraph 已发布 **v1 / v1.1**，官方定位是**低层编排运行时（orchestration runtime）**。它与 LangChain v1 的关系是：**LangChain 的 `create_agent` 就构建在 LangGraph 之上**。当你需要更细粒度的控制时，才直接使用 LangGraph。

四大核心能力：

| 能力 | 说明 | 关键词 |
|------|------|--------|
| **持久化（Persistence）** | 每一步状态自动落盘，支持断点恢复 | `checkpointer`、`store` |
| **持久执行（Durable Execution）** | 进程崩溃后可从中断处续跑 | 长时任务、可靠性 |
| **流式（Streaming）** | 实时输出 token / 工具调用 / 推理轨迹 | `stream_mode`、typed streaming v2 |
| **人机协同（Human-in-the-Loop）** | 关键节点暂停，等待人工审批/修改 | `interrupt`、`Command` |

### 6.1 v1.1 的类型化流式（typed streaming v2）

v1.1 引入了更规范的流式输出。向 `stream()` / `astream()` 传入 `version="v2"`，输出会被统一为 **`StreamPart`** 格式，每个分片包含 `type`、`ns`、`data` 字段：

```python
for part in app.stream(
    {"messages": [{"role": "user", "content": "你好"}]},
    stream_mode=["messages", "updates"],
    version="v2",
):
    # part 形如: {"type": "messages", "ns": (), "data": (chunk, metadata)}
    print(part["type"], part["ns"])
```

> 💡 类型化流式让前端/网关可以**稳定地解析**多路流（消息、状态更新、自定义事件），是生产级流式接口的首选。

### 6.2 持久化与断点恢复

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, END

workflow = StateGraph(MyState)
# ... 添加节点与边 ...
app = workflow.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "task-1"}}
app.invoke({"input": "开始"}, config)      # 中途崩溃也不怕
app.invoke({"input": "继续"}, config)      # 从上次状态续跑
```

| Checkpointer | 场景 |
|--------------|------|
| `InMemorySaver` | 开发调试 |
| `SqliteSaver` | 单机持久化 |
| `PostgresSaver` | 生产、多实例 |

### 6.3 人机协同（HITL）

```python
from langgraph.types import interrupt, Command

def review_node(state):
    # 在此处暂停，把决策权交给人类
    decision = interrupt({"question": "是否批准这笔转账？", "amount": state["amount"]})
    return {"approved": decision}

# 恢复执行时传入人工决策
app.invoke(Command(resume=True), config)
```

### 6.4 与 LangChain v1 的关系

| 你的需求 | 选择 |
|----------|------|
| 快速构建标准 Agent（工具循环） | LangChain `create_agent` |
| 精细控制分支/循环/并行 | LangGraph 自定义图 |
| 需要持久化/HITL/时间旅行 | 两者皆可，LangGraph 更底层灵活 |

> 📌 本教程 3.4 节用 `create_agent` + `checkpointer` 构建聊天 Agent，其实已经在用 LangGraph 的能力了。

---

## 七、常见问题

### ❌ State 类型错误

```python
# ❌ 错误：返回的 key 在 State 中未定义
def my_node(state):
    return {"unknown_key": "value"}  # 运行时报错

# ✅ 正确：返回的 key 必须在 State 定义中
def my_node(state):
    return {"output": "value"}  # ✅
```

### ❌ 忘记设置入口点

```python
# ❌ 错误：没有设置入口
workflow = StateGraph(MyState)
workflow.add_node("a", node_a)
workflow.add_node("b", node_b)
workflow.add_edge("a", "b")
workflow.add_edge("b", END)

app = workflow.compile()  # 报错：no entry point

# ✅ 正确：设置入口
workflow.set_entry_point("a")
```

### ❌ 边连接了不存在的节点

```python
# ❌ 错误：node_x 不存在
workflow.add_edge("a", "node_x")

# ✅ 正确：确保添加了所有节点
workflow.add_node("a", node_a)
workflow.add_node("b", node_b)
workflow.add_edge("a", "b")
```

---

## 八、本章总结

| 概念 | 一句话说明 |
|------|------------|
| **StateGraph** | 基于状态共享的图工作流框架 |
| **State** | 所有节点共享的数据，定义为 TypedDict |
| **Node** | 处理函数，接收 state 返回部分更新 |
| **Edge** | 节点间的连接线 |
| **END** | 终止节点，图执行结束 |
| **set_entry_point** | 设置开始节点 |

---

## 📝 课后练习

1. **✅ 基础**：创建一个 3 个节点的顺序执行图（A→B→C），每个节点输出一句话
2. **💡 观察**：使用 `app.get_graph().print_ascii()` 打印图的拓扑结构
3. **🚀 扩展**：在 State 中添加一个 `counter` 字段，每个节点将其值 +1，观察最终结果
4. **🔍 探索**：尝试用 LangGraph 实现和 Chain 相同的功能，对比代码量和可读性
