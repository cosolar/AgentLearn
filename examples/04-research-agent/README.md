# 示例 04: 研究助手

## 📖 说明

一个基于 **LangChain v1 `create_agent`** 的研究助手 Agent：接收研究主题，自动搜索资料、综合分析，并生成结构化研究报告。

## 运行

```bash
python examples/04-research-agent/main.py
```

运行前请确保已在项目根目录配置好 `.env`（`LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL_NAME`）。

## 功能

- 🔍 使用 `search_web` 工具搜索资料（示例为模拟数据）
- 📝 综合分析并生成结构化 Markdown 报告
- 💾 使用 `save_report` 工具把报告保存到文件

## 代码结构

单文件 `main.py`：

- `search_web` / `save_report`：两个 `@tool` 工具
- `create_research_agent()`：用 `create_agent` 组装 Agent（内置工具循环）
- `main()`：交互式命令行入口

## 示例

```
🤖 AgentLearn - 研究助手
==================================================
输入研究主题，我将为你生成研究报告（输入 exit 退出）

研究主题：AI Agent 的发展趋势

🔍 正在研究...

==================================================
## AI Agent 发展趋势研究报告

### 1. 摘要
...
### 2. 核心发现
...
### 3. 结论与展望
...
==================================================
```
