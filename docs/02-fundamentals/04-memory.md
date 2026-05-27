# 2.4 记忆机制 —— 让 Agent 拥有"记性"

## 📖 导读

> **一个没有记忆的 Agent，就像一个人面对你说过的每句话都当作第一次听到。**

记忆是 Agent 从"工具"进化为"伙伴"的关键能力。有了记忆，Agent 才能**记住用户说过的话、记住之前任务的结果、持续优化自己的行为**。本文将从记忆的底层原理到实战实现，全面讲解 Agent 记忆机制。

---

## 一、前置知识

| 概念 | 说明 |
|------|------|
| **LLM 的无状态性** | 每次 LLM 调用都是独立的，不保留之前的对话 |
| **Context Window** | LLM 一次能处理的最大 token 数（GPT-4o 约 128K） |
| **Token 成本** | 每次调用都会按输入输出的 token 数计费 |
| **消息类型** | SystemMessage / HumanMessage / AIMessage |

---

## 二、为什么需要记忆？

### 2.1 没有记忆 vs 有记忆

```text
❌ 没有记忆：
用户：我叫小明
Agent：好的

用户：我刚才说了我叫什么？
Agent：我不记得了 ❌（每次调用都是全新的）

✅ 有记忆：
用户：我叫小明
Agent：好的，小明

用户：我刚才说了我叫什么？
Agent：你叫小明 ✅
```

### 2.2 记忆为 Agent 带来的核心能力

| 能力 | 说明 | 价值 |
|------|------|------|
| **上下文连贯** | 能跟上多轮对话 | 自然的人机交互 |
| **用户画像** | 记住用户的偏好、习惯 | 个性化服务 |
| **任务跟踪** | 记住当前任务的进度 | 断点续执行 |
| **知识积累** | 跨会话记住学到的知识 | 持续进化 |
| **错误学习** | 记住之前的错误，避免重复 | 自愈能力 |

---

## 三、记忆的分类与实现

### 3.1 短期记忆（Short-term Memory）

**工作原理**：将对话历史累积在消息列表中，每次调用时把完整历史传入 LLM。

```python
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o")

# 短期记忆 - 缓冲区记忆
memory = ConversationBufferMemory()
conversation = ConversationChain(
    llm=llm,
    memory=memory,
    verbose=False,
)

# 对话
conversation.predict(input="你好，我是小明")
conversation.predict(input="我喜欢编程")
conversation.predict(input="你还记得我叫什么吗？")
# → 记得！你叫小明
conversation.predict(input="我最大的爱好是什么？")
# → 编程！
```

**内存中的数据**：

```python
# memory.buffer 的内容
[
    ("human", "你好，我是小明"),
    ("ai", "你好，小明！很高兴认识你。"),
    ("human", "我喜欢编程"),
    ("ai", "太棒了！编程是一项非常有价值的技能。"),
    ("human", "你还记得我叫什么吗？"),
    ("ai", "当然记得！你叫小明。"),
]
```

**优点**：实现简单，100% 准确  
**缺点**：对话越长，token 消耗越大，成本线性增长

### 3.2 窗口记忆（Window Memory）

只保留最近 N 轮对话，丢弃早期的对话。

```python
from langchain.memory import ConversationBufferWindowMemory

# 只保留最近 3 轮对话
memory = ConversationBufferWindowMemory(k=3)

conversation = ConversationChain(
    llm=llm,
    memory=memory,
)

# 经过 5 轮对话后，只记得最后 3 轮
# 优点：token 消耗可控
# 缺点：最早的对话被遗忘了
```

**k 值选择的权衡**：

| k 值 | token 消耗 | 记忆范围 | 适用场景 |
|------|-----------|----------|----------|
| 2-3 | 极低 | 最近几轮 | 简单问答、客服 |
| 5-10 | 中 | 最近对话 | 一般聊天 |
| 20-50 | 高 | 较长历史 | 复杂分析任务 |
| 全量 | 极高 | 全部历史 | 需要完整回顾的场景 |

### 3.3 摘要记忆（Summary Memory）

LLM 定期对历史对话进行**自动摘要**，用摘要代替完整历史。

```python
from langchain.memory import ConversationSummaryMemory

# 摘要记忆
memory = ConversationSummaryMemory(llm=llm)
conversation = ConversationChain(
    llm=llm,
    memory=memory,
)

# 每轮对话后，LLM 自动生成摘要
# 记忆中的内容：
"""
用户是一个叫小明的程序员，使用 Python 语言，
最近在学习 AI Agent 开发。
他对 LangChain 框架特别感兴趣。
"""
```

**工作原理**：

```
原始对话（1000 tokens）→ LLM 摘要（100 tokens）
↓
下次对话：摘要 + 最新消息（150 tokens）
↓
新摘要（100 tokens）
↓
持续迭代...
```

**优点**：token 消耗稳定增长而非线性增长  
**缺点**：摘要可能丢失细节，且摘要本身有 token 成本

### 3.4 向量记忆（Vector Memory）

通过语义搜索从大量记忆中检索相关信息。适用于**长期记忆**。

```python
from langchain.memory import VectorStoreRetrieverMemory
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

# 初始化向量存储
embeddings = OpenAIEmbeddings()
vectorstore = Chroma(
    embedding_function=embeddings,
    persist_directory="./memory_db"
)

# 创建向量记忆
memory = VectorStoreRetrieverMemory(
    retriever=vectorstore.as_retriever(search_kwargs={"k": 3}),
    memory_key="relevant_memory",
)

# 保存记忆
memory.save_context(
    {"input": "我叫小明，来自北京"},
    {"output": "已记录"}
)

# 检索相关记忆
# 输入问"用户来自哪里"，能自动匹配到"小明"和"北京"
```

**优点**：可存储海量记忆，语义检索灵活  
**缺点**：需要额外配置向量数据库，有 embedding 成本

---

## 四、记忆类型对比总结

| 类型 | 存储方式 | 检索方式 | Token 消耗 | 适合场景 |
|------|----------|----------|-----------|----------|
| **缓冲区记忆** | 完整消息列表 | 全量读取 | 高（线性增长） | 短对话 |
| **窗口记忆** | 最近 N 轮消息 | 截取最新 | 可控 | 客服、常规对话 |
| **摘要记忆** | LLM 生成的摘要 | 读取摘要 | 中（稳定） | 长对话 |
| **向量记忆** | 向量数据库 | 语义搜索 | 低（按需检索） | 跨会话、海量记忆 |

---

## 五、实战：构建带记忆的对话 Agent

### 5.1 完整的聊天 Agent 实现

```python
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferWindowMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser

class ChatAgentWithMemory:
    """带记忆的聊天 Agent"""
    
    def __init__(self, model="gpt-4o", window_size=5):
        self.llm = ChatOpenAI(model=model, temperature=0.7)
        self.memory = ConversationBufferWindowMemory(
            k=window_size,
            return_messages=True,  # 返回消息对象而非字符串
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个友好的 AI 助手，记住用户说过的重要信息。"),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ])
        self.parser = StrOutputParser()
    
    def chat(self, user_input: str) -> str:
        """单轮对话"""
        # 1. 从记忆中获取历史消息
        history = self.memory.load_memory_variables({})
        messages = history.get("history", [])
        
        # 2. 构建完整的消息链
        chain = (
            RunnablePassthrough.assign(
                history=lambda x: messages
            )
            | self.prompt
            | self.llm
            | self.parser
        )
        
        # 3. 调用 LLM
        response = chain.invoke({"input": user_input})
        
        # 4. 保存到记忆
        self.memory.save_context(
            {"input": user_input},
            {"output": response}
        )
        
        return response
    
    def get_conversation_summary(self) -> str:
        """获取对话摘要"""
        memory_vars = self.memory.load_memory_variables({})
        history = memory_vars.get("history", [])
        summary_parts = []
        for msg in history:
            if isinstance(msg, HumanMessage):
                summary_parts.append(f"👤 用户: {msg.content}")
            elif isinstance(msg, AIMessage):
                summary_parts.append(f"🤖 AI: {msg.content}")
        return "\n".join(summary_parts)


# 使用示例
agent = ChatAgentWithMemory(window_size=5)

print("🤖 带记忆的 Agent 开始对话\n")
while True:
    user_input = input("👤 你: ")
    if user_input.lower() == "exit":
        break
    
    response = agent.chat(user_input)
    print(f"🤖 AI: {response}\n")

print("\n📋 对话记录：")
print(agent.get_conversation_summary())
```

### 5.2 记忆管理最佳实践

```python
class MemoryManager:
    """记忆管理器"""
    
    def __init__(self, max_token_limit=2000):
        self.max_token_limit = max_token_limit
        self.short_term = []  # 短期记忆
        self.long_term = {}   # 长期记忆（关键信息）
        
    def add_to_short_term(self, message: dict):
        """添加短期记忆"""
        self.short_term.append(message)
        self._prune_if_needed()
    
    def add_to_long_term(self, key: str, value: str):
        """添加长期记忆"""
        self.long_term[key] = value
    
    def extract_key_info(self, text: str) -> dict:
        """从文本中提取关键信息"""
        # 使用 LLM 提取用户的重要信息
        # 如：姓名、偏好、重要日期等
        pass
    
    def _prune_if_needed(self):
        """控制记忆大小"""
        total_tokens = self._estimate_tokens()
        while total_tokens > self.max_token_limit:
            # 移除最早的对话
            removed = self.short_term.pop(0)
            total_tokens -= self._estimate_message_tokens(removed)
    
    def _estimate_tokens(self) -> int:
        """估算 token 数量"""
        # 简单估算：中文字符 * 2.5
        total = 0
        for msg in self.short_term:
            total += self._estimate_message_tokens(msg)
        return total
    
    def _estimate_message_tokens(self, msg: dict) -> int:
        return len(msg.get("content", "")) * 2.5
```

---

## 六、记忆策略选择指南

### 6.1 不同场景的推荐配置

| 应用场景 | 推荐记忆类型 | 原因 |
|----------|-------------|------|
| **客服机器人** | 窗口记忆(k=3) | 只关心当前问题上下文 |
| **AI 学习助手** | 摘要记忆 | 需要跟踪学习进度 |
| **个人助理** | 向量记忆 | 需要记住用户长期偏好 |
| **代码助手** | 窗口记忆(k=10) | 需要整个函数/文件的上下文 |
| **数据分析 Agent** | 缓冲区+摘要 | 短期要精确，长期要总结 |

### 6.2 记忆的成本管理

```python
def estimate_memory_cost(memory_type: str, num_turns: int) -> dict:
    """估算不同记忆类型的成本"""
    costs = {
        "buffer": {
            "5_turns": "~500 tokens",
            "20_turns": "~2000 tokens", 
            "100_turns": "~10000 tokens ❌ 高成本",
        },
        "window_k5": {
            "5_turns": "~500 tokens",
            "20_turns": "~500 tokens ✅ 恒定",
            "100_turns": "~500 tokens ✅ 恒定",
        },
        "summary": {
            "5_turns": "~300 tokens ✅",
            "20_turns": "~400 tokens ✅",
            "100_turns": "~500 tokens ✅",
        },
    }
    return costs.get(memory_type, {})
```

---

## 七、常见问题与排查

### ❌ 记忆丢失

```python
# 问题：重启程序后所有记忆消失
# 原因：默认记忆存储在内存中
# 解决：使用持久化存储

# 文件持久化
import json

def save_memory(memory_data: dict, path: str = "memory.json"):
    with open(path, "w") as f:
        json.dump(memory_data, f)

def load_memory(path: str = "memory.json") -> dict:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
```

### ❌ Token 超限

```python
# 问题：Context Window 溢出
# 原因：记忆累积过多
# 解决：使用窗口记忆或摘要记忆

# 或手动截断
def truncate_memory(messages: list, max_tokens: int = 4000) -> list:
    """截断消息列表到最大 token 数"""
    total = 0
    truncated = []
    for msg in reversed(messages):  # 保留最新消息
        tokens = len(msg.content) * 2.5
        if total + tokens > max_tokens:
            break
        truncated.insert(0, msg)
        total += tokens
    return truncated
```

### ❌ 记忆混淆

```python
# 问题：多用户共用同一个记忆
# 原因：没有按会话隔离
# 解决：用 session_id 隔离

memory_store = {}  # {session_id: Memory}

def get_memory(session_id: str):
    if session_id not in memory_store:
        memory_store[session_id] = ConversationBufferWindowMemory(k=5)
    return memory_store[session_id]
```

---

## 八、本章总结

| 知识点 | 一句话说明 |
|--------|------------|
| **短期记忆** | 完整的消息历史，精确但 token 成本高 |
| **窗口记忆** | 只保留最近 N 轮，成本可控 |
| **摘要记忆** | LLM 自动压缩历史，成本稳定 |
| **向量记忆** | 语义检索，适合长期海量存储 |
| **成本管控** | 选择合适的记忆类型，设置窗口大小 |
| **持久化** | 跨会话记忆需要存储到文件或数据库 |

---

## 📝 课后练习

1. **✅ 基础**：使用 `ConversationBufferWindowMemory` 实现一个 `k=3` 的聊天 Agent，运行 5 轮对话，观察前 2 轮的信息是否被遗忘
2. **💡 对比**：分别用窗口记忆和摘要记忆实现同一个聊天场景，观察回答质量的差异和 token 消耗的差异
3. **🚀 挑战**：实现一个"关键信息提取"功能，在对话中自动提取用户的姓名、偏好等关键信息存入长期记忆，并在后续对话中能正确使用这些信息
4. **🔍 探索**：使用 LangChain 的 `VectorStoreRetrieverMemory` 配合 Chroma 实现一个跨会话记忆的 Agent
