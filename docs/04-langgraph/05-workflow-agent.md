# 4.5 实战：工作流 Agent —— 构建生产级内容创作系统

## 📖 导读

本章我们学习了 LangGraph 的核心概念——状态管理、条件路由、循环、子图。现在是时候**把它们综合起来，构建一个真正的生产级工作流 Agent**。

本节我们将开发一个**内容创作工作流 Agent**，它能够：
1. 接收一个主题
2. 自动进行资料调研
3. 生成内容大纲
4. 撰写完整内容
5. 质量审查与迭代优化

---

## 一、项目需求

### 1.1 功能清单

| 阶段 | 功能 | 说明 |
|------|------|------|
| 调研 | 搜索相关资料 | 收集主题相关的最新信息 |
| 规划 | 生成内容大纲 | 结构化组织内容 |
| 写作 | 逐节撰写内容 | 基于大纲生成完整文章 |
| 审查 | 质量评估 | 打分 + 反馈 + 迭代优化 |
| 输出 | 格式化输出 | 生成最终版本 |

### 1.2 工作流设计

```text
                     ┌──────────────────┐
                     │   用户输入主题     │
                     └────────┬─────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │       Research Subgraph        │
              │  ┌─────────┐  ┌────────────┐  │
              │  │ 搜索资料  │→│ 分析整理    │  │
              │  └─────────┘  └────────────┘  │
              └───────────────┬───────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │       Outline Subgraph         │
              │  ┌─────────┐  ┌────────────┐  │
              │  │ 生成大纲  │→│ 大纲验证    │──┼──→ 否 → 重新生成
              │  └─────────┘  └──────┬─────┘  │
              │               是     │         │
              └──────────────────────┼─────────┘
                                     │
                                     ▼
              ┌───────────────────────────────┐
              │       Writing Subgraph         │
              │  ┌───────────────────────┐    │
              │  │ 逐节写作（循环）       │    │
              │  │ 写完一节 → 还有下节？ │    │
              │  └───────────────────────┘    │
              └───────────────┬───────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │       Review Subgraph          │
              │  ┌─────────┐  ┌────────────┐  │
              │  │ 质量评估  │→│ 评分 ≥ 7？ │──┼──→ 是 → 最终输出
              │  └─────────┘  └──────┬─────┘  │
              │               否     │         │
              │         ┌────────────┘         │
              │         ▼                      │
              │  ┌────────────┐                │
              │  │ 修改优化    │──→ 回到评估    │
              │  └────────────┘                │
              └───────────────────────────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │    最终输出       │
                     └──────────────────┘
```

---

## 二、状态定义

```python
from typing import TypedDict, Annotated, List, Optional
import operator
from langgraph.graph import StateGraph, END


# ===== 子图状态 =====

class ResearchState(TypedDict):
    """研究子图状态"""
    topic: str
    search_results: Annotated[List[str], operator.add]
    research_summary: str


class OutlineState(TypedDict):
    """大纲子图状态"""
    topic: str
    research_summary: str
    outline: List[str]
    outline_approved: bool


class WritingState(TypedDict):
    """写作子图状态"""
    topic: str
    outline: List[str]
    current_section: int
    total_sections: int
    draft: str


class ReviewState(TypedDict):
    """审查子图状态"""
    draft: str
    quality_score: float
    feedback: str
    revision_count: int
    max_revisions: int
    is_approved: bool


# ===== 主图状态 =====

class ContentWorkflowState(TypedDict):
    """完整内容创作工作流状态"""
    # 输入
    topic: str
    requirements: str
    
    # 研究阶段
    search_results: Annotated[List[str], operator.add]
    research_summary: str
    
    # 规划阶段
    outline: List[str]
    
    # 写作阶段
    draft: str
    current_section: int
    total_sections: int
    
    # 审查阶段
    quality_score: float
    feedback: str
    revision_count: int
    max_revisions: int
    is_approved: bool
    
    # 最终输出
    final_content: str
```

---

## 三、子图实现

### 3.1 研究子图

```python
def create_research_subgraph():
    """研究子图：搜索和分析资料"""
    
    def search_node(state: ResearchState) -> dict:
        print(f"  🔍 搜索资料: {state['topic']}")
        results = [
            f"关于'{state['topic']}'的核心概念介绍",
            f"'{state['topic']}'的最新发展趋势",
            f"'{state['topic']}'的实践案例和最佳实践",
        ]
        return {"search_results": results}
    
    def analyze_node(state: ResearchState) -> dict:
        print(f"  📊 分析 {len(state['search_results'])} 份资料...")
        summary = f"## 研究摘要\n\n"
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
```

### 3.2 大纲子图

```python
def create_outline_subgraph():
    """大纲子图：生成和确认内容结构"""
    
    def generate_outline(state: OutlineState) -> dict:
        print(f"  📝 生成大纲...")
        outline = [
            f"1. {state['topic']}概述与背景",
            f"2. {state['topic']}核心概念解析",
            f"3. {state['topic']}关键技术点",
            f"4. {state['topic']}实战案例",
            f"5. {state['topic']}最佳实践",
            f"6. 总结与展望",
        ]
        return {"outline": outline}
    
    def validate_outline(state: OutlineState) -> dict:
        print(f"  ✅ 验证大纲...")
        approved = len(state['outline']) >= 3
        return {"outline_approved": approved}
    
    def route_outline(state: OutlineState) -> str:
        if state['outline_approved']:
            return "approved"
        return "regenerate"
    
    def regenerate_outline(state: OutlineState) -> dict:
        print(f"  🔄 重新生成大纲...")
        outline = state['outline'] + [f"{len(state['outline'])+1}. 补充章节"]
        return {"outline": outline, "outline_approved": True}
    
    subgraph = StateGraph(OutlineState)
    subgraph.add_node("generate", generate_outline)
    subgraph.add_node("validate", validate_outline)
    subgraph.add_node("regenerate", regenerate_outline)
    
    subgraph.set_entry_point("generate")
    subgraph.add_edge("generate", "validate")
    
    subgraph.add_conditional_edges(
        "validate",
        route_outline,
        {"approved": END, "regenerate": "regenerate"},
    )
    subgraph.add_edge("regenerate", END)
    
    return subgraph
```

### 3.3 写作子图

```python
def create_writing_subgraph():
    """写作子图：按大纲逐节写作"""
    
    def write_section(state: WritingState) -> dict:
        section = state["outline"][state["current_section"]]
        section_number = state["current_section"] + 1
        total = state["total_sections"]
        print(f"  ✍️ 写作章节 {section_number}/{total}: {section[:20]}...")
        
        section_content = f"""
## {section}

### 概述
本节将深入探讨{section}的相关内容...

### 详细内容
{section}是理解{state['topic']}的关键部分。
在实际应用中，我们需要注意以下几点：
1. 首先了解其基本概念
2. 掌握核心原理
3. 通过实践加深理解

### 小结
本节我们学习了{section}的核心要点。
"""
        
        new_draft = state["draft"] + section_content + "\n\n"
        next_section = state["current_section"] + 1
        
        return {
            "draft": new_draft,
            "current_section": next_section,
        }
    
    def should_continue_writing(state: WritingState) -> str:
        if state["current_section"] >= state["total_sections"]:
            return "complete"
        return "continue"
    
    subgraph = StateGraph(WritingState)
    subgraph.add_node("write", write_section)
    
    subgraph.set_entry_point("write")
    subgraph.add_conditional_edges(
        "write",
        should_continue_writing,
        {"continue": "write", "complete": END},
    )
    
    return subgraph
```

### 3.4 审查子图

```python
def create_review_subgraph():
    """审查子图：质量评估和迭代优化"""
    
    def evaluate_quality(state: ReviewState) -> dict:
        print(f"  📋 质量评估 (第 {state['revision_count'] + 1} 次)...")
        
        draft = state["draft"]
        length = len(draft)
        score = 0
        feedback_parts = []
        
        if length > 500:
            score += 3
            feedback_parts.append("✅ 内容长度充足")
        else:
            feedback_parts.append("❌ 内容需要扩展")
        
        if "实战" in draft or "案例" in draft:
            score += 2
            feedback_parts.append("✅ 包含实战内容")
        else:
            feedback_parts.append("💡 建议增加实战案例")
        
        if "总结" in draft:
            score += 2
            feedback_parts.append("✅ 有总结部分")
        
        if "最佳实践" in draft:
            score += 2
            feedback_parts.append("✅ 包含最佳实践")
        
        import random
        score += random.randint(0, 1)
        
        return {
            "quality_score": score,
            "feedback": "\n".join(feedback_parts),
            "revision_count": state["revision_count"] + 1,
        }
    
    def route_review(state: ReviewState) -> str:
        if state["quality_score"] >= 7:
            return "approved"
        elif state["revision_count"] >= state["max_revisions"]:
            return "max_revisions"
        else:
            return "needs_revision"
    
    def optimize_content(state: ReviewState) -> dict:
        print(f"  🔧 根据反馈优化...")
        feedback = state["feedback"]
        improved = state["draft"] + f"\n\n---\n*根据审查意见优化：{feedback[:50]}...*"
        return {"draft": improved}
    
    subgraph = StateGraph(ReviewState)
    subgraph.add_node("evaluate", evaluate_quality)
    subgraph.add_node("optimize", optimize_content)
    
    subgraph.set_entry_point("evaluate")
    
    subgraph.add_conditional_edges(
        "evaluate",
        route_review,
        {
            "approved": END,
            "needs_revision": "optimize",
            "max_revisions": END,
        },
    )
    subgraph.add_edge("optimize", "evaluate")
    
    return subgraph
```

---

## 四、主图组装

```python
from langgraph.checkpoint import MemorySaver


def create_content_workflow():
    """组装完整的内容创作工作流"""
    
    workflow = StateGraph(ContentWorkflowState)
    
    # 添加子图
    workflow.add_node("research", create_research_subgraph().compile())
    workflow.add_node("outline", create_outline_subgraph().compile())
    workflow.add_node("writing", create_writing_subgraph().compile())
    workflow.add_node("review", create_review_subgraph().compile())
    
    # 添加输出节点
    def finalize(state: ContentWorkflowState) -> dict:
        print("\n  🎉 完成最终输出...")
        content = f"""
# {state['topic']}

{state['research_summary']}

---

{state['draft']}

---
*本文由 AI 内容创作工作流自动生成*
*质量评分: {state['quality_score']}/10*
*迭代次数: {state['revision_count']}*
"""
        return {"final_content": content}
    
    workflow.add_node("finalize", finalize)
    
    # 编排流程
    workflow.set_entry_point("research")
    
    workflow.add_edge("research", "outline")
    workflow.add_edge("outline", "writing")
    workflow.add_edge("writing", "review")
    workflow.add_edge("review", "finalize")
    workflow.add_edge("finalize", END)
    
    # 启用持久化
    memory = MemorySaver()
    
    return workflow.compile(checkpointer=memory)


def print_workflow_structure(app):
    """打印工作流结构"""
    print("📊 工作流结构:")
    print(app.get_graph().draw_ascii())
```

---

## 五、运行与测试

```python
def run_content_workflow():
    """运行内容创作工作流"""
    
    app = create_content_workflow()
    
    # 打印结构
    print_workflow_structure(app)
    
    # 输入
    topic = "AI Agent 开发实战指南"
    
    print(f"\n🚀 开始创作: {topic}")
    print("=" * 60)
    
    # 执行
    config = {"configurable": {"thread_id": "content_001"}}
    result = app.invoke(
        {
            "topic": topic,
            "requirements": "面向有 Python 基础的开发者",
            "search_results": [],
            "outline": [],
            "draft": "",
            "current_section": 0,
            "total_sections": 6,
            "quality_score": 0.0,
            "feedback": "",
            "revision_count": 0,
            "max_revisions": 3,
            "is_approved": False,
            "final_content": "",
        },
        config=config,
    )
    
    print("\n" + "=" * 60)
    print("✅ 创作完成！")
    print(f"📄 最终内容长度: {len(result['final_content'])} 字")
    print(f"📊 质量评分: {result['quality_score']}/10")
    print(f"🔄 迭代次数: {result['revision_count']}")
    
    print("\n📝 最终内容预览:")
    print("-" * 40)
    print(result["final_content"][:500] + "...")
    
    return result


if __name__ == "__main__":
    run_content_workflow()
```

---

## 六、调试与监控

```python
def debug_step_by_step():
    """逐步执行，观察每个节点的变化"""
    app = create_content_workflow()
    
    config = {"configurable": {"thread_id": "debug_session"}}
    
    # 逐步执行
    for step_output in app.stream(
        {"topic": "测试主题", "outline": [], "draft": "",
         "current_section": 0, "total_sections": 3,
         "quality_score": 0, "feedback": "", "revision_count": 0,
         "max_revisions": 2, "is_approved": False, "final_content": "",
         "search_results": [], "research_summary": "", "requirements": ""},
        config=config,
    ):
        for node_name, state_update in step_output.items():
            if state_update:  # 有状态更新
                keys = list(state_update.keys())
                print(f"  🟢 {node_name}: 更新了 {keys}")
```

---

## 七、扩展与优化

| 扩展方向 | 实现方案 | 效果 |
|----------|----------|------|
| **真实搜索** | 接入 SerpAPI/Bing Search | 获取真实信息 |
| **LLM 写作** | 用 ChatOpenAI 生成各章节 | 内容质量更高 |
| **并行审查** | 同时做多项质量检查 | 评估更全面 |
| **用户反馈** | 增加人工审核节点 | 人机协作 |
| **多格式输出** | 支持 HTML/PDF/Word | 适应不同场景 |

---

## 八、本章总结

| 要点 | 说明 |
|------|------|
| **模块化设计** | 4 个子图（研究/大纲/写作/审查）各自独立 |
| **条件路由** | 大纲验证、审查评分后的分支决策 |
| **循环迭代** | 逐节写作循环 + 质量迭代循环 |
| **状态传递** | 主图状态在子图间流转 |
| **持久化** | MemorySaver 支持断点续执行 |

---

## 📝 课后练习

1. **✅ 基础**：运行内容创作工作流，观察每个阶段的执行过程
2. **💡 改进**：用真实的 LLM 替换模拟的写作文本，让内容真正由 AI 生成
3. **🚀 扩展**：在审查子图中增加"语言风格检查"和"事实准确性检查"
4. **🔍 探索**：使用 `app.stream()` 逐步执行，观察每个子图内部的状态变化
