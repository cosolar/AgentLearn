# 2.2 Chain 模式详解 —— 用管道连接智能

## 📖 导读

> **单独的 LLM 调用就像一个能干的员工，但真正的生产力来自于将多个步骤组合成工作流。**

Chain（链）是 LangChain 的核心设计模式，它将多个组件（LLM调用、数据处理、工具使用等）按顺序连接，形成一个完整的处理流程。**理解 Chain，你就掌握了 Agent 开发的骨架。**

---

## 一、前置知识

在学习 Chain 之前，你需要熟悉以下概念：

| 概念 | 说明 |
|------|------|
| **LLM** | 大语言模型，Chain 中的核心处理单元 |
| **Prompt Template** | 带变量的提示模板，`{variable}` 形式占位 |
| **Output Parser** | 解析 LLM 输出为结构化数据 |
| **管道操作符 `\|`** | LangChain 表达语言（LCEL）的连接操作符 |

---

## 二、什么是 Chain？

### 2.1 直观理解

```text
一个 Chain 就像一条生产线：

输入 → [预处理] → [LLM 处理] → [后处理] → 输出
```

每个环节处理完，把结果交给下一个环节，**上一个环节的输出就是下一个环节的输入**。

### 2.2 为什么要用 Chain？

| 场景 | 单独调用 LLM | 使用 Chain |
|------|-------------|------------|
| 简单问答 | ✅ 够用 | ⚠️ 可能过度设计 |
| 多步骤任务 | ❌ 需要手动拼接多个调用 | ✅ Chain 自动串联 |
| 数据转换 | ❌ 需要自己写转换逻辑 | ✅ LCEL 内置支持 |
| 错误处理 | ❌ 需要手动 try-catch | ✅ 统一错误处理 |
| 可测试性 | ⚠️ 一般 | ✅ 每个环节可独立测试 |

### 2.3 Chain 的核心优势

1. **声明式**：用 `|` 描述流程，而非写 if-else
2. **可组合**：小的 Chain 可以组合成大的 Chain
3. **可观测**：每个环节的输入输出都可追踪
4. **类型安全**：Parser 确保输出符合预期格式

---

## 三、Chain 的核心组件

### 3.1 Prompt Template（提示模板）

```python
from langchain_core.prompts import ChatPromptTemplate

# 无变量模板
prompt_simple = ChatPromptTemplate.from_messages([
    ("system", "你是一个 AI 助手。"),
    ("human", "你好"),
])

# 带变量模板（核心用法）
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个{role}。请用{language}回答用户问题。"),
    ("human", "{input}"),
])

# 使用模板
formatted = prompt.invoke({
    "role": "Python 专家",
    "language": "中文",
    "input": "什么是装饰器？"
})
```

**模板中常用的变量**：

| 变量 | 用途 | 示例 |
|------|------|------|
| `{input}` | 用户输入 | 问题、指令 |
| `{context}` | 上下文信息 | 文档、对话历史 |
| `{role}` | 角色设定 | 专家身份 |
| `{format}` | 输出格式 | JSON、Markdown |

### 3.2 Output Parser（输出解析器）

让 LLM 的输出**可被程序直接使用**。

```python
from langchain_core.output_parsers import StrOutputParser, CommaSeparatedListOutputParser
from langchain_core.output_parsers import JsonOutputParser, PydanticOutputParser
from pydantic import BaseModel

# 1. 字符串解析器（最常用）
str_parser = StrOutputParser()
# 作用：从 AIMessage 对象中提取 .content 字符串

# 2. 逗号分隔列表解析器
list_parser = CommaSeparatedListOutputParser()
# 输入："苹果,香蕉,橙子"
# 输出：["苹果", "香蕉", "橙子"]

# 3. JSON 解析器
json_parser = JsonOutputParser()
# 输入：'{"name": "小明", "age": 18}'
# 输出：{"name": "小明", "age": 18}

# 4. Pydantic 解析器（推荐，带类型校验）
class Person(BaseModel):
    name: str
    age: int

pydantic_parser = PydanticOutputParser(pydantic_object=Person)
```

### 3.3 使用 LCEL 连接组件

LangChain Expression Language（LCEL）用 `|` 操作符将组件串联。

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 初始化组件
llm = ChatOpenAI(model="gpt-4o", temperature=0)

# 定义模板
prompt = ChatPromptTemplate.from_template(
    "请将以下内容翻译成{target_language}：{text}"
)

# 创建 parser
parser = StrOutputParser()

# 用 | 连接成 Chain
chain = prompt | llm | parser

# 一行调用
result = chain.invoke({
    "target_language": "中文",
    "text": "Hello, welcome to the world of AI Agents!"
})
print(result)  # 你好，欢迎来到 AI Agent 的世界！
```

---

## 四、实战：构建多种 Chain

### 4.1 简单文本处理 Chain

```python
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel, RunnablePassthrough

llm = ChatOpenAI(model="gpt-4o", temperature=0.3)

# 一个简单的摘要 Chain
summarize_prompt = PromptTemplate.from_template(
    "请用一句话总结以下内容：\n\n{text}"
)

summarize_chain = summarize_prompt | llm | StrOutputParser()

# 执行
summary = summarize_chain.invoke({
    "text": "AI Agent 是一种能够自主感知环境、理解意图、做出决策并采取行动的智能软件系统..."
})
print(summary)
```

### 4.2 顺序 Chain

多个 Chain 串联，前一个的输出作为后一个的输入。

```python
# Chain 1: 生成大纲
outline_prompt = PromptTemplate.from_template(
    "为以下主题生成一个文章大纲（3-5个点）：\n{theme}"
)
outline_chain = outline_prompt | llm | StrOutputParser()

# Chain 2: 根据大纲写文章
article_prompt = PromptTemplate.from_template(
    "根据以下大纲，写一篇完整的文章：\n\n{outline}"
)
article_chain = article_prompt | llm | StrOutputParser()

# 组合成顺序 Chain
full_chain = outline_chain | article_chain

# 执行
result = full_chain.invoke({"theme": "为什么 AI Agent 是未来的趋势"})
print(result)
```

### 4.3 并行 Chain

同时处理多个任务，最后合并结果。

```python
# 定义三个独立的处理链
chain_analysis = prompt_analysis | llm | StrOutputParser()
chain_summary = prompt_summary | llm | StrOutputParser()
chain_keywords = prompt_keywords | llm | StrOutputParser()

# 并行执行
parallel_chain = RunnableParallel(
    analysis=chain_analysis,
    summary=chain_summary,
    keywords=chain_keywords,
)

# 输入一次，三个结果
results = parallel_chain.invoke({"text": "某篇长文章..."})
print(results["analysis"])
print(results["summary"])
print(results["keywords"])
```

### 4.4 带条件分支的 Chain

根据中间结果决定下一步走向。

```python
def route_by_sentiment(text: str) -> Runnable:
    """根据情感倾向选择不同的处理链"""
    # 先做一个简单的情感分析
    sentiment_chain = (
        PromptTemplate.from_template("判断情感是正面还是负面：{text}")
        | llm
        | StrOutputParser()
    )
    sentiment = sentiment_chain.invoke({"text": text})
    
    if "正面" in sentiment:
        return positive_chain  # 正面 → 推荐处理
    else:
        return negative_chain  # 负面 → 投诉处理

# 使用 RunnableBranch 实现
from langchain_core.runnables import RunnableBranch

branch = RunnableBranch(
    (lambda x: "投诉" in x, complaint_chain),
    (lambda x: "咨询" in x, inquiry_chain),
    default_chain,  # 兜底
)
```

### 4.5 流式输出 Chain

让 LLM 的回复**一个字一个字地出现**，提升用户体验。

```python
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个故事讲述者。"),
    ("human", "讲一个关于{topic}的短故事"),
])

chain = prompt | llm | StrOutputParser()

# 流式调用
print("🤖 AI 正在创作中...\n")
for chunk in chain.stream({"topic": "一只会说话的猫"}):
    print(chunk, end="", flush=True)
# flush=True 让每个字符立刻显示，形成打字效果
```

---

## 五、进阶 Chain 模式

### 5.1 带记忆的 Chain

```python
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain

memory = ConversationBufferMemory()
conversation = ConversationChain(
    llm=llm,
    memory=memory,
    verbose=True,  # 打印中间步骤
)

# 多轮对话
conversation.predict(input="我叫小明")
conversation.predict(input="我叫什么名字？")
# 能正确回答：你叫小明
```

### 5.2 自定义 Runnable

当内置组件不满足需求时，可以自定义处理函数。

```python
from langchain_core.runnables import RunnableLambda

# 自定义数据清洗函数
def clean_text(text: str) -> str:
    """清洗文本：去空格、截断过长内容"""
    text = text.strip()
    if len(text) > 1000:
        text = text[:1000] + "..."
    return text

# 自定义格式化函数
def format_output(text: str) -> dict:
    return {
        "content": text,
        "length": len(text),
        "timestamp": "2024-01-01"
    }

# 组装自定义 Chain
custom_chain = (
    RunnableLambda(clean_text)
    | prompt
    | llm
    | StrOutputParser()
    | RunnableLambda(format_output)
)

result = custom_chain.invoke("  很长很长的输入文本...  ")
print(result["content"])   # 处理后的内容
print(result["length"])    # 内容长度
```

### 5.3 错误处理

```python
from langchain_core.runnables import RunnableConfig
import time

# 添加重试逻辑
def retry_on_fail(func):
    def wrapper(*args, **kwargs):
        max_retries = 3
        for i in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if i == max_retries - 1:
                    raise e
                time.sleep(1)  # 等待1秒后重试
    return wrapper

chain_with_retry = RunnableLambda(retry_on_fail(lambda x: x)) | prompt | llm | StrOutputParser()
```

---

## 六、Chain 的适用场景

| 场景 | 推荐 Chain 类型 | 原因 |
|------|-----------------|------|
| 翻译应用 | 简单 LCEL Chain | 输入翻译，输出结果 |
| 文章生成器 | 顺序 Chain | 先生成大纲，再写全文 |
| 内容审核系统 | 并行 Chain | 同时审核敏感词、格式、版权 |
| 客服机器人 | 条件分支 Chain | 根据意图走不同流程 |
| 数据分析报告 | 自定义 Runnable | 需要数据清洗+分析+格式化 |

---

## 七、常见问题与排查

### ❌ invoke() 参数错误

```python
# ❌ 错误：模板需要字典
chain.invoke("直接传字符串")

# ✅ 正确：传字典
chain.invoke({"input": "用户输入", "role": "专家"})
```

### ❌ Chain 连接顺序错误

```python
# ❌ 错误：LLM 不能直接接 PromptTemplate
Chain = llm | prompt

# ✅ 正确：先模板 → 再 LLM → 最后 Parser
Chain = prompt | llm | parser
```

### ❌ 输出解析失败

```python
# 如果 LLM 输出不符合 parser 的格式预期
# 在 Prompt 中明确指定输出格式

prompt = PromptTemplate.from_template(
    """严格按 JSON 格式输出，不要包含其他内容：
    
    主题：{topic}
    
    {{"title": "标题", "summary": "摘要"}}
    """
)
```

---

## 八、本章总结

| 概念 | 一句话说明 |
|------|------------|
| **Chain** | 用 `\|` 连接多个组件的处理流程 |
| **LCEL** | LangChain 表达语言，声明式定义 Chain |
| **Prompt Template** | 带变量的提示模板 |
| **Output Parser** | 将 LLM 回复解析为结构化数据 |
| **顺序 Chain** | 前一个输出是后一个输入 |
| **并行 Chain** | 同时执行多个独立处理 |
| **RunnableLambda** | 自定义处理函数 |

---

## 📝 课后练习

1. **✅ 基础**：实现一个"翻译 + 总结"的顺序 Chain：先翻译英文文章为中文，再总结中文内容
2. **💡 进阶**：实现一个并行 Chain：对一篇文章同时做"情感分析"和"关键词提取"
3. **🚀 挑战**：实现一个带条件分支的客服 Chain：如果用户输入包含"投诉"，走投诉处理链；包含"咨询"，走咨询链；其他走默认回复
4. **🔍 探索**：在 LangChain 官方文档中查找 `RunnableParallel` 和 `RunnablePassthrough` 的官方示例
