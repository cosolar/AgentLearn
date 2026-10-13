# 2.3 Agent 核心架构 —— ReAct 循环与 create_agent + Middleware

> 📅 更新至 2026-10 · 技术栈基线见 [教程大纲](../教程大纲.md)

## 📖 导读

> **一句话结论**：Agent 的本质是一个 **"思考 → 行动 → 观察"（TAO / ReAct）循环**；在 LangChain v1 中，这个循环由 **`create_agent` 自动封装**，你用 **Middleware** 控制它的行为，用**终止条件**控制它的边界。

- **前置阅读**：[2.2 Chain 模式详解](./02-Chain模式详解.md)（理解"确定性流程"与"自主决策"的分工）。
- **本章你将学到**：
  1. Agent 与 Chain 的本质区别；
  2. **ReAct / TAO 循环**的工作原理与终止条件；
  3. v1 中如何用 **`create_agent` + Middleware** 构建与控制 Agent；
  4. 旧 API（`AgentExecutor` / `create_react_agent`）到 v1 的**迁移对照**；
  5. Agent 的决策机制与常见局限性。

---

## 一、前置知识

| 概念 | 说明 |
|------|------|
| **Chain** | 固定执行路径，不自主决策（见 [2.2](./02-Chain模式详解.md)） |
| **Tool** | Agent 可调用的外部功能（搜索、计算、API） |
| **LLM** | Agent 的"大脑"，负责推理与决策 |
| **ReAct** | Reasoning + Acting，Agent 的核心思考模式 |
| **Middleware** | v1 中注入"规划/审批/压缩/护栏"等能力的机制 |

---

## 二、Agent vs Chain 的本质区别

| 特性 | Chain | Agent |
|------|-------|-------|
| **执行路径** | 固定、预先定义 | 动态、运行时决定 |
| **决策者** | 开发者（写代码时） | LLM（运行时） |
| **工具使用** | 硬编码 | 模型自主选择 |
| **是否循环** | ❌ 无环 | ✅ 模型↔工具循环 |
| **可预测性** | 高（确定性） | 中（需护栏） |
| **适用场景** | 确定性强的工作流 | 不确定、需推理的任务 |

**一句话区分**：

- **Chain**：你在写代码时就决定了"第一步、第二步"；
- **Agent**：LLM 在运行时自己决定"接下来做什么"。

---

## 三、ReAct / TAO 循环详解

ReAct（Reasoning + Acting）由论文 [*ReAct: Synergizing Reasoning and Acting in Language Models*](https://arxiv.org/abs/2210.03629) 提出，也叫 **TAO 循环**（Thought–Action–Observation）。

### 3.1 工作循环

```
输入问题
    │
    ▼
┌─────────────────────┐
│  Thought（思考）     │  分析当前情况，规划下一步
└────────┬────────────┘
         ▼
┌─────────────────────┐
│  Action（行动）      │  选择一个工具执行
└────────┬────────────┘
         ▼
┌─────────────────────┐
│  Observation（观察） │  获取工具返回结果
└────────┬────────────┘
         │  是否已能回答？
         ├── 是 → 输出最终答案（结束）
         └── 否 → 回到 Thought（继续循环）
```

### 3.2 具体示例

```text
问题：2023 年诺贝尔文学奖得主的代表作是什么？

Thought 1: 我需要先知道 2023 年诺贝尔文学奖得主是谁。
Action 1: search_web("2023 Nobel Prize in Literature winner")
Observation 1: 得主是挪威剧作家约翰·福瑟（Jon Fosse）

Thought 2: 现在需要查他的代表作。
Action 2: search_web("Jon Fosse 代表作")
Observation 2: 代表作有《名字》《有人会来》《秋之梦》等

Thought 3: 信息已足够。
Answer: 2023 年诺贝尔文学奖得主是约翰·福瑟，代表作包括《名字》《有人会来》《秋之梦》等。
```

### 3.3 三种终止条件

| 条件 | 说明 | 表现 |
|------|------|------|
| **自然终止** | 模型不再请求工具，直接给出回答 | 最常见、正常结束 |
| **达上限** | 超过最大步数 / `recursion_limit` | 强制中断，返回已有结果 |
| **遇异常** | 工具报错或模型输出非法 | 报错或触发回退 |

> ⚠️ **v1 无 `max_iterations` 参数**：旧版的 `AgentExecutor(max_iterations=...)` 已取消。要限制循环，用**中间件**或 LangGraph 的 `recursion_limit`（见 [六、终止与循环控制](#六终止与循环控制)）。

---

## 四、v1 中的 Agent：create_agent + Middleware

### 4.1 最小示例

```python
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain.tools import tool

load_dotenv()


@tool
def search_web(query: str) -> str:
    """搜索互联网，用于查找最新资料。"""
    return f"关于'{query}'的搜索结果：……"


@tool
def calculate(expression: str) -> str:
    """执行数学计算，expression 为算式字符串。"""
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as exc:      # noqa: BLE001
        return f"计算错误：{exc}"


model = ChatOpenAI(
    model=os.getenv("LLM_MODEL_NAME", "gpt-5.5"),
    api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_API_BASE"),
    temperature=0,
)

agent = create_agent(
    model=model,
    tools=[search_web, calculate],
    system_prompt="你是一个善于使用工具的助手，必要时先搜索再计算。",
)

# Agent 会自主决定：先搜索 → 再计算 → 组织回答
result = agent.invoke(
    {"messages": [{"role": "user", "content": "搜索 2023 年诺贝尔奖得主人数，并乘以 2"}]}
)
print(result["messages"][-1].content)
```

### 4.2 迁移对照表（旧写法 → v1）

> 📌 下面这张表**仅用于帮助迁移**，其中的 `AgentExecutor` / `create_react_agent` 已不是推荐写法，**本教程的可运行代码一律使用 `create_agent`**。

| 能力 | v0.x 旧写法 | v1 新写法 |
|------|-------------|-----------|
| 创建 ReAct Agent | `langgraph.prebuilt.create_react_agent` | `langchain.agents.create_agent` |
| 工具调用执行器 | `AgentExecutor` | 内置（无需手动配置） |
| 限制最大轮次 | `AgentExecutor(max_iterations=n)` | 中间件 / `recursion_limit` |
| 多轮记忆 | `ConversationBufferMemory` | `checkpointer`（LangGraph） |
| 上下文压缩 | 手写摘要 | `SummarizationMiddleware` |
| 人工审批 | 自己实现中断 | `HumanInTheLoopMiddleware` |
| 结构化输出 | `with_structured_output` / `PydanticOutputParser` | `response_format=ToolStrategy(Model)` |

### 4.3 Middleware：控制循环的"总开关"

Middleware 是 v1 的标志性特性，用于**上下文工程与循环控制**。它让你在不改动 Agent 核心逻辑的前提下，注入"压缩、审批、脱敏、计数"等行为。

**内置中间件**：

| 中间件 | 作用 | 关键参数 |
|--------|------|----------|
| `SummarizationMiddleware` | 历史过长时自动摘要压缩 | `trigger={"tokens": 4000}` |
| `HumanInTheLoopMiddleware` | 敏感工具调用前人工审批 | `interrupt_on={"工具名": True}` |
| `PIIMiddleware` | 发送给模型前脱敏 | `strategy="redact" \| "block"` |

```python
from langchain.agents import create_agent
from langchain.agents.middleware import (
    SummarizationMiddleware,
    HumanInTheLoopMiddleware,
    PIIMiddleware,
)
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver


@tool
def send_email(to: str, body: str) -> str:
    """发送邮件（示例）。"""
    return f"已发送给 {to}"


agent = create_agent(
    model="gpt-5.5",
    tools=[send_email],
    middleware=[
        SummarizationMiddleware(trigger={"tokens": 4000}),           # 压缩上下文
        PIIMiddleware(strategy="redact"),                            # 脱敏
        HumanInTheLoopMiddleware(interrupt_on={"send_email": True}), # 发邮件前需审批
    ],
    checkpointer=InMemorySaver(),   # HITL 依赖 checkpointer 才能中断/恢复
)
```

> 💡 `interrupt_on` 的值可以是 `True`（允许全部决策）或 `{"allowed_decisions": ["approve", "reject"]}` 等配置；被中断后需用 `Command(resume={"decisions": [...]})` 恢复执行。

**自定义中间件的 Hook**：

| Hook | 运行时机 | 典型用途 |
|------|----------|----------|
| `before_agent` | 调用 Agent 前 | 加载记忆、校验输入 |
| `before_model` | 每次 LLM 调用前 | 更新提示词、裁剪消息 |
| `wrap_model_call` | 包裹每次 LLM 调用 | 拦截/修改请求与响应 |
| `wrap_tool_call` | 包裹每次工具调用 | 拦截/修改工具执行 |
| `after_model` | 每次 LLM 响应后 | 校验输出、应用护栏 |
| `after_agent` | Agent 完成后 | 保存结果、清理 |

```python
from langchain.agents.middleware import AgentMiddleware


class StepGuardMiddleware(AgentMiddleware):
    """示例：统计模型调用次数，超过阈值时给出提示。"""

    def __init__(self, max_steps: int = 8):
        super().__init__()
        self.max_steps = max_steps
        self.count = 0

    def before_model(self, state, runtime):
        self.count += 1
        if self.count > self.max_steps:
            raise RuntimeError(f"超过最大步数 {self.max_steps}，已中断循环")
        return None
```

> 📌 中间件的完整清单与自定义方式见 [3.1 LangChain v1 核心组件](../03-LangChain实战/01-LangChain核心组件.md)。

---

## 五、决策机制：模型如何选工具

### 5.1 工具选择的推理过程

```
可用工具：
1. search_web(query)   搜索互联网
2. calculate(expr)     数学计算
3. get_weather(city)   查询天气

输入："北京明天多少度？"

模型推理：
- 用户问天气 → 匹配 get_weather
- 不需要搜索/计算 → 不选其余工具
- ✅ 选择：get_weather("北京")
```

### 5.2 影响决策的因素

| 因素 | 说明 |
|------|------|
| **工具描述（docstring）** | 决定模型能否识别工具用途——**最重要** |
| **参数说明与类型** | 影响模型能否正确传参 |
| **历史观察** | 之前的工具结果影响下一步决策 |
| **System Prompt** | 规则约束（如"不确定就搜索"）影响行为风格 |

```python
# 保守型：先查证
system_prompt = """你是 Agent。规则：
1. 如果不确定，先用 search_web 查证
2. 不要猜测事实
3. 每一步都解释你的思考"""

# 激进型：优先自身知识
system_prompt = """你是 Agent。规则：
1. 优先凭知识回答
2. 遇到不确定的才用工具验证
3. 回答简洁直接"""
```

---

## 六、终止与循环控制

| 手段 | 做法 | 适用 |
|------|------|------|
| **自然终止** | 模型不再调用工具 | 默认行为 |
| **步数上限** | 自定义中间件计数（见 4.3） | 防止无限循环 |
| **图递归上限** | `agent.invoke(..., config={"recursion_limit": 25})` | 快速兜底 |
| **人工介入** | `HumanInTheLoopMiddleware` | 关键动作前审批 |

```python
# 兜底：限制整张图的递归深度（防止死循环）
result = agent.invoke(
    {"messages": [{"role": "user", "content": "帮我规划一周的行程"}]},
    config={"recursion_limit": 25},
)
```

---

## 七、Agent 类型对比

| Agent 类型 | 决策方式 | 适用场景 |
|-----------|----------|----------|
| **ReAct Agent** | TAO 循环，多步推理 | 通用工具调用（`create_agent` 的默认形态） |
| **Plan-and-Execute** | 先规划完整计划，再逐步执行 | 多步骤长流程 |
| **Reflection / Self-Refine** | 生成后自我检查再优化 | 高质量输出 |
| **Multi-Agent** | 多个 Agent 分工协作 | 大型复杂项目（见 [6.1 多 Agent 协作](../06-高级主题/01-多Agent协作.md)） |

> 🆕 **2026 实践**：以上架构在 v1 中都以 `create_agent` 为基座，通过 **Middleware** 注入"规划/反思/审批/压缩"能力实现。复杂的分支与循环编排交给 **LangGraph**（第 4 章）。

**Plan-and-Execute 示意**：

```text
Phase 1 规划：
1. 搜索"2023 年全球碳排放数据"
2. 搜索"主要国家减排政策"
3. 对比分析
4. 生成报告

Phase 2 执行：
✅ 步骤 1 完成
⏳ 步骤 2 进行中
❌ 步骤 3 报错 → 调整后继续
```

---

## 八、Agent 的局限性与应对

| 局限性 | 表现 | 应对策略 |
|--------|------|----------|
| **幻觉** | 编造信息 | 严格规则 + 强制工具查证 + 输出校验 |
| **死循环** | 在几步间反复横跳 | 中间件计数 / `recursion_limit` |
| **工具误用** | 选错工具 | 优化 docstring，减少工具数量与重叠 |
| **过度推理** | 简单问题绕很多步 | 设置"直接回答优先"策略 |
| **成本失控** | 来回思考消耗大量 token | 精简上下文、限制步数、用小模型做简单判断 |

---

## 本章小结

| 要点 | 说明 |
|------|------|
| **Agent vs Chain** | Chain 写死步骤，Agent 运行时自主决策 |
| **ReAct / TAO** | 思考 → 行动 → 观察 的循环 |
| **终止条件** | 自然终止 / 达上限 / 遇异常 |
| **v1 入口** | `create_agent`（唯一推荐入口） |
| **循环控制** | Middleware 计数或 `recursion_limit`（无 `max_iterations`） |
| **决策关键** | 工具 docstring 与 System Prompt |
| **迁移** | `AgentExecutor` / `create_react_agent` → `create_agent`（仅对照表提及） |

---

## 📝 课后练习

**基础**
1. 用自己的话解释为什么 Agent 比 Chain 更适合"不确定性任务"，并举一个不适合用 Agent 的场景。

**进阶**
2. 用 `create_agent` + 两个工具（搜索、计算）实现一个 Agent，打印完整消息序列，标出每一轮的 Thought / Action / Observation（提示：`AIMessage.tool_calls` 对应 Action，`ToolMessage` 对应 Observation）。
3. 给练习 2 的 Agent 加一个 `StepGuardMiddleware`，把最大步数限制为 3，构造一个需要 4 步的任务，验证中断逻辑生效。

**挑战**
4. 对比实验：分别用"纯 LCEL 顺序链"和"`create_agent`"实现"查询北京天气并给出穿衣建议"，从实现复杂度、灵活性、可预测性三个维度写出对比结论，并说明你会如何选择。
