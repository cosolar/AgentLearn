# 2.2 Chain 模式详解 —— LCEL、Runnable 协议与确定性工作流

> 📅 更新至 2026-10 · 技术栈基线见 [知识库大纲](../知识库大纲.md)

## 📖 导读

> **一句话结论**：Chain 是 LangChain 用 **LCEL（LangChain Expression Language）** 把多个组件用 `|` 串起来的**声明式工作流**；在 v1 中，**确定性流程用 LCEL，自主决策交给 `create_agent`**——二者分工明确，不是替代关系。

- **前置阅读**：[2.1 Prompt 与上下文工程](./01-Prompt与上下文工程.md)。
- **本章你将学到**：
  1. Chain 的价值与 LCEL 的设计思想；
  2. **Runnable 协议**（统一的 `invoke/batch/stream` 接口与组合原语）；
  3. 顺序、并行、分支、**回退（fallback）** 四类工作流的写法；
  4. **LCEL 在 LangChain v1 中的定位**——为什么它管"确定性流程"，而 Agent 的循环由 `create_agent` 封装；
  5. 常见错误与排查。

---

## 一、前置知识

| 概念 | 说明 |
|------|------|
| **LLM** | Chain 中的核心处理单元 |
| **Prompt Template** | 带变量的提示模板，`{variable}` 形式占位 |
| **Output Parser** | 把 LLM 输出解析为字符串/结构化数据 |
| **管道操作符 `\|`** | LCEL 的连接符，`a \| b` 表示"a 的输出喂给 b" |

---

## 二、什么是 Chain？

### 2.1 直观理解

Chain 就像一条生产线：

```
输入 → [预处理] → [LLM 处理] → [后处理] → 输出
```

**上一个环节的输出，就是下一个环节的输入。**

### 2.2 为什么要用 Chain？

| 场景 | 单独调用 LLM | 使用 Chain |
|------|-------------|------------|
| 简单问答 | ✅ 够用 | ⚠️ 可能过度设计 |
| 多步骤任务 | ❌ 需手动拼接 | ✅ 自动串联 |
| 数据转换 | ❌ 需自写逻辑 | ✅ 内置组合原语 |
| 可测试性 | ⚠️ 一般 | ✅ 每个环节可独立测试 |
| 可观测性 | ⚠️ 一般 | ✅ 每步输入输出可追踪 |

### 2.3 Chain 的核心优势

1. **声明式**：用 `|` 描述流程，而非 if-else；
2. **可组合**：小 Chain 可组合成大 Chain；
3. **统一接口**：所有组件都实现 Runnable 协议，可无缝拼接；
4. **天然支持流式/批量/异步**：无需为每种能力重写代码。

---

## 三、Runnable 协议（核心）

LCEL 的基石是 **Runnable 协议**：只要一个对象实现了 Runnable 接口，就能用 `|` 连接。`ChatModel`、`PromptTemplate`、`OutputParser`、`Retriever` 都是 Runnable。

### 3.1 统一调用接口

| 方法 | 作用 | 是否流式 |
|------|------|----------|
| `invoke(input)` | 处理单个输入，返回完整结果 | ❌ |
| `batch(inputs)` | 批量处理，返回结果列表 | ❌ |
| `stream(input)` | 流式返回结果块 | ✅ |
| `ainvoke / abatch / astream` | 上述方法的异步版本 | 异步 |

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-5.5", temperature=0)
prompt = ChatPromptTemplate.from_template("用一句话解释：{topic}")
chain = prompt | llm | StrOutputParser()

print(chain.invoke({"topic": "什么是 LCEL"}))                 # 单次
print(chain.batch([{"topic": "A"}, {"topic": "B"}]))         # 批量
for chunk in chain.stream({"topic": "流式输出"}):             # 流式
    print(chunk, end="", flush=True)
```

### 3.2 组合原语

| 原语 | 作用 | 典型用途 |
|------|------|----------|
| `RunnableSequence`（`a \| b`） | 顺序执行 | 串行流程 |
| `RunnableParallel` | 并行执行，输出合并为字典 | 一次输入、多路处理 |
| `RunnablePassthrough` | 原样透传输入 | 保留原始输入与中间结果 |
| `RunnableLambda` | 包装任意 Python 函数 | 自定义处理步骤 |
| `RunnableBranch` | 条件分支 | 按规则路由 |
| `.with_fallbacks()` | 失败时回退到备用链 | 容错、多模型兜底 |
| `.with_retry()` | 自动重试 | 处理瞬时网络抖动 |

---

## 四、核心组件

### 4.1 Prompt Template

```python
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

# 带变量的消息模板（推荐）
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个{role}。请用{language}回答。"),
    ("human", "{input}"),
])

messages = prompt.invoke({"role": "Python 专家", "language": "中文", "input": "什么是装饰器？"})
print(messages.to_messages())
```

### 4.2 Output Parser

```python
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser

str_parser = StrOutputParser()      # AIMessage → str（最常用）
json_parser = JsonOutputParser()    # 文本 → dict

# 需要带类型校验的结构化输出时，优先用 v1 的 response_format=ToolStrategy(...)
# （见 2.1），而不是 PydanticOutputParser。
```

---

## 五、实战：四类工作流

### 5.1 顺序 Chain

前一个的输出作为后一个的输入：

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-5.5", temperature=0.3)
parser = StrOutputParser()

outline_chain = (
    ChatPromptTemplate.from_template("为以下主题生成 3-5 点的文章大纲：\n{theme}")
    | llm | parser
)
article_chain = (
    ChatPromptTemplate.from_template("根据以下大纲写一篇完整文章：\n\n{outline}")
    | llm | parser
)

# 组合成顺序 Chain：outline_chain 的输出直接喂给 article_chain
full_chain = outline_chain | article_chain

print(full_chain.invoke({"theme": "为什么 AI Agent 是未来趋势"}))
```

> 💡 注意 `outline_chain` 输出的是**字符串**，而 `article_chain` 的模板需要 `{outline}`。LCEL 会自动把字符串映射到模板中同名的唯一变量，因此能直接串联。

### 5.2 并行 Chain

一次输入，多路处理，结果合并为字典：

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-5.5", temperature=0)
parser = StrOutputParser()

analysis = ChatPromptTemplate.from_template("分析以下文本的结构：\n{text}") | llm | parser
summary = ChatPromptTemplate.from_template("用一句话总结：\n{text}") | llm | parser
keywords = ChatPromptTemplate.from_template("提取 5 个关键词：\n{text}") | llm | parser

# RunnablePassthrough 保留原始 text，三路并行共享同一输入
parallel = RunnableParallel(
    original=RunnablePassthrough(),
    analysis=analysis,
    summary=summary,
    keywords=keywords,
)

results = parallel.invoke({"text": "某篇长文章……"})
print(results["summary"])
print(results["keywords"])
print(results["original"]["text"])   # 原始输入仍可访问
```

### 5.3 条件分支 Chain

根据输入或中间结果决定走哪条路。用 `RunnableBranch` 声明式实现：

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableBranch, RunnableLambda
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-5.5", temperature=0)
parser = StrOutputParser()

def make_chain(role: str):
    return ChatPromptTemplate.from_template(f"你是{role}，请回应：{{input}}") | llm | parser

complaint_chain = make_chain("投诉处理专员")
inquiry_chain = make_chain("售前咨询顾问")
default_chain = make_chain("通用客服")

branch = RunnableBranch(
    (lambda x: "投诉" in x["input"], complaint_chain),
    (lambda x: "咨询" in x["input"], inquiry_chain),
    default_chain,          # 兜底：以上都不匹配时走这里
)

print(branch.invoke({"input": "我要投诉你们的物流"}))
print(branch.invoke({"input": "这个功能怎么用？"}))
```

> ⚠️ 复杂的分支/循环（尤其是需要回边的图）建议改用 **LangGraph**（见 [4.3 路由与循环](../04-LangGraph进阶/03-路由与循环.md)），LCEL 更适合"有向无环"的流程。

### 5.4 回退与重试（容错）

生产环境必须考虑"主模型挂了怎么办"。`.with_fallbacks()` 与 `.with_retry()` 是 LCEL 内置的容错能力：

```python
import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

primary = ChatOpenAI(
    model=os.getenv("LLM_MODEL_NAME", "gpt-5.5"),
    api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_API_BASE"),
)
backup = ChatOpenAI(model="gpt-5-mini", temperature=0)   # 备用模型

prompt = ChatPromptTemplate.from_template("用一句话解释：{topic}")
parser = StrOutputParser()

chain = (
    prompt
    | primary.with_retry(stop_after_attempt=2)          # 先重试
    | parser
).with_fallbacks([prompt | backup | parser])            # 再回退

print(chain.invoke({"topic": "LCEL 的容错机制"}))
```

| 能力 | 方法 | 说明 |
|------|------|------|
| **回退** | `.with_fallbacks([...])` | 主链抛错时依次尝试备用链 |
| **重试** | `.with_retry(stop_after_attempt=n)` | 对瞬时错误自动重试 |

### 5.5 流式输出

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-5.5", temperature=0.7)
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个故事讲述者。"),
    ("human", "讲一个关于{topic}的短故事"),
])
chain = prompt | llm | StrOutputParser()

for chunk in chain.stream({"topic": "一只会说话的猫"}):
    print(chunk, end="", flush=True)   # flush 形成打字机效果
```

---

## 六、LCEL 在 LangChain v1 中的定位

这是本章最重要的一节。**v1 把"确定性流程"和"自主决策"分成了两条路：**

| 维度 | LCEL（Chain） | `create_agent`（Agent） |
|------|---------------|-------------------------|
| **控制流** | 开发者预先定义 | LLM 运行时决定 |
| **是否循环** | ❌ 无环（DAG） | ✅ 内置"模型↔工具"循环 |
| **工具使用** | 手动编排 | 模型自主选择 |
| **适用场景** | 步骤固定的流水线 | 不确定的多步任务 |
| **可预测性** | 高 | 中（需护栏） |

**一句话选型**：

- 步骤**固定、可预测** → 用 **LCEL**；
- 步骤**需要模型当场决定** → 用 **`create_agent`**；
- 需要**复杂分支/循环/人工介入** → 用 **LangGraph**。

> 🆕 **v1 关键变化**：旧版的 `LLMChain`、`ConversationChain`、`ConversationBufferMemory` 等已迁往 [`langchain-classic`](https://pypi.org/project/langchain-classic/)。新项目里：
> - 简单链 → 直接用 LCEL 组合（`prompt | llm | parser`）；
> - 会话记忆 → 用 LangGraph 的 `checkpointer`（见 [2.4 记忆机制](./04-记忆机制.md)）；
> - Agent → 用 `create_agent`（见 [2.3](./03-Agent核心架构.md)）。

**二者是协作关系**：典型生产架构是"**Agent 负责决策，LCEL 负责执行**"——把确定性的后处理（格式化、校验、落库）做成 LCEL 链，嵌在 Agent 的工具或中间件里。

---

## 七、常见问题与排查

### ❌ `invoke()` 参数类型错误

```python
# ❌ 模板需要字典，却传了字符串
chain.invoke("直接传字符串")

# ✅ 正确
chain.invoke({"input": "用户输入", "role": "专家"})
```

### ❌ 连接顺序错误

```python
# ❌ LLM 的输出不是消息模板，接不上
bad = llm | prompt

# ✅ 正确：模板 → LLM → Parser
good = prompt | llm | parser
```

### ❌ 输出解析失败

```python
# 原因：LLM 输出不符合 parser 预期格式
# 解决 1：在 Prompt 中明确要求格式
# 解决 2：需要结构化时，改用 response_format=ToolStrategy(Model)（v1 推荐）
```

### ❌ `RunnableBranch` 报 "no default"

```python
# 必须提供兜底分支（最后一个位置参数）
branch = RunnableBranch((cond1, chain1), (cond2, chain2), default_chain)
```

---

## 本章小结

| 概念 | 说明 |
|------|------|
| **Chain / LCEL** | 用 `\|` 声明式连接多个 Runnable 组件 |
| **Runnable 协议** | 统一 `invoke/batch/stream`（+ 异步）接口 |
| **顺序** | `a \| b`，前一个输出喂给后一个 |
| **并行** | `RunnableParallel`，一次输入、多路处理 |
| **透传** | `RunnablePassthrough`，保留原始输入 |
| **分支** | `RunnableBranch`，必须带兜底分支 |
| **回退/重试** | `.with_fallbacks()` / `.with_retry()` |
| **v1 定位** | 确定性流程用 LCEL，自主决策用 `create_agent`，复杂编排用 LangGraph |

---

## 📝 课后练习

**基础**
1. 实现一个"翻译 + 总结"的顺序 Chain：先把英文文章翻译成中文，再总结中文内容。

**进阶**
2. 实现一个并行 Chain：对一篇文章同时做"情感分析"和"关键词提取"，并保留原文输出。

**挑战**
3. 实现一个带**回退**的客服 Chain：主模型用 `gpt-5.5`，备用模型用 `gpt-5-mini`，用 `.with_fallbacks()` 保证主模型不可用时自动降级；再叠加条件分支（含"投诉"走投诉链）。
4. 用一句话回答：为什么"需要模型自己决定调几次工具"的任务不适合用纯 LCEL 实现？请结合"有环 vs 无环"说明。
