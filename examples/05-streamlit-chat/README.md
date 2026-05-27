# Streamlit 聊天界面

基于 Streamlit 的对话式 AI Agent 聊天界面，支持 **流式输出**。

## 功能

- 💬 多轮对话，保留上下文记忆
- ⚡ 流式输出，实时显示 LLM 响应
- 🎛️ 侧边栏设置（模型选择、温度调节、系统提示词）
- 🧠 内置三层记忆系统（工作记忆 + 短期记忆 + 长期记忆）
- 🗑️ 清空对话 / 重建 Agent

## 使用方法

### 1. 安装依赖

```bash
pip install streamlit
```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件（或复制 `.env.example`）：

```env
OPENAI_API_KEY=你的OpenAI_API密钥
```

### 3. 启动应用

```bash
cd AgentLearn
streamlit run examples/05-streamlit-chat/main.py
```

### 4. 浏览器访问

终端会输出本地地址，默认为 `http://localhost:8501`

## 架构说明

### 流式输出

`DialogAgent.stream_reply()` 方法采用 Python 生成器实现：

```python
# 使用示例
agent = DialogAgent(name="bot", llm=llm)
for chunk in agent.stream_reply(Msg.user_msg("你好")):
    print(chunk, end="", flush=True)
```

- 每次 `yield` 一个 token/文本片段
- 流式结束后自动将完整回复存入 Agent 记忆系统
- 支持错误处理：若 LLM 流式调用异常，会 yield 错误信息

### 记忆系统

- **WorkingMemory**: 当前上下文窗口（滑动窗口，默认保留最近 20 条消息）
- **ShortTermMemory**: 完整会话历史（默认最多 200 条）
- **LongTermMemory**: 跨会话知识（键值存储，支持关键词检索）

## 技术栈

| 组件 | 技术 |
|------|------|
| Web UI | Streamlit |
| LLM | OpenAI (via LangChain) |
| Agent 框架 | AgentLearn (DialogAgent) |
| 消息协议 | Msg (参考 AgentScope 设计) |
