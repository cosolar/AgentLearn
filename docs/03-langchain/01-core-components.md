# 3.1 LangChain 核心组件 —— 框架全景与组件详解

## 📖 导读

LangChain 是当前最流行的 LLM 应用开发框架，也是构建 AI Agent 最常用的基础设施。**它不是一个大而全的"黑盒"，而是一组精心设计的可组合模块。** 理解 LangChain 的架构和核心组件，是掌握 Agent 开发的必经之路。

---

## 一、前置知识

学习本章前，建议你已完成：

- ✅ 环境搭建（第 1.2 节）
- ✅ 第一个 Agent（第 1.3 节）
- ✅ Prompt Engineering 基础（第 2.1 节）
- ✅ Chain 模式（第 2.2 节）

---

## 二、LangChain 架构全景

### 2.1 整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        LangChain 框架                             │
│                                                                   │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐ │
│  │     Models     │  │    Prompts     │  │      Memory         │ │
│  │  ┌──────────┐  │  │  ┌──────────┐  │  │  ┌───────────────┐  │ │
│  │  │  LLMs    │  │  │  │Template  │  │  │  │ Buffer        │  │ │
│  │  │ Chat     │  │  │  │Parsers   │  │  │  │ Window        │  │ │
│  │  │ Embed    │  │  │  │Selector  │  │  │  │ Summary       │  │ │
│  │  └──────────┘  │  │  └──────────┘  │  │  │ Vector        │  │ │
│  └────────────────┘  └────────────────┘  │  └───────────────┘  │ │
│                                           └─────────────────────┘ │
│                                                                   │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐ │
│  │     Chains     │  │     Agents     │  │   Document Loaders  │ │
│  │  ┌──────────┐  │  │  ┌──────────┐  │  │  ┌───────────────┐  │ │
│  │  │  LCEL    │  │  │  │ ReAct    │  │  │  │ PDF, HTML,    │  │ │
│  │  │ Sequential│  │  │  │ Tool Use │  │  │  │ Markdown...   │  │ │
│  │  │ Parallel  │  │  │  │ Multi    │  │  │  └───────────────┘  │ │
│  │  └──────────┘  │  │  └──────────┘  │  └─────────────────────┘ │
│  └────────────────┘  └────────────────┘                           │
│                                                                   │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐ │
│  │  Vector Stores │  │   Callbacks    │  │   Integrations      │ │
│  │  ┌──────────┐  │  │  ┌──────────┐  │  │  ┌───────────────┐  │ │
│  │  │ Chroma   │  │  │  │ Logging  │  │  │  │ OpenAI, ...   │  │ │
│  │  │ FAISS    │  │  │  │ Tracing  │  │  │  │ 100+ 集成     │  │ │
│  │  │ Pinecone │  │  │  │ Monitor  │  │  │  └───────────────┘  │ │
│  │  └──────────┘  │  │  └──────────┘  │  └─────────────────────┘ │
│  └────────────────┘  └────────────────┘                           │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 架构分层

| 层级 | 说明 | 核心类 |
|------|------|--------|
| **Model I/O** | 模型输入输出管理 | `ChatOpenAI`, `PromptTemplate`, `OutputParser` |
| **Retrieval** | 数据检索与增强 | `DocumentLoader`, `TextSplitter`, `VectorStore` |
| **Chains** | 流程编排 | `RunnableParallel`, `RunnableSequence` |
| **Agents** | 自主决策系统 | `AgentExecutor`, `Tool`, `Agent` |
| **Memory** | 记忆管理 | `ConversationBufferMemory`, `VectorStoreRetrieverMemory` |
| **Callbacks** | 生命周期钩子 | `BaseCallbackHandler`, `LangChainTracer` |

---

## 三、核心组件详解

### 3.1 Models（模型）

LangChain 提供统一的接口来调用不同提供商的模型。

#### LLM vs ChatModel

| 特性 | LLM（传统） | ChatModel（聊天） |
|------|-------------|-------------------|
| **输入** | 纯文本字符串 | 消息列表（System/Human/AI） |
| **输出** | 纯文本字符串 | AIMessage 对象 |
| **示例** | OpenAI, LlamaCpp | ChatOpenAI, ChatAnthropic |
| **当前趋势** | 逐渐被 ChatModel 替代 | ✅ 主流选择 |

```python
# LLM（传统方式）
from langchain_openai import OpenAI
llm = OpenAI(model="gpt-3.5-turbo-instruct")
result = llm.invoke("你好")

# ChatModel（推荐方式）
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

chat = ChatOpenAI(model="gpt-4o")
messages = [
    SystemMessage(content="你是一个 AI 助手。"),
    HumanMessage(content="你好"),
]
result = chat.invoke(messages)  # 返回 AIMessage 对象
print(result.content)  # 获取文本内容
```

#### Embedding 模型

将文本转换为向量，用于**语义搜索**和**相似度匹配**。

```python
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# 将文本转为向量
vector = embeddings.embed_query("什么是 AI Agent？")
print(f"向量维度: {len(vector)}")  # 1536 维

# 批量转换
vectors = embeddings.embed_documents([
    "第一段文本",
    "第二段文本",
    "第三段文本",
])
```

---

### 3.2 Prompts（提示管理）

#### PromptTemplate

```python
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder

# 1. 基本字符串模板
template = PromptTemplate.from_template(
    "请用{language}回答：{question}"
)
prompt = template.invoke({
    "language": "中文",
    "question": "什么是 AI？"
})

# 2. 聊天消息模板（推荐）
chat_template = ChatPromptTemplate.from_messages([
    ("system", "你是一个{role}专家。"),
    ("human", "{input}"),
    # 也可以插入历史消息
    MessagesPlaceholder(variable_name="history"),
])

# 3. 使用模板
prompt = chat_template.invoke({
    "role": "Python",
    "input": "什么是装饰器？",
    "history": [],  # 空历史
})
```

#### OutputParser（输出解析）

```python
from langchain_core.output_parsers import StrOutputParser
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

# 1. 字符串解析（最常用）
str_parser = StrOutputParser()

# 2. JSON 解析
json_parser = JsonOutputParser()

# 3. Pydantic 模型解析（带类型校验）
class Movie(BaseModel):
    title: str = Field(description="电影名称")
    year: int = Field(description="上映年份")
    rating: float = Field(description="评分")
    
pydantic_parser = PydanticOutputParser(pydantic_object=Movie)

# 获取格式指令（会自动生成格式说明）
format_instructions = pydantic_parser.get_format_instructions()
```

---

### 3.3 Chains（流程编排）

LCEL（LangChain Expression Language）是编排组件的**声明式语法**。

```python
from langchain_core.runnables import RunnablePassthrough, RunnableParallel

# 1. 基础链
chain = prompt | chat | str_parser

# 2. 通过 RunnablePassthrough 传递上下文
chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | chat
    | str_parser
)

# 3. 并行执行
parallel_chain = RunnableParallel(
    summary=summarize_chain,
    keywords=keywords_chain,
    sentiment=sentiment_chain,
)
```

---

### 3.4 Retrieval（检索系统）

```python
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

# 1. 加载文档
loader = TextLoader("document.txt")
documents = loader.load()

# 2. 文本分块
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
)
chunks = splitter.split_documents(documents)

# 3. 创建向量存储
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=OpenAIEmbeddings(),
)

# 4. 检索
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
results = retriever.invoke("用户问题")
```

---

### 3.5 Callbacks（回调系统）

用于**日志记录、监控、调试**等场景。

```python
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.callbacks import StdOutCallbackHandler

# 1. 标准输出回调（打印所有中间步骤）
handler = StdOutCallbackHandler()

# 2. 自定义回调
class MyCallbackHandler(BaseCallbackHandler):
    def on_llm_start(self, serialized, prompts, **kwargs):
        print(f"🚀 LLM 调用开始，prompts: {len(prompts)}")
    
    def on_llm_end(self, response, **kwargs):
        print(f"✅ LLM 调用完成，生成 {len(response.generations[0])} 个结果")
    
    def on_chain_start(self, serialized, inputs, **kwargs):
        print(f"🔗 Chain 开始: {serialized.get('name', 'unnamed')}")
    
    def on_tool_start(self, serialized, input_str, **kwargs):
        print(f"🛠️ 工具调用: {serialized.get('name')}, 输入: {input_str[:50]}...")

# 使用回调
chain = prompt | chat | str_parser
result = chain.invoke(
    {"input": "你好"},
    config={"callbacks": [MyCallbackHandler()]}
)
```

---

## 四、组件组合实战

### 4.1 完整的 RAG 检索链

```python
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_community.vectorstores import Chroma

# 1. 准备组件
llm = ChatOpenAI(model="gpt-4o")
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# 2. 定义提示模板
template = """根据以下上下文回答问题：

上下文：{context}

问题：{question}

回答（如果上下文找不到，请直接说不知道）："""
prompt = ChatPromptTemplate.from_template(template)

# 3. 构建 RAG 链
def format_docs(docs):
    """格式化检索结果"""
    return "\n\n".join([doc.page_content for doc in docs])

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# 4. 使用
result = rag_chain.invoke("什么是向量数据库？")
```

### 4.2 带记忆的对话链

```python
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import MessagesPlaceholder

memory = ConversationBufferMemory(
    return_messages=True,
    memory_key="history",
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个友好的助手。"),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

chain = prompt | llm | StrOutputParser()

def chat(input_text):
    # 加载历史
    history = memory.load_memory_variables({})["history"]
    
    # 执行
    response = chain.invoke({
        "input": input_text,
        "history": history,
    })
    
    # 保存
    memory.save_context({"input": input_text}, {"output": response})
    return response
```

---

## 五、组件选择指南

| 需求 | 推荐组件 | 替代方案 |
|------|----------|----------|
| 调用 LLM | `ChatOpenAI` | `ChatAnthropic`, `ChatOllama` |
| 文本模板 | `ChatPromptTemplate` | `PromptTemplate` |
| 输出解析 | `StrOutputParser` | `JsonOutputParser` |
| 文档加载 | `DirectoryLoader` | `PyPDFLoader`, `TextLoader` |
| 文本分块 | `RecursiveCharacterTextSplitter` | `TokenTextSplitter` |
| 向量存储 | `Chroma` | `FAISS`, `Pinecone` |
| 记忆管理 | `ConversationBufferWindowMemory` | `SummaryMemory` |
| 回调处理 | `StdOutCallbackHandler` | 自定义 Handler |

---

## 六、版本兼容性注意事项

```python
# LangChain 版本演进（重要！）

# v0.1.x（旧版）方式 —— 部分已废弃
from langchain.chains import LLMChain
chain = LLMChain(llm=llm, prompt=prompt)

# v0.2+ / v0.3（新版）方式 —— 推荐
from langchain_core.runnables import RunnableSequence
chain = prompt | llm | parser

# 迁移提示
# 1. 优先使用 langchain_core 中的类
# 2. 特定集成使用 langchain_openai / langchain_community
# 3. LCEL (|) 是未来方向
```

---

## 七、常见问题

### ❌ 版本冲突

```python
# 问题：不同的 LangChain 版本 API 不一致
# 解决：锁定版本
# pyproject.toml
langchain>=0.2.0,<0.4.0
langchain-openai>=0.1.0
langchain-community>=0.1.0
```

### ❌ 导入路径错误

```python
# ❌ 旧版本导入（v0.1）
from langchain.chat_models import ChatOpenAI

# ✅ 新版本导入（v0.2+）
from langchain_openai import ChatOpenAI
```

### ❌ 异步调用

```python
# 如果需要异步
result = await chain.ainvoke({"input": "你好"})

# 流式输出
async for chunk in chain.astream({"input": "你好"}):
    print(chunk, end="")
```

---

## 八、本章总结

| 组件 | 一句话说明 |
|------|------------|
| **Models** | 统一的模型调用接口 |
| **Prompts** | 提示模板与解析器 |
| **Chains** | LCEL 声明式流程编排 |
| **Retrieval** | 文档加载、分块、向量化 |
| **Memory** | 对话历史管理 |
| **Callbacks** | 生命周期钩子 |

---

## 📝 课后练习

1. **✅ 基础**：使用 `ChatPromptTemplate` + `ChatOpenAI` + `StrOutputParser` 构建一个翻译 Chain
2. **💡 进阶**：添加 `StdOutCallbackHandler` 观察 Chain 的执行过程
3. **🚀 挑战**：构建一个包含检索 + 对话 + 记忆的完整系统
4. **🔍 探索**：查阅 LangChain 官方文档，了解 `RunnableBranch` 的用法
