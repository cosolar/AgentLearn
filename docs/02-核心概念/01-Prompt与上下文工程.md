# 2.1 Prompt 与上下文工程 —— 从"写好一句话"到"设计整个信息环境"

> 📅 更新至 2026-10 · 技术栈基线见 [教程大纲](../教程大纲.md)

## 📖 导读

> **一句话结论**：相同的模型，不同的 Prompt 得到完全不同的结果；而在 2026 年，决定 Agent 上限的已不只是"那句话写得好不好"，而是**送进上下文窗口的全部信息组织得好不好**——这就是从 Prompt Engineering 到 **Context Engineering** 的演进。

- **前置阅读**：[1.3 第一个 Agent](../01-入门基础/03-第一个Agent.md)。
- **本章你将学到**：
  1. Prompt 的四大基础技法（Zero-shot / Few-shot / CoT / Role）；
  2. 五种进阶模式（ReAct / Plan-and-Solve / Self-Refine / 结构化输出 / Persona Cascade）；
  3. **Prompt → Context Engineering 的演进**，以及"**信噪比**"与"**context rot**"两个关键概念；
  4. 上下文工程的四个核心动作，以及 LangChain v1 的工程化支持（Middleware）；
  5. 可复用的 Prompt 模板与优化 checklist。

---

## 一、前置知识

| 概念 | 说明 |
|------|------|
| **System Prompt** | 系统级指令，设定角色、规则与输出约束（`create_agent` 的 `system_prompt`） |
| **User Prompt** | 用户输入，包含具体问题与指令 |
| **Few-shot** | 在 Prompt 中提供示例，引导模型按示例模式输出 |
| **Token** | LLM 的最小处理单元，1 个汉字 ≈ 2–3 tokens |
| **Context Window** | 一次能处理的最大 token 数（2026 主流模型约 128K–1M） |
| **上下文工程** | 设计送入模型窗口的**全部信息**（指令、示例、检索、工具结果、记忆） |

---

## 二、为什么 Prompt 如此重要？

### 2.1 直观对比

```text
❌ 差的 Prompt：
"写一个故事"

✅ 好的 Prompt：
"请写一个 800 字的科幻短篇，核心创意是'时间可以被购买但不能被创造'，
主人公是一个时间商人。第三人称限知视角，开头设悬念，结尾要反转。"
```

同样的模型，后者的输出在**方向、结构、质量稳定性**上都显著更好。

### 2.2 Prompt 的质量差距

| 维度 | 差 Prompt | 好 Prompt |
|------|-----------|-----------|
| **明确性** | 模糊、多义 | 清晰、具体、无歧义 |
| **约束性** | 无约束 | 有格式/长度/风格约束 |
| **上下文** | 缺少背景 | 提供完整上下文 |
| **示例** | 无示例 | 有准确的 few-shot 示例 |
| **结构** | 一段文字 | 分部分、分层级 |

---

## 三、基础 Prompt 技巧

### 3.1 Zero-shot（零样本提示）

不给示例，直接让模型完成任务。适用于**简单、常见**的任务。

```text
请判断以下文本的情感是"正面"还是"负面"：
"这部电影太精彩了，我看了三遍！"
```

**局限**：对复杂或罕见任务，效果不稳定。

### 3.2 Few-shot（少样本提示）

提供 2–5 个示例，让模型"照猫画虎"。适用于**格式严格或模式复杂**的任务。

```text
输入：今天天气真好        输出：闲聊
输入：帮我查一下订单 12345 输出：查询
输入：我要投诉你们的产品   输出：投诉
输入：价格实惠，质量不错   输出：
```

| 示例数量 | 效果 |
|----------|------|
| 0（zero-shot） | 基线 |
| 1–3 | 大多数任务的最佳区间 |
| 3–5 | 复杂任务更稳 |
| 5+ | 边际递减，可能分散注意力 |

### 3.3 Chain-of-Thought（CoT，思维链）

引导模型**先讲逻辑再给答案**，适用于数学、逻辑、推理任务。

```text
小明有 5 个苹果，吃了 2 个，又买了 3 个，现在有几个？请逐步推理。
```

研究表明，CoT 在推理类任务上能显著提升准确率。注意：**推理型模型（如 GPT-5.x 的推理档）已内置思维链**，此时不必再手动加"请逐步推理"，过度引导反而可能画蛇添足。

### 3.4 Role Prompting（角色设定）

给模型分配**专业角色**，激活领域知识：

```text
你是一名资深 Python 架构师，专注于高性能 Web 服务，熟悉 FastAPI 的最佳实践与陷阱。
请 review 以下代码……
```

---

## 四、进阶 Prompt 模式

### 4.1 ReAct（Reasoning + Acting）

让模型**边思考边行动**，是 Agent 的基础模式（原理详见 [2.3 Agent 核心架构](./03-Agent核心架构.md)）：

```text
问题：用户的问题是什么？
思考：我需要做什么才能回答？
行动：调用某个工具（如 search_web / calculate）
观察：工具返回的结果
思考：现在能否回答？
回答：最终答案
```

> 💡 在 LangChain v1 中，**你无需手写这段 ReAct 提示词**——`create_agent` 已把"思考→行动→观察"循环内置。手写仅用于理解原理或高度定制。

### 4.2 Plan-and-Solve（先规划后执行）

先制定完整计划，再逐步执行，适合**复杂多步骤任务**：

```text
请按以下步骤完成技术文章写作：
第一步：制定大纲（列出核心论点与子标题）
第二步：逐章写作（每章 300–500 字）
第三步：全局修改（检查逻辑连贯性、统一术语）
现在，开始第一步。
```

### 4.3 Self-Refine（自我优化）

让模型先输出，再**自查并优化**：

```text
第一步：请写一段关于 AI Agent 的介绍，200 字左右。
第二步：检查上述内容是否存在（1）技术不准确（2）逻辑不连贯（3）可读性差。
第三步：根据审查结果生成优化版本。
```

### 4.4 结构化输出（Structured Output）

指定输出格式，让模型回复**可被程序直接解析**。在 LangChain v1 中，推荐用 `create_agent` 的 `response_format` 配合 `ToolStrategy`，**在主循环内一次生成结构化结果**：

```python
from pydantic import BaseModel, Field
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy


class ProductReview(BaseModel):
    """产品分析结果"""
    name: str = Field(description="产品名")
    category: str = Field(description="类别")
    pros: list[str] = Field(description="优点列表")
    cons: list[str] = Field(description="缺点列表")
    rating: int = Field(description="评分，1-10")


agent = create_agent(
    model="gpt-5.5",
    tools=[],
    response_format=ToolStrategy(ProductReview),   # v1 推荐：结构化输出策略
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "分析一下 iPhone 15 Pro"}]}
)

# structured_response 是已校验的 Pydantic 对象
review = result["structured_response"]
print(review.name, review.rating)
```

> 📌 更完整的结构化输出与 `handle_errors` 配置见 [3.1 LangChain v1 核心组件](../03-LangChain实战/01-LangChain核心组件.md)。

### 4.5 Persona Cascade（多重人格级联）

在一个对话中让模型扮演**多个角色**依次处理：

```text
你现在是三位一体的专家团队：
1. 🧑‍💻 工程师：评估技术可行性
2. 🎨 设计师：评估用户体验
3. 📊 产品经理：评估商业价值
请三位依次给出意见，最后产品经理综合给出最终建议。
产品想法：一个用 AI 自动生成代码注释的工具
```

---

## 五、从 Prompt Engineering 到 Context Engineering

### 5.1 三阶段演进

| 阶段 | 核心问题 | 主要手段 | 时代 |
|------|----------|----------|------|
| **Prompt Engineering** | "这句话怎么说" | 措辞、格式、few-shot、CoT | 2022–2024 |
| **RAG / 检索增强** | "从哪找知识塞进去" | 向量检索、重排 | 2023–2025 |
| **Context Engineering** | "整个窗口该放什么、不该放什么" | 写入/选择/压缩/隔离 | **2025–2026** |

到了 2026 年，业界共识是：**决定 Agent 效果的不再只是"那句 Prompt 写得好不好"，而是"送进上下文窗口的信息组织得好不好"。**

### 5.2 什么是"上下文"？

一次 LLM 调用真正接收到的"上下文"，远不止用户的提问：

```
┌─────────────────── 上下文窗口（Context Window）───────────────────┐
│ ① System Prompt   角色、规则、输出约束                             │
│ ② 工具定义        Agent 可调用的工具及其 schema                     │
│ ③ 记忆           历史对话摘要 / 用户画像 / 长期记忆检索结果          │
│ ④ RAG 检索片段   从知识库召回的文档块                               │
│ ⑤ 工具执行结果   上一轮工具返回的 Observation                       │
│ ⑥ 当前用户输入    本轮的 HumanMessage                              │
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 两个关键概念：信噪比 与 Context Rot

**信噪比（Signal-to-Noise Ratio）**：上下文里"真正有用的信息"占比越高，模型表现越好。堆砌无关内容会稀释有效信号。

**Context Rot（上下文腐烂）**：**上下文越长，模型对其中信息的利用能力越差**——即使没超出窗口上限，塞入过多内容也会让关键信息被"淹没"，导致：
- 遗忘中间位置的指令（"lost in the middle"）；
- 抓错重点、被无关内容带偏；
- 成本与时延上升，而质量下降。

> ⚠️ **反直觉的结论**：**"能塞 100 万 token" ≠ "应该塞 100 万 token"**。上下文工程的目标是**提高信噪比**，而不是填满窗口。

### 5.4 一条实践原则

> **不是"给得越多越好"，而是"给的每一条都要有理由"。**
> 能压缩就压缩，能检索就按需检索，能隔离就隔离。

---

## 六、上下文工程的四个核心动作

### 6.1 四动作

| 动作 | 解决的问题 | 常用手段 |
|------|-----------|----------|
| **写入（Write）** | 该记什么 | 记忆抽取、要点沉淀、外部存储 |
| **选择（Select）** | 该放什么进窗口 | RAG 检索、记忆召回、工具筛选 |
| **压缩（Compress）** | 窗口放不下 | 摘要、裁剪（`trim_messages`）、分层记忆 |
| **隔离（Isolate）** | 信息互相干扰 | 子 Agent、分步处理、专用上下文 |

### 6.2 LangChain v1 的工程化支持：Middleware

v1 把上下文工程做成了"开箱即用"的**中间件（Middleware）**：

```python
from langchain.agents import create_agent
from langchain.agents.middleware import (
    SummarizationMiddleware,     # 历史过长时自动摘要压缩（Compress）
    PIIMiddleware,               # 发送前脱敏敏感信息（选择/净化）
)

agent = create_agent(
    model="gpt-5.5",
    tools=[],
    middleware=[
        SummarizationMiddleware(trigger={"tokens": 4000}),   # 超 4000 token 自动摘要
        PIIMiddleware(strategy="redact"),                    # 脱敏而非阻断
    ],
)
```

> 💡 另有 `HumanInTheLoopMiddleware(interrupt_on={"工具名": True})` 用于敏感工具调用前的人工审批（需配合 `checkpointer`），详见 [2.3 Agent 核心架构](./03-Agent核心架构.md)。

> 📌 中间件的完整讲解见 [3.1 LangChain v1 核心组件](../03-LangChain实战/01-LangChain核心组件.md)；记忆的工程实现见 [2.4 记忆机制](./04-记忆机制.md)。

### 6.3 一句话记住

> **Prompt Engineering 关心"怎么说"，Context Engineering 关心"给模型看什么"。** 后者才是 2026 年 Agent 工程的核心竞争力。

---

## 七、Prompt 模板库（可直接复用）

### 7.1 代码审查

```text
你是一名资深代码审查员，请 review 以下代码：
1. 找出潜在 bug 和逻辑错误
2. 指出性能问题
3. 检查代码风格与最佳实践
4. 指出安全隐患

输出格式：
- 严重问题（必须修复）：
- 建议改进（推荐修改）：
- 风格建议（可选）：
- 总结（总体评价 + 修改优先级）：

代码：
{code}
```

### 7.2 知识问答

```text
你是一名专业的技术导师。请回答以下问题：
1. 先用一句话给出核心答案
2. 然后分点详细解释
3. 如果可能，提供代码示例
4. 指出常见误解或踩坑点

问题：{question}
```

### 7.3 文本总结

```text
请总结以下内容：
【任务】
1. 用 3 句话概括核心内容
2. 列出 3–5 个关键要点
3. 保留文中的关键数据

【原文】
{text}

【输出格式】
核心概括：{一句话}
详细总结：{3 句话}
关键要点：
- ...
原文数据：{保留关键数据}
```

---

## 八、Prompt 优化 checklist

| 检查项 | 说明 |
|--------|------|
| ✅ **目标明确** | 模型知道你要什么吗？ |
| ✅ **约束充分** | 格式、长度、风格定了吗？ |
| ✅ **上下文完整** | 背景信息给够了吗？ |
| ✅ **边界清晰** | 什么能做、什么不能做说清了吗？ |
| ✅ **示例准确** | 示例是否典型、是否与目标一致？ |
| ✅ **输出可解析** | 需要程序处理时，格式指定了吗？ |
| ✅ **信噪比高** | 每条信息都必要吗？有没有可以删掉的噪声？ |

**常见错误**：

```text
❌ 过于模糊： "总结这篇文章"
✅ 清晰具体： "用 3 句话总结，突出核心论点，中文输出，每句 ≤ 50 字"

❌ 信息过载： 一次把 10 个要求塞进一个 Prompt
✅ 结构清晰： 分步骤、分模块提供信息

❌ 噪声堆积： 把整个文件塞进去让模型自己找
✅ 精准选择： 只放相关片段（检索 + 裁剪）
```

---

## 本章小结

| 要点 | 说明 |
|------|------|
| **Zero-shot / Few-shot** | 不给示例 / 给 2–5 个示例 |
| **CoT** | 引导展示推理过程（推理模型可能已内置） |
| **Role** | 分配专业角色激活领域知识 |
| **进阶模式** | ReAct / Plan-and-Solve / Self-Refine / 结构化输出 / Persona |
| **结构化输出** | v1 用 `response_format=ToolStrategy(Model)` |
| **Context Engineering** | 设计送进窗口的全部信息，核心是**提高信噪比** |
| **Context Rot** | 上下文越长，信息利用率越差——"能塞"不等于"该塞" |
| **四动作** | 写入 / 选择 / 压缩 / 隔离 |

---

## 📝 课后练习

**基础**
1. 针对同一任务（如"用 Python 写一个计算器"），分别用 Zero-shot 和 Few-shot（提供 3 个代码示例）写 Prompt，对比输出质量。

**进阶**
2. 用本文的 checklist 优化你之前写过的某个 Prompt，记录优化前后的输出差异，并指出优化主要提升了哪个维度（明确性/约束/信噪比）。
3. 用 `response_format=ToolStrategy(...)` 写一个 Agent，让它把一段自由文本解析成你自定义的 Pydantic 模型（如"简历 → name/skills/years"）。

**挑战**
4. 构造一个"反例实验"：给同一个模型分别喂入 200 token 的精炼上下文和 4000 token 的冗余上下文（后者包含大量无关内容），完成同一任务。对比两次的准确率与耗时，用"信噪比/context rot"解释结果。
