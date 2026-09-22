# 第九部分：Agent Harness（驾驭工程）

> 🚀 **2026 年最重要的一次认知升级：`Agent = Model + Harness`**

## 📖 这一部分讲什么

前八部分，我们学会了用 LangChain v1 / LangGraph 把模型、工具、记忆、RAG 组装成 Agent。

到了 2026 年，社区形成了一个新共识：

> **当模型不再是瓶颈，Harness 就成了决定性的战场。**

**Harness（驾驭层）** 指的是**模型之外的一切**——系统提示词、工具、技能、沙箱、编排循环、权限、验证、可观测性。它决定了模型**看到什么、能做什么、何时停止、出错时怎么办**。

**本部分是全教程的收官之作**，带你从"会搭 Agent"进阶到"会设计 Harness"。

---

## 📚 章节导航

| 章节 | 标题 | 一句话 |
|:----|:-----|:-------|
| [9.1](01-intro.md) | 什么是 Agent Harness | 核心公式、三大类比、为什么 2026 是 Harness 之年 |
| [9.2](02-anatomy.md) | Harness 十二大模块解剖 | 完整工程地图：从编排循环到生命周期 |
| [9.3](03-context-engineering.md) | 上下文工程与压缩流水线 | 对抗 context rot；Claude Code 五层压缩 |
| [9.4](04-permissions-sandbox.md) | 权限、护栏与沙箱 | deny-first、七级权限、Hooks、沙箱执行 |
| [9.5](05-verification.md) | 验证循环 | 玩具 Demo 与生产级 Agent 的分界线 |
| [9.6](06-subagents-longtasks.md) | 子 Agent 编排与长时任务 | Fork/Teammate/Worktree、Ralph Loop |
| [9.7](07-harness-engineering.md) | Harness Engineering 方法论 | OpenAI 六大概念、Fowler 控制论、七问决策 |
| [9.8](08-build-your-harness.md) | 实战：从零构建最小可行 Harness | 约 300 行可运行代码 |
| [9.9](09-open-source-landscape.md) | 开源 Harness 全景与选型 | dsh、Deep Agents、Claude Code、Codex… |
| [9.10](10-standards-skills.md) | AGENTS.md、Agent Skills 与 Spec 驱动开发 | 跨工具标准与技能生态 |
| [9.11](11-evaluation-observability.md) | Harness 评测与可观测性 | 如何证明你的 Harness 更好 |

---

## 🗺️ 建议学习路径

```text
建立认知          9.1 导论 → 9.2 十二大模块（地图）
     │
     ▼
掌握三大核心机制   9.3 上下文工程 → 9.4 权限与沙箱 → 9.5 验证循环
     │
     ▼
突破边界          9.6 子 Agent 与长时任务
     │
     ▼
动手实践          9.8 从零构建最小可行 Harness
     │
     ▼
方法论与选型      9.7 Harness Engineering → 9.9 开源全景 → 9.10 标准 → 9.11 评测
```

---

## 🎯 学完你能做到

- ✅ 说清 `Agent = Model + Harness`，并判断一个系统里"哪些属于 Harness"
- ✅ 独立设计 Harness 的**十二大模块**，尤其是上下文、权限、验证三大核心
- ✅ 用 **deny-first** 权限模型 + 沙箱，让 Agent 的"手"变得可托付
- ✅ 设计**验证循环**，把任务完成率从"能跑"提升到"可信"
- ✅ 用 **子 Agent + 状态持久化**突破上下文窗口，跑长时任务
- ✅ 从零写出一个**可运行的最小可行 Harness**，并知道如何逐阶段加固到生产
- ✅ 在 **dsh / Deep Agents / Claude Code / Codex** 等开源方案中做出合理选型
- ✅ 用 **AGENTS.md / Skills / Spec** 建立跨工具、可移植的 Harness
- ✅ 用 **评测与可观测性**证明"我的 Harness 更好"

---

## 🔑 三个必须记住的结论

| # | 结论 |
|:-:|------|
| 1 | **用机制强制质量，而不是用 prompt 请求质量。** Prompt 是一次性的，Harness 是永久复利的。 |
| 2 | **95% 单步成功率 × 20 步 ≈ 36% 端到端成功率。** 长任务的成败取决于 Harness 能否抑制错误复合。 |
| 3 | **The model is commodity. The harness is moat.**（模型是商品，Harness 是护城河。） |

---

## 🔗 与其它部分的联系

| 本部分概念 | 前置章节 |
|-----------|----------|
| 编排循环 / TAO | [2.3 Agent 核心架构](../02-fundamentals/03-agent-architecture.md) |
| 上下文管理 / 记忆 | [2.4 记忆机制](../02-fundamentals/04-memory.md) |
| 工具 / MCP | [3.2 模型与工具](../03-langchain/02-models-and-tools.md)、[8.10 MCP](../08-ecosystem/protocols/01-mcp.md) |
| 状态与持久化 | [4.2 状态管理与节点](../04-langgraph/02-state-nodes.md) |
| 多 Agent 协作 | [6.1 多 Agent 协作](../06-advanced/01-multi-agent.md) |
| 评测与可观测性 | [6.2 评估](../06-advanced/02-evaluation.md)、[7.3 可观测性](../07-deployment/03-monitoring.md) |
| 安全与沙箱 | [6.4 安全与合规](../06-advanced/04-security.md)、[8.8 安全沙箱](../08-ecosystem/survey/08-security-sandbox.md) |
