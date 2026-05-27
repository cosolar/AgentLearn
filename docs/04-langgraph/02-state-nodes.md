# 4.2 状态管理与节点 —— 深入理解图的"血液"和"细胞"

## 📖 导读

在 LangGraph 中，**State（状态）是图的血液，Node（节点）是图的细胞**。状态贯穿整个工作流，节点是状态的处理单元。理解二者的设计和交互方式，是构建复杂 Agent 工作流的基础。

---

## 一、前置知识

| 概念 | 章节 | 说明 |
|------|------|------|
| State 基础 | 4.1 | TypedDict 定义状态 |
| Node 基础 | 4.1 | 处理状态的函数 |
| Annotated | 4.1 | 用 operator.add 实现追加 |

---

## 二、状态（State）详解

### 2.1 State 的定义方式

```python
from typing import TypedDict, Annotated, List, Optional
import operator
from langgraph.graph import StateGraph, END


# 方式一：TypedDict（推荐，类型安全）
class AgentState(TypedDict):
    """Agent 的完整状态"""
    # 基础信息
    input: str                          # 用户输入
    output: str                         # 最终输出
    
    # 消息列表（自动追加，不是覆盖）
    messages: Annotated[List[dict], operator.add]
    
    # 任务状态
    current_step: int                   # 当前步数
    max_steps: int                      # 最大步数
    is_complete: bool                   # 是否完成
    
    # 工具调用
    tool_calls: Annotated[List[dict], operator.add]
    
    # 中间结果
    intermediate_results: Annotated[List[str], operator.add]
    
    # 错误信息
    error: Optional[str]                # 可选字段


# 方式二：Dataclass（适合使用默认值）
from dataclasses import dataclass, field

@dataclass
class AgentStateDataclass:
    input: str = ""
    output: str = ""
    messages: List[dict] = field(default_factory=list)
    current_step: int = 0
    max_steps: int = 10
    is_complete: bool = False
```

### 2.2 状态更新机制

节点函数通过**返回字典**来更新状态，返回的 key 必须包含在 State 定义中。

```python
class MyState(TypedDict):
    counter: int
    items: Annotated[List[str], operator.add]
    status: str


# 节点 1：更新基础字段（覆盖）
def node_increment(state: MyState) -> dict:
    """将 counter +1（覆盖旧值）"""
    return {"counter": state["counter"] + 1}


# 节点 2：追加到列表（使用 operator.add）
def node_add_item(state: MyState) -> dict:
    """追加一项到 items（自动追加，不是覆盖）"""
    return {"items": [f"item_{state['counter']}"]}
    # items 原本是 ["a"] → 现在是 ["a", "item_1"]


# 节点 3：不返回任何更新
def node_noop(state: MyState) -> None:
    """什么也不做"""
    return None  # 状态不变
    # 或直接省略 return


# 节点 4：返回多个字段
def node_multi_update(state: MyState) -> dict:
    """同时更新多个字段"""
    return {
        "counter": state["counter"] + 1,
        "status": "processing",
    }
```

### 2.3 Annotated 机制详解

`Annotated[type, reducer]` 中的 `reducer` 决定了**如何合并多个节点的更新**。

```python
from typing import TypedDict, Annotated
import operator

class ReducerDemo(TypedDict):
    # 1. operator.add：追加模式
    #    多个节点都返回该字段时，结果会合并
    items: Annotated[List[str], operator.add]
    #    Node A: {"items": ["a"]}
    #    Node B: {"items": ["b"]}
    #    → 最终 items = ["a", "b"] ✅ 合并了
    
    # 2. 默认（不注解）：覆盖模式
    #    多个节点都返回该字段时，后面的覆盖前面的
    name: str
    #    Node A: {"name": "Alice"}
    #    Node B: {"name": "Bob"}
    #    → 最终 name = "Bob" ❌ Alice 被覆盖了
    
    # 3. 自定义 reducer
    counter: Annotated[int, lambda a, b: a + b]  # 自定义求和
```

---

## 三、节点（Node）详解

### 3.1 节点的本质

节点就是一个**函数**（或可调用对象）：

- **输入**：当前状态（TypedDict）
- **输出**：部分状态更新（dict）或 None

```python
# 3种合法的 Node 形式

# 1. 普通函数（最常用）
def my_node(state: MyState) -> dict:
    return {"output": "结果"}

# 2. 异步函数（需要 async 运行时）
async def my_async_node(state: MyState) -> dict:
    await asyncio.sleep(0.1)
    return {"output": "结果"}

# 3. 可调用类
class MyNode:
    def __call__(self, state: MyState) -> dict:
        return {"output": "结果"}
```

### 3.2 节点最佳实践

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from typing import TypedDict, Annotated, List
import operator

# 定义状态
class AgentState(TypedDict):
    messages: Annotated[List[dict], operator.add]
    next_action: str
    result: str


# 最佳实践 1：一个节点只做一件事
def call_llm_node(state: AgentState) -> dict:
    """节点：调用 LLM（职责单一）"""
    llm = ChatOpenAI(model="gpt-4o")
    response = llm.invoke(state["messages"])
    return {
        "messages": [response],
        "next_action": "analyze",  # 告诉路由下一步去哪
    }


def analyze_result_node(state: AgentState) -> dict:
    """节点：分析 LLM 输出（职责单一）"""
    last_message = state["messages"][-1]
    content = last_message.content
    
    if "需要搜索" in content:
        return {"result": "需要搜索", "next_action": "search"}
    else:
        return {"result": "直接回答", "next_action": "respond"}


# 最佳实践 2：统一的错误处理
def safe_node(state: AgentState) -> dict:
    """带错误处理的节点"""
    try:
        # 核心逻辑
        result = do_something(state)
        return {"result": result, "error": None}
    except Exception as e:
        return {"result": None, "error": str(e)}
```

### 3.3 节点间的数据流

```python
# 构建图来演示节点间数据流
workflow = StateGraph(AgentState)

# 入口节点
workflow.add_node("start", lambda s: {"messages": [], "next_action": ""})
workflow.add_node("llm", call_llm_node)
workflow.add_node("analyze", analyze_result_node)

workflow.set_entry_point("start")
workflow.add_edge("start", "llm")
workflow.add_edge("llm", "analyze")
workflow.add_edge("analyze", END)

app = workflow.compile()

# 查看图结构
print(app.get_graph().draw_ascii())
```

---

## 四、状态持久化

```python
from langgraph.checkpoint import MemorySaver

# 内存持久化（默认，程序重启后丢失）
memory = MemorySaver()

app = workflow.compile(checkpointer=memory)

# 带 checkpoint 的执行
config = {"configurable": {"thread_id": "session_1"}}
result = app.invoke(
    {"input": "你好", "messages": []},
    config=config,
)

# 第二次执行会使用之前保存的状态
result2 = app.invoke(
    {"input": "继续", "messages": []},
    config=config,  # 相同 thread_id
)
```

---

## 五、复杂 State 设计模式

### 5.1 分层状态设计

```python
class ResearchState(TypedDict):
    """研究任务的 State"""
    
    # 第一层：任务信息
    topic: str                           # 研究主题
    depth: str                           # 研究深度（浅/深）
    
    # 第二层：执行状态
    plan: List[str]                      # 研究计划
    current_step_index: int              # 当前步索引
    completed_steps: Annotated[List[str], operator.add]
    
    # 第三层：研究结果
    search_results: Annotated[List[dict], operator.add]
    report_draft: str                    # 报告草稿
    report_final: str                    # 最终报告
    
    # 第四层：元信息
    total_tokens_used: int
    start_time: float
    error: Optional[str]
```

### 5.2 条件字段

```python
class ConditionalState(TypedDict):
    """不同条件下包含不同字段的状态"""
    
    # 必须字段
    input: str
    task_type: str  # "qa", "search", "write"
    
    # QA 场景
    answer: Optional[str]
    
    # 搜索场景
    query: Optional[str]
    search_results: Optional[List[str]]
    
    # 写作场景
    outline: Optional[List[str]]
    draft: Optional[str]
```

---

## 六、调试技巧

```python
# 1. 打印图结构
print(app.get_graph().draw_ascii())

# 2. 逐节点调试
def debug_node(state: dict) -> dict:
    """调试用节点：打印当前状态"""
    print(f"🔍 当前状态:")
    for key, value in state.items():
        if isinstance(value, list) and len(value) > 3:
            print(f"   {key}: [{len(value)} items] {value[:2]}...")
        else:
            print(f"   {key}: {value}")
    return {}  # 不修改状态

# 3. 流式执行
for output in app.stream({"input": "测试"}, config):
    for node_name, state_update in output.items():
        print(f"节点 [{node_name}] 更新: {state_update}")
```

---

## 七、常见问题

### ❌ 节点返回了 State 中未定义的字段

```python
class MyState(TypedDict):
    name: str

def bad_node(state: MyState) -> dict:
    return {"unknown_field": "xxx"}  # ❌ 运行时错误

# ✅ 只返回 State 中定义的字段
def good_node(state: MyState) -> dict:
    return {"name": "Alice"}  # ✅
```

### ❌ 使用 operator.add 但返回了非列表

```python
class MyState(TypedDict):
    items: Annotated[List[str], operator.add]

def bad_node(state: MyState) -> dict:
    return {"items": "single_item"}  # ❌ 类型错误

def good_node(state: MyState) -> dict:
    return {"items": ["single_item"]}  # ✅
```

---

## 八、本章总结

| 概念 | 要点 |
|------|------|
| **State** | 共享数据结构，所有节点可以读写 |
| **更新规则** | 返回字典，只更新指定字段 |
| **operator.add** | 追加到列表（不覆盖） |
| **Node** | 单一职责的处理函数 |
| **持久化** | MemorySaver 实现状态持久化 |
| **调试** | draw_ascii() 可视化 + stream() 逐节点 |

---

## 📝 课后练习

1. **✅ 基础**：定义一个包含 5 个字段的 State，创建 3 个节点分别更新不同字段
2. **💡 对比**：对比 `operator.add` 和普通字段在多个节点更新时的行为差异
3. **🚀 挑战**：设计一个"带重试计数"的状态，实现一个节点最多重试 3 次的逻辑
4. **🔍 探索**：使用 MemorySaver 实现状态的持久化，验证 thread_id 的隔离效果
