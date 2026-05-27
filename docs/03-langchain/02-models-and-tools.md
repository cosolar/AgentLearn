# 3.2 模型调用与工具集成 —— 让 LLM 之手触及真实世界

## 📖 导读

> **模型是 Agent 的大脑，工具是 Agent 的双手。没有工具，Agent 只能思考不能行动。**

LangChain 的核心价值之一就是**统一了 100+ 个 LLM 模型的调用接口**，同时提供了丰富的工具集成。无论你使用 OpenAI、Anthropic 还是本地模型，调用方式完全一样。本章将深入讲解模型调用的标准模式，以及如何为 Agent 配备各种各样的"工具"。

---

## 一、前置知识

| 概念 | 章节 | 说明 |
|------|------|------|
| LLM 基础 | 1.1 | 大语言模型的基本概念 |
| Prompt | 1.3 / 2.1 | 提示工程 |
| Chain | 2.2 | 链式调用模式 |

---

## 二、模型调用的标准接口

### 2.1 基础调用

LangChain 对 LLM 的调用抽象为两种接口：

| 接口 | 输入 | 输出 | 适用场景 |
|------|------|------|----------|
| **LLM**（已弃用，过渡用） | 纯字符串 | 纯字符串 | 传统 LLM 接口 |
| **ChatModel** | 消息列表 `List[BaseMessage]` | 消息对象 `AIMessage` | 对话模型（推荐） |

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# 创建模型实例
llm = ChatOpenAI(
    model="gpt-4o",         # 模型名称
    temperature=0.7,         # 创造度（0-2）
    max_tokens=1000,         # 最大输出 token
    timeout=30,              # 超时秒数
    max_retries=2,           # 失败重试次数
)

# 方式一：传入字符串（自动转为 HumanMessage）
response = llm.invoke("什么是 AI Agent？")
print(response.content)

# 方式二：传入消息列表（推荐）
messages = [
    SystemMessage(content="你是一个专业的 AI 导师，用通俗的语言解释概念。"),
    HumanMessage(content="什么是 AI Agent？"),
]
response = llm.invoke(messages)
print(response.content)
```

### 2.2 流式输出

```python
# 流式输出：逐 token 输出，适合实时显示
for chunk in llm.stream("请写一段关于 AI Agent 的介绍，字数 200 字左右。"):
    print(chunk.content, end="", flush=True)
```

### 2.3 异步调用

```python
import asyncio

async def async_demo():
    llm = ChatOpenAI(model="gpt-4o-mini")
    
    # 异步调用
    response = await llm.ainvoke("推荐三本 Python 入门书籍")
    print(response.content)


# 批量异步调用
async def batch_demo():
    llm = ChatOpenAI(model="gpt-4o-mini")
    
    questions = [
        "Python 是什么？",
        "什么是 AI？",
        "RAG 是什么？",
    ]
    
    # 并发执行
    tasks = [llm.ainvoke(q) for q in questions]
    responses = await asyncio.gather(*tasks)
    
    for q, r in zip(questions, responses):
        print(f"Q: {q}")
        print(f"A: {r.content[:50]}...\n")
```

### 2.4 批量调用（Batch）

```python
# 批量调用（同一次请求处理多条，OpenAI 支持）
llm = ChatOpenAI(model="gpt-4o-mini")

batch_messages = [
    [HumanMessage(content="解释一下 Python 的 list")],
    [HumanMessage(content="解释一下 Python 的 dict")],
    [HumanMessage(content="解释一下 Python 的 set")],
]

# 批量发送（节省 API 调用次数）
responses = llm.batch(batch_messages)
for i, r in enumerate(responses):
    print(f"回复 {i+1}: {r.content[:30]}...")
```

---

## 三、多模型支持

LangChain 支持超过 100 种模型，接口完全一致：

```python
# === OpenAI ===
from langchain_openai import ChatOpenAI
openai_llm = ChatOpenAI(model="gpt-4o")

# === Anthropic (Claude) ===
from langchain_anthropic import ChatAnthropic
claude_llm = ChatAnthropic(model="claude-3-sonnet-20240229")

# === Google (Gemini) ===
from langchain_google_genai import ChatGoogleGenerativeAI
gemini_llm = ChatGoogleGenerativeAI(model="gemini-pro")

# === 本地模型 (Ollama) ===
from langchain_community.chat_models import ChatOllama
ollama_llm = ChatOllama(model="qwen2.5:7b")

# === 兼容 OpenAI API 的本地部署 ===
# vLLM / LM Studio / LocalAI 等
from langchain_openai import ChatOpenAI
local_llm = ChatOpenAI(
    base_url="http://localhost:8000/v1",  # 本地地址
    api_key="not-needed",
    model="local-model",
)
```

---

## 四、工具系统详解

### 4.1 什么是工具？

工具是赋予 Agent"行动能力"的函数。一个工具包含：

| 要素 | 说明 | 示例 |
|------|------|------|
| **名称** | 唯一标识 | `search_web` |
| **描述** | 告诉 LLM 何时使用 | "搜索互联网，获取实时信息" |
| **参数** | 输入参数定义 | `query: str` |
| **实现** | 实际执行的代码 | `return requests.get(...)` |

### 4.2 定义工具

```python
from langchain_core.tools import tool


# 方式一：使用 @tool 装饰器（推荐）
@tool
def search_knowledge_base(query: str) -> str:
    """搜索内部知识库，获取与查询相关的内容"""
    # 实际实现：向量检索
    results = vectorstore.similarity_search(query, k=3)
    return "\n\n".join([r.page_content for r in results])


@tool
def calculate(expression: str) -> str:
    """执行数学计算，输入一个数学表达式"""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"计算错误: {e}"


# 方式二：使用 BaseTool 类
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class WeatherInput(BaseModel):
    """查询天气的输入参数"""
    city: str = Field(description="城市名称，如 北京、上海")
    date: str = Field(description="日期，格式 YYYY-MM-DD，默认为今天")


class WeatherTool(BaseTool):
    """天气查询工具"""
    name: str = "get_weather"
    description: str = "查询指定城市在指定日期的天气"
    args_schema: type = WeatherInput
    
    def _run(self, city: str, date: str = None) -> str:
        # 实际实现：调用天气 API
        return f"{city} {date or '今天'} 天气：晴，25°C"
```

### 4.3 工具的关键设计原则

| 原则 | 错误做法 | 正确做法 |
|------|----------|----------|
| **描述清晰** | "一个搜索工具" | "搜索互联网获取中文技术文档，输入搜索关键词，返回前 3 条结果" |
| **参数明确** | `data: dict` | `query: str, max_results: int = 5` |
| **单一职责** | 一个大工具做所有事 | 拆分为多个小工具各司其职 |
| **错误处理** | 裸抛异常 | 返回友好的错误信息 |

### 4.4 工具数量原则

```text
工具数量 vs Agent 效果的关系：

0-2 个工具：Agent 很快会用，但能力有限
3-8 个工具：✅ 最佳区间，Agent 能准确选择
8-15 个工具：开始出现选择困难，偶尔选错
15+ 个工具：❌ Agent 频繁误选，需要简化
```

---

## 五、绑定工具到模型

### 5.1 基础用法

```python
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

# 定义工具
@tool
def search_web(query: str) -> str:
    """搜索网络获取实时信息"""
    return f"关于'{query}'的搜索结果..."

@tool
def read_file(file_path: str) -> str:
    """读取本地文件内容"""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

# 绑定工具到模型
llm = ChatOpenAI(model="gpt-4o")
llm_with_tools = llm.bind_tools([search_web, read_file])

# 调用时，模型会自动判断是否需要调用工具
response = llm_with_tools.invoke("搜索一下 AI Agent 的最新发展")
print(response.content)
# 如果模型认为需要调用工具，response.tool_calls 会包含调用信息
```

### 5.2 工具调用的完整流程

```python
# 1. 模型决定需要调用工具
response = llm_with_tools.invoke("搜索 AI Agent 的最新发展")

if response.tool_calls:
    # 2. 遍历工具调用请求
    for tool_call in response.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        
        print(f"🛠️ 调用工具: {tool_name}")
        print(f"   参数: {tool_args}")
        
        # 3. 执行工具
        if tool_name == "search_web":
            result = search_web.invoke(tool_args)
        elif tool_name == "read_file":
            result = read_file.invoke(tool_args)
        
        print(f"   结果: {result[:100]}...")
else:
    # 模型直接回答，无需调用工具
    print(f"直接回答: {response.content}")
```

---

## 六、常用工具包

### 6.1 内置工具包

```python
from langchain_community.tools import (
    DuckDuckGoSearchRun,       # 网络搜索
    WikipediaQueryRun,         # Wikipedia
    ArxivQueryRun,             # 学术论文
    PubMedQueryRun,            # 医学文献
    ShellTool,                 # Shell 命令（谨慎使用！）
    HumanInputRun,             # 人工输入
)
```

### 6.2 Tavily 搜索（推荐）

```bash
pip install tavily-python
```

```python
from langchain_community.tools.tavily_search import TavilySearchResults

search = TavilySearchResults(
    max_results=3,
    api_key="tvly-xxx",  # 在 tavily.com 获取
)
result = search.invoke("AI Agent 框架对比")
```

### 6.3 自定义工具集

```python
@tool
def read_pdf(file_path: str, page_start: int = 0, page_end: int = None) -> str:
    """读取 PDF 文件的内容"""
    from langchain_community.document_loaders import PyPDFLoader
    loader = PyPDFLoader(file_path)
    docs = loader.load()[page_start:page_end]
    return "\n".join([d.page_content for d in docs])


@tool
def query_database(sql: str) -> str:
    """执行 SQL 查询（只读），获取数据库信息"""
    import sqlite3
    conn = sqlite3.connect("company.db")
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        results = cursor.fetchall()
        return "\n".join([str(r) for r in results[:10]])
    finally:
        conn.close()


tools = [read_pdf, query_database, search_web]
```

---

## 七、实战：工具增强的问答 Agent

```python
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
import json


# 1. 定义工具
@tool
def search_web(query: str) -> str:
    """搜索实时信息"""
    return {
        "query": query,
        "results": [
            {"title": f"关于{query}的最新报道", "url": "https://example.com/1"},
            {"title": f"{query}的深度分析", "url": "https://example.com/2"},
        ],
    }

@tool
def get_current_time() -> str:
    """获取当前时间"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@tool
def summarize_text(text: str, max_length: int = 200) -> str:
    """总结长文本"""
    return f"[总结] {text[:max_length]}..."


# 2. 创建带工具的 Agent
llm = ChatOpenAI(model="gpt-4o", temperature=0)
tools = [search_web, get_current_time, summarize_text]
agent = llm.bind_tools(tools)

# 3. 执行对话
def chat_with_tools(user_input: str) -> str:
    messages = [
        SystemMessage(content="你是一个智能助手，可以使用各种工具帮助用户。"),
        HumanMessage(content=user_input),
    ]
    
    response = agent.invoke(messages)
    
    # 检查是否调用了工具
    if response.tool_calls:
        for call in response.tool_calls:
            tool_name = call["name"]
            tool_args = call["args"]
            
            # 执行对应工具
            for t in tools:
                if t.name == tool_name:
                    tool_result = t.invoke(tool_args)
                    messages.append(response)  # AI 的工具调用请求
                    messages.append({
                        "role": "tool",
                        "content": str(tool_result),
                        "tool_call_id": call["id"],
                    })
        
        # 让模型基于工具结果生成最终回答
        final_response = agent.invoke(messages)
        return final_response.content
    
    return response.content


# 使用
print(chat_with_tools("现在几点？"))
print(chat_with_tools("搜索 AI Agent 的最新发展"))
```

---

## 八、最佳实践

| 实践 | 说明 |
|------|------|
| **提供清晰的工具描述** | 工具描述直接影响 LLM 能否正确选择 |
| **参数使用类型注解** | `str`, `int`, `List[str]` 帮助 LLM 正确传参 |
| **优雅的错误处理** | 工具异常时返回友好信息，而非抛异常 |
| **控制工具数量** | 最适合 3-8 个 |
| **使用 @tool 装饰器** | 比 BaseTool 类更简洁 |

---

## 九、本章总结

| 概念 | 要点 |
|------|------|
| **ChatModel** | 所有模型统一接口，支持流式和异步 |
| **多模型支持** | OpenAI / Claude / Gemini / 本地模型，切换只需改一行 |
| **@tool** | 将任意函数变为 Agent 可用的工具 |
| **bind_tools** | 将工具列表绑定到模型 |
| **tool_calls** | 模型自动判断何时调用工具 |

---

## 📝 课后练习

1. **✅ 基础**：调用 ChatOpenAI 并绑定一个搜索工具，询问需要搜索的问题
2. **💡 进阶**：定义 3 个自定义工具（搜索、计算、时间），让 Agent 根据问题自动选择
3. **🚀 挑战**：实现一个完整的工具调用循环——模型选工具 → 执行 → 返回结果给模型 → 生成最终回答
4. **🔍 探索**：对比 GPT-4o 和 GPT-4o-mini 在工具选择上的准确率差异
