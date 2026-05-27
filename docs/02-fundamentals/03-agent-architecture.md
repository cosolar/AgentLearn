# 2.3 Agent 核心架构 —— 理解 Agent 如何思考与行动

## 📖 导读

> **Chain 是固定的流水线，Agent 是一个能自主决策的"机器人"。**

前面我们学习了 Chain——把处理步骤写死成一条线。但很多时候，我们不知道用户会问什么、需要什么工具。这时就需要 **Agent**：它像一个人，先思考需要做什么，再决定调用什么工具，然后观察结果，再思考下一步。**这套"思考→行动→观察"的循环，就是 Agent 的核心。**

---

## 一、前置知识

| 概念 | 说明 |
|------|------|
| **Chain** | 固定执行路径，不自主决策 |
| **Tool** | Agent 可调用的外部功能（搜索、计算、API） |
| **LLM** | Agent 的"大脑"，负责推理和决策 |
| **ReAct** | Reasoning + Acting，Agent 的核心思考模式 |

---

## 二、Agent vs Chain 的本质区别

| 特性 | Chain | Agent |
|------|-------|-------|
| **执行路径** | 固定、预先定义 | 动态、运行时决定 |
| **决策者** | 开发者（写代码时） | LLM（运行时） |
| **工具使用** | 硬编码写死 | LLM 自主选择 |
| **灵活性** | 低 | 高 |
| **可预测性** | 高（确定性） | 中（LLM 输出会有变化） |
| **适用场景** | 确定性强的工作流 | 不确定性强、需要推理的任务 |

**一句话区分**：

- **Chain**：开发者在写代码时就决定了"第一步做什么，第二步做什么"
- **Agent**：LLM 在运行时根据输入自己决定"接下来应该做什么"

---

## 三、ReAct 模式详解

ReAct（Reasoning + Acting）是 Agent 最核心的工作模式，由论文 [*ReAct: Synergizing Reasoning and Acting in Language Models*](https://arxiv.org/abs/2210.03629) 提出。

### 3.1 工作循环

```
输入问题
    │
    ▼
┌─────────────────────┐
│   Thought（思考）    │ ← 分析当前情况，规划下一步
│   "我需要先搜索..."  │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   Action（行动）     │ ← 选择一个工具执行
│   search_web(...)   │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Observation（观察） │ ← 获取工具返回的结果
│   "搜索结果是..."    │
└────────┬────────────┘
         │
         │  是否已能回答问题？
         │  ┌─── 是 → 输出最终答案
         │  └─── 否 → 回到 Thought（继续循环）
         │
         ▼
         循环直到得到答案或达到最大轮次
```

### 3.2 具体示例

```text
问题：2023 年诺贝尔文学奖得主的代表作是什么？

Thought 1: 我需要先知道 2023 年诺贝尔文学奖得主是谁。
Action 1: search_web("2023 Nobel Prize in Literature winner")
Observation 1: 2023 年诺贝尔文学奖得主是挪威剧作家约翰·福瑟（Jon Fosse）

Thought 2: 现在我知道得主是 Jon Fosse，接下来需要查他的代表作。
Action 2: search_web("Jon Fosse 代表作")
Observation 2: 代表作有《名字》《有人会来》《秋之梦》等

Thought 3: 我已经获得了完整的信息，可以回答用户了。
Answer: 2023 年诺贝尔文学奖得主是挪威剧作家约翰·福瑟（Jon Fosse），
        代表作包括《名字》《有人会来》《秋之梦》等戏剧作品。
```

### 3.3 ReAct 的三种终止条件

| 条件 | 说明 | 示例输出 |
|------|------|----------|
| **有答案** | Agent 认为信息足够回答 | `Answer: 答案是...` |
| **达上限** | 超过最大思考轮次 | 返回"无法确定答案" |
| **遇异常** | 工具调用出错 | 返回错误信息 |

---

## 四、Agent 的决策机制

### 4.1 工具选择策略

Agent 如何决定调用哪个工具？

```
可用工具列表：
1. search_web(query)    - 搜索互联网信息
2. calculate(expr)      - 执行数学计算
3. get_weather(city)    - 查询天气预报

输入："北京明天多少度？"

Agent 的推理过程：
- 用户问天气 → 与 get_weather 工具最匹配
- 不需要搜索 → 不选 search_web
- 不需要计算 → 不选 calculate
- ✅ 选择：get_weather("北京")
```

### 4.2 影响决策的因素

| 因素 | 说明 |
|------|------|
| **工具描述** | 每个工具的 `description` 决定 LLM 能否识别其用途 |
| **参数说明** | 参数的名称和类型影响 LLM 能否正确传参 |
| **历史观察** | 之前工具调用的结果影响下一步决策 |
| **任务约束** | 用户明确要求的限制条件 |

### 4.3 Prompt 对 Agent 行为的影响

同样的工具集，不同的 system prompt 会让 Agent 表现出完全不同的行为：

```python
# 保守型 Agent
system_prompt = """
你是 Agent。规则：
1. 如果不确定，先用 search_web 查证
2. 不要猜测事实
3. 每一步都要解释你的思考
"""

# 激进型 Agent  
system_prompt = """
你是 Agent。规则：
1. 优先凭你的知识回答
2. 遇到不确定的才用工具验证
3. 回答要简洁直接
"""
```

---

## 五、Agent 类型对比

### 5.1 不同 Agent 架构

| Agent 类型 | 决策方式 | 工具使用 | 适用场景 |
|-----------|----------|----------|----------|
| **Zero-shot Agent** | 一步决定 | LLM 自行推理 | 简单工具调用 |
| **ReAct Agent** | 思考→行动→观察循环 | 多步推理 | 需要多步推理的复杂任务 |
| **Plan-and-Execute Agent** | 先规划再执行 | 按计划顺序调用 | 多步骤长流程任务 |
| **Self-Ask Agent** | 自主提问并分步回答 | 逐步拆解子问题 | 信息搜索类任务 |
| **Multi-Agent** | 多个 Agent 协作 | 分工调用不同工具 | 大型复杂项目 |

### 5.2 Plan-and-Execute 模式详解

```text
Phase 1: 规划
LLM 制定完整计划：
计划：
1. 搜索"2023 年全球碳排放数据"
2. 搜索"主要国家减排政策"
3. 对比分析
4. 生成报告

Phase 2: 执行
按计划逐步执行，每步完成后标记进度：

✅ 步骤 1 完成：获取到数据
⏳ 步骤 2 进行中（...
❌ 步骤 3 报错（数据格式不一致，调整后继续）
...
```

---

## 六、实战：用代码理解 Agent 工作流

### 6.1 模拟一个 ReAct Agent 的执行过程

```python
def simulate_agent_execution():
    """模拟 Agent 一步一步执行的过程"""
    print("🤖 Agent 开始执行")
    print("=" * 60)
    
    # 模拟 Agent 的状态
    state = {
        "question": "2023 年诺贝尔文学奖得主的代表作是什么？",
        "thoughts": [],
        "actions": [],
        "observations": [],
        "step": 0,
    }
    
    # 第 1 轮
    state["step"] += 1
    print(f"\n📝 第 {state['step']} 轮")
    print(f"Thought: 我需要先查 2023 年诺贝尔文学奖得主是谁")
    print(f"Action: search_web('2023 Nobel Prize in Literature winner')")
    print(f"Observation: 2023 年得主是 Jon Fosse")
    state["observations"].append("得主是 Jon Fosse")
    
    # 第 2 轮
    state["step"] += 1
    print(f"\n📝 第 {state['step']} 轮")
    print(f"Thought: 现在查 Jon Fosse 的代表作")
    print(f"Action: search_web('Jon Fosse 代表作')")
    print(f"Observation: 代表作有《名字》《有人会来》《秋之梦》")
    state["observations"].append("代表作品列表")
    
    # 最终回答
    print(f"\n✅ 信息获取完成")
    print(f"Answer: 2023 年诺贝尔文学奖得主是 Jon Fosse，代表作有...")
    
    print("\n" + "=" * 60)
    print(f"共执行 {state['step']} 轮，调用 2 次工具")

simulate_agent_execution()
```

### 6.2 实际使用 LangChain Agent

```python
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.tools import tool
from langchain_core.prompts import PromptTemplate

# 定义工具
@tool
def search_web(query: str) -> str:
    """搜索互联网信息，用于查找最新资料"""
    # 这里简化实现，实际应调用搜索 API
    return f"关于'{query}'的搜索结果..."

@tool
def calculate(expression: str) -> str:
    """执行数学计算"""
    try:
        return str(eval(expression))
    except:
        return "计算错误"

# 初始化 LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0)

# 创建 Agent
tools = [search_web, calculate]
agent = create_react_agent(
    llm=llm,
    tools=tools,
    prompt=PromptTemplate.from_template("{input}"),
)

# Agent 执行器
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,  # 打印中间步骤
    max_iterations=5,  # 最大循环次数
)

# 执行
result = agent_executor.invoke({
    "input": "计算 2023 年诺贝尔奖得主人数乘以 2 的结果"
})
print(result["output"])
```

---

## 七、Agent 的局限性与应对

| 局限性 | 表现 | 应对策略 |
|--------|------|----------|
| **幻觉** | Agent 凭空编造信息 | 设置严格的「不确定就说不知道」规则 |
| **循环** | Agent 在几个步骤间死循环 | 设置 `max_iterations` 上限 |
| **工具误用** | 选了不对的工具 | 优化工具的描述文字 |
| **过度推理** | 简单问题也绕很多步 | 设置「直接回答优先」策略 |
| **Token 消耗** | 来回思考消耗大量 tokens | 精简 Prompt，限制最大步数 |

---

## 八、本章总结

| 知识点 | 一句话说明 |
|--------|------------|
| **Agent vs Chain** | Chain 写死步骤，Agent 自主决策 |
| **ReAct 模式** | 思考→行动→观察 循环直到得出答案 |
| **工具选择** | LLM 根据工具描述决定调用哪个 |
| **终止条件** | 有答案 / 达上限 / 遇异常 |
| **Plan-and-Execute** | 先制定完整计划，再逐步执行 |
| **关键参数** | `max_iterations` 控制最大循环轮次 |

---

## 📝 课后练习

1. **📝 理解题**：用自己的话解释为什么 Agent 比 Chain 更适合"不确定性的任务"
2. **💡 对比题**：分别用 Chain 和 Agent 实现"查询北京当前天气并告诉我是否需要带伞"，对比实现难度和灵活性
3. **🔍 观察题**：运行一个带 `verbose=True` 的 Agent，观察它的思考过程，记录每一步的 Thought/Action/Observation
4. **🚀 挑战题**：设计一个场景，让 Agent 在 3 步内完成推理，再用文字描述每一轮中 Agent 的 Thought/Action/Observation
