# 3.4 构建聊天 Agent —— 从对话到自主行动

## 📖 导读

前几节我们学习了 Chain、Prompt、记忆、工具等独立概念。现在是时候**把它们组合成一个完整的聊天 Agent**——既能自然对话，又能使用工具，还有记忆能力。这就像拼图一样：每个模块都是独立的一块，拼在一起就是一个能真正"做事"的聊天智能体。

---

## 一、前置知识

| 概念 | 章节 | 说明 |
|------|------|------|
| Chain（链） | 2.2 | 用 `\|` 连接多个组件 |
| 记忆（Memory） | 2.4 | 对话历史管理 |
| 工具（Tool） | 3.2 | Agent 调用的外部功能 |
| Prompt Engineering | 2.1 | 控制 Agent 行为 |

---

## 二、基础聊天 Agent

### 2.1 最简单版本

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

# 1. 初始化 LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0.7)

# 2. 创建 Prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个友好的 AI 助手，名叫 AgentBot。用中文回答用户的问题。"),
    ("human", "{input}"),
])

# 3. 组合 Chain
chat_chain = prompt | llm | StrOutputParser()

# 4. 使用
response = chat_chain.invoke({"input": "你好，你是谁？"})
print(response)
```

### 2.2 进阶版本：多轮对话

```python
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import MessagesPlaceholder

class ChatAgent:
    """支持多轮对话的聊天 Agent"""
    
    def __init__(self, model="gpt-4o", system_prompt=None):
        self.llm = ChatOpenAI(model=model, temperature=0.7)
        
        # 使用窗口记忆（保留最近 10 轮）
        self.memory = ConversationBufferMemory(
            k=10,
            return_messages=True,
            memory_key="history",
        )
        
        # 系统提示
        self.system_prompt = system_prompt or "你是一个友好的 AI 助手。"
        
        # 构建带历史的 Prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ])
        
        self.chain = self.prompt | self.llm | StrOutputParser()
    
    def chat(self, user_input: str) -> str:
        """单轮对话（自动维护历史）"""
        # 1. 加载记忆
        history = self.memory.load_memory_variables({})["history"]
        
        # 2. 调用 LLM
        response = self.chain.invoke({
            "input": user_input,
            "history": history,
        })
        
        # 3. 保存到记忆
        self.memory.save_context(
            {"input": user_input},
            {"output": response},
        )
        
        return response
    
    def get_history(self) -> list:
        """获取对话历史"""
        return self.memory.load_memory_variables({})["history"]


# 使用
agent = ChatAgent(system_prompt="你是一个 Python 编程助手。")

print("🤖 开始对话（输入 'exit' 退出）\n")
while True:
    user_input = input("👤 你: ")
    if user_input.lower() == "exit":
        break
    
    response = agent.chat(user_input)
    print(f"🤖 AI: {response}\n")
```

---

## 三、添加流式输出

流式输出（逐字显示）能显著提升用户体验。

```python
class StreamingChatAgent:
    """支持流式输出的聊天 Agent"""
    
    def __init__(self, model="gpt-4o"):
        self.llm = ChatOpenAI(model=model, temperature=0.7, streaming=True)
        self.memory = ConversationBufferMemory(
            k=10,
            return_messages=True,
            memory_key="history",
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个友好的 AI 助手。"),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ])
    
    async def chat_stream(self, user_input: str):
        """流式对话"""
        history = self.memory.load_memory_variables({})["history"]
        
        chain = self.prompt | self.llm | StrOutputParser()
        
        full_response = ""
        async for chunk in chain.astream({
            "input": user_input,
            "history": history,
        }):
            full_response += chunk
            yield chunk  # 逐块返回
        
        # 保存到记忆
        self.memory.save_context(
            {"input": user_input},
            {"output": full_response},
        )


# 使用流式输出
import asyncio

async def main():
    agent = StreamingChatAgent()
    
    async for chunk in agent.chat_stream("给我讲一个程序员的笑话"):
        print(chunk, end="", flush=True)
    print()  # 换行

# asyncio.run(main())
```

---

## 四、添加工具调用能力

这是 Agent 从"聊天"进化为"行动"的关键一步。

```python
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.tools import tool

class ToolUsingChatAgent:
    """能使用工具的聊天 Agent"""
    
    def __init__(self, model="gpt-4o"):
        self.llm = ChatOpenAI(model=model, temperature=0)
        self.tools = self._setup_tools()
        self.agent = self._create_agent()
    
    def _setup_tools(self):
        """定义 Agent 可用工具"""
        
        @tool
        def search_web(query: str) -> str:
            """搜索互联网信息，获取最新知识和资料"""
            # 实际项目中应调用搜索 API
            return f"关于'{query}'的搜索结果：\n1. AI Agent 是一种...\n2. 相关技术有..."
        
        @tool
        def calculate(expression: str) -> str:
            """执行数学计算，支持加减乘除等运算"""
            try:
                return str(eval(expression))
            except Exception as e:
                return f"计算错误: {e}"
        
        @tool
        def get_time(timezone: str = "Asia/Shanghai") -> str:
            """获取指定时区的当前时间"""
            from datetime import datetime
            import pytz
            tz = pytz.timezone(timezone)
            return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        
        return [search_web, calculate, get_time]
    
    def _create_agent(self):
        """创建 Agent"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个有用的 AI 助手。使用工具来回答用户问题。"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            max_iterations=5,
            handle_parsing_errors=True,
        )
    
    def chat(self, user_input: str) -> str:
        """对话"""
        result = self.agent.invoke({"input": user_input})
        return result["output"]


# 使用
agent = ToolUsingChatAgent()
response = agent.chat("计算 (1234 + 5678) * 3 的结果，并告诉我现在的时间")
print(response)
```

---

## 五、完整版：带记忆 + 工具 + 流式的聊天 Agent

```python
import json
from typing import List, Dict, Any
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.memory import ConversationBufferWindowMemory


class FullChatAgent:
    """
    完整的聊天 Agent：对话 + 记忆 + 工具 + 流式
    """
    
    def __init__(
        self,
        model: str = "gpt-4o",
        system_prompt: str = None,
        window_size: int = 10,
    ):
        self.llm = ChatOpenAI(
            model=model,
            temperature=0.7,
            streaming=True,  # 启用流式
        )
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.memory = ConversationBufferWindowMemory(
            k=window_size,
            return_messages=True,
            memory_key="chat_history",
        )
        self.tools = self._setup_tools()
        self.agent = self._create_agent()
    
    def _default_system_prompt(self) -> str:
        return """你是一个全能 AI 助手，具备以下能力：
1. 自然对话：记住用户说过的重要信息
2. 工具使用：搜索、计算、查时间等
3. 知识问答：基于你的知识回答

回答规则：
- 用中文回答，简洁明了
- 不确定的不要说，使用工具查证
- 多步问题分步解决"""
    
    def _setup_tools(self) -> list:
        """配置工具集"""
        
        @tool
        def search_web(query: str) -> str:
            """搜索互联网获取最新信息。当需要最新知识或不确定答案时使用。"""
            return f"【搜索结果】关于 '{query}' 的最新信息已获取..."
        
        @tool
        def calculate(expression: str) -> str:
            """数学计算工具。支持 +, -, *, /, **, () 等运算。"""
            try:
                return str(eval(expression))
            except Exception as e:
                return f"计算失败：{e}"
        
        @tool
        def get_current_time(format: str = "%Y-%m-%d %H:%M:%S") -> str:
            """获取当前日期和时间。"""
            return datetime.now().strftime(format)
        
        return [search_web, calculate, get_current_time]
    
    def _create_agent(self) -> AgentExecutor:
        """创建带记忆的 Agent"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            max_iterations=5,
            handle_parsing_errors=True,
        )
    
    def chat(self, user_input: str) -> str:
        """执行对话"""
        # 注入记忆
        result = self.agent.invoke({
            "input": user_input,
            "chat_history": self.memory.load_memory_variables({})["chat_history"],
        })
        
        # 保存到记忆
        self.memory.save_context(
            {"input": user_input},
            {"output": result["output"]},
        )
        
        return result["output"]
    
    def stream_chat(self, user_input: str):
        """流式对话（迭代器）"""
        # 暂存完整响应用于记忆
        full_response = ""
        
        # 这里简化处理：使用普通 invoke，但 LLM 已设 streaming=True
        # 生产环境可使用 astream_events 实现真正的逐 token 流式
        response = self.chat(user_input)
        
        # 模拟流式输出（每个字符）
        for char in response:
            yield char


# ===== 使用示例 =====
def demo():
    agent = FullChatAgent()
    
    print("=" * 50)
    print("🤖 全能聊天 Agent")
    print("=" * 50)
    
    questions = [
        "你好，我是小明",
        "你能做什么？",
        "计算 25 的平方根乘以 3 的结果",
        "你还记得我叫什么吗？",
    ]
    
    for q in questions:
        print(f"\n👤 我: {q}")
        print(f"🤖 AI: {agent.chat(q)}")


if __name__ == "__main__":
    demo()
```

---

## 六、会话管理（多用户支持）

```python
class SessionManager:
    """多会话管理"""
    
    def __init__(self):
        self.sessions: Dict[str, FullChatAgent] = {}
    
    def get_or_create_session(self, session_id: str) -> FullChatAgent:
        """获取或创建会话"""
        if session_id not in self.sessions:
            self.sessions[session_id] = FullChatAgent(
                system_prompt=f"你是用户 {session_id} 的私人助手。"
            )
        return self.sessions[session_id]
    
    def chat(self, session_id: str, message: str) -> str:
        """用户会话对话"""
        agent = self.get_or_create_session(session_id)
        return agent.chat(message)
    
    def delete_session(self, session_id: str):
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]


# 使用多会话
manager = SessionManager()

# 用户 A
print(manager.chat("user_a", "我喜欢编程"))   # user_a 的对话
print(manager.chat("user_a", "我最大的爱好是什么？"))  # → 记得是编程

# 用户 B（独立记忆）
print(manager.chat("user_b", "我喜欢音乐"))   # user_b 的对话
print(manager.chat("user_b", "我最大的爱好是什么？"))  # → 记得是音乐

# 两用户互不干扰 ✅
```

---

## 七、常见问题与优化

### ❌ 记忆和工具冲突

```python
# 问题：工具调用的中间步骤也存入了记忆
# 解决方案：只保存最终的对话结果

# 在 AgentExecutor 中设置
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    return_intermediate_steps=False,  # 不返回中间步骤
)
```

### ❌ Token 超限

```python
# 问题：对话太长超过 context window
# 解决方案：限制记忆窗口 + 截断历史

# 1. 使用窗口记忆
memory = ConversationBufferWindowMemory(k=5)

# 2. 或自定义 Token 限制器
def truncate_history(history: list, max_tokens: int = 2000) -> list:
    """截断历史到最大 token 数"""
    total = 0
    result = []
    # 从最新消息开始保留
    for msg in reversed(history):
        tokens = len(msg.content) * 2.5  # 估算
        if total + tokens > max_tokens:
            break
        result.insert(0, msg)
        total += tokens
    return result
```

### ❌ 工具调用失败

```python
# 设置 handle_parsing_errors 让 Agent 自动重试
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    handle_parsing_errors=True,  # LLM 输出格式错误时自动重试
    max_retries=2,               # 最大重试次数
)
```

---

## 八、适用场景

| 场景 | 必须的功能 | 可选功能 |
|------|-----------|----------|
| **客服机器人** | 记忆、知识库 | 工具调用 |
| **编程助手** | 代码执行工具、长记忆 | 流式输出 |
| **个人助理** | 日历/天气/搜索工具 | 多模态 |
| **教育辅导** | 记忆、计算工具 | 流式输出 |
| **数据分析助手** | 代码执行、文件读写 | 多步骤推理 |

---

## 九、本章总结

| 功能 | 实现方式 | 关键代码 |
|------|----------|----------|
| **基础对话** | Prompt + LLM | `prompt \| llm \| parser` |
| **多轮记忆** | ConversationBufferWindowMemory | `memory.save_context(...)` |
| **流式输出** | streaming=True | `chain.astream(...)` |
| **工具调用** | bind_tools / AgentExecutor | `create_tool_calling_agent()` |
| **会话管理** | session_id 隔离 | `sessions[session_id]` |

---

## 📝 课后练习

1. **✅ 基础**：构建一个最简单的聊天 Agent（无工具、无记忆），运行 3 轮对话
2. **💡 进阶**：添加记忆功能，验证 Agent 能否记住之前的信息
3. **🚀 综合**：实现"记忆+工具+流式"三位一体的聊天 Agent
4. **🔍 探索**：实现多会话隔离，让两个用户的对话互不干扰
