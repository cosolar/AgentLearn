# 8.2 多智能体协作模式深度解析

## 📖 本章目标

- 掌握多 Agent 系统的四大协作模式
- 理解各模式的适用场景与优劣
- 学会设计多 Agent 协作架构

---

## 为什么需要多 Agent？

> 第 6.1 章介绍了多 Agent 的基础概念，本章从生态视角深入解析各种协作模式的工程实现。

```
单 Agent 瓶颈：
┌──────────────────────────────────────┐
│  一个 Agent 做所有事：                 │
│  - 能力有限（单一模型）                │
│  - 容易出错（缺少校验）                │
│  - Token 浪费（上下文膨胀）            │
│  - 难以扩展（耦合度高）                │
└──────────────────────────────────────┘

多 Agent 优势：
┌──────────────────────────────────────┐
│  多个 Agent 分工协作：                 │
│  - 专业化（每个 Agent 专注一件事）      │
│  - 互相校验（减少幻觉）                │
│  - 可扩展（按需增加 Agent）             │
│  - 可维护（职责分离）                   │
└──────────────────────────────────────┘
```

---

## 四大协作模式

### 模式一：层级式协作 (Hierarchical)

**代表框架：** CrewAI、AutoGen（Manager-Employee 模式）

```
                  ┌──────────────┐
                  │  Manager     │
                  │  (规划/分配)  │
                  └──────┬───────┘
                         │
           ┌─────────────┼─────────────┐
           │             │             │
           ▼             ▼             ▼
     ┌──────────┐  ┌──────────┐  ┌──────────┐
     │  Worker  │  │  Worker  │  │  Worker  │
     │  A       │  │  B       │  │  C       │
     └──────────┘  └──────────┘  └──────────┘
           │             │             │
           └─────────────┼─────────────┘
                         │
                         ▼
                  ┌──────────────┐
                  │  Result      │
                  └──────────────┘
```

**特点：**
- 一个 Manager Agent 负责任务分解和分配
- Worker Agent 执行具体任务
- Manager 汇总结果、质量把控

**适用场景：** 软件开发、项目管理、内容创作流水线

**CrewAI 实现：**
```python
from crewai import Agent, Task, Crew, Process

manager = Agent(role="项目经理", goal="规划并监督项目", allow_delegation=True)
dev = Agent(role="开发者", goal="编写代码", ...)
tester = Agent(role="测试员", goal="测试代码", ...)

tasks = [
    Task(description="设计系统架构", agent=manager),
    Task(description="实现核心功能", agent=dev),
    Task(description="编写测试用例", agent=tester),
]

crew = Crew(agents=[manager, dev, tester], tasks=tasks, process=Process.hierarchical)
```

### 模式二：平等对话式协作 (Peer-to-Peer)

**代表框架：** AutoGen（默认模式）、Swarm

```
         ┌──────────┐
         │  Agent   │
         │   A      │
         └────┬─────┘
              │ 对话
         ┌────▼─────┐
         │  Agent   │
         │   B      │
         └────┬─────┘
              │ 对话
         ┌────▼─────┐
         │  Agent   │
         │   C      │
         └──────────┘
```

**特点：**
- 所有 Agent 地位平等
- 通过自然语言对话协商
- 动态决定谁做什么

**AutoGen 实现：**
```python
from autogen import AssistantAgent, GroupChat, GroupChatManager

agent_a = AssistantAgent(name="研究员", ...)
agent_b = AssistantAgent(name="分析师", ...)
agent_c = AssistantAgent(name="审查员", ...)

group_chat = GroupChat(
    agents=[agent_a, agent_b, agent_c],
    messages=[],
    max_round=10,
)
manager = GroupChatManager(groupchat=group_chat)
```

### 模式三：流程化协作 (Pipeline)

**代表框架：** MetaGPT、LangGraph Pipeline

```
输入 → [角色1] → [角色2] → [角色3] → [角色4] → 输出
       产品经理   架构师    开发者     测试员
```

**特点：**
- 固定流程，每个节点有明确角色
- 上一节点输出是下一节点输入
- 适合生产流程明确的场景

**MetaGPT 实现（模拟软件公司）：**
```python
from metagpt.software_company import SoftwareCompany
from metagpt.roles import ProductManager, Architect, Engineer, QAEngineer

company = SoftwareCompany()
company.hire([
    ProductManager(),
    Architect(),
    Engineer(),
    QAEngineer(),
])
company.start_project("开发一个电商网站")
```

### 模式四：竞争/辩论式协作 (Competitive)

**代表框架：** MultiAgentBench、LangGraph Debate

```
         ┌──────────┐
         │  问题     │
         └────┬──────┘
              │
     ┌────────┼────────┐
     ▼        ▼        ▼
┌────────┐┌────────┐┌────────┐
│ Agent  ││ Agent  ││ Agent  │
│  A     ││  B     ││  C     │
└───┬────┘└───┬────┘└───┬────┘
    │         │         │
    └─────────┼─────────┘
              ▼
         ┌──────────┐
         │  裁决者   │
         │  (投票/评分)│
         └──────────┘
```

**特点：**
- 多个 Agent 独立回答同一问题
- 投票或评分机制选择最佳答案
- 减少偏见，提高准确性

**LangGraph 实现（辩论模式）：**
```python
# 用 LangGraph 实现辩论（本教程 6.1 章的扩展）
from langgraph.graph import StateGraph

def debater_a(state): ...  # Agent A 发言
def debater_b(state): ...  # Agent B 发言  
def judge(state): ...      # 裁判裁决

workflow = StateGraph(DebateState)
workflow.add_node("debater_a", debater_a)
workflow.add_node("debater_b", debater_b)
workflow.add_node("judge", judge)
# ... 配置边和循环逻辑
```

---

## 协作模式对比

| 维度 | 层级式 | 平等对话 | 流程化 | 竞争辩论 |
|------|--------|---------|-------|---------|
| **控制方式** | 集中 | 分散 | 预定义 | 分散 |
| **灵活性** | 中 | 高 | 低 | 中 |
| **可预测性** | 高 | 低 | 高 | 中 |
| **适用规模** | 大 | 中 | 大 | 小 |
| **通信开销** | 中 | 高 | 低 | 低 |
| **代表框架** | CrewAI | AutoGen | MetaGPT | MultiAgentBench |

---

## 选型建议

| 场景 | 推荐模式 | 推荐框架 |
|------|---------|---------|
| 软件项目开发 | 流程化 | MetaGPT |
| 市场研究报告 | 层级式 | CrewAI |
| 代码审查/校对 | 平等对话 | AutoGen |
| 风险评估 | 竞争辩论 | LangGraph 自建 |
| 智能客服 | 层级式 | AgentScope/EDDI |
| 研究实验 | 平等对话 | AutoGen |

---

## 本章小结

| 要点 | 说明 |
|------|------|
| 👥 | 四种模式：层级、平等、流程、辩论 |
| 🎯 | 选择取决于：控制粒度、灵活性需求、团队规模 |
| 🔧 | LangGraph 可灵活实现任意模式 |
| 📚 | 不同框架在特定模式上有优化 |

---

## 📝 课后练习

1. **设计题**：用 LangGraph 实现一个平等对话模式的多 Agent 系统
2. **对比题**：跑通 AutoGen 和 CrewAI 的官方示例，对比体验差异
3. **思考题**：什么场景下竞争辩论模式比协作模式更有效？

