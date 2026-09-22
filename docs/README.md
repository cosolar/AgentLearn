# 🤖 AgentLearn

> **AI Agent 从零开始构建智能体 — 全面、系统的开源学习教程**

> 📅 内容同步至 **2026 年 9 月** 技术栈 · LangChain v1 · LangGraph 1.1 · MCP 2026-07-28

## 📖 项目简介

**AgentLearn** 是一份从零开始的 **AI Agent 学习教程**，旨在帮助开发者系统掌握 AI Agent 的核心概念、开发框架和实践技巧。

无论你是刚刚接触 AI Agent 的新手，还是有经验的开发者，都能在这里找到适合自己的内容。全部 **55+ 篇教程、~80 小时学习内容**，免费开源。

### 🎯 适合人群

| 人群 | 特点 | 推荐章节 |
|------|------|----------|
| 🟢 **AI 初学者** | 了解基本编程，想入门 AI Agent | 第一、二部分 |
| 🔵 **Python 开发者** | 熟悉 Python，想学习 Agent 开发 | 第三、四部分 |
| 🟠 **AI 工程师** | 有 AI 基础，想深入 Agent 架构 | 第五、六部分 |
| 🔴 **技术负责人** | 关注落地、协议与部署 | 第七、八部分 |

### 🎓 你将学到

| # | 技能 | 对应章节 |
|:-|:-----|:---------|
| ✅ | 理解 AI Agent 的核心概念与工作原理 | 第一部分 |
| ✅ | 熟练使用 LangChain v1 构建生产级 Agent | 第二、三部分 |
| ✅ | 掌握 LangGraph 设计复杂工作流 | 第四部分 |
| ✅ | 实现 RAG / Agentic RAG 系统 | 第五部分 |
| ✅ | 构建多 Agent 协作系统并做好评测与成本控制 | 第六部分 |
| ✅ | 将 Agent 部署到生产环境并接入可观测性 | 第七部分 |
| ✅ | 掌握 MCP / A2A 协议，融入 2026 年 Agent 生态 | 第八部分 |

---

## 🗺️ 学习路径

```
基础概念 → LangChain v1 实战 → LangGraph 工作流 → RAG 系统 → 协议与生态 → 生产部署
```

| 阶段 | 章节 | 目标 |
|:-----|:-----|:-----|
| ① 认知 | 第 1-2 部分 | 理解 Agent 是什么、如何思考 |
| ② 动手 | 第 3 部分 | 用 LangChain v1 写出第一个可用的 Agent |
| ③ 进阶 | 第 4-5 部分 | 用 LangGraph 编排复杂流程，接入 RAG |
| ④ 生产 | 第 6-7 部分 | 多 Agent、评估、成本、安全、部署 |
| ⑤ 全景 | 第 8 部分 | 生态选型，掌握 MCP / A2A 协议 |

---

## 📚 内容导航

| 章节 | 内容 | 文档数 |
|:----|:-----|:------:|
| 🟢 **第一部分：入门基础** | Agent 概念、环境搭建、第一个 Agent | 3 |
| 🔵 **第二部分：核心概念** | Prompt 与上下文工程、Chain、Agent 架构、记忆 | 4 |
| 🟠 **第三部分：LangChain v1 实战** | 核心组件、模型与工具、向量存储、聊天 Agent、研究助手 | 5 |
| 🟣 **第四部分：LangGraph 进阶** | 基础、状态管理、路由、子图、工作流 | 5 |
| 🟤 **第五部分：RAG 系统** | RAG 原理、文档处理、向量数据库、优化、企业知识库 | 5 |
| 🔴 **第六部分：高级主题** | 多 Agent、评估、成本、安全 | 4 |
| ⚫ **第七部分：生产部署** | API、Docker、可观测性、CI/CD | 4 |
| 🌟 **第八部分：生态全景** | 框架对比、MCP/A2A 协议、工具生态、选型、HiClaw、AgentScope | 11+ |

---

## 🚀 快速开始

```bash
# 1. 确保已安装 Python 3.12+ 和 uv
# 2. 克隆项目
git clone https://gitcode.com/mininote/AgentLearn.git
cd AgentLearn

# 3. 安装依赖
uv sync

# 4. 配置 API Key
cp .env.example .env
# 编辑 .env 填入你的 LLM_API_KEY

# 5. 运行第一个 Agent
python examples/01-hello-agent/main.py
```

---

## 🛠️ 环境要求

| 要求 | 说明 |
|:----|:-----|
| 🐍 Python | **3.12+** |
| 📦 包管理器 | **uv** >= 0.5.0 |
| 🔑 API Key | OpenAI / Anthropic / Gemini / DeepSeek / 通义 等任一 |

---

## 💻 运行文档网站

```bash
# 使用 Docsify 本地预览文档
npx docsify serve docs
# 访问 http://localhost:3000
```

---

## 📄 许可证

本项目采用 **MIT License** — 详见根目录 [LICENSE](../LICENSE) 文件
