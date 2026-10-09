# 8.1 核心 Agent 框架全景对比

## 📖 本章目标

- 了解 2026 年主流 Agent 框架的定位与差异
- 掌握各框架的核心优势与适用场景
- 学会根据项目需求选择合适的框架

> 📅 **2026 年 9 月更新**：AutoGen 与 Semantic Kernel 已合并为 **Microsoft Agent Framework**；OpenAI 推出 **Agents SDK**；Anthropic 推出 **Claude Agent SDK**；协议层由 **MCP / A2A** 统一。本章内容已据此重写。

---

## 框架总览

2026 年的 AI Agent 框架生态进入 **"工程化落地"** 阶段，形成了清晰的层次：

```
┌─────────────────────────────────────────────────────────┐
│  协议层： MCP（工具连接）  ·  A2A（Agent 互操作）           │
├─────────────────────────────────────────────────────────┤
│  编排层： LangGraph · LlamaIndex Workflows · Google ADK    │
├─────────────────────────────────────────────────────────┤
│  框架层： LangChain v1 · OpenAI Agents SDK ·              │
│          Microsoft Agent Framework · CrewAI · Pydantic AI │
├─────────────────────────────────────────────────────────┤
│  平台层： Dify · n8n · Flowise · LangSmith（见 8.5）       │
└─────────────────────────────────────────────────────────┘
```

| 框架 | 核心定位 | 技术特色 | 语言/许可 |
|------|---------|---------|-----------|
| **LangGraph** | 图编排运行时 | 状态机、持久化、HITL、时间旅行 | Python/JS · MIT |
| **LangChain v1** | Agent 开发基础 | `create_agent`、中间件、内容块 | Python/JS · MIT |
| **OpenAI Agents SDK** | 轻量 Agent 编排 | handoff、guardrails、tracing | Python/JS · MIT |
| **Microsoft Agent Framework** | 企业级 Agent 框架 | AutoGen + SK 合并、Azure 集成 | Python/.NET · MIT |
| **CrewAI** | 角色化团队协作 | 角色/任务/流程，上手快 | Python · MIT |
| **LlamaIndex** | 数据/RAG 优先 | Workflows、索引、检索强 | Python/TS · MIT |
| **Google ADK** | Google 生态 Agent | 与 Gemini/Vertex 深度集成 | Python/Java · Apache-2.0 |
| **Pydantic AI** | 类型安全 Agent | Pydantic 校验、FastAPI 式开发 | Python · MIT |
| **Claude Agent SDK** | Anthropic 官方 | 与 Claude 工具/记忆深度配合 | Python/TS · MIT |
| **AgentScope** | 分布式多 Agent | 消息驱动、可视化、大规模部署 | Python · Apache-2.0 |

> ⚠️ **已合并/过渡**：`AutoGen` 与 `Semantic Kernel` 已并入 **Microsoft Agent Framework**，新项目请直接使用 MAF。

---

## 框架深度对比

### 1. LangChain v1 + LangGraph — 本教程主力

**核心优势：**
- **LangChain v1**：`create_agent` + 中间件，开箱即用的 Agent 基础
- **LangGraph**：图状态机，表达任意复杂逻辑（分支/循环/并行）
- **生产级**：持久化（checkpointer）、流式（typed streaming v2）、HITL、时间旅行
- **生态最全**：集成数百个模型、向量库、工具，MCP 支持完善

```python
from langchain.agents import create_agent
from langchain.tools import tool

@tool
def search(query: str) -> str:
    """搜索信息。"""
    return f"{query} 的搜索结果..."

agent = create_agent("gpt-5.5", tools=[search], system_prompt="你是研究助手。")
agent.invoke({"messages": [{"role": "user", "content": "研究一下 MCP 协议"}]})
```

**适用场景**：复杂推理、多步骤工作流、需要精细控制和生产可靠性的 Agent 系统。

### 2. OpenAI Agents SDK — 轻量编排

OpenAI 官方（Swarm 的正式后继），与 **Responses API** 配合使用。

**核心优势：**
- **handoff**：Agent 之间优雅交接任务
- **内置 guardrails**：输入/输出护栏
- **tracing**：原生追踪面板
- **轻量**：核心概念少，上手快

```python
from agents import Agent, Runner

agent = Agent(name="assistant", instructions="你是一个友好的助手。")
result = Runner.run_sync(agent, "用一句话解释什么是 Agent")
print(result.final_output)
```

> 📌 **Responses API 是未来**：OpenAI 已宣布 **Assistants API 逐步退役**，能力迁移到 Responses API；Agents SDK 构建在其之上。

**适用场景**：以 OpenAI 模型为主、需要快速编排与 tracing 的项目。

### 3. Microsoft Agent Framework（MAF）— 企业级

AutoGen + Semantic Kernel 合并后的统一框架，**1.0 已 GA（2026 年 4 月）**。

**核心优势：**
- **企业级**：稳定 API、合规、可观测
- **Azure 深度集成**：Microsoft 365 / Foundry / Entra
- **多语言**：Python 与 .NET
- **多 Agent 编排**：延续 AutoGen 的对话协作能力

```python
# 概念示意
from agent_framework import ChatAgent, AzureAIAgentClient

agent = ChatAgent(
    chat_client=AzureAIAgentClient(...),
    instructions="你是一个客服助手。",
)
```

**适用场景**：微软技术栈、企业合规、需长期支持的组织。

### 4. CrewAI — 角色扮演团队

**核心优势：**
- **角色分配**：为每个 Agent 定义 role / goal / backstory
- **任务链**：自动分解为顺序或并行子任务
- **上手快**：适合快速搭建"团队式"协作

```python
from crewai import Agent, Task, Crew

researcher = Agent(role="市场研究员", goal="收集市场数据", backstory="...")
analyst = Agent(role="数据分析师", goal="分析趋势", backstory="...")

research = Task(description="调研 2026 年 AI Agent 市场", agent=researcher)
analysis = Task(description="分析数据", agent=analyst)

crew = Crew(agents=[researcher, analyst], tasks=[research, analysis])
crew.kickoff()
```

**适用场景**：内容创作、市场研究、项目管理等"团队分工"型任务。

### 5. LlamaIndex — 数据与 RAG 优先

**核心优势：**
- **检索能力顶尖**：索引、混合检索、重排、GraphRAG 开箱即用
- **Workflows**：事件驱动的编排，适合数据密集型流程
- **与 LangChain 互补**：可互相调用

**适用场景**：以知识库/文档为核心的应用、复杂 RAG 系统。

### 6. Google ADK — Google 生态

**核心优势：**
- 与 **Gemini / Vertex AI** 深度集成
- 多语言（Python / Java），面向企业部署
- 与 **A2A 协议**天然契合（Google 主导 A2A）

**适用场景**：Google Cloud 技术栈、需要 A2A 互操作的项目。

### 7. Pydantic AI — 类型安全

**核心优势：**
- **Pydantic 风格**：类型安全、结构化输出友好
- **FastAPI 式体验**：依赖注入、易测试
- 轻量、Pythonic

**适用场景**：重视类型安全与可测试性的 Python 团队。

### 8. AgentScope — 分布式多 Agent

消息驱动的多 Agent 框架，强调**透明可控**与**大规模部署**。

**核心特性：**
- **分布式 Agent**：跨进程、跨机器通信
- **消息追踪**：完整链路追踪
- **Web 可视化**：内置监控 UI
- **服务化部署**：一键部署为微服务

> 📌 本教程 8.3 有完整的 AgentScope 专题教程。

**适用场景**：企业级多 Agent 协作、需要监管合规与大规模部署的场景。

---

## 框架选型决策树

```
你的需求是什么？
│
├── 需要精细控制工作流 / 生产可靠性？
│   └── 是 → LangChain v1 + LangGraph（本教程首选）
│
├── 多 Agent 协作？
│   ├── 角色分工 → CrewAI
│   ├── 交接式轻量编排 → OpenAI Agents SDK（handoff）
│   ├── 企业级/微软栈 → Microsoft Agent Framework
│   └── 分布式/大规模 → AgentScope
│
├── 以文档/知识库为核心？
│   └── LlamaIndex（或 LangChain + RAG）
│
├── Google Cloud / 需要 A2A？
│   └── Google ADK
│
├── 重视类型安全？
│   └── Pydantic AI
│
└── 非开发者可视化编排？
    └── 低代码平台（见 8.5 章）
```

---

## 与本教程的关系

| 你在本教程学到 | 对应生态中的位置 |
|--------------|----------------|
| LangChain v1 核心组件 | Agent 开发的基础构建块 |
| LangGraph 工作流 | 最灵活的工作流运行时 |
| RAG 系统 | 知识增强的通用模式 |
| 多 Agent 协作 | CrewAI / MAF / AgentScope 的核心能力 |
| 部署与可观测性 | 所有框架通用的工程实践 |
| MCP / A2A 协议 | 跨框架、跨组织互操作的标准 |

> 💡 **建议**：先精通 **LangChain v1 + LangGraph**（本教程内容），再根据项目需求拓展。图思维、状态管理、工具调用是所有框架的通用基础；而 **MCP / A2A** 让你不必被单一框架锁定。

---

## 本章小结

| 要点 | 说明 |
|------|------|
| 🎯 | 主流框架各有定位，没有"最好"只有"最合适" |
| 📚 | LangChain v1 + LangGraph 是生态最完善的生产方案 |
| 🔀 | AutoGen + Semantic Kernel 已合并为 Microsoft Agent Framework |
| 🧩 | OpenAI Agents SDK 主打轻量编排与 tracing |
| 🔌 | MCP / A2A 是跨框架的事实标准 |
| 🔍 | 选型要从需求出发，而非追热门 |

---

## 📝 课后练习

1. **调研题**：选择 3 个框架（除 LangGraph 外），各跑通一个官方示例
2. **对比题**：列出你项目中可能需要多 Agent 协作的场景，匹配最合适的框架
3. **思考题**：如果让你用 LangGraph 实现 OpenAI Agents SDK 的 handoff 模式，你会怎么设计？
