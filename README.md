<div align="center">

# 🤖 AgentLearn

> **AI Agent 从零开始构建智能体 — 全面、系统的开源学习教程**

<p align="center">
  <a href="https://gitcode.com/mininote/AgentLearn">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square" alt="License"/>
  </a>
  <a href="https://python.org">
    <img src="https://img.shields.io/badge/python-3.12%2B-green.svg?style=flat-square" alt="Python"/>
  </a>
  <a href="https://docs.langchain.com/oss/python/langchain/overview">
    <img src="https://img.shields.io/badge/langchain-v1.x-orange.svg?style=flat-square" alt="LangChain"/>
  </a>
  <a href="https://docs.langchain.com/oss/python/langgraph/overview">
    <img src="https://img.shields.io/badge/langgraph-v1.1%2B-purple.svg?style=flat-square" alt="LangGraph"/>
  </a>
  <a href="https://modelcontextprotocol.io">
    <img src="https://img.shields.io/badge/MCP-2026--07--28-8A2BE2.svg?style=flat-square" alt="MCP"/>
  </a>
  <a href="https://gitcode.com/mininote/AgentLearn/stars">
    <img src="https://img.shields.io/badge/⭐-Star%20Us-brightgreen?style=flat-square" alt="Stars"/>
  </a>
  <a href="https://gitcode.com/mininote/AgentLearn">
    <img src="https://img.shields.io/badge/📖-65%2B%20docs-ff69b4?style=flat-square" alt="Docs"/>
  </a>
  <a href="https://agentlearn.minims.cn" target="_blank">
    <img src="https://img.shields.io/badge/🇨🇳-国内访问-blue?style=flat-square" alt="国内访问"/>
  </a>
</p>

</div>

---

## 📖 项目简介

> **打造你的第一个 AI Agent，从认知到生产，一步到位。**
>
> 🌐 **国内访问**：[https://al.towao.com](https://al.towao.com)

AgentLearn 是当前最系统的开源 AI Agent 教程之一，内容同步至 **2026 年 9 月** 的最新技术栈。无论你是 AI 新手还是资深后端开发者，都可以在这里找到适合自己的成长路径。

🔹 **你将从「是什么」开始**：理解 Agent、Chain、Tool、Memory、RAG、MCP 的核心概念  
🔹 **接着「动手做」**：基于 LangChain v1 + LangGraph v1.1 搭建真实可运行的 Agent 应用  
🔹 **最终「上生产」**：掌握多 Agent 协作、上下文工程、性能调优、安全防护与生产部署

```
🤖 AgentLearn 学习路径：
  基础概念 → LangChain v1 实战 → LangGraph 工作流 → RAG 系统 → 协议与生态 → 生产部署
```

本项目配套完整的 Python 包 [`agentlearn`](src/agentlearn/) 和 **12+ 个实战项目**，代码即学即用。无论你想构建聊天机器人、自动化工作流、知识库问答系统还是多智能体协作平台，这里都有现成的模板和最佳实践。

**已有 65+ 篇教程、~90 小时学习内容，全部免费开源。** 🚀

---

<table>
<tr>
<td width="50%" valign="top">

### 🎯 项目仪表盘

| 指标 | 数据 |
|:-----|:-----|
| 📚 教程章节 | **9 大章节** · 65+ 篇文档 |
| ⏱️ 总学习时长 | **~90 小时** |
| 💻 可运行示例 | **12+ 个**实战项目 |
| 📦 源代码包 | **agentlearn** v1.0+ |
| 🐍 最低 Python | **3.12+** |
| 🧠 核心框架 | **LangChain v1** + **LangGraph v1.1** |
| 📝 最后更新 | **2026 年 9 月** |

</td>
<td width="50%" valign="top">

### ✨ 项目特色

| 特色 | 说明 |
|:----|:-----|
| 🎯 **从零开始** | 无需 AI 基础，手把手教学 |
| 📚 **系统全面** | 覆盖 Agent 开发全链路 |
| 💻 **实战驱动** | 每个知识点都有可运行代码示例 |
| 🛠️ **技术前沿** | LangChain v1 中间件 / LangGraph 1.1 / MCP 2026-07-28 |
| 📦 **工程规范** | 使用 `uv` 管理，符合生产标准 |
| 🌐 **生态全景** | 涵盖 2026 年主流框架、协议与选型 |

</td>
</tr>
</table>

---

## 📑 目录导航

> 快速跳转至感兴趣的部分

| 章节 | 内容 | 适合人群 |
|:----|:-----|:---------|
| [🟢 入门基础](#-第一部分入门基础-01-intro) | AI Agent 概念、环境搭建、第一个 Agent | 新手 |
| [🔵 核心概念](#-第二部分核心概念-02-fundamentals) | Prompt 与上下文工程、Chain、Agent 架构、记忆 | 新手 |
| [🟠 LangChain v1 实战](#-第三部分langchain-v1-实战-03-langchain) | create_agent、中间件、工具调用、向量存储 | 进阶 |
| [🟣 LangGraph 进阶](#-第四部分langgraph-进阶-04-langgraph) | 状态管理、路由、子图、持久化、人机协同 | 进阶 |
| [🟤 RAG 系统](#-第五部分rag-系统-05-rag) | 文档处理、向量数据库、Agentic RAG、GraphRAG | 进阶 |
| [🔴 高级主题](#-第六部分高级主题-06-advanced) | 多 Agent、评估、成本控制、安全 | 高级 |
| [⚫ 生产部署](#-第七部分生产部署-07-deployment) | API 封装、Docker、可观测性、CI/CD | 高级 |
| [🌟 生态全景](#-第八部分生态全景-08-ecosystem) | 框架对比、MCP/A2A 协议、工具生态、选型 | 所有 |
| [🛠️ Agent Harness](#-第九部分agent-harness驾驭工程-09-agent-harness) | Agent=Model+Harness、十二大模块、权限沙箱、验证循环、实战 | 高级 |

---

## 🎯 学习目标

完成本教程后，你将能够：

<div>

| # | 技能 | 对应章节 |
|:-|:-----|:---------|
| ✅ | 理解 AI Agent 的核心概念与工作原理 | 第一部分 |
| ✅ | 熟练使用 LangChain v1 构建生产级 Agent | 第二、三部分 |
| ✅ | 掌握 LangGraph 设计复杂工作流（持久化/人机协同） | 第四部分 |
| ✅ | 实现 RAG 系统，让 Agent 拥有知识库 | 第五部分 |
| ✅ | 构建多 Agent 协作系统并做好评测与成本控制 | 第六部分 |
| ✅ | 将 Agent 部署到生产环境并接入可观测性 | 第七部分 |
| ✅ | 掌握 MCP / A2A 协议，融入 2026 年 Agent 生态 | 第八部分 |
| ✅ | 掌握 Agent Harness 工程，构建可托付的生产级 Agent | 第九部分 |

</div>

---

## 📚 内容大纲

### 🟢 第一部分：入门基础 (01-intro)

> 适合零基础入门，了解 AI Agent 是什么，搭建开发环境，运行第一个 Agent。

| 章节 | 内容 | 预计时间 |
|:----|:-----|:---------|
| 1.1 | [AI Agent 导论](docs/01-intro/01-agent-intro.md) | 2 小时 |
| 1.2 | [开发环境搭建](docs/01-intro/02-environment-setup.md) | 1 小时 |
| 1.3 | [第一个 Agent](docs/01-intro/03-first-agent.md) | 1 小时 |

### 🔵 第二部分：核心概念 (02-fundamentals)

> 深入理解 LLM、Prompt 与上下文工程、Chain 模式、Agent 架构和记忆机制。

| 章节 | 内容 | 预计时间 |
|:----|:-----|:---------|
| 2.1 | [Prompt 工程与上下文工程](docs/02-fundamentals/01-prompt-engineering.md) | 3 小时 |
| 2.2 | [Chain 模式详解](docs/02-fundamentals/02-chain-pattern.md) | 2 小时 |
| 2.3 | [Agent 核心架构](docs/02-fundamentals/03-agent-architecture.md) | 3 小时 |
| 2.4 | [记忆机制](docs/02-fundamentals/04-memory.md) | 2 小时 |

### 🟠 第三部分：LangChain v1 实战 (03-langchain)

> 掌握 LangChain v1（create_agent / 中间件 / 内容块）核心能力，实现工具调用与聊天 Agent。

| 章节 | 内容 | 预计时间 |
|:----|:-----|:---------|
| 3.1 | [LangChain v1 核心组件](docs/03-langchain/01-core-components.md) | 2 小时 |
| 3.2 | [模型调用与工具集成](docs/03-langchain/02-models-and-tools.md) | 3 小时 |
| 3.3 | [向量存储与检索](docs/03-langchain/03-vector-store.md) | 3 小时 |
| 3.4 | [构建聊天 Agent](docs/03-langchain/04-chat-agent.md) | 2 小时 |
| 3.5 | [实战：研究助手](docs/03-langchain/05-research-agent.md) | 4 小时 |

### 🟣 第四部分：LangGraph 进阶 (04-langgraph)

> 学习 LangGraph 工作流引擎，掌握状态管理、条件路由、子图、持久化与人机协同。

| 章节 | 内容 | 预计时间 |
|:----|:-----|:---------|
| 4.1 | [LangGraph 基础](docs/04-langgraph/01-basics.md) | 2 小时 |
| 4.2 | [状态管理与节点](docs/04-langgraph/02-state-nodes.md) | 2 小时 |
| 4.3 | [条件路由与循环](docs/04-langgraph/03-routing-loops.md) | 3 小时 |
| 4.4 | [子图与模块化](docs/04-langgraph/04-subgraphs.md) | 2 小时 |
| 4.5 | [实战：工作流 Agent](docs/04-langgraph/05-workflow-agent.md) | 4 小时 |

### 🟤 第五部分：RAG 系统 (05-rag)

> 构建检索增强生成系统，让 Agent 拥有外部知识库。

| 章节 | 内容 | 预计时间 |
|:----|:-----|:---------|
| 5.1 | [RAG 原理详解](docs/05-rag/01-principles.md) | 2 小时 |
| 5.2 | [文档处理与分块](docs/05-rag/02-document-processing.md) | 2 小时 |
| 5.3 | [向量数据库实战](docs/05-rag/03-vector-database.md) | 3 小时 |
| 5.4 | [检索优化技巧](docs/05-rag/04-optimization.md) | 2 小时 |
| 5.5 | [实战：企业知识库](docs/05-rag/05-enterprise-kb.md) | 4 小时 |

### 🔴 第六部分：高级主题 (06-advanced)

> 探索多 Agent 协作、评估优化、成本控制和安全合规。

| 章节 | 内容 | 预计时间 |
|:----|:-----|:---------|
| 6.1 | [多 Agent 协作](docs/06-advanced/01-multi-agent.md) | 3 小时 |
| 6.2 | [Agent 评估与优化](docs/06-advanced/02-evaluation.md) | 2 小时 |
| 6.3 | [成本控制策略](docs/06-advanced/03-cost-control.md) | 2 小时 |
| 6.4 | [安全与合规](docs/06-advanced/04-security.md) | 2 小时 |

### ⚫ 第七部分：生产部署 (07-deployment)

> 将 Agent 应用部署到生产环境，实现容器化、可观测性和持续集成。

| 章节 | 内容 | 预计时间 |
|:----|:-----|:---------|
| 7.1 | [API 服务封装](docs/07-deployment/01-api-service.md) | 2 小时 |
| 7.2 | [Docker 容器化](docs/07-deployment/02-docker.md) | 2 小时 |
| 7.3 | [可观测性、监控与日志](docs/07-deployment/03-monitoring.md) | 2 小时 |
| 7.4 | [持续集成/部署](docs/07-deployment/04-cicd.md) | 2 小时 |

### 🌟 第八部分：生态全景 (08-ecosystem)

> 俯瞰 2026 年 AI Agent 全生态，从框架对比到协议标准，做出最优选型。

| 章节 | 内容 | 预计时间 |
|:----|:-----|:---------|
| 8.1 | [核心 Agent 框架全景对比](docs/08-ecosystem/survey/01-core-frameworks.md) | 2 小时 |
| 8.2 | [多智能体协作模式深度解析](docs/08-ecosystem/survey/02-multi-agent-patterns.md) | 2 小时 |
| 8.3 | [工具调用与编排生态](docs/08-ecosystem/survey/03-tool-ecosystem.md) | 1.5 小时 |
| 8.4 | [记忆系统全景](docs/08-ecosystem/survey/04-memory-systems.md) | 1.5 小时 |
| 8.5 | [低代码/可视化 Agent 平台](docs/08-ecosystem/survey/05-low-code-platforms.md) | 1.5 小时 |
| 8.6 | [专业领域 Agent](docs/08-ecosystem/survey/06-domain-agents.md) | 2 小时 |
| 8.7 | [评估与监控工具](docs/08-ecosystem/survey/07-evaluation-tools.md) | 1.5 小时 |
| 8.8 | [安全与沙箱](docs/08-ecosystem/survey/08-security-sandbox.md) | 1.5 小时 |
| 8.9 | [选型指南与决策矩阵](docs/08-ecosystem/survey/09-selection-guide.md) | 2 小时 |
| 8.10 | [MCP 协议完全指南](docs/08-ecosystem/protocols/01-mcp.md) | 2 小时 |
| 8.11 | [A2A 协议与 Agent 互操作](docs/08-ecosystem/protocols/02-a2a.md) | 1.5 小时 |
| 📦 **HiClaw 实践** | [HiClaw 教程](docs/08-ecosystem/hiclaw/README.md) — Kubernetes 原生多 Agent 编排系统 | 专题 |
| 🧩 **AgentScope 实战** | [AgentScope 教程](docs/08-ecosystem/agentscope/index.md) — 消息驱动的分布式 Agent 框架 | 专题 |

### 🛠️ 第九部分：Agent Harness（驾驭工程）(09-agent-harness)

> 🚀 **2026 年的认知升级：`Agent = Model + Harness`** —— 当模型不再是瓶颈，Harness 就是护城河。

| 章节 | 内容 | 预计时间 |
|:----|:-----|:---------|
| 9.0 | [章节导读](docs/09-agent-harness/README.md) | — |
| 9.1 | [什么是 Agent Harness](docs/09-agent-harness/01-intro.md) | 1.5 小时 |
| 9.2 | [Harness 十二大模块解剖](docs/09-agent-harness/02-anatomy.md) | 3 小时 |
| 9.3 | [上下文工程与压缩流水线](docs/09-agent-harness/03-context-engineering.md) | 2.5 小时 |
| 9.4 | [权限、护栏与沙箱](docs/09-agent-harness/04-permissions-sandbox.md) | 2.5 小时 |
| 9.5 | [验证循环](docs/09-agent-harness/05-verification.md) | 2 小时 |
| 9.6 | [子 Agent 编排与长时任务](docs/09-agent-harness/06-subagents-longtasks.md) | 2.5 小时 |
| 9.7 | [Harness Engineering 方法论](docs/09-agent-harness/07-harness-engineering.md) | 2.5 小时 |
| 9.8 | [实战：从零构建最小可行 Harness](docs/09-agent-harness/08-build-your-harness.md) | 4 小时 |
| 9.9 | [开源 Harness 全景与选型](docs/09-agent-harness/09-open-source-landscape.md) | 2 小时 |
| 9.10 | [AGENTS.md、Agent Skills 与 Spec 驱动开发](docs/09-agent-harness/10-standards-skills.md) | 2 小时 |
| 9.11 | [Harness 评测与可观测性](docs/09-agent-harness/11-evaluation-observability.md) | 2 小时 |

---

## 🚀 快速开始

### 前置要求

| 要求 | 说明 |
|:----|:-----|
| 🐍 Python | **3.12+** |
| 📦 包管理器 | **uv** >= 0.5.0 |
| 🔑 API Key | **OpenAI / Anthropic / 通义 / DeepSeek** 等任一 LLM API |

### 📥 安装 uv

<details>
<summary>点击展开安装命令</summary>

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 验证安装
uv --version
```

</details>

### 🛠️ 克隆 & 安装

```bash
# 克隆仓库
git clone https://gitcode.com/mininote/AgentLearn.git
cd AgentLearn

# 安装依赖（自动创建虚拟环境）
uv sync
```

### 🔑 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，至少填入你的 API Key
# LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
# LLM_BASE_URL=https://api.openai.com/v1   # 官方或中转地址，结尾带 /v1
# LLM_MODEL_NAME=gpt-5.5
```

> 💡 **关于两套变量名（重要）**
> - `OPENAI_API_KEY` / `OPENAI_API_BASE`：`langchain-openai` 的**原生变量**，`ChatOpenAI` 会自动读取。**仓库自带的 `examples/` 是直接使用 `ChatOpenAI` 的，因此要跑通它们，必须设置 `OPENAI_API_KEY`**（并把示例中的模型名改成你可用的模型）。
> - `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL_NAME`：**本教程统一约定**，教程中的示例代码会显式读取并传入，便于在 OpenAI / Anthropic / Gemini / DeepSeek / 通义之间切换。
>
> 两套变量都已列在 `.env.example`，按你的使用场景保留其一即可。

> 🔐 `.env` 已被 `.gitignore` 忽略，**不会提交到仓库**。请勿把真实 Key 写入 `.env.example`。

### 🎮 运行示例

```bash
# 🖐️ 第一个 Agent — 最简单的 Hello World
python examples/01-hello-agent/main.py

# 🧪 研究助手 — 多工具协作
python examples/04-research-agent/main.py

# 💬 Streamlit 聊天界面 — 交互式对话
streamlit run examples/05-streamlit-chat/main.py

# 🧰 最小可行 Harness（mini-harness）— 离线自检，无需 API Key
python examples/09-mini-harness/smoke_test.py
```

### 📖 本地运行文档网站（可选）

教程文档本身是一个 [Docsify](https://docsify.js.org/) 站点，源码位于 `docs/`。

```bash
# 方式一：docsify-cli（推荐）
npx docsify-cli serve docs
#   ⚠️ 是 docsify-cli，不是 docsify —— npm 上的 `docsify` 包没有命令行入口，
#      执行 `npx docsify serve docs` 会报 "could not determine executable to run"。
#   ⚠️ docsify-cli 要求 Node >= 20.11
# 访问 http://localhost:3000

# 方式二：全局安装后使用
npm i -g docsify-cli
docsify serve docs

# 方式三：任意静态服务器（在 docs 目录下启动，使其成为网站根目录）
cd docs
python -m http.server 3000
```

> ⚠️ **必须通过 HTTP 访问**：docsify 依赖 `fetch` 加载 Markdown，直接双击打开 `docs/index.html`（`file://` 协议）会显示空白页。
>
> 💡 **部署提示**：`docs/index.html` 中的 `basePath` 请**保持默认（留空）**，这样无论部署在站点根目录还是子目录（如 `/docs/`）都能正确加载 `README.md` / `_sidebar.md`；写死 `basePath: '/'` 会在子路径部署时导致这两个文件 404，页面一片空白。
>
> 🔌 页面依赖的 CDN 资源若在你的网络环境下访问不稳定，可将 docsify / prism 等文件下载到 `docs/assets/` 后改为本地引用。

---

## 📁 项目结构

<details>
<summary><b>展开查看完整目录结构</b></summary>

```
AgentLearn/
├── 📄 项目配置
│   ├── README.md                    # 项目说明（你在这里）
│   ├── LICENSE                      # MIT 许可证
│   ├── pyproject.toml               # 项目配置 (uv)
│   ├── uv.lock                      # 依赖锁定文件
│   └── .env.example                 # 环境变量模板
│
├── 📚 教程文档 (docs/)
│   ├── 01-intro/               # 🟢 入门基础 (3 篇)
│   ├── 02-fundamentals/        # 🔵 核心概念 (4 篇)
│   ├── 03-langchain/           # 🟠 LangChain v1 实战 (5 篇)
│   ├── 04-langgraph/           # 🟣 LangGraph 进阶 (5 篇)
│   ├── 05-rag/                 # 🟤 RAG 系统 (5 篇)
│   ├── 06-advanced/            # 🔴 高级主题 (4 篇)
│   ├── 07-deployment/          # ⚫ 生产部署 (4 篇)
│   ├── 08-ecosystem/           # 🌟 生态全景 (11 篇 + HiClaw + AgentScope)
│   │   ├── survey/             # 生态调研
│   │   ├── protocols/          # MCP / A2A 协议
│   │   ├── hiclaw/             # HiClaw 实践
│   │   └── agentscope/         # AgentScope 实战
│   └── 09-agent-harness/       # 🛠️ Agent Harness (12 篇)
│
├── 💻 代码示例 (examples/)
│   ├── 01-hello-agent/         # 🖐️ 第一个 Agent
│   ├── 02-tool-use/            # 🔧 工具调用
│   ├── 03-chat-agent/          # 💬 聊天 Agent
│   ├── 04-research-agent/      # 🔬 研究助手
│   ├── 05-streamlit-chat/      # 🎨 Streamlit 聊天界面
│   ├── 06-multi-agent/         # 👥 多 Agent 协作
│   └── 09-mini-harness/        # 🧰 最小可行 Harness（可离线自检）
│
├── 📦 核心库 (src/agentlearn/)
│   ├── base.py                 # 基础类
│   ├── agent.py                # Agent 实现
│   ├── tools.py                # 工具集合
│   ├── memory.py               # 记忆管理
│   ├── message.py              # 消息模型
│   ├── pipeline.py             # 流水线编排
│   └── utils.py                # 工具函数
│
├── 🧪 测试 (tests/)
└── 🔧 辅助脚本 (scripts/)
```

</details>

---

## 🛠️ 技术栈

> 以下版本以 **2026 年 9 月** 为准，实际请以各官方最新发布为准。

| 类别 | 技术 | 版本 / 说明 |
|:----|:-----|:-----|
| 📦 **包管理** | [uv](https://docs.astral.sh/uv/) | >= 0.5.0 |
| 🐍 **语言** | [Python](https://python.org) | >= 3.12 |
| 🧠 **核心框架** | [LangChain](https://docs.langchain.com/oss/python/langchain/overview) | v1.x（`create_agent` / 中间件 / 内容块） |
| 🔄 **工作流** | [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) | >= 1.1 |
| 🔌 **工具协议** | [MCP](https://modelcontextprotocol.io) / A2A | MCP 2026-07-28 / A2A v1.0 |
| 🗄️ **向量数据库** | Chroma / FAISS / Qdrant / Milvus | >= 1.5.0 |
| 🤖 **LLM** | OpenAI GPT-5.x · Claude Sonnet 4.6 / Opus 5 · Gemini 3.x · DeepSeek V4 · Qwen | - |
| 🐳 **部署** | Docker / FastAPI / Streamlit | - |
| 🔭 **可观测性** | LangSmith / Langfuse / OpenTelemetry | - |
| ✅ **代码质量** | Ruff + Mypy + Pytest | - |

---

## 📈 学习路线图

<p>

```
┌─────────────────────────────────────────────────────────────┐
│                 10 周完整学习路线 🗺️                         │
├─────────────────────────────────────────────────────────────┤
│  Week 1-2: 🟢 入门基础                                       │
│  ├── 理解 AI Agent 概念                                       │
│  ├── 搭建开发环境                                             │
│  └── 运行第一个 Agent 🖐️                                     │
├─────────────────────────────────────────────────────────────┤
│  Week 3-4: 🔵🟠 核心技能                                      │
│  ├── 掌握 LangChain v1 核心组件与中间件                        │
│  ├── 精通 Prompt 与上下文工程                                 │
│  ├── 实现工具调用与记忆                                       │
│  └── 构建聊天 Agent 💬                                       │
├─────────────────────────────────────────────────────────────┤
│  Week 5-6: 🟣🟤 进阶实战                                      │
│  ├── 学习 LangGraph 工作流与持久化                             │
│  ├── 构建 RAG / Agentic RAG 知识库系统                        │
│  └── 多 Agent 协作实战 👥                                    │
├─────────────────────────────────────────────────────────────┤
│  Week 7-8: ⚫🌟 生产部署 + 生态全景                             │
│  ├── API 封装与 Docker 部署 🐳                                │
│  ├── 了解全生态框架、MCP/A2A 协议与选型                        │
│  ├── 可观测性、评估与安全 ⚡                                   │
│  └── 完成最终项目 🏆                                         │
├─────────────────────────────────────────────────────────────┤
│  Week 9-10: 🛠️ Agent Harness（进阶必修）                      │
│  ├── 认知升级：Agent = Model + Harness                        │
│  ├── 掌握十二大模块与三大核心机制（上下文/权限/验证）           │
│  ├── 从零构建最小可行 Harness 🧰                              │
│  └── 开源 Harness 选型 + AGENTS.md / Skills 标准              │
└─────────────────────────────────────────────────────────────┘

```

</p>

---

## 🤝 贡献指南

我们欢迎任何形式的贡献！无论是修复错别字、改进文档，还是添加新功能。

### 🏗️ 工作流程

```mermaid
graph LR
    A[Fork 仓库] --> B[创建分支]
    B --> C[提交更改]
    C --> D[推送分支]
    D --> E[Pull Request]
    E --> F[Code Review]
    F --> G[Merge 🎉]
```

### 📐 代码规范

| 规范 | 要求 |
|:----|:-----|
| 📦 **依赖管理** | 使用 `uv` 管理依赖 |
| ✨ **代码风格** | 遵循 PEP 8，使用 Ruff 格式化与检查 |
| 📝 **文档** | 函数/类添加类型注解和文档字符串 |
| 🧪 **测试** | 新功能必须包含单元测试 |
| 🔍 **类型检查** | 通过 Mypy 检查 |

---

## 📄 许可证

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

本项目采用 **MIT License** — 详见 [LICENSE](LICENSE) 文件

**你可以自由地：** ✅ 使用 · ✅ 修改 · ✅ 分发 · ✅ 商用

---

## 🔗 相关资源

<div>

| 🧠 核心框架 | 🔌 协议标准 | 🌐 平台工具 |
|:-----------|:-----------|:-----------|
| [LangChain](https://docs.langchain.com/oss/python/langchain/overview) | [MCP](https://modelcontextprotocol.io) | [Dify](https://dify.ai/) |
| [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) | [A2A](https://a2aproject.github.io/A2A/) | [Flowise](https://flowiseai.com/) |
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) | [OpenTelemetry GenAI](https://opentelemetry.io/) | [LangSmith](https://smith.langchain.com/) |
| [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/) | [JSON-RPC](https://www.jsonrpc.org/) | [Langfuse](https://langfuse.com/) |

</div>

---

## ⭐ 支持项目

如果你觉得这个项目有帮助，请给我们一个 ⭐ 支持！

<div>

| [![Star](https://img.shields.io/badge/⭐-Star%20on%20GitCode-brightgreen?style=for-the-badge)](https://gitcode.com/mininote/AgentLearn) | [![Fork](https://img.shields.io/badge/🍴-Fork%20this%20repo-blue?style=for-the-badge)](https://gitcode.com/mininote/AgentLearn) | [![Issue](https://img.shields.io/badge/🐛-Report%20Issue-red?style=for-the-badge)](https://gitcode.com/mininote/AgentLearn/issues) |
|:-|:-|:-|

</div>

---

### 🙏 致谢

感谢以下出色的开源项目，以及所有贡献者和社区成员的支持：

| 项目 | 用途 | 链接 |
|:----|:----|:-----|
| [LangChain](https://github.com/langchain-ai/langchain) | 核心 Agent 框架 | ⭐ 110k+ |
| [LangGraph](https://github.com/langchain-ai/langgraph) | 工作流编排运行时 | ⭐ 20k+ |
| [MCP](https://github.com/modelcontextprotocol) | 工具调用协议 | ⭐ 60k+ |
| [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) | 轻量 Agent 框架 | ⭐ 15k+ |
| [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) | 企业级 Agent 框架 | ⭐ 20k+ |
| [AgentScope](https://github.com/agentscope-ai/agentscope) | 消息驱动分布式 Agent | ⭐ 10k+ |
| [Dify](https://github.com/langgenius/dify) | LLMOps 平台 | ⭐ 60k+ |
| [uv](https://github.com/astral-sh/uv) | Python 包管理 | ⭐ 40k+ |

---

> ### 🚀 让 AI Agent 成为你的超级助手，开启智能开发新纪元！
>
> **有问题？** 欢迎提交 [Issue](https://gitcode.com/mininote/AgentLearn/issues) 或参与社区讨论 💬
