# 4.4 子图与模块化 —— 构建可复用的工作流组件

## 📖 导读

> **当一张图变得太大时，就该拆分了。子图就是 LangGraph 的"函数"——可复用、可组合、可独立测试。**

随着 Agent 系统的复杂度增加，一张图可能包含几十个节点。把相关节点封装成**子图**，可以显著提升代码的可维护性和可复用性。就像你不会把整个程序写在一个函数里一样，你也不该把整个工作流放在一张图里。

---

## 一、前置知识

| 概念 | 章节 | 说明 |
|------|------|------|
| State | 4.2 | 节点共享的状态 |
| Node | 4.1 | 图中的处理单元 |
| Conditional Edge | 4.3 | 条件路由 |

---

## 二、为什么需要子图？

### 2.1 模块化的好处

```text
❌ 一张大图：
input → analyze → search → parse → filter → rank → 
generate → review → revise → review → output

✅ 拆分子图：
input → [Research Subgraph] → [Writing Subgraph] → output
            ├── search               ├── generate
            ├── parse                ├── review
            ├── filter               └── revise
            └── rank
```

| 好处 | 说明 |
|------|------|
| **可复用** | 子图可以在不同项目中使用 |
| **可测试** | 子图可以独立测试 |
| **可维护** | 每个子图职责清晰 |
| **可组合** | 子图可以像积木一样拼装 |

---

## 三、创建子图

### 3.1 基本用法

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict


# 第一步：定义子图的状态
class ResearchState(TypedDict):
    topic: str
    search_results: list
    analyzed: bool


# 第二步：创建子图
def create_research_subgraph() -> StateGraph:
    """创建研究子图：搜索和分析"""
    
    # 子图内部的节点
    def search_node(state: ResearchState) -> dict:
        """搜索节点"""
        print(f"  [子图] 搜索: {state['topic']}")
        return {"search_results": [f"结果1", "结果2"]}
    
    def analyze_node(state: ResearchState) -> dict:
        """分析节点"""
        print(f"  [子图] 分析: {len(state['search_results'])} 个结果")
        return {"analyzed": True}
    
    # 构建子图
    subgraph = StateGraph(ResearchState)
    subgraph.add_node("search", search_node)
    subgraph.add_node("analyze", analyze_node)
    subgraph.set_entry_point("search")
    subgraph.add_edge("search", "analyze")
    subgraph.add_edge("analyze", END)
    
    return subgraph


# 第三步：在主图中使用子图
class MainState(TypedDict):
    topic: str
    output: str


# 创建主图
workflow = StateGraph(MainState)

# 子图实例
research_subgraph = create_research_subgraph()

# 将子图作为节点添加到主图
workflow.add_node("research", research_subgraph.compile())

def output_node(state: MainState) -> dict:
    return {"output": f"研究报告完成: {state['topic']}"}

workflow.add_node("output", output_node)

workflow.set_entry_point("research")
workflow.add_edge("research", "output")
workflow.add_edge("output", END)

app = workflow.compile()

# 执行
result = app.invoke({"topic": "AI Agent", "output": ""})
print(f"结果: {result['output']}")
```

**输出**：

```text
  [子图] 搜索: AI Agent
  [子图] 分析: 2 个结果
结果: 研究报告完成: AI Agent
```

---

### 3.2 子图访问主图状态

子图不仅能访问自己的状态，还能**读取主图的状态字段**。

```python
class MainState(TypedDict):
    topic: str
    depth: str          # "basic" 或 "deep"
    search_results: list
    report: str


# 子图状态（继承主图的部分字段）
class SearchState(TypedDict):
    topic: str          # 从主图传入
    depth: str          # 从主图传入
    search_results: list


def create_search_subgraph():
    """创建搜索子图"""
    
    def search_basic(state: SearchState) -> dict:
        return {"search_results": [f"[基础]关于 {state['topic']} 的搜索结果"]}
    
    def search_deep(state: SearchState) -> dict:
        return {"search_results": [f"[深度]关于 {state['topic']} 的详细搜索结果"]}
    
    def router(state: SearchState) -> str:
        if state["depth"] == "deep":
            return "deep_search"
        return "basic_search"
    
    subgraph = StateGraph(SearchState)
    subgraph.add_node("basic_search", search_basic)
    subgraph.add_node("deep_search", search_deep)
    subgraph.set_entry_point("router")
    
    subgraph.add_conditional_edges(
        "router",
        router,
        {"basic_search": "basic_search", "deep_search": "deep_search"},
    )
    subgraph.add_edge("basic_search", END)
    subgraph.add_edge("deep_search", END)
    
    return subgraph


# 主图中使用
workflow = StateGraph(MainState)
workflow.add_node("search", create_search_subgraph().compile())
workflow.set_entry_point("search")
workflow.add_edge("search", END)

app = workflow.compile()

# 基础研究
result1 = app.invoke({"topic": "Python", "depth": "basic", "search_results": [], "report": ""})
print(result1["search_results"])

# 深度研究
result2 = app.invoke({"topic": "Python", "depth": "deep", "search_results": [], "report": ""})
print(result2["search_results"])
```

---

## 四、实战：内容创作工作流

### 4.1 架构设计

```text
主图：ContentCreationWorkflow
│
├── [Research Subgraph]  ← 研究子图
│   ├── search_web       ← 搜索资料
│   └── analyze_data     ← 分析整理
│
├── [Writing Subgraph]  ← 写作子图
│   ├── generate_outline ← 生成大纲
│   └── write_content    ← 撰写内容
│
└── [Review Subgraph]  ← 审查子图
    ├── quality_check    ← 质量检查
    └── final_polish     ← 最终润色
```

### 4.2 完整实现

```python
"""内容创作工作流"""
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List
import operator

# ===== 状态定义 =====

class ResearchState(TypedDict):
    """研究子图状态"""
    topic: str
    search_results: Annotated[List[str], operator.add]
    research_summary: str

class WritingState(TypedDict):
    """写作子图状态"""
    topic: str
    research_summary: str
    outline: List[str]
    draft: str

class ReviewState(TypedDict):
    """审查子图状态"""
    draft: str
    quality_score: int
    feedback: str
    revised_draft: str

class MainState(TypedDict):
    """主图状态"""
    topic: str
    search_results: Annotated[List[str], operator.add]
    research_summary: str
    outline: List[str]
    draft: str
    quality_score: int
    feedback: str
    final_content: str


# ===== 子图 1：研究子图 =====

def create_research_subgraph():
    """创建研究子图"""
    
    def search_node(state: ResearchState) -> dict:
        print(f"  [研究] 搜索关于 '{state['topic']}' 的资料...")
        return {"search_results": [
            f"资料1: {state['topic']}的基础概念",
            f"资料2: {state['topic']}的最新发展",
            f"资料3: {state['topic']}的实践应用",
        ]}
    
    def analyze_node(state: ResearchState) -> dict:
        print(f"  [研究] 分析 {len(state['search_results'])} 份资料...")
        summary = f"关于'{state['topic']}'的研究摘要：\n"
        for i, r in enumerate(state['search_results'], 1):
            summary += f"{i}. {r}\n"
        return {"research_summary": summary}
    
    subgraph = StateGraph(ResearchState)
    subgraph.add_node("search", search_node)
    subgraph.add_node("analyze", analyze_node)
    subgraph.set_entry_point("search")
    subgraph.add_edge("search", "analyze")
    subgraph.add_edge("analyze", END)
    
    return subgraph


# ===== 子图 2：写作子图 =====

def create_writing_subgraph():
    """创建写作子图"""
    
    def outline_node(state: WritingState) -> dict:
        print(f"  [写作] 生成大纲...")
        outline = [
            f"1. {state['topic']}概述",
            f"2. {state['topic']}核心概念",
            f"3. {state['topic']}最佳实践",
            f"4. 总结与展望",
        ]
        return {"outline": outline}
    
    def write_node(state: WritingState) -> dict:
        print(f"  [写作] 基于大纲撰写内容...")
        draft = f"# {state['topic']}\n\n"
        for section in state['outline']:
            draft += f"## {section}\n\n"
            draft += f"这是{section}的详细内容...\n\n"
        return {"draft": draft}
    
    subgraph = StateGraph(WritingState)
    subgraph.add_node("outline", outline_node)
    subgraph.add_node("write", write_node)
    subgraph.set_entry_point("outline")
    subgraph.add_edge("outline", "write")
    subgraph.add_edge("write", END)
    
    return subgraph


# ===== 子图 3：审查子图 =====

def create_review_subgraph():
    """创建审查子图"""
    
    def quality_node(state: ReviewState) -> dict:
        print(f"  [审查] 检查内容质量...")
        length = len(state["draft"])
        score = min(10, max(1, length // 100))
        feedback = f"内容长度: {length}字"
        return {"quality_score": score, "feedback": feedback}
    
    def revise_node(state: ReviewState) -> dict:
        print(f"  [审查] 根据反馈优化...")
        revised = state["draft"] + "\n\n*（已根据审查意见优化）*"
        return {"revised_draft": revised}
    
    subgraph = StateGraph(ReviewState)
    subgraph.add_node("quality_check", quality_node)
    subgraph.add_node("revise", revise_node)
    subgraph.set_entry_point("quality_check")
    subgraph.add_edge("quality_check", "revise")
    subgraph.add_edge("revise", END)
    
    return subgraph


# ===== 主图 =====

def create_content_workflow():
    """创建完整的内容创作工作流"""
    
    workflow = StateGraph(MainState)
    
    # 添加子图
    workflow.add_node("research", create_research_subgraph().compile())
    workflow.add_node("writing", create_writing_subgraph().compile())
    workflow.add_node("review", create_review_subgraph().compile())
    
    # 连接节点
    workflow.set_entry_point("research")
    workflow.add_edge("research", "writing")
    workflow.add_edge("writing", "review")
    workflow.add_edge("review", END)
    
    return workflow.compile()


# ===== 执行 =====

def main():
    app = create_content_workflow()
    
    print("🚀 开始内容创作工作流")
    print("=" * 50)
    
    result = app.invoke({
        "topic": "AI Agent 开发指南",
        "search_results": [],
        "outline": [],
        "quality_score": 0,
    })
    
    print("\n" + "=" * 50)
    print("✅ 内容创作完成")
    print(f"📄 内容长度: {len(result['final_content'])} 字")
    print(f"📊 质量评分: {result.get('quality_score', 'N/A')}/10")


if __name__ == "__main__":
    main()
```

---

## 五、子图的设计原则

### 5.1 何时应该拆分子图？

| 信号 | 说明 |
|------|------|
| **职责过多** | 一张图在做多件不同的事 |
| **节点过多** | 超过 10 个节点，难以理解 |
| **需要复用** | 同一段逻辑要在多个地方使用 |
| **独立测试** | 这部分逻辑需要单独验证 |

### 5.2 子图状态设计

```python
# 原则 1：子图只关注自己的状态
# ✅ 好的设计
class SearchSubgraphState(TypedDict):
    query: str              # 只关心搜索相关
    results: list[str]

# ❌ 不好的设计
class SearchSubgraphState(TypedDict):
    query: str
    results: list[str]
    report: str             # 报告不归搜索管
    user_preferences: dict  # 用户偏好不应该在这里


# 原则 2：使用状态映射
class SubgraphState(TypedDict):
    input_data: str
    output_data: str

# 可以定义状态映射函数
def map_to_subgraph(main_state: MainState) -> SubgraphState:
    return {"input_data": main_state["topic"]}

def map_from_subgraph(sub_state: SubgraphState) -> dict:
    return {"output": sub_state["output_data"]}
```

---

## 六、调试子图

```python
# 1. 单独测试子图
research_subgraph = create_research_subgraph().compile()
test_result = research_subgraph.invoke({
    "topic": "测试主题",
    "search_results": [],
    "research_summary": "",
})
print("子图独立测试通过:", test_result)

# 2. 查看完整图结构
app = create_content_workflow()
print(app.get_graph().draw_ascii())
# 可以看到主图和子图的层次结构

# 3. 流式执行（观察子图内部执行）
for step in app.stream({"topic": "测试", "search_results": []}):
    for node_name, state in step.items():
        print(f"  🟢 {node_name}: {list(state.keys())}")
```

---

## 七、本章总结

| 概念 | 一句话说明 |
|------|------------|
| **子图** | 封装了多个节点的完整图，可以作为主图的一个节点 |
| **模块化** | 将大型工作流拆分为独立、可复用的子图 |
| **状态隔离** | 子图只关注与自己职责相关的状态 |
| **组合** | 子图可以像积木一样组装成更大的工作流 |

---

## 📝 课后练习

1. **✅ 基础**：创建一个包含 3 个节点的简单子图，并在主图中使用它
2. **💡 进阶**：创建一个"翻译工作流"，包含"检测语言→翻译→校对"三个子图
3. **🚀 挑战**：实现一个可复用的 "RetrySubgraph"（重试子图），当节点失败时自动重试
4. **🔍 探索**：用 `draw_ascii()` 打印包含子图的完整图结构，理解层次关系
