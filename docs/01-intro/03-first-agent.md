# 1.3 第一个 Agent —— 动手创建属于你的 AI 助手

## 📖 导读

环境搭建好了，我们来做一件最酷的事——**写一个真正能用的 AI Agent**。本文将通过一个完整的示例，带你理解 Agent 的基本结构、代码组织方式，以及每一步背后的原理。**即使你没有 LLM 开发经验，跟着做也能跑起来。**

---

## 一、前置知识

在开始编码之前，需要了解几个 LangChain 中的基础概念：

| 概念 | 类比 | 说明 |
|------|------|------|
| **ChatOpenAI** | 大脑 | 封装了 LLM 的调用，就是我们 Agent 的"大脑" |
| **SystemMessage** | 角色设定 | 告诉 LLM 它的身份和行为规则 |
| **HumanMessage** | 用户提问 | 用户的输入消息 |
| **AIMessage** | AI 回复 | LLM 生成的消息 |
| **invoke()** | 问问题 | 把消息发给 LLM 并获取回复 |

---

## 二、项目结构

```
examples/01-hello-agent/
├── main.py          # 主程序文件
└── README.md        # 示例说明文档（如果你看到的）
```

这是一个非常简单的单文件结构，后续我们会逐步引入更复杂的多文件组织。

---

## 三、代码详解（逐行解读）

### 3.1 完整代码

```python
"""
第一个 Agent - Hello Agent

这是一个最简单的 Agent 示例，展示如何使用 LangChain
创建一个能够对话的 AI 助手。
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# 加载环境变量（读取 .env 文件中的配置）
load_dotenv()


def create_agent():
    """创建并返回一个 LLM 实例"""
    # 初始化 LLM
    llm = ChatOpenAI(
        model="gpt-4o",          # 使用的模型名称
        temperature=0.7,         # 创意度（0=确定性，1=高创意）
    )
    return llm


def chat_with_agent(llm, user_message: str):
    """与 Agent 进行单轮对话"""
    # 构建消息列表
    messages = [
        SystemMessage(content="你是一个有用的 AI 助手，用中文回答用户问题。"),
        HumanMessage(content=user_message),
    ]

    # 调用 LLM 获取回复
    response = llm.invoke(messages)

    return response.content


def main():
    """主函数：程序入口"""
    print("🤖 AgentLearn - 第一个 Agent")
    print("=" * 50)

    # 1. 创建 Agent
    llm = create_agent()

    # 2. 准备测试问题
    questions = [
        "你是谁？",
        "请用一句话解释什么是 AI Agent",
        "讲一个关于程序员的笑话",
    ]

    # 3. 逐个提问
    for i, question in enumerate(questions, 1):
        print(f"\n📝 问题 {i}: {question}")
        print("-" * 30)

        answer = chat_with_agent(llm, question)
        print(f"🤖 回答: {answer}")

    print("\n" + "=" * 50)
    print("🎉 第一个 Agent 运行完成！")


if __name__ == "__main__":
    main()
```

---

### 3.2 逐行拆解

#### 导入模块

```python
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
```

| 导入语句 | 作用 |
|----------|------|
| `os` | Python 标准库，用于读取环境变量 |
| `load_dotenv` | 从 `.env` 文件加载配置到环境变量 |
| `ChatOpenAI` | LangChain 对 OpenAI API 的封装，提供流式/批量调用能力 |
| `HumanMessage` | 用户消息类型 |
| `SystemMessage` | 系统提示消息类型 |

#### 初始化 LLM

```python
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.7,
)
```

`ChatOpenAI` 会自动从环境变量读取以下配置（无需手动传入）：

```env
LLM_API_KEY=sk-...      # → 传给 api_key 参数
LLM_BASE_URL=https://... # → 传给 base_url 参数
```

这种**自动注入**的设计让代码更干净——你不需要在每个文件中重复配置 API Key。

#### 消息结构

```python
messages = [
    SystemMessage(content="你是一个有用的 AI 助手，用中文回答用户问题。"),
    HumanMessage(content=user_message),
]
```

LangChain 的消息系统有三种基础类型：

| 类型 | 来源 | 作用 |
|------|------|------|
| `SystemMessage` | 系统 | 设定角色和规则，**通常只有第一条** |
| `HumanMessage` | 用户 | 用户输入的问题或指令 |
| `AIMessage` | AI | LLM 的回复（在多轮对话中使用） |

> ⚠️ **注意**：`SystemMessage` 的影响力非常大，一个好的 system prompt 能显著提升回复质量。后续我们在 Prompt Engineering 章节会深入讲解。

#### 调用 LLM

```python
response = llm.invoke(messages)
```

`invoke()` 是 LangChain 的核心方法，它将消息发送给 LLM 并返回完整的回复。`response` 是一个 `AIMessage` 对象，通过 `.content` 获取纯文本内容。

---

### 3.3 运行程序

确保虚拟环境已激活，然后执行：

```bash
# 激活虚拟环境（如果未激活）
# macOS/Linux: source .venv/bin/activate
# Windows: .venv\Scripts\activate

# 运行程序
python examples/01-hello-agent/main.py
```

**期望输出**：

```
🤖 AgentLearn - 第一个 Agent
==================================================

📝 问题 1: 你是谁？
------------------------------
🤖 回答: 我是一个 AI 助手，由大语言模型驱动，可以帮你回答问题、提供建议、完成各种文字任务。

📝 问题 2: 请用一句话解释什么是 AI Agent
------------------------------
🤖 回答: AI Agent 是一种能够自主感知环境、理解意图、做出决策并采取行动的智能软件系统。

📝 问题 3: 讲一个关于程序员的笑话
------------------------------
🤖 回答: 程序员问上帝："上帝，什么时候才能没有 bug？"
上帝说："等我先修复一下我自己的 bug。"

==================================================
🎉 第一个 Agent 运行完成！
```

---

## 四、进阶尝试

### 4.1 调整 temperature 参数

`temperature` 控制 LLM 输出的随机性：

| temperature | 效果 | 适用场景 |
|-------------|------|----------|
| 0.0 | 每次输出基本一致 | 事实问答、翻译 |
| 0.3–0.5 | 轻微变化 | 客服、常规对话 |
| 0.7–0.9 | 创意丰富 | 写作、头脑风暴 |
| 1.0+ | 高度随机 | 创意故事、诗歌 |

```python
# 事实型 Agent（确定性高）
llm_factual = ChatOpenAI(model="gpt-4o", temperature=0.0)

# 创意型 Agent（变化丰富）
llm_creative = ChatOpenAI(model="gpt-4o", temperature=0.9)

# 多次调用同一模型，观察输出差异
for i in range(3):
    response = llm.invoke([
        SystemMessage(content="用 20 个字介绍你自己"),
        HumanMessage(content="开始"),
    ])
    print(f"第 {i+1} 次: {response.content}")
```

### 4.2 实现多轮对话

上面的示例是单轮对话，每次提问都是独立的。

如果要实现有历史记忆的对话，需要维护消息列表：

```python
def chat_multi_turn():
    """多轮对话：把历史消息累积传递"""
    llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
    
    # 消息历史列表
    messages = [
        SystemMessage(content="你是一个友好的 AI 助手。"),
    ]
    
    print("开始对话（输入 'exit' 退出）:")
    
    while True:
        user_input = input("\n🧑 你: ")
        if user_input.lower() == 'exit':
            break
        
        # 添加用户消息
        messages.append(HumanMessage(content=user_input))
        
        # 调用 LLM
        response = llm.invoke(messages)
        
        # 添加 AI 回复到历史
        messages.append(response)
        
        print(f"🤖 AI: {response.content}")
        print(f"📊 当前消息数: {len(messages)}")

chat_multi_turn()
```

运行效果示例：

```
开始对话（输入 'exit' 退出）:

🧑 你: 我叫小明
🤖 AI: 你好小明！很高兴认识你。

🧑 你: 我刚才说了我叫什么？
🤖 AI: 你说你叫小明！😊
```

> ⚠️ 注意：这里的记忆是通过在消息列表中累积所有对话实现的，实际上会消耗大量 tokens。后续我们会介绍更高效的记忆管理方案。

---

## 五、常见错误与排查

### ❌ API Key 未配置

```
openai.AuthenticationError: 
The api key is invalid or missing.
```

**排查步骤**：
1. 检查项目根目录是否有 `.env` 文件
2. 检查 `.env` 中是否包含 `LLM_API_KEY=sk-...`
3. 确认 `load_dotenv()` 在代码中被调用
4. 添加调试输出验证：

```python
load_dotenv()
api_key = os.getenv("LLM_API_KEY")
print(f"API Key 是否存在: {'是' if api_key else '否'}")
print(f"API Key 前8位: {api_key[:8] if api_key else '未找到'}")
```

### ❌ 网络连接失败

```
httpx.ConnectError: [Errno 61] Connection refused
```

**解决方案**：
1. 检查 `LLM_BASE_URL` 是否配置正确
2. 确认网络可以访问该地址（国内访问 OpenAI 需科学上网）
3. 尝试用 curl 测试：

```bash
# 替换成你的 Base URL 和 Key
curl -X POST "https://api.example.com/v1/chat/completions" \
  -H "Authorization: Bearer $LLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"hi"}]}'
```

### ❌ 模型不存在

```
openai.BadRequestError: 
The model `gpt-999` does not exist
```

**解决方案**：使用有效的模型名称：
```python
# ✅ 正确
llm = ChatOpenAI(model="gpt-4o")

# ❌ 错误
llm = ChatOpenAI(model="gpt-999")

# 常见可用模型
# gpt-4o       - 最新全能模型（推荐）
# gpt-4-turbo  - 上代旗舰
# gpt-3.5-turbo - 快速经济
```

### ❌ 虚拟环境未激活

```
ModuleNotFoundError: No module named 'langchain_openai'
```

**解决方案**：确保虚拟环境已激活：
```bash
# 检查
which python
# 应该显示类似: /path/to/AgentLearn/.venv/bin/python

# 如果没激活
source .venv/bin/activate  # macOS/Linux
# 或
.venv\Scripts\activate      # Windows
```

---

## 六、本章总结

| 知识点 | 要点 |
|--------|------|
| **Agent 基础结构** | LLM（大脑）+ 消息（交互方式）+ invoke（调用方法） |
| **三种消息类型** | SystemMessage（角色设定）、HumanMessage（用户输入）、AIMessage（AI 回复） |
| **temperature** | 控制输出的创造性，0=确定，1=创意 |
| **多轮对话** | 通过累积消息列表实现"记忆" |
| **错误排查** | API Key 问题最常见，其次为网络和模型名 |

---

## 📝 课后练习

1. **✅ 必做**：运行示例代码，完成至少 3 轮对话
2. **📝 修改练习**：尝试 `temperature=0.0` 和 `temperature=1.0` 分别运行三次，观察输出一致性
3. **💡 拓展**：在 chat_multi_turn 函数中加入对话轮次上限（如最多 10 轮）
4. **🔍 探索**：尝试不同的 `SystemMessage` 内容，例如让 Agent 扮演"专业翻译"或"面试官"，观察行为变化

---

> 🔗 **下一章预告**：我们将深入 Prompt Engineering，学习如何通过提示词精确控制 Agent 的行为和输出质量。
