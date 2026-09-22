# 9.7 Harness Engineering 方法论 —— 从「写代码」到「设计环境」

## 📖 导读

> **Humans steer, agents execute.**
> （人类掌舵，Agent 执行。）

**Harness Engineering** 由 OpenAI 于 **2026 年 2 月** 正式提出，标志着软件工程从"人类编写代码"向"**人类设计环境，Agent 执行任务**"的范式转变。

如果说 [9.2](02-anatomy.md) 讲的是 Harness **由什么组成**，本章讲的是 Harness **该怎么设计**。

---

## 一、范式演进：三层同心圆

```text
   ③ Harness Engineering   —— 设计"环境与机制"
   ┌──────────────────────────────────────────┐
   │  ② Context Engineering —— 管理"模型看到什么"│
   │  ┌────────────────────────────────────┐  │
   │  │ ① Prompt Engineering —— 设计"指令"  │  │
   │  └────────────────────────────────────┘  │
   └──────────────────────────────────────────┘
```

| 代际 | 时间 | 核心问题 | 典型产物 |
|------|------|----------|----------|
| ① Prompt Engineering | 2023–2024 | 怎么问？ | 提示词模板 |
| ② Context Engineering | 2025 | 给模型看什么？ | RAG、记忆、压缩 |
| ③ **Harness Engineering** | **2026+** | **怎么用机制保证质量？** | **规则、门禁、验证闭环、可读仓库** |

> 🔑 **Harness Engineering 是 Context Engineering 的一种特定形式**（Martin Fowler 团队的观点），但关注点更偏"**机制**"而非"**信息**"。

---

## 二、OpenAI 的六大概念

出处：《Harness engineering: leveraging Codex in an agent-first world》（Ryan Lopopolo，2026-02-11）。

| # | 概念 | 含义 | 落地做法 |
|:-:|------|------|----------|
| 1 | **仓库即记录系统** | 用仓库承载上下文，而非外部文档（Notion/Confluence） | 决策写进 `DECISIONS.md`、架构写进仓库内的 `architecture.md` |
| 2 | **地图而非手册** | 提供**导航**，而非详尽指引 | `AGENTS.md` 写"去哪找"，不写"全部细节" |
| 3 | **机械化执行** | 用**确定性工具**保证约束 | linter、类型检查、结构测试、CI 门禁 |
| 4 | **智能体可读性** | 让代码/配置对 Agent 友好 | 清晰的目录结构、可 grep 的命名、显式契约 |
| 5 | **吞吐量改变合并理念** | 高吞吐下重新定义"合并"的意义 | 更小的 PR、更快的 CI、更强的自动验证 |
| 6 | **熵管理** | 对抗代码库随规模增长的混乱 | 定期重构、架构适应度函数、依赖方向检查 |

### 2.1 标志性案例

> **3 人团队、零手写代码、5 个月生成超过 100 万行代码。**

关键不在"模型多强"，而在于：

| 要素 | 具体做法 |
|------|----------|
| **机器可读产物** | 架构约束文件、API 契约、设计决策记录（ADR） |
| **闭环验证** | pre-commit、自定义 linter、结构测试；**失败原因回灌重试** |
| **角色转变** | 工程师不再写代码，而是**设计 harness** |

### 2.2 六条原则的一句话总结

```
把"上下文"放进仓库 → 给 Agent 一张地图 → 用工具而非口头约定来强制规范
→ 让一切对 Agent 可读 → 用高吞吐重新设计协作 → 持续对抗熵增
```

---

## 三、Martin Fowler 的控制论框架（最实用的心智模型）

出处：《Harness engineering for coding agent users》（Birgitta Böckeler，Thoughtworks，2026-04-02）。

### 3.1 两个维度

| 维度 | 取值 |
|------|------|
| **作用时机** | **Guides（引导器 / 前馈）**——行动**前**引导 ｜ **Sensors（传感器 / 反馈）**——行动**后**观察 |
| **实现方式** | **Computational（计算性 / 确定性）**——CPU 可判定 ｜ **Inferential（推理性 / 语义）**——需要 LLM |

### 3.2 2×2 矩阵（务必背下来）

|  | **Computational（确定性）** | **Inferential（语义 / LLM）** |
|:--|:---------------------------|:-----------------------------|
| **Guides（前馈）** | bootstrap 脚本、OpenRewrite、**LSP**、代码模板、脚手架 | **`AGENTS.md`、Skills、`architecture.md`、ADR** |
| **Sensors（反馈）** | **linter、ArchUnit、类型检查、覆盖率、结构测试** | **AI code review、LLM-as-judge、对抗性评审** |

### 3.3 三条关键原则

| 原则 | 说明 |
|------|------|
| **单独任一都不行** | 只有反馈 → **反复犯同样的错**；只有前馈 → **不知道规则是否生效** |
| **Ashby 必要多样性定律** | 调节器必须拥有与被调节系统**同等多样性**；因此**选定架构拓扑 = 削减多样性 = 让全面 harness 变得可行** |
| **Harnessability（可驾驭性）** | **不是所有代码库都同样适合被 harness**——混乱、隐式约定的仓库很难 |

### 3.4 共同哲学

> **与其规定怎么做（prescription），不如设置门控拒绝坏结果（backpressure）。**

这与 [9.5 验证循环](05-verification.md) 的"背压"完全一致：**不试图阻止 Agent 犯错，而是让错误后果立刻反馈回去。**

### 3.5 三条规制维度的成熟度

| 维度 | 成熟度 | 现状 |
|------|:------:|------|
| **可维护性 Harness** | ⭐⭐⭐ 最成熟 | 计算性传感器（linter / 类型检查）能可靠捕获结构问题 |
| **架构适应度 Harness** | ⭐⭐ 中等 | 本质是 **Fitness Functions**（架构约束的自动化测试） |
| **行为 Harness** | ⭐ 最弱 | **"房间里的大象"**——功能正确性的自动验证仍然不够好 |

> 📌 这解释了为什么 [9.5 验证循环](05-verification.md) 里"规则型验证"最可靠、"LLM-as-judge"最不可靠——**行为正确性本质上难以被确定性工具判定**。

---

## 四、定义每个 Harness 的七个关键决策

这是本章最实用的部分：**七个必须做的架构级选择**。

### 决策 1：单 Agent vs 多 Agent

| 判断依据 | 结论 |
|----------|------|
| 工具数 < 10、任务域单一 | ✅ **单 Agent** |
| 工具数 >~10 且高度重叠 | 考虑按领域拆分 |
| 任务域明显可分 | 考虑多 Agent |
| "想让效果更好" | ❌ 先优化单 Agent |

> **Anthropic 与 OpenAI 一致建议：先把单 Agent 榨到极致。**
> 多 Agent 的额外开销：路由的额外 LLM 调用、handoff 的上下文损失。

### 决策 2：ReAct vs Plan-and-Execute

| 模式 | 特点 | 代价 |
|------|------|------|
| **ReAct** | 每步交织"推理 + 行动"，灵活 | 每步都要调模型，成本高 |
| **Plan-and-Execute** | 先规划再执行，规划一次、执行多次 | 计划出错时调整代价大 |

> 📊 **数据**：LLMCompiler 报告相比顺序 ReAct **提速 3.6×**。

### 决策 3：上下文窗口管理策略

五种生产做法（详见 [9.3](03-context-engineering.md)）：

| 策略 | 何时用 |
|------|--------|
| 基于时间的清理 | 会话极长 |
| 对话摘要 | 通用 |
| Observation 屏蔽 | 工具输出很多 |
| 结构化笔记 | 长任务 |
| 子 Agent 委派 | 探索型任务 |

> 📊 **ACON 研究**：优先保留推理轨迹、丢弃原始工具输出，可减 **26%–54%** token，同时保持 **95%+** 准确率。

### 决策 4：验证循环设计

| 验证类型 | 优势 | 代价 |
|----------|------|------|
| **计算型**（测试 / linter） | 确定性 ground truth | 覆盖不了语义问题 |
| **推断型**（LLM-as-judge） | 能抓语义问题 | 增加延迟与成本，有主观性 |

用 Fowler 的框架表达：**Guides（前馈，行动前引导）vs Sensors（反馈，行动后观察）**。

### 决策 5：权限与安全架构

| 模式 | 特点 | 适用 |
|------|------|------|
| **宽松型** | 快，多数操作自动通过 | 可信环境、内部工具 |
| **严格型** | 安全，每操作需批准 | 生产、涉敏数据 |

> 📌 实践建议：**从激进审批开始，随信心建立逐步放宽**（详见 [9.4](04-permissions-sandbox.md)）。

### 决策 6：工具边界策略

> **工具越多，往往越差。**

| 证据 | 结果 |
|------|------|
| **Vercel v0** | 从 v0 编码 Agent **砍掉 80% 工具**，结果反而更好 |
| **Claude Code** | 靠懒加载实现 **95% 上下文缩减** |

**原则**：只暴露"当前步骤真正需要的最小工具集"。

### 决策 7：Harness 厚度

| 取向 | 主张 | 代表 |
|------|------|------|
| **薄 Harness** | 把智能交给模型，Harness 只做治理 | **Anthropic**（每次新模型内化规划能力后，就从 Claude Code 的 harness 里**删掉对应规划步骤**） |
| **厚 Harness** | 用显式控制换可预测性 | 图编排框架 |

```text
薄 Harness：  Model ████████████████  Harness ██
厚 Harness：  Model ██████            Harness ████████████

趋势：模型变强 → Harness 变薄，但不会消失
```

---

## 五、脚手架隐喻与共同演化

### 5.1 脚手架会拆，但活儿还在

> **大楼盖好，脚手架就拆了。** —— 模型变强，harness 复杂度应**下降**。

**Manus 的实证**：六个月内重写 **5 次**，每次都在**去复杂度**：

| 从 | 到 |
|----|----|
| 复杂的工具定义 | 通用 shell 执行 |
| "管理 Agent" 的复杂机制 | 简单结构化 handoff |

### 5.2 共同演化（Co-evolution）

> 模型现在是与特定 harness **一起 post-train** 的。

这意味着：

| 推论 | 说明 |
|------|------|
| Claude Code 的模型与它那套 harness 一起训练 | **更换工具实现反而可能降低性能**（耦合极紧） |
| 从零自建 harness 未必能复现闭源工具效果 | 除非你也在做 post-training |

### 5.3 面向未来测试（Future-proofing Test）

```text
换上更强的模型：
  ✅ 不需要增加 harness 复杂度，性能就自动上来  → 设计正确
  ❌ 还要加一堆补丁才不崩                     → 设计有问题（硬编码了弱模型的行为）
```

**这是检验 Harness 设计质量最简洁的判据。**

---

## 六、Spec / Rule / Skill 三层区分

三者常被混用，但**区别在于加载机制**：

| 层 | 加载机制 | 位置 | 用途 |
|:--:|----------|------|------|
| **Rule** | **头部常驻**（always in context） | `AGENTS.md` / 根级规则 | 永远生效的硬约束 |
| **Skill** | **尾部按需**（lazy, on-demand） | `skills/<name>/SKILL.md` | 特定任务才需要的能力包 |
| **Spec** | **被 Skill 消费** | `specs/<feature>.md` | 可执行的规格，供实现与验收 |

```text
上下文窗口
┌──────────────────────────────────────┐
│ [常驻] Rule：AGENTS.md 的核心规则      │ ← 每条会话都加载
│ [常驻] System Prompt                  │
│ ...                                  │
│ [按需] Skill：需要时才注入             │ ← 渐进式披露
│ [按需] Spec：被 Skill 读取             │
└──────────────────────────────────────┘
```

> 📖 三层标准的完整写法（AGENTS.md 模板、SKILL.md 结构、Spec 驱动工作流）见 **[9.10](10-standards-skills.md)**。

---

## 七、现实数据：不要被"效率神话"骗了

Harness Engineering 值得投入，但也要清醒看待收益数据。

| 数据 | 来源 | 说明 |
|------|------|------|
| AI 辅助客观**慢 19%**，但主观觉得**快 20%**（偏差 39pp） | METR RCT | **主观感受与客观效率差距巨大** |
| 个体 PR **+98%**，但 **DORA 四大指标无一改善** | Faros 万人遥测 | 写得快 ≠ 交付快 |
| PR 体积 **+154%**，评审时间 **+91%** | 同上 | 高吞吐的代价转嫁给了评审环节 |

> 🎯 **结论**：Harness Engineering 的价值不在于"让代码写得更快"，而在于**让交付变得可靠**。
> 这也正是"人机效率悖论"的根源——**瓶颈从"写代码"转移到了"验证与交付"**。

---

## 八、可落地模板

### 8.1 `AGENTS.md` 模板（控制在 **50 行以内**）

> 原则：**只放"Agent 不可能从代码推断出的东西"**。

```markdown
# AGENTS.md

## 项目概览
企业知识库问答服务。Python 3.12 + FastAPI + LangGraph。
入口：`src/kb_api/main.py`；核心编排：`src/kb_api/graph/`。

## 构建与测试（Agent 最需要的信息）
- 装依赖：`uv sync`
- 跑测试：`uv run pytest -q`
- 类型检查：`uv run mypy src/`
- 格式化：`uv run ruff format .`
- 启动服务：`uv run uvicorn kb_api.main:app --reload`

## 代码风格（与默认不同的部分）
- 行宽 100（Ruff 配置为准）
- 异步优先：IO 一律用 `async`，禁止在 async 函数里调用阻塞 IO
- 类型注解必填，禁止 `Any`（确有需要必须写注释说明）

## 目录导航（地图而非手册）
- `src/kb_api/api/` 路由层，只做参数校验与编排调用
- `src/kb_api/graph/` LangGraph 图定义与节点
- `src/kb_api/rag/` 检索与重排
- `tests/` 与 src 结构镜像

## 硬性禁止
- ❌ 禁止修改 `tests/` 下的测试来"让测试通过"
- ❌ 禁止提交 `.env`、密钥、真实用户数据
- ❌ 禁止直接 push 到 `main`，一律走 PR
- ❌ 禁止引入新的重量级依赖而不更新 `pyproject.toml`

## PR 惯例
- 分支：`feat/xxx`、`fix/xxx`
- 提交信息：Conventional Commits（`feat:` / `fix:` / `refactor:`）
- 每个 PR 必须包含测试或说明为何不需要
```

> 💡 大型仓库用**级联加载**：根 `AGENTS.md` + 各目录下的 `AGENTS.md` 覆盖（Codex 的机制，**单文件 32 KiB 上限**）。

### 8.2 自定义 linter 规则模板（四段式）

> 每条规则都要带**修复指令**——这是把人类经验固化进 Harness 的最佳载体。

```python
RULE_TEMPLATE = """
[{code}] {title}
ERROR: {error}
WHY:   {why}
FIX:   {fix}
EXAMPLE:
  ❌ {bad}
  ✅ {good}
"""

RULES = [
    RULE_TEMPLATE.format(
        code="KB001", title="async 函数中禁止阻塞 IO",
        error="在 async def 中检测到 requests.get()",
        why="阻塞事件循环，服务吞吐会整体下降",
        fix="改用 httpx.AsyncClient()",
        bad="async def f(): return requests.get(url)",
        good="async def f():\n    async with httpx.AsyncClient() as c:\n        return await c.get(url)",
    ),
    RULE_TEMPLATE.format(
        code="KB002", title="检索层禁止直接拼接用户输入到 SQL",
        error="检测到 f-string 直接拼接 SQL",
        why="SQL 注入风险",
        fix="使用参数化查询",
        bad='cur.execute(f"SELECT * FROM docs WHERE id={doc_id}")',
        good='cur.execute("SELECT * FROM docs WHERE id=%s", (doc_id,))',
    ),
]
```

> 🔥 **复利效应**：**加一条规则，从此每个会话都不会再犯这个错。**
> Prompt 是一次性的，Harness 是**永久**的。

---

## 九、时间预期：这不是一周能做完的事

| 团队 | 耗时 |
|------|------|
| **Manus** | 6 个月 + 5 次架构重写 |
| **LangChain（LangGraph 执行引擎）** | 迭代 4 种架构，耗时**超过一年** |
| **Martin Fowler 团队观察** | Harness 工程量**常大于 Agent 逻辑本身** |
| **小团队普遍经验** | **2–4 个月**才达到生产就绪 |

> ⚠️ 因此本章的实践建议是：**从最小可行 Harness 出发，按"验证 → 持久化 → 可观测 → 人在回路"逐阶段加固**（见 [9.8](08-build-your-harness.md)）。

---

## 十、本章总结

| 要点 | 说明 |
|------|------|
| **范式** | Prompt → Context → **Harness Engineering**（设计环境而非写代码） |
| **OpenAI 六概念** | 仓库即记录系统 / 地图而非手册 / 机械化执行 / 智能体可读性 / 吞吐量改变合并 / 熵管理 |
| **Fowler 控制论** | **Guides × Sensors × Computational × Inferential** 四格矩阵 |
| **三原则** | 单独任一都不行；Ashby 必要多样性；Harnessability |
| **核心哲学** | **与其规定怎么做，不如设置门控拒绝坏结果（背压）** |
| **七问决策** | 单/多 Agent、ReAct/Plan、上下文策略、验证设计、权限架构、工具边界、Harness 厚度 |
| **Spec/Rule/Skill** | 区别在**加载机制**（常驻 / 按需 / 被消费） |
| **共同演化** | 模型与 harness 一起 post-train；换实现可能降性能 |
| **未来测试** | 换更强模型不需要加复杂度 → 设计正确 |
| **时间预期** | 数月而非数天；harness 工程量常大于 agent 逻辑 |

---

## 📝 课后练习

1. **矩阵填空**：不看本章，凭记忆画出 Fowler 的 2×2 矩阵，为每一格至少填 2 个具体工具或产物，然后对照检查。
2. **决策练习**：为"一个需要爬取 20 个网站并生成对比报告"的任务，逐条回答"七个关键决策"，并给出你的选择与理由。
3. **写一份 AGENTS.md**：为你当前的项目写一份不超过 50 行的 `AGENTS.md`，要求包含"Agent 不可能从代码推断出的信息"，并说明你删掉了哪些"能从代码推断"的冗余内容。
4. **规则沉淀 + 未来测试**：把你项目中一个反复出现的代码问题写成四段式 linter 规则；然后设想"如果换上一个更强的新模型，这条规则还需要吗？"——如果不需要，说明它属于"补偿弱模型"的临时手段。
