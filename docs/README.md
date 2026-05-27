# 🤖 AgentLearn

> **AI Agent 从零开始构建智能体 — 全面、系统的开源学习教程**

## 📖 项目简介

**AgentLearn** 是一份从零开始的 **AI Agent 学习教程**，旨在帮助开发者系统掌握 AI Agent 的核心概念、开发框架和实践技巧。

无论你是刚刚接触 AI Agent 的新手，还是有经验的开发者，都能在这里找到适合自己的内容。

### 🎯 适合人群

| 人群 | 特点 | 推荐章节 |
|------|------|----------|
| 🟢 **AI 初学者** | 了解基本编程，想入门 AI Agent | 第一、二部分 |
| 🔵 **Python 开发者** | 熟悉 Python，想学习 Agent 开发 | 第三、四部分 |
| 🟠 **AI 工程师** | 有 AI 基础，想深入 Agent 架构 | 第五、六部分 |
| 🔴 **技术负责人** | 关注落地和部署 | 第七、八部分 |

### 🎓 你将学到

| # | 技能 | 对应章节 |
|:-|:-----|:---------|
| ✅ | 理解 AI Agent 的核心概念与工作原理 | 第一部分 |
| ✅ | 熟练使用 LangChain 构建基础 Agent | 第二、三部分 |
| ✅ | 掌握 LangGraph 设计复杂工作流 | 第四部分 |
| ✅ | 实现 RAG 系统，让 Agent 拥有知识库 | 第五部分 |
| ✅ | 构建多 Agent 协作系统 | 第六部分 |
| ✅ | 将 Agent 部署到生产环境 | 第七部分 |

---

## 📚 内容导航

| 章节 | 内容 | 文档数 |
|:----|:-----|:------:|
| 🟢 **第一部分：入门基础** | Agent 概念、环境搭建、第一个 Agent | 3 |
| 🔵 **第二部分：核心概念** | Prompt、Chain、Agent 架构、记忆 | 4 |
| 🟠 **第三部分：LangChain 实战** | 组件、工具、向量存储、聊天 Agent、研究助手 | 5 |
| 🟣 **第四部分：LangGraph 进阶** | 图结构、状态管理、路由、子图、工作流 | 5 |
| 🟤 **第五部分：RAG 系统** | RAG 原理、文档处理、向量数据库、优化、知识库 | 5 |
| 🔴 **第六部分：高级主题** | 多 Agent、评估、成本、安全 | 4 |
| ⚫ **第七部分：生产部署** | API、Docker、监控、CI/CD | 4 |
| 🌟 **第八部分：生态全景** | 框架对比、工具生态、技术选型、HiClaw 实践 | 10（含 HiClaw 教程） |

---

## 🚀 快速开始

```bash
# 1. 确保已安装 Python 3.10+ 和 uv
# 2. 克隆项目
git clone https://gitcode.com/mininote/AgentLearn.git
cd AgentLearn

# 3. 安装依赖
uv sync

# 4. 配置 API Key
cp .env.example .env
# 编辑 .env 填入你的 OPENAI_API_KEY

# 5. 运行第一个 Agent
python examples/01-hello-agent/main.py
```

---

## 💻 运行文档网站

```bash
# 使用 Docsify 本地预览文档
npx docsify serve docs
# 访问 http://localhost:3000
```

---

## 📄 许可证

本项目采用 **MIT License** — 详见 [LICENSE](LICENSE) 文件
