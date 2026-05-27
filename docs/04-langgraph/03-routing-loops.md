# 4.3 条件路由与循环 —— 让工作流"活"起来

## 📖 导读

> **顺序执行是线性的，条件路由和循环让工作流有了"判断力"和"耐力"。**

前面的例子中，节点都是固定顺序执行的（A→B→C）。但真实世界的流程充满了**分支**——"如果 A 条件成立走这条路，否则走那条路"，以及**循环**——"如果结果不够好，重试一次"。LangGraph 的**条件边（Conditional Edge）** 让这些变为可能。

---

## 一、前置知识

| 概念 | 章节 | 说明 |
|------|------|------|
| State | 4.2 | 共享状态，条件判断的依据 |
| Node | 4.2 | 图中的处理单元 |
| Edge | 4.1 | 节点的连接线 |

---

## 二、条件路由（Conditional Edge）

### 2.1 基本概念

条件路由就像铁路的道岔——根据状态来决定下一步走哪条路。

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Literal


class RouterState(TypedDict):
    input: str
    sentiment: str  # "positive", "negative", "neutral"
    result: str


# 路由函数：根据情感倾向决定下一步
def route_by_sentiment(state: RouterState) -> Literal["positive_handler", "negative_handler", "neutral_handler"]:
    """路由函数，返回值必须是已注册的节点名（或 END）"""
    sentiment = state["sentiment"]
    
    if sentiment == "positive":
        return "positive_handler"
    elif sentiment == "negative":
        return "negative_handler"
    else:
        return "neutral_handler"


# 3 个不同的处理节点
def positive_handler(state: RouterState) -> dict:
    return {"result": f"👍 正面反馈处理: {state['input']}"}

def negative_handler(state: RouterState) -> dict:
    return {"result": f"👎 负面反馈处理，需要跟进: {state['input']}"}

def neutral_handler(state: RouterState) -> dict:
    return {"result": f"➖ 中性反馈: {state['input']}"}


# 构建带条件路由的图
workflow = StateGraph(RouterState)

workflow.add_node("analyze", lambda s: {"sentiment": "positive"})  # 模拟情感分析
workflow.add_node("positive_handler", positive_handler)
workflow.add_node("negative_handler", negative_handler)
workflow.add_node("neutral_handler", neutral_handler)

workflow.set_entry_point("analyze")

# 条件边：从 analyze 节点出发，根据情感路由
workflow.add_conditional_edges(
    "analyze",               # 从哪里出发
    route_by_sentiment,      # 路由函数
    {
        "positive_handler": "positive_handler",
        "negative_handler": "negative_handler",
        "neutral_handler": "neutral_handler",
    }
)

# 所有处理节点最终都指向 END
workflow.add_edge("positive_handler", END)
workflow.add_edge("negative_handler", END)
workflow.add_edge("neutral_handler", END)

app = workflow.compile()
```

---

### 2.2 路由函数的三种写法

```python
# 写法 1：返回节点名字符串（最常用）
def simple_router(state) -> str:
    if state["value"] > 0:
        return "positive_branch"
    return "negative_branch"

# 写法 2：返回 Literal 类型（类型安全）
from typing import Literal

def typed_router(state) -> Literal["branch_a", "branch_b", "branch_c"]:
    if state["value"] == 0:
        return "branch_a"
    elif state["value"] < 0:
        return "branch_b"
    else:
        return "branch_c"

# 写法 3：返回特殊值 END
def router_with_end(state) -> str:
    if state["is_complete"]:
        return END  # 直接结束
    return "continue_node"
```

### 2.3 常用的路由场景

```python
class TaskState(TypedDict):
    input: str
    task_type: str      # "qa", "search", "code", "translate"
    requires_tool: bool
    has_error: bool
    retry_count: int


# 场景 1：按任务类型路由
def route_by_task_type(state: TaskState) -> str:
    """根据任务类型路由到不同的处理器"""
    routing = {
        "qa": "qa_agent",
        "search": "search_agent",
        "code": "code_agent",
        "translate": "translate_agent",
    }
    return routing.get(state["task_type"], "default_agent")


# 场景 2：是否需要工具
def route_tool_needed(state: TaskState) -> str:
    """根据是否需要工具来路由"""
    if state["requires_tool"]:
        return "tool_executor"
    return "direct_responder"


# 场景 3：错误/重试路由
def route_error(state: TaskState) -> str:
    """错误处理路由"""
    if state["has_error"]:
        if state["retry_count"] < 3:
            return "retry_node"      # 重试
        else:
            return "error_handler"   # 超过重试次数，交给错误处理
    return "success_handler"
```

---

## 三、循环（Loop）

### 3.1 基本循环

```python
class LoopState(TypedDict):
    counter: int
    max_count: int
    result: str


def worker_node(state: LoopState) -> dict:
    """工作节点"""
    new_counter = state["counter"] + 1
    print(f"  第 {new_counter}/{state['max_count']} 轮")
    return {"counter": new_counter}


def should_continue(state: LoopState) -> str:
    """判断是否继续循环"""
    if state["counter"] >= state["max_count"]:
        return "end"
    return "continue"


# 构建带循环的图
workflow = StateGraph(LoopState)

workflow.add_node("worker", worker_node)

workflow.set_entry_point("worker")

# 条件边实现循环
workflow.add_conditional_edges(
    "worker",
    should_continue,
    {
        "continue": "worker",  # 回到自己 → 循环
        "end": END,            # 结束
    }
)

app = workflow.compile()

result = app.invoke({
    "counter": 0,
    "max_count": 3,
    "result": "",
})
print(f"完成！共执行 {result['counter']} 轮")
```

**输出**：

```text
  第 1/3 轮
  第 2/3 轮
  第 3/3 轮
完成！共执行 3 轮
```

---

### 3.2 Agent 工作流中的 ReAct 循环

这是 LangGraph 最强大的应用之一——用图实现 ReAct 模式。

```python
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from typing import TypedDict, Annotated, List, Literal
import operator
import json


class AgentState(TypedDict):
    messages: Annotated[List[dict], operator.add]
    max_iterations: int
    iteration_count: int


# 定义工具
@tool
def search_web(query: str) -> str:
    """搜索互联网"""
    return f"关于 '{query}' 的搜索结果..."

@tool
def calculate(expr: str) -> str:
    """数学计算"""
    return str(eval(expr))


# 节点 1：调用 LLM 思考
def call_model(state: AgentState) -> dict:
    """LLM 思考并决定下一步行动"""
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    llm_with_tools = llm.bind_tools([search_web, calculate])
    
    response = llm_with_tools.invoke(state["messages"])
    
    return {
        "messages": [response],
        "iteration_count": state["iteration_count"] + 1,
    }


# 节点 2：执行工具
def execute_tools(state: AgentState) -> dict:
    """执行 LLM 请求的工具调用"""
    last_message = state["messages"][-1]
    tool_messages = []
    
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        
        if tool_name == "search_web":
            result = search_web.invoke(tool_args)
        elif tool_name == "calculate":
            result = calculate.invoke(tool_args)
        else:
            result = f"未知工具: {tool_name}"
        
        tool_messages.append(ToolMessage(
            content=str(result),
            tool_call_id=tool_call["id"],
        ))
    
    return {"messages": tool_messages}


# 路由：是否继续循环
def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """判断：LLM 是否还需要调用工具？"""
    last_message = state["messages"][-1]
    
    # 超过最大迭代次数
    if state["iteration_count"] >= state["max_iterations"]:
        return "__end__"
    
    # LLM 没有请求工具调用 → 结束
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return "__end__"
    
    # 还有工具调用 → 继续循环
    return "tools"


# 构建 ReAct 图
workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("tools", execute_tools)

workflow.set_entry_point("agent")

# agent → 条件路由 → tools（继续）或 END（结束）
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        "__end__": END,
    }
)

# tools → agent（回到思考）
workflow.add_edge("tools", "agent")

app = workflow.compile()

# 执行
result = app.invoke({
    "messages": [HumanMessage(content="计算 123 * 456 的结果，然后搜索 AI Agent 的信息")],
    "max_iterations": 5,
    "iteration_count": 0,
})

for msg in result["messages"]:
    if isinstance(msg, HumanMessage):
        print(f"👤 {msg.content}")
    elif isinstance(msg, AIMessage) and msg.content:
        print(f"🤖 {msg.content[:100]}")
    elif isinstance(msg, ToolMessage):
        print(f"🛠️  {msg.content[:100]}")
```

---

## 四、条件路由 + 循环的完整示例

```python
class WorkflowState(TypedDict):
    input: str
    stage: str           # "analyze", "search", "generate", "review"
    search_results: Annotated[List[str], operator.add]
    draft: str
    review_score: int    # 1-10
    revision_count: int
    max_revisions: int
    is_approved: bool


def analyze_input(state: WorkflowState) -> dict:
    """分析输入，决定是否需要搜索"""
    return {"stage": "search" if "?" in state["input"] else "generate"}


def route_from_analyze(state: WorkflowState) -> str:
    """分析后的路由"""
    return state["stage"]  # "search" 或 "generate"


def search_node(state: WorkflowState) -> dict:
    """搜索节点"""
    return {
        "search_results": [f"关于 {state['input']} 的结果"],
        "stage": "generate",
    }


def generate_node(state: WorkflowState) -> dict:
    """生成节点"""
    context = "\n".join(state["search_results"])
    return {
        "draft": f"基于输入 '{state['input']}' 和上下文 '{context}' 生成的回答",
        "stage": "review",
    }


def review_node(state: WorkflowState) -> dict:
    """审查节点"""
    # 简化：根据内容长度打分
    score = min(10, len(state["draft"]) // 10)
    return {
        "review_score": score,
        "revision_count": state["revision_count"] + 1,
    }


def route_from_review(state: WorkflowState) -> str:
    """审查后的路由"""
    if state["review_score"] >= 7:
        return "approved"
    elif state["revision_count"] >= state["max_revisions"]:
        return "max_reached"
    else:
        return "needs_revision"


workflow = StateGraph(WorkflowState)

workflow.add_node("analyze", analyze_input)
workflow.add_node("search", search_node)
workflow.add_node("generate", generate_node)
workflow.add_node("review", review_node)

workflow.set_entry_point("analyze")

# 分析后的条件路由
workflow.add_conditional_edges(
    "analyze",
    route_from_analyze,
    {"search": "search", "generate": "generate"},
)

workflow.add_edge("search", "generate")
workflow.add_edge("generate", "review")

# 审查后的条件路由（含循环）
workflow.add_conditional_edges(
    "review",
    route_from_review,
    {
        "approved": END,
        "needs_revision": "generate",    # 循环回 generate
        "max_reached": END,
    }
)

app = workflow.compile()

# 查看图结构
print("图结构:")
print(app.get_graph().draw_ascii())
```

---

## 五、循环的终止条件

```python
class SafeLoopState(TypedDict):
    counter: int
    max_iterations: int
    is_converged: bool  # 是否收敛


def safe_loop_router(state: SafeLoopState) -> str:
    """安全终止的循环路由"""
    # 条件 1：达到最大迭代次数
    if state["counter"] >= state["max_iterations"]:
        return END
    
    # 条件 2：已收敛（任务完成）
    if state["is_converged"]:
        return END
    
    # 条件 3：继续
    return "loop_node"
```

**永远记得设置循环终止条件！**

---

## 六、最佳实践

| 实践 | 说明 |
|------|------|
| **总是设置 max_iterations** | 防止无限循环导致的 token 浪费和超时 |
| **路由函数保持简单** | 复杂的路由逻辑应放在节点中完成 |
| **使用 Literal 类型** | 让 IDE 能自动补全和检查 |
| **记录循环次数** | 在 State 中跟踪迭代次数，便于调试 |
| **错误退出** | 总是为异常情况设计退出路径 |

---

## 七、本章总结

| 概念 | 一句话说明 |
|------|------------|
| **条件边** | 根据状态值决定下一步走向哪个节点 |
| **路由函数** | 返回目标节点名字符串的函数 |
| **循环** | 条件边指向自己或其他节点 |
| **ReAct 循环** | Agent→Tool→Agent 的思考行动循环 |
| **终止条件** | 防止无限循环的安全机制 |

---

## 📝 课后练习

1. **✅ 基础**：实现一个"情感分析 → 条件路由"的图，根据情感走不同分支
2. **💡 进阶**：实现一个"最多重试 3 次"的循环，如果节点返回 error 则重试
3. **🚀 挑战**：用 LangGraph 实现一个完整的 ReAct Agent（思考→工具→思考→...→回答）
4. **🔍 探索**：使用 `app.get_graph().draw_mermaid()` 生成 Mermaid 流程图，在浏览器中查看
