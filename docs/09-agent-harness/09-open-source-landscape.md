# 9.9 开源 Harness 全景与选型 —— 2026 年 9 月

## 📖 本章目标

- 建立 **Agent Harness / 底层编排库 / 低代码平台** 的三分法分类框架
- 逐个厘清 2026 年 9 月主流开源 Harness 的定位、架构与适用场景
- 掌握三张决策表：**方案对比 / 入口形态选型 / 开源 vs 闭源**
- 学会用 5 步清单把"工作入口、权限边界、交付方式"映射到具体工具
- 跑通 `dsh` 与 LangChain Deep Agents 的最小示例，并设计一套横向对比脚本

> 📅 **2026 年 9 月更新**：DeepSeek Harness（`dsh`，2026-08-13 开源）成为生态最大变量；LangChain Deep Agents 于 2026-05-07 引入 harness profiles；MAF 在 BUILD 2026 发布 Agent Harness 与 Hosted Agents。本章据此重写。
>
> ⚠️ **准确性声明**：本章涉及的工具迭代极快，命令、包名、API 与销量数据请**以官方文档为准**。文中标注"以官方文档为准"处表示该细节可能随版本变化，请在使用前核对当前文档。

---

## 一、先分类：三种"做 Agent 的方式"

在动手之前，必须先搞清一个反复被混淆的问题：**"Harness" 不是框架的同义词**。

2026 年 9 月，LangChain 官方给出的分类把生态切成三层：

```text
┌───────────────────────────────────────────────────────────────┐
│  低代码 / 平台层                                                │
│  Dify · n8n · Flowise · Coze                                   │
│  特征：可视化编排为主，非开发者也能用，可预测性高、灵活性低        │
├───────────────────────────────────────────────────────────────┤
│  Agent Harness（"batteries-included"）                          │
│  DeepSeek Harness(dsh) · Deep Agents · Claude Code ·            │
│  OpenAI Codex · MAF Agent Harness · AgentScope                  │
│  特征：内置工具 + 提示词 + 子 Agent + 上下文管理，开箱即用         │
├───────────────────────────────────────────────────────────────┤
│  底层编排库（Orchestration Library）                             │
│  LangGraph · LlamaIndex Workflows · Google ADK（编排部分）        │
│  特征：只给你"状态机/图/事件"，其余全部自己搭，灵活性最高          │
└───────────────────────────────────────────────────────────────┘
```

**Agent Harness** 的核心特征可以概括为一句话：

> Harness 是**内置了工具、提示词和子 Agent 等能力的 "batteries-included" 框架**——你不需要从零搭 tool 注册表、memory、上下文压缩、权限，它替你做好了一套"默认工程实践"。

三层之间不是替代关系，而是**从"你写代码"到"你点鼠标"的连续谱**：

| 维度 | 底层编排库 | Agent Harness | 低代码平台 |
|------|-----------|---------------|-----------|
| 一句话 | 给你积木 | 给你一台整机 | 给你一条流水线 |
| 代表 | LangGraph、LlamaIndex Workflows | `dsh`、Deep Agents、Claude Code、Codex | Dify、n8n、Flowise |
| 决策者 | 工程团队 | 开发/运维/独立开发者 | 业务方 + 少量 IT |
| 灵活性 | 最高 | 中高（可通过插件/中间件扩展） | 低 |
| 可预测性 | 取决于你 | 较高（有约定） | 最高（固定流程） |
| 上手成本 | 高 | 中 | 低 |
| 对模型要求 | 高（需强 function calling） | 中高 | 中 |

> 💡 **判断口诀**：如果你在纠结"用不用 Harness"，先问自己——**我到底是在造工具，还是在用工具干活？** 造工具用底层库，干活用 Harness。
>
> 🔗 底层库的选择见 [8.1 核心 Agent 框架全景对比](../08-ecosystem/survey/01-core-frameworks.md)；Harness 内部有哪些模块，见 [9.2 十二大模块](02-anatomy.md)。

---

## 二、表 A：Harness vs Framework（库）vs 低代码平台

这是本章第一张决策表。注意"框架（库）"一列指的是 LangGraph / LlamaIndex Workflows 这类**编排库**，与"Harness"是并列关系。

| 对比维度 | **Agent Harness** | **Framework（库）** | **低代码平台** |
|---------|-------------------|---------------------|----------------|
| **决策者** | 开发者个人 / 小团队 / DevOps | 架构师 + 工程团队 | 业务负责人 / 产品经理 |
| **核心产物** | 可运行的 Agent 运行时（CLI/服务） | 你写的图 / 工作流代码 | 画布上的可视化流程 |
| **灵活性** | 中高：插件、中间件、profiles 可覆盖 | **最高**：任意逻辑都能表达 | 低：受限于节点能力 |
| **可预测性** | 较高：有约定优于配置的默认行为 | 取决于你的实现质量 | **最高**：流程固定、可审计 |
| **开发成本** | 低到中：多数能力开箱即用 | 高：基础设施要自己搭 | **最低**：拖拽即可 |
| **维护成本** | 低：上游升级即可获得新能力 | 高：需自行跟进生态演进 | 中：受平台版本绑定 |
| **对模型要求** | 中高：依赖稳定的工具调用 | 高：需强推理与结构化输出 | 中：通常内置提示词模板 |
| **调试/可观测** | 平台自带（trace、日志） | 需接入 LangSmith 等 | 平台内置 |
| **典型场景** | 改仓库、跑长任务、自动化运维 | 定制化业务流程、深度集成 | 客服、营销、内部工具 |
| **典型代表** | `dsh`、Deep Agents、Codex、Claude Code | LangGraph、LlamaIndex Workflows | Dify、n8n、Flowise |

> 🎯 **一句话**：**Harness 把"工程实践"变成默认值，库把"控制权"还给你，低代码把"参与门槛"降到最低。**
>
> 🔗 低代码平台的详细对比见 [8.5 低代码平台](../08-ecosystem/survey/05-low-code-platforms.md)。

---

## 三、重点 Harness 逐个详解

每个 Harness 我们都按同一模板拆解：**定位 / 是否开源 / 架构特征 / 适用场景 / 上手方式**。

### 3.1 DeepSeek Harness（命令行 `dsh`）

| 项目 | 说明 |
|------|------|
| **定位** | 通用 Agent 运行时底座（Agent runtime substrate），命令行入口 `dsh` |
| **是否开源** | ✅ 开源，**MIT 协议**，2026-08-13 发布 |
| **核心哲学** | **"Everything is a plugin"** |
| **内核** | 依托 **Cordis 内核**实现模块化定制 |
| **模型** | **不绑定模型**：支持 DeepSeek / OpenAI / Ollama 等 |
| **热度** | 开源 3 天内 GitHub Stars 破 10 万级，至 2026 年 9 月已 **20 万+** |
| **生态** | `dsh-plugin-radar`（索引 1.5 万+ 仓库、验证近 3000 个插件）、`awesome-dsh-plugin` |

**架构特征 —— "Everything is a plugin"**

`dsh` 最反直觉也最有远见的一点：**它把几乎所有东西都抽象成可替换的插件**——模型、工具、任务规划、调度、沙箱、存储、Agent Loop，**甚至"模型本身"也只是 Harness 里的一个部件**。

```text
                      ┌──────────────────────┐
                      │    Cordis 内核        │
                      │  （模块化 / 插件宿主）│
                      └──────────┬───────────┘
        ┌───────────┬────────────┼────────────┬───────────┐
        ▼           ▼            ▼            ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐
   │ Model   │ │ Tools   │ │ Planner │ │ Scheduler│ │ Sandbox  │
   │ plugin  │ │ plugin  │ │ plugin  │ │ plugin   │ │ plugin   │
   └─────────┘ └─────────┘ └─────────┘ └─────────┘ └──────────┘
        ┌───────────┬────────────┬────────────┬───────────┐
        ▼           ▼            ▼            ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐
   │ Storage │ │ Agent   │ │ Permission│ │ Skill    │ │ ...     │
   │ plugin  │ │ Loop    │ │ plugin   │ │ plugin   │ │         │
   └─────────┘ └─────────┘ └──────────┘ └──────────┘ └─────────┘
```

这种设计带来的直接收益：

- **不绑定模型**：换模型只需换一个 plugin，业务代码零改动
- **不绑定沙箱**：本地 shell、容器、远程沙箱都可作为 sandbox plugin 接入
- **不绑定存储**：内存、SQLite、远端对象存储任选
- **可插拔的 Agent Loop**：想换 ReAct / Plan-and-Execute / 自定义循环，换 plugin 即可

**适用场景**：需要长期演进、不希望被单一厂商锁定的 Agent 平台建设；团队想把 Agent 运行时作为"基础设施"而非"框架依赖"。

**上手方式**（以官方文档为准）：

```bash
# 安装（以官方文档为准：包管理器/分发渠道可能随版本变化）
npm install -g @deepseek/dsh      # 示例形式，请核对官方安装说明
# 或从源码安装
git clone https://github.com/deepseek-ai/harness.git
cd harness && npm install && npm link

# 初始化配置
dsh init
dsh config set model deepseek-chat      # 也可指向 OpenAI / Ollama
dsh config set sandbox local

# 最小运行
dsh run "列出当前仓库的 TODO 并生成一份待办清单"
```

> ⚠️ **生态提示**：`dsh-plugin-radar` 会索引社区插件（1.5 万+ 仓库、近 3000 个通过验证）。插件质量参差，生产环境请**只启用已验证插件**并做权限隔离。

### 3.2 LangChain Deep Agents

| 项目 | 说明 |
|------|------|
| **定位** | LangChain 官方的 Agent Harness，构建于 LangGraph 之上 |
| **是否开源** | ✅ 开源（LangChain 生态，MIT 系许可） |
| **关键时间点** | 2026-03 开源；**2026-05-07** 推出 **harness profiles** |
| **术语** | 明确使用 **"agent harness"** 这一说法 |
| **架构特征** | 内置 planning、sub-agent、文件系统、上下文压缩等能力 |
| **上手方式** | Python / JS，三行代码起一个 Agent |

**架构特征 —— harness profiles**

Deep Agents 的定位很清晰：**它不取代 LangGraph，而是在 LangGraph 之上提供一套"默认工程实践"**。它的关键创新是 **harness profiles**——以**声明式**的方式覆盖 system prompt、tools 等 harness 配置，从而让同一个 Agent 逻辑适配不同场景：

```python
# 声明式 profile（概念示意，API 以官方文档为准）
profile = {
    "name": "research",
    "system_prompt": "你是一名严谨的研究助手。",
    "tools": ["web_search", "read_file", "write_file"],
}
```

**适用场景**：已经在用 LangChain / LangGraph 的团队，想快速获得"harness 级"的默认能力，又不愿放弃底层图的控制力。

**上手方式**（以官方文档为准）：

```python
from deepagents import create_deep_agent

agent = create_deep_agent(model="gpt-5.5")
agent.invoke({"messages": [{"role": "user", "content": "帮我调研 MCP 协议"}]})
```

> 🔗 本教程主力栈是 LangChain v1 + LangGraph，Deep Agents 与其天然衔接，详见 [3.1 LangChain v1 核心组件](../03-langchain/01-core-components.md)。

### 3.3 Claude Code / Claude Agent SDK（Anthropic）

| 项目 | 说明 |
|------|------|
| **定位** | Anthropic 官方编码 Agent（Claude Code）与可编程 SDK（Claude Agent SDK） |
| **是否开源** | ❌ 核心闭源；SDK 开放 |
| **API 形态** | 单一 `query()` 函数即可创建 agent 循环，返回**流式消息的异步迭代器** |
| **自我定位** | Anthropic 自称其 runtime 是 **"dumb loop"**（笨循环） |
| **循环范式** | Claude Code 走 **Gather-Act-Verify** 循环 |
| **工程占比** | Code 库中模型决策逻辑仅 **1.6%**，其余 **98.4%** 是 operational harness |

**架构特征 —— "98.4% 是 harness"**

这是理解 Harness 价值最有力的一个数字：在 Claude Code 的代码库里，**真正"让模型做决策"的逻辑只占 1.6%**，剩下 98.4% 全是围绕模型的**操作性 harness**——文件读写、权限确认、上下文管理、diff 应用、命令执行、错误恢复……

```text
Claude Code 代码构成（示意）
┌────────────────────────────────────────────────┐
│ ▏1.6%  模型决策逻辑（"聪明"的部分）              │
├────────────────────────────────────────────────┤
│ ██████████████████████████████████████████ 98.4%│
│           operational harness（工程的部分）      │
└────────────────────────────────────────────────┘
```

**Gather-Act-Verify 循环**：

```text
Gather   → 收集上下文：读文件、grep、看目录、跑测试
  ↓
Act      → 执行动作：编辑文件、运行命令、写新文件
  ↓
Verify   → 验证结果：跑测试 / 类型检查 / lint，失败则回到 Gather
  ↺
```

`query()` 的极简形态（以官方文档为准）：

```python
from claude_agent_sdk import query

async for message in query(prompt="修复 tests/test_api.py 中的失败用例"):
    print(message)   # 流式消费 agent 循环产生的消息
```

**适用场景**：以 Claude 模型为主的开发工作流、需要高可信度文件编辑与命令执行的场景。

### 3.4 OpenAI Codex / Agents SDK

| 项目 | 说明 |
|------|------|
| **定位** | OpenAI 官方编码 Agent（Codex）与轻量 Agent 编排（Agents SDK） |
| **是否开源** | Codex Core 部分开源；Agents SDK 开源；服务侧闭源 |
| **Codex 架构** | **三层：Codex Core / App Server / client 层** |
| **关键设计** | **所有客户端共享同一 harness** |
| **Agents SDK 风格** | **"code-first"**：工作流用**原生 Python** 而非图 DSL |
| **运行模式** | 三种：**async / sync / streamed** |

**架构特征 —— Codex 三层架构**

```text
┌──────────────────────────────────────────────────────┐
│  client 层                                             │
│  CLI        VS Code 扩展        web app        ...     │
└───────────────┬──────────────────────────────────────┘
                │  双向 JSON-RPC
┌───────────────▼──────────────────────────────────────┐
│  App Server                                            │
│  （协议桥接、会话管理、事件分发）                        │
└───────────────┬──────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────┐
│  Codex Core                                            │
│  agent 代码 + runtime（真正的 harness 内核）            │
└──────────────────────────────────────────────────────┘
```

**"所有客户端共享同一 harness"** 是 Codex 的关键工程决策：无论你在 CLI、VS Code 还是 web app 使用 Codex，**背后跑的是同一套 agent 逻辑**——一次修复，处处生效，行为一致。

**Agents SDK 的 "code-first"**：与 LangGraph 的"图 DSL"相对，Agents SDK 主张用**原生 Python 控制流**（if/for/while）表达工作流，降低学习成本：

```python
from agents import Agent, Runner

agent = Agent(name="assistant", instructions="你是一个友好的助手。")
result = Runner.run_sync(agent, "用一句话解释什么是 Agent")   # sync 模式
print(result.final_output)
```

| 运行模式 | 入口 | 适用 |
|---------|------|------|
| **async** | `Runner.run()` | 高并发服务 |
| **sync** | `Runner.run_sync()` | 脚本、CLI |
| **streamed** | `Runner.run_streamed()` | 实时 UI、逐 token 呈现 |

> 🔗 Agents SDK 的框架定位详见 [8.1 核心 Agent 框架全景对比](../08-ecosystem/survey/01-core-frameworks.md)。

### 3.5 Microsoft Agent Framework（MAF）

| 项目 | 说明 |
|------|------|
| **定位** | 企业级 Agent 框架，AutoGen + Semantic Kernel 合并而来 |
| **是否开源** | ✅ 开源（MIT） |
| **关键发布** | **BUILD 2026** 发布 **Agent Harness** 与 **Hosted Agents** |
| **语言** | Python / .NET |
| **集成** | Azure、Microsoft 365、Foundry、Entra |

**架构特征**：

- **Agent Harness**：把企业级 agent 运行所需的工具、记忆、权限、可观测性打包
- **Hosted Agents**：把 Agent 作为托管服务运行，天然接入企业身份与合规体系
- **多 Agent 编排**：延续 AutoGen 的对话协作范式

```text
MAF 企业栈
┌────────────────────────────────────────────┐
│  Hosted Agents（托管运行 + 企业合规）        │
├────────────────────────────────────────────┤
│  Agent Harness（工具/记忆/权限/可观测）      │
├────────────────────────────────────────────┤
│  MAF 核心（多 Agent 编排 + Azure 集成）      │
└────────────────────────────────────────────┘
```

**适用场景**：微软技术栈、强合规要求、需要长期支持（LTS）的组织。

### 3.6 AgentScope / AgentScope Java 2.0 GA

| 项目 | 说明 |
|------|------|
| **定位** | 分布式多 Agent 框架，2026 年长出完整 Harness 工程化层 |
| **是否开源** | ✅ 开源（Apache-2.0） |
| **推理内核** | ReActAgent |
| **Harness 能力** | Workspace、持久记忆、上下文压缩、Subagent 编排、Sandbox、Skill、Plan Mode、Permission、Channel |
| **关键理念** | **按需启用**；同一份 Agent 逻辑可从单机玩具搬到企业级分布式服务 |

**架构特征 —— "在 ReActAgent 之上长出 Harness"**

AgentScope 的演进路线很有代表性：**先有 ReActAgent 推理内核，再在其上叠加一整套 Harness 工程化层**。

```text
┌───────────────────────────────────────────────────────────────┐
│  Harness 工程化层（按需启用）                                   │
│  Workspace · 持久记忆 · 上下文压缩 · Subagent 编排 · Sandbox     │
│  Skill · Plan Mode · Permission · Channel                       │
├───────────────────────────────────────────────────────────────┤
│  ReActAgent 推理内核                                            │
├───────────────────────────────────────────────────────────────┤
│  消息驱动运行时（跨进程 / 跨机器 / 分布式）                       │
└───────────────────────────────────────────────────────────────┘
```

| Harness 能力 | 作用 |
|-------------|------|
| **Workspace** | 给 Agent 一个受控的工作目录 |
| **持久记忆** | 跨会话保留关键信息 |
| **上下文压缩** | 长任务不爆 context window |
| **Subagent 编排** | 主 Agent 派发子任务给子 Agent |
| **Sandbox** | 隔离代码执行 |
| **Skill** | 按需加载能力包（见 [9.10](10-standards-skills.md)） |
| **Plan Mode** | 先规划后执行的模式 |
| **Permission** | 细粒度权限边界 |
| **Channel** | 接入 IM / 消息渠道 |

**适用场景**：企业级多 Agent 协作、需要大规模分布式部署与监管合规的场景。
🔗 详见 [AgentScope 教程](../08-ecosystem/agentscope/index.md)。

---

## 四、终端类开源 Harness 选型对比

"在终端里改仓库"是最主流的 Harness 使用方式。下表覆盖 10 个代表工具。

| 工具 | 出品方 | 开源 | 模型灵活度 | 突出特点 | 典型适用 |
|------|-------|------|-----------|---------|---------|
| **Claude Code** | Anthropic | ❌ | 低（Claude 为主） | Gather-Act-Verify，编辑稳 | Claude 工作流、复杂重构 |
| **Codex** | OpenAI | 部分 | 低（OpenAI 为主） | 三层架构、客户端共享 harness | OpenAI 栈、多端一致 |
| **Gemini CLI** | Google | ✅ | 中 | 与 Gemini/Google 云集成 | Google 生态 |
| **OpenCode** | 社区 | ✅ | **高** | 开源、可自托管、模型无关 | 自托管、数据敏感团队 |
| **Qwen Code** | 阿里 | ✅ | 中 | 面向 Qwen，中文友好 | 中文场景、Qwen 栈 |
| **Aider** | 社区 | ✅ | **高** | 极简 diff 编辑、git 友好 | 小步快跑的补丁式修改 |
| **Goose** | Block | ✅ | **高** | 可扩展、本地优先 | 本地自动化、隐私优先 |
| **Amp** | Sourcegraph | ❌ | 中 | 面向大规模代码库 | 大型 mono-repo |
| **OpenHands** | 社区（原 OpenDevin） | ✅ | **高** | 端到端自动化、沙箱执行 | 批量任务、SWE-bench 类 |
| **SWE-agent** | 学术（普林斯顿） | ✅ | **高** | 为自动修复 issue 而生 | 研究、自动化修 bug |

> 💡 **选型提示**：上表"模型灵活度"仅表示**可替换模型的自由度**，不代表能力高低。闭源工具往往在**自家模型 + 自家 harness 的协同调优**上更强。

---

## 五、编辑器类 Harness 对比

如果你主要在编辑器里工作，关注的是另一种权衡。

| 工具 | 形态 | 开源 | 核心差异 | 适合谁 |
|------|------|------|---------|--------|
| **Cursor** | 独立 IDE（VS Code 分支） | ❌ | 深度 AI 原生、Tab 补全 + Agent 模式 | 愿换 IDE 的深度用户 |
| **Kiro** | 独立 IDE | ❌ | **Spec 驱动开发**为第一公民 | 重视规格先行的团队 |
| **Cline** | VS Code 扩展 | ✅ | 开源、透明、可换模型 | 想留在 VS Code 的开源派 |
| **Continue** | VS Code / JetBrains 扩展 | ✅ | 可接自建模型、企业可私有化 | 企业内私有化部署 |

> 🔗 Spec 驱动开发的理念详见 [9.10 AGENTS.md、Agent Skills 与 Spec 驱动开发](10-standards-skills.md)。
>
> ⚠️ 各家功能迭代很快，具体支持的模型与定价**以官方文档为准**。

---

## 六、表 B：入口形态选型

这是第二张决策表——**先确定你的工作入口，再在对应池子里选**。

```text
你主要在哪儿干活？
│
├── 在【终端】里改仓库 ────────────▶ 池 A
│
├── 在【编辑器】里交互 ────────────▶ 池 B
│
└── 需要【端到端自动化】 ──────────▶ 池 C
```

| 入口形态 | 比较对象（池） | 关键考量 | 首选倾向 |
|---------|---------------|---------|---------|
| **主要在终端改仓库** | Claude Code、Codex、Gemini CLI、OpenCode、Qwen Code、Aider、Goose、Amp | 模型自由度、可自托管、diff 精度、命令权限 | 闭源求稳：Claude Code / Codex；开源可控：OpenCode / Goose / Aider |
| **主要在编辑器内交互** | Cursor、Kiro、Cline、Continue | 是否愿换 IDE、是否要开源、能否私有化 | 愿换 IDE：Cursor / Kiro；留 VS Code：Cline / Continue |
| **需要端到端自动化** | OpenHands、SWE-agent | 沙箱隔离、批量并发、可复现 | OpenHands（工程自动化）/ SWE-agent（issue 修复研究） |

**选择池 A 的细分决策**：

| 你的约束 | 推荐 | 理由 |
|---------|------|------|
| 必须可自托管、数据不出内网 | OpenCode / Goose | 开源 + 模型无关 |
| 追求最高编辑成功率 | Claude Code | 编辑与验证循环成熟 |
| 团队统一多端体验 | Codex | 客户端共享同一 harness |
| 中文任务为主、用 Qwen | Qwen Code | 面向中文 + Qwen 优化 |
| 只要"最小侵入式补丁" | Aider | diff 式编辑、git 友好 |

---

## 七、表 C：开源 vs 闭源 Harness

第三张决策表。**没有绝对优劣，只有权衡**。

| 对比维度 | **开源 Harness** | **闭源 Harness** |
|---------|-----------------|-----------------|
| **模型灵活性** | **高**：可换 DeepSeek / OpenAI / Ollama / 本地模型 | 低：通常绑定自家模型 |
| **可自托管** | ✅ 可完全私有部署 | ❌ 一般只能用云服务 |
| **数据安全** | **可控**：数据不出内网 | 依赖厂商合规承诺 |
| **生态插件** | 增长快但质量参差（如 `dsh-plugin-radar` 需验证） | 官方策展、质量更稳但数量少 |
| **上手成本** | 中：需自行配置模型/沙箱 | **低**：开箱即用、体验打磨好 |
| **成本模型** | 主要为模型 token 成本 + 运维 | 订阅费 + token 成本 |
| **定制深度** | **无限**：可改源码、写插件 | 受限于开放接口 |
| **厂商锁定风险** | 低 | 高 |
| **典型代表** | `dsh`、Deep Agents、OpenCode、Goose、Aider、OpenHands | Claude Code、Codex、Cursor、Amp |

> 🎯 **经验法则**：
> - **个人开发者 / 快速验证** → 闭源优先，省时间
> - **企业核心研发 / 数据敏感** → 开源优先，控风险
> - **两者都要** → 用开源做底座、闭源做尖刀（混合策略）

---

## 八、选型方法论：5 步清单

本章最重要的一句话：

> **Coding Agent Harness 没有脱离场景的"最强"，只有与「工作入口、权限边界、交付方式」匹配的方案。**

三要素的定义：

```text
工作入口 = 你每天真正坐在哪里干活（终端 / 编辑器 / 服务）
权限边界 = Agent 能碰什么（只读？可写仓库？能跑命令？能访问网络？）
交付方式 = 你要的产出是什么（一个 PR？一次批量修复？一份报告？）
```

**5 步选型清单**：

| 步骤 | 问题 | 产出 |
|------|------|------|
| **1. 定入口** | 我/团队每天在哪工作？ | 确定池 A / B / C |
| **2. 划边界** | Agent 允许读写什么？能否执行命令/联网？ | 权限矩阵（参考 [8.8 安全沙箱](../08-ecosystem/survey/08-security-sandbox.md)） |
| **3. 明交付** | 期望的最终产物是什么形态？ | 是否需要沙箱、批量并发 |
| **4. 试候选** | 在各池挑 2–3 个，跑同一批真实任务 | 完成率 / token / 步数数据 |
| **5. 定标准** | 团队的迁移与合规要求？ | 结合表 C 做开源/闭源决策 |

> 💡 **常见误区**：
> - ❌ "看榜单选最强的" → 榜单任务与你的场景未必一致
> - ❌ "选 stars 最多的" → 热度 ≠ 适配
> - ✅ "选与我的入口/边界/交付最匹配的，然后用数据验证"

---

## 九、实战

### 9.1 `dsh` 的安装与最小可用示例

> ⚠️ 以下命令为示例形式，**以官方文档为准**；包名、分发渠道可能随版本变化。

```bash
# 1) 安装（示例，请核对官方安装说明）
npm install -g @deepseek/dsh

# 2) 初始化：生成配置文件与插件清单
dsh init

# 3) 配置模型（不绑定模型，此处示例为 DeepSeek；也可指向 OpenAI / Ollama）
dsh config set model deepseek-chat
dsh config set base_url https://api.deepseek.com

# 4) 配置沙箱（local | container | remote，以官方文档为准）
dsh config set sandbox local

# 5) 最小运行：让 agent 观察仓库并输出待办
dsh run "阅读 README 与 src/ 目录，列出 5 条可执行的改进建议"
```

插件管理的典型形态（以官方文档为准）：

```bash
dsh plugin list                 # 查看已安装插件
dsh plugin add <plugin-name>    # 安装插件
dsh plugin search <keyword>     # 搜索（可对接 dsh-plugin-radar）
```

> 🛡️ **安全提醒**：`dsh` 的插件能力极强（可替换沙箱、调度甚至 Agent Loop）。**只启用已验证插件**，并在隔离环境中先试跑。
>
> 🔗 Harness 内部的权限与沙箱设计见 [9.2 十二大模块](02-anatomy.md) 与 [9.7 Harness Engineering](07-harness-engineering.md)。

### 9.2 用 LangChain Deep Agents 三行代码创建 Agent

> ⚠️ API 名称与参数**以官方文档为准**。以下为最小示例。

```python
# 1 行：导入
from deepagents import create_deep_agent

# 2 行：创建 agent（内置 planning / sub-agent / 文件系统等能力）
agent = create_deep_agent(model="gpt-5.5")

# 3 行：运行
result = agent.invoke(
    {"messages": [{"role": "user", "content": "调研 MCP 协议并写一份 300 字摘要"}]}
)
print(result["messages"][-1].content)
```

若要用 **harness profiles** 覆盖默认行为（声明式，以官方文档为准）：

```python
agent = create_deep_agent(
    model="gpt-5.5",
    profile="research",              # 声明式 profile：覆盖 system_prompt / tools 等
)
```

> 🔗 Deep Agents 与 LangGraph 的关系见 [9.2 十二大模块](02-anatomy.md)；本教程主力栈见 [8.1 核心框架对比](../08-ecosystem/survey/01-core-frameworks.md)。

### 9.3 横向对比脚本思路：同一批任务跑多个 Harness

**目标**：不要凭感觉选型。用**同一批真实任务**喂给多个 harness，量化比较。

**任务集设计（示例）**：

| 任务 ID | 类型 | 描述 | 验收方式 |
|--------|------|------|---------|
| T1 | 修 bug | 修复 `tests/test_api.py` 的失败用例 | 测试通过 |
| T2 | 加特性 | 为某函数补充边界处理与单测 | 测试通过 + 覆盖率 |
| T3 | 重构 | 拆分超长函数，保持行为不变 | 测试通过 |
| T4 | 文档 | 为模块补 docstring 与 README 段落 | 人工评审 |
| T5 | 调研 | 阅读仓库并总结架构 | 人工评分 1–5 |

**度量指标**：

| 指标 | 定义 | 为什么重要 |
|------|------|-----------|
| **完成率** | 验收通过的任务数 / 总任务数 | 能力底线 |
| **平均 token** | 总 token / 任务数 | 直接成本 |
| **平均步数** | 总工具调用轮次 / 任务数 | 效率与"绕路"程度 |
| **平均耗时** | wall-clock 时间 | 交互体验 |
| **人工干预次数** | 需人确认/纠偏的次数 | 自主性 |
| **编辑准确性** | 正确 diff 行数 / 总 diff 行数 | 是否"越改越乱" |

**脚本伪代码**：

```python
# benchmark_harness.py —— 思路示例，实际命令以各工具官方文档为准
import subprocess, json, time, statistics
from dataclasses import dataclass, asdict

TASKS = ["T1", "T2", "T3", "T4", "T5"]

HARNESSES = {
    "claude-code": "claude -p '{task}'",          # 示例命令，以官方为准
    "codex":       "codex exec '{task}'",         # 示例命令，以官方为准
    "opencode":    "opencode run '{task}'",       # 示例命令，以官方为准
    "aider":       "aider --message '{task}'",    # 示例命令，以官方为准
}

@dataclass
class Run:
    harness: str
    task: str
    passed: bool
    tokens: int | None
    steps: int | None
    seconds: float

def run_one(harness: str, cmd: str, task: str) -> Run:
    t0 = time.time()
    proc = subprocess.run(cmd.format(task=task), shell=True,
                          capture_output=True, text=True, timeout=1800)
    elapsed = time.time() - t0
    # 关键：从各工具的输出/metadata 中解析 token 与步数；缺失则记为 None
    # 例如读取 session 日志、--json 输出或 trace 文件（以官方文档为准）
    tokens = parse_tokens(proc.stdout)
    steps = parse_steps(proc.stdout)
    passed = run_acceptance_check(task)      # 跑单测 / 人工评分
    return Run(harness, task, passed, tokens, steps, elapsed)

def main():
    rows = []
    for h, cmd in HARNESSES.items():
        for t in TASKS:
            rows.append(run_one(h, cmd, t))

    # 汇总
    summary = {}
    for h in HARNESSES:
        rs = [r for r in rows if r.harness == h]
        summary[h] = {
            "完成率":  sum(r.passed for r in rs) / len(rs),
            "平均token": statistics.mean([r.tokens for r in rs if r.tokens is not None]) if any(r.tokens for r in rs) else None,
            "平均步数": statistics.mean([r.steps for r in rs if r.steps is not None]) if any(r.steps for r in rs) else None,
            "平均耗时": statistics.mean([r.seconds for r in rs]),
        }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
```

**结果呈现建议**：

| Harness | 完成率 | 平均 token | 平均步数 | 平均耗时 | 人工干预 |
|---------|-------|-----------|---------|---------|---------|
| Claude Code | 4/5 | — | — | — | 2 |
| Codex | 4/5 | — | — | — | 1 |
| OpenCode | 3/5 | — | — | — | 4 |
| Aider | 3/5 | — | — | — | 3 |

> 📌 表中数值留空是**刻意的**——请务必用**你自己仓库的真实任务**填满它，而不是抄任何公开榜单。
>
> 🎯 **方法论要点**：
> 1. **任务必须来自你的真实 backlog**，否则数据无意义
> 2. **同一初始 commit**，保证可比
> 3. **每任务重复 3 次取中位数**，抵消模型随机性
> 4. **验收脚本自动化**（跑测试），减少人工评分偏差
> 5. 记录**失败原因**，比只记通过率更有价值

---

## 本章小结

| 要点 | 说明 |
|------|------|
| 🧭 | Harness = 内置工具/提示词/子 Agent 的 "batteries-included" 框架；与编排库、低代码平台三分天下 |
| 🐋 | **DeepSeek Harness（`dsh`）**：MIT 开源，**"Everything is a plugin"**，依托 **Cordis 内核**，不绑定模型 |
| 🧱 | **Deep Agents** 用 harness profiles 声明式覆盖；**Claude Code** 98.4% 是 harness；**Codex** 三层架构共享 harness |
| 🏢 | **MAF** 发布 Agent Harness + Hosted Agents；**AgentScope** 在 ReActAgent 之上长出全套 Harness |
| 📊 | 三张决策表：方案对比 / 入口形态 / 开源 vs 闭源 |
| 🎯 | 没有"最强"，只有与**工作入口、权限边界、交付方式**匹配的方案 |
| 🔬 | 用同一批**真实任务**横向对比，量化为完成率 / token / 步数 |

---

## 📝 课后练习

1. **分类题**：从你熟悉的 3 个工具中，判断它们分别属于 Harness、底层编排库还是低代码平台，并说明依据
2. **上手题**：参照官方文档跑通 `dsh` 的最小示例（或 Deep Agents 三行示例），记录安装过程中遇到的坑
3. **边界题**：为你的项目写一份"权限矩阵"——Agent 可读写哪些目录？能否执行命令、联网？据此选择沙箱方案
4. **对比题**：设计 5 个来自你真实 backlog 的任务，用第 9.3 节的脚本思路跑 2 个 harness，填写对比表并给出选型结论

---

> 🔗 **延伸阅读**：Harness 内部由哪些模块组成、如何协同？请阅读 [9.2 十二大模块](02-anatomy.md)；如何自己动手搭一个 Harness，见 [9.7 Harness Engineering](07-harness-engineering.md)；跨工具的配置与标准，见 [9.10 AGENTS.md、Agent Skills 与 Spec 驱动开发](10-standards-skills.md)。
