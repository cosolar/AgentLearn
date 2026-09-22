# 9.2 Harness 十二大模块解剖 —— 一份完整的工程地图

## 📖 导读

> **Harness 的复杂性不在循环本身，而在于循环所管理的所有东西。**

[9.1](01-intro.md) 我们建立了 `Agent = Model + Harness` 的认知。本章把 Harness **完整拆开**，逐个讲清它的十二大模块、一次循环的七个步骤、以及生产框架的真实实现。

这一章是本部分的**地图**：后面 [9.3](03-context-engineering.md)–[9.6](06-subagents-longtasks.md) 会深入其中的关键模块。

---

## 一、Harness 十二大模块总览

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Agent Harness                                 │
│                                                                      │
│  ① 编排循环 ── 心跳：TAO/ReAct 循环，驱动一切                          │
│                                                                      │
│  ┌─── 输入侧 ────────────────────────┐  ┌─── 执行侧 ──────────────┐  │
│  │ ⑤ Prompt 构造（分层组装每步输入）   │  │ ② 工具（注册/校验/沙箱）│  │
│  │ ④ 上下文管理（对抗 context rot）    │  │ ⑨ 护栏与安全（权限）    │  │
│  │ ③ 记忆（短期 + 长期）              │  │ ⑧ 错误处理（四类分类）  │  │
│  └───────────────────────────────────┘  └─────────────────────────┘  │
│                                                                      │
│  ┌─── 控制侧 ────────────────────────┐  ┌─── 保障侧 ──────────────┐  │
│  │ ⑥ 输出解析（原生 tool_calls）      │  │ ⑩ 验证循环（质量闭环）  │  │
│  │ ⑦ 状态管理（checkpoint/恢复）      │  │ ⑪ 子 Agent 编排         │  │
│  └───────────────────────────────────┘  │ ⑫ 生命周期管理          │  │
│                                          └─────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

| # | 模块 | 一句话职责 | 深入章节 |
|:-:|------|-----------|:--------:|
| ① | **编排循环** | 心跳：TAO / ReAct 循环 | 本章 |
| ② | **工具** | Agent 的手：注册、校验、沙箱执行、结果格式化 | [9.4](04-permissions-sandbox.md) |
| ③ | **记忆** | 多时间尺度：短期会话 + 跨会话持久化 | 本章 / [2.4](../02-fundamentals/04-memory.md) |
| ④ | **上下文管理** | 对抗 context rot，维持最小高信号 token 集 | [9.3](03-context-engineering.md) |
| ⑤ | **Prompt 构造** | 分层组装每一步的实际输入 | 本章 |
| ⑥ | **输出解析** | 依赖原生 `tool_calls`，而非解析自由文本 | 本章 |
| ⑦ | **状态管理** | 图状态、checkpoint、断点恢复 | 本章 / [4.2](../04-langgraph/02-state-nodes.md) |
| ⑧ | **错误处理** | 四类错误分类 + 重试上限 | 本章 |
| ⑨ | **护栏与安全** | 输入/输出/工具三级护栏 + 权限架构 | [9.4](04-permissions-sandbox.md) |
| ⑩ | **验证循环** | 玩具 Demo 与生产级 Agent 的分界线 | [9.5](05-verification.md) |
| ⑪ | **子 Agent 编排** | Fork / Teammate / Worktree 等执行模型 | [9.6](06-subagents-longtasks.md) |
| ⑫ | **生命周期管理** | 启动、健康监控、优雅关闭、崩溃恢复 | 本章 |

> 📌 **注意**：不同团队的模块划分略有差异（有的文献列 11 个，有的列 12 个）。**重点是模块之间的协作关系，而不是编号本身。**

---

## 二、① 编排循环（Orchestration Loop）

### 2.1 它就是那个"笨循环"

编排循环实现 **Thought-Action-Observation（TAO）**，也就是我们在 [2.3 Agent 核心架构](../02-fundamentals/03-agent-architecture.md) 学过的 ReAct 循环：

```
组装 prompt → 调 LLM → 解析输出 → 执行工具调用 → 结果喂回 → 重复直至终止
```

**机械上看，它往往只是一个 `while` 循环**：

```python
while True:
    prompt = build_prompt(state)              # ⑤ Prompt 构造
    response = model.invoke(prompt)           # → 模型推理
    if not response.tool_calls:               # ⑥ 输出解析
        return response.content               # 终止：无工具调用
    for call in response.tool_calls:          # ② 工具执行
        result = execute_tool(call)
        state.messages.append(result)         # ⑦ 状态更新 / ④ 上下文更新
    if state.turns > MAX_TURNS:               # 终止：轮数上限
        return "达到最大轮数"
```

> 🎯 **关键认知**：**复杂度不在循环本身，而在循环所管理的所有东西。**
> Anthropic 自述其 runtime 是 **"dumb loop"** —— 所有智能在模型里，Harness 只负责管理每一轮。

### 2.2 一次循环的七个步骤（生产级）

| 步骤 | 内容 | 关键细节 |
|:--:|------|----------|
| **1** | **Prompt 组装** | system prompt + 工具 schema + 记忆文件 + 对话历史 + 当前用户消息；**重要内容放首尾** |
| **2** | **LLM 推理** | 组装好的 prompt 发往模型 API，返回文本 / 工具调用请求 / 两者兼有 |
| **3** | **输出分类** | 纯文本无工具调用 → 结束；有工具调用 → 进入执行；请求 handoff → 切换 agent 并重启 |
| **4** | **工具执行** | 校验参数 → 检查权限 → **沙箱内执行** → 抓取结果；**只读并发，写操作串行** |
| **5** | **结果打包** | 格式化为模型可读消息；错误被捕获并作为 error result 返回以供自纠 |
| **6** | **上下文更新** | 结果追加至对话历史；接近窗口上限时触发压缩 |
| **7** | **循环** | 回到第 1 步，直至终止 |

### 2.3 分层终止条件

一个健壮的 Harness **必须有多种终止机制**：

| 终止条件 | 说明 | 优先级 |
|----------|------|:------:|
| **模型输出无工具调用的响应** | 正常结束（模型认为自己完成了） | 正常 |
| **护栏 tripwire 触发** | 安全终止（见 ⑨） | **最高** |
| **用户中断** | 人工接管 | 高 |
| **token 预算耗尽** | 成本保护 | 中 |
| **达到最大轮数** | 死循环保护 | 中 |
| **返回安全拒绝** | 内容策略拦截 | 中 |

> ⚠️ **反模式**：只依赖 `max_iterations` 而不做循环检测。模型可能在 3 个工具之间"乒乓"直到耗尽轮数，白烧 token。正确做法见 [9.11 死循环检测](11-evaluation-observability.md)。

### 2.4 规模感受

| 任务类型 | 典型轮数 | 工具调用次数 |
|----------|:--------:|:------------:|
| 简单问答 | 1–2 | 0–1 |
| 查资料 + 总结 | 3–6 | 2–5 |
| 复杂重构 / 长任务 | 数十轮 | 几十次 |

---

## 三、② 工具（Tools）—— Agent 的手

### 3.1 工具的定义形式

工具本质是一段 **schema**，注入模型上下文以告知"可用手段"：

```python
from langchain.tools import tool


@tool
def search_web(query: str, max_results: int = 5) -> str:
    """搜索互联网获取实时信息。

    Args:
        query: 搜索关键词，应简洁明确
        max_results: 返回结果数量，默认 5
    """
    return do_search(query, max_results)
```

| 要素 | 作用 | 工程要点 |
|------|------|----------|
| **name** | 唯一标识 | 动词开头，一眼看懂 |
| **description** | 告诉模型**何时**使用 | **决定工具选择准确率的第一因素** |
| **parameters** | 参数类型与说明 | 用类型注解 + 描述，减少传参错误 |
| **返回值** | Observation | 结构化、可控长度（过长会挤爆上下文） |

### 3.2 工具层的完整职责链

```
注册 → schema 校验 → 参数提取 → 权限检查 → 沙箱执行 → 结果捕获 → 格式化为 observation
```

**只有第 5 步"沙箱执行"是模型真正关心的，前面 4 步都是 Harness 的治理职责。**

### 3.3 各框架的工具分类

| 框架 | 工具分类 |
|------|----------|
| **Claude Code** | 六类：文件操作、搜索、执行、Web 访问、代码智能、子 Agent 派生 |
| **OpenAI Agents SDK** | 函数工具（`@function_tool`）、托管工具（WebSearch / CodeInterpreter / FileSearch）、MCP server 工具 |
| **LangChain v1** | `@tool` 装饰器、`BaseTool` 类、MCP 适配器（`langchain-mcp-adapters`） |

### 3.4 并发策略（重要）

> **只读操作并发执行，写 / 变更操作串行执行。**

```python
# 伪代码：Harness 层的调度策略
READ_ONLY = {"read_file", "search_web", "grep", "list_dir"}

async def execute_batch(calls):
    reads = [c for c in calls if c.name in READ_ONLY]
    writes = [c for c in calls if c.name not in READ_ONLY]

    # 只读：并发，快
    read_results = await asyncio.gather(*[run(c) for c in reads])
    # 写操作：串行，避免竞态
    write_results = [await run(c) for c in writes]
    return read_results + write_results
```

### 3.5 铁律：工具越多，往往越差

| 证据 | 结果 |
|------|------|
| **Vercel v0** | 从编码 Agent 中**移除 80% 的工具**，结果反而更好 |
| **Claude Code** | 通过**懒加载**（按需加载工具定义）实现 **95% 的上下文缩减** |

> 🔑 **原则**：只暴露"当前步骤真正需要的最小工具集"。在 [9.7](07-harness-engineering.md) 中我们会把它作为"七个关键决策"之一详细展开。

---

## 四、③ 记忆（Memory）—— 跨时间尺度的连续性

### 4.1 多时间尺度

| 尺度 | 含义 | 实现示例 |
|------|------|----------|
| **短期** | 单次会话的对话历史 | 会话内消息列表 / LangGraph checkpointer |
| **长期** | 跨会话持久化 | `CLAUDE.md` + 自动生成的 `MEMORY.md`；LangGraph 命名空间化的 JSON Store；OpenAI 基于 SQLite/Redis 的 Sessions |

### 4.2 Claude Code 的三层记忆结构

这是一种非常精巧的设计，值得直接借鉴：

| 层 | 内容 | 加载策略 |
|:--:|------|----------|
| **1** | 轻量级索引（每条约 **150 字符**） | **永远加载**，保证"知道自己知道什么" |
| **2** | 详细主题文件 | **按需拉取** |
| **3** | 原始 transcript | **只能通过搜索访问** |

> 💡 **设计精髓**：索引常驻（成本极低）+ 详情按需（渐进式披露），既不会"忘记"，也不会占满窗口。

### 4.3 记忆的关键设计原则

> ⚠️ **Agent 应把自己的记忆当作"提示（hint）"，而非事实。**
> 动手前先与**真实状态**对齐验证（例如：记忆说"这个文件里有 A 函数"，用之前先 grep 确认）。

这是一个极易被忽略、却直接影响可靠性的原则。详见 [2.4 记忆机制](../02-fundamentals/04-memory.md)。

---

## 五、④ 上下文管理（Context Management）—— 第一性资源

### 5.1 核心问题：Context Rot（上下文腐化）

| 现象 | 数据 |
|------|------|
| 关键内容落在窗口中段时，模型表现**下降 30%+** | Chroma 研究（与斯坦福 "Lost in the Middle" 互证） |
| 即便百万 token 窗口，上下文变长也会导致**指令遵循能力退化** | 多家长上下文评测 |

### 5.2 四种生产策略（速览）

| 策略 | 机制 | 代表实现 |
|------|------|----------|
| **压缩 Compaction** | 接近上限时总结会话历史 | Claude Code 保留架构决策与未解决 bug，丢弃冗余工具输出 |
| **Observation 屏蔽** | 隐藏旧工具输出，但保留工具调用本身可见 | JetBrains Junie |
| **即时检索 JIT** | 只存轻量标识符，动态加载 | Claude Code 用 `grep`/`glob`/`head`/`tail`，而非整文件加载 |
| **子 Agent 委派** | 子 Agent 大量探索，只回传 **1,000–2,000 token** 浓缩总结 | Claude Code / Deep Agents |

> 🎯 Anthropic 的官方目标：**"找到最小的一组高信号 token，把达成期望结果的概率最大化。"**
>
> 📖 完整展开（含 Claude Code 五层压缩流水线与 prompt cache 优化）见 **[9.3 上下文工程与压缩流水线](03-context-engineering.md)**。

---

## 六、⑤ Prompt 构造（Prompt Construction）

### 6.1 分层组装结构

```text
┌────────────────────────────────────────┐
│ 1. System Prompt         ← 角色、规则   │  ← 最高优先级
│ 2. 工具定义（schema）                    │
│ 3. 记忆文件（CLAUDE.md / MEMORY.md）     │
│ 4. 对话历史                             │
│ 5. 当前用户消息                          │  ← 次高优先级（首尾效应）
└────────────────────────────────────────┘
```

### 6.2 OpenAI Codex 的严格优先级栈

| 优先级 | 内容 | 说明 |
|:--:|------|------|
| 1（最高） | **服务端控制的 system message** | 由平台锁定，用户改不了 |
| 2 | 工具定义 | — |
| 3 | 开发者指令 | — |
| 4 | 用户指令（**级联 `AGENTS.md`，32 KiB 上限**） | 目录级覆盖 |
| 5（最低） | 对话历史 | — |

> 💡 **位置策略**：把最重要的内容放在 prompt 的**开头与结尾**，规避 "Lost in the Middle"。
>
> 📌 AGENTS.md 的级联加载与写法详见 [9.10](10-standards-skills.md)。

---

## 七、⑥ 输出解析（Output Parsing）

### 7.1 现代 Harness 依赖"原生工具调用"

| 代际 | 做法 | 问题 |
|------|------|------|
| 早期（2023） | 解析自由文本（`ReAct` 文本格式） | 格式脆弱，需大量容错 |
| **现代（2026）** | **原生 `tool_calls` 结构化输出** | 稳定、类型安全 |

判定逻辑极其简洁：

```
有 tool_calls → 执行工具，继续循环
无 tool_calls → 这就是最终答案，结束
```

### 7.2 结构化输出

OpenAI 与 LangChain 都通过 **Pydantic 模型**做 schema 约束（LangChain v1 中推荐 `response_format=ToolStrategy(Model)`，见 [3.1](../03-langchain/01-core-components.md)）。

**遗留兜底方案**：`RetryWithErrorOutputParser` —— 把「原 prompt + 失败的补全 + 解析错误」一起喂回模型重试。**仅用于边缘场景**。

---

## 八、⑦ 状态管理（State Management）

### 8.1 三种主流路线

| 框架 | 状态模型 | 恢复机制 |
|------|----------|----------|
| **LangGraph** | 状态 = 在图节点间流动的**类型化字典**，reducer 合并更新 | **super-step 边界**上的 checkpoint；支持中断恢复与**时间回溯调试** |
| **OpenAI** | 四种**互斥**策略：application memory / SDK sessions / 服务端 Conversations API / 轻量 `previous_response_id` 串联 | 服务端或客户端承载 |
| **Claude Code** | 另辟一路：**git commit 当 checkpoint，进度文件当结构化草稿纸** | 靠文件系统恢复 |

### 8.2 LangGraph 示例

```python
from typing import Annotated, TypedDict
import operator
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver


class AgentState(TypedDict):
    messages: Annotated[list, operator.add]   # reducer：追加而非覆盖
    artifacts: dict                            # 产出物
    turns: int


graph = StateGraph(AgentState)
graph.add_node("llm", llm_call_node)
graph.add_node("tools", tool_node)
graph.add_conditional_edges("llm", should_continue, {"tools": "tools", "end": END})
graph.add_edge("tools", "llm")
graph.set_entry_point("llm")

app = graph.compile(checkpointer=InMemorySaver())   # ← 状态持久化
config = {"configurable": {"thread_id": "task-1"}}
app.invoke({"messages": [HumanMessage("开始")]}, config)
app.invoke({"messages": [HumanMessage("继续")]}, config)   # 从中断处续跑
```

> 💡 **Claude Code 的"文件系统当状态"值得借鉴**：`git commit` 天然具备版本、diff、回滚能力，比自建 checkpoint 更省事，且**人类可读**。
>
> 📖 详见 [4.2 状态管理与节点](../04-langgraph/02-state-nodes.md)。

---

## 九、⑧ 错误处理（Error Handling）

### 9.1 为什么必须分类处理

```
10 步流程，每步 99% 成功率：
  0.99^10 ≈ 90.4%     ← 错误复合极快
```

### 9.2 LangGraph 的四类错误分类（推荐直接采用）

| 类型 | 典型场景 | 处理方式 |
|------|----------|----------|
| **瞬时错误**（Transient） | 网络抖动、限流 429 | 按**指数退避**重试 |
| **LLM 可恢复**（LLM-recoverable） | 工具参数写错、调用顺序不对 | 作为 `ToolMessage` 返回，**让模型自行调整** |
| **用户可修复**（User-fixable） | 缺少必要信息、需要授权 | **中断**，等待人类输入 |
| **意外错误**（Unexpected） | 代码 bug、未知异常 | **向上冒泡**用于调试，不要吞掉 |

### 9.3 工程要点

| 实践 | 说明 |
|------|------|
| **捕获工具内所有失败** | Anthropic 的做法：在工具 handler 内捕获一切异常，作为 error result 返回，**保证循环不中断** |
| **重试次数上限** | Stripe 的生产 harness 把重试上限设为 **2 次** |
| **错误信息要可行动** | 不要返回 `"Error"`，要返回 `"参数 max_results 必须为正整数，当前为 -1"` |

```python
from functools import wraps


def tool_safe(func):
    """工具级容错：任何异常都转成模型可读的 error result"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            return f"[参数错误] {e}。请检查参数后重试。"
        except TimeoutError:
            return "[超时] 工具执行超时，可尝试缩小查询范围。"
        except Exception as e:
            return f"[工具失败] {type(e).__name__}: {e}"
    return wrapper
```

---

## 十、⑨ 护栏与安全（Guardrails & Safety）

### 10.1 三级护栏（OpenAI Agents SDK）

| 级别 | 触发时机 |
|------|----------|
| **输入护栏** | 在第一个 agent 上执行 |
| **输出护栏** | 在**最终输出**上执行 |
| **工具护栏** | 在**每次**工具调用时执行 |

**tripwire 机制**：一旦触发，Agent **立即停机**（不是"继续但忽略"）。

### 10.2 架构式分离（Anthropic 的核心主张）

> **权限执行与模型推理解耦：**
> **模型决定"尝试做什么"，工具系统决定"什么被允许"。**

这是 Harness 安全设计的基石——**安全性不能依赖模型的判断力**。

### 10.3 Claude Code 的权限设计（速览）

- 对约 **40 个离散工具能力**分别设卡
- 三阶段：**项目加载时建立信任 → 每次工具调用前检查 → 高风险操作要求显式确认**
- **deny-first**：deny 永远覆盖 allow（类似防火墙）

> 📖 完整的七级权限光谱、Hooks 机制与沙箱实现见 **[9.4 权限、护栏与沙箱](04-permissions-sandbox.md)**。

---

## 十一、⑩ 验证循环（Verification Loops）

> 🔥 **这是把"玩具 Demo"与"生产级 Agent"真正分开的一条线。**

### 11.1 三条验证路径（Anthropic 推荐）

| 路径 | 手段 | 特点 |
|------|------|------|
| **基于规则的反馈** | 测试、linter、类型检查、构建 | 确定性 ground truth，最可靠 |
| **视觉反馈** | UI 任务用 Playwright 截图 | 适合前端 / 图形界面 |
| **LLM-as-judge** | 专门 subagent 评估输出 | 能抓语义问题，但增加延迟与成本 |

### 11.2 效果数据

| 来源 | 数据 |
|------|------|
| Claude Code 作者 Boris Cherny | 给模型一个自我验证的办法，**质量提升 2–3 倍** |
| 某团队结构化验证实践 | 任务完成率 **83% → 96%** |
| HumanLayer "Back-Pressure" | 测试 / 构建 / 类型检查构成**自我验证回路** |

> 📖 完整的四档验证强度（内联 → `/goal` → Stop Hook → 对抗性子 Agent）见 **[9.5 验证循环](05-verification.md)**。

---

## 十二、⑪ 子 Agent 编排（Subagent Orchestration）

### 12.1 为什么需要子 Agent

> **子 Agent 是上下文的防火墙。**
> 子 Agent 大量探索（消耗大量 token），但只把 **1,000–2,000 token** 的浓缩结论回传主 Agent。

这让主 Agent 的上下文**始终保持在高信号状态**。

### 12.2 Claude Code 的三种执行模型

| 模型 | 机制 | 适用 |
|------|------|------|
| **Fork** | 父上下文的**字节级副本** | 需要完整上下文的并行分支 |
| **Teammate** | 独立终端 pane，通过**基于文件的邮箱**通信 | 长期并行的多个 Agent |
| **Worktree** | 每个 agent 拥有自己的 **git worktree** 与隔离分支 | 并行改代码不冲突 |

### 12.3 其他框架的实现

| 框架 | 实现方式 |
|------|----------|
| **OpenAI Agents SDK** | `agents-as-tools`（专家处理受限子任务）、`handoffs`（专家接管全部控制权） |
| **LangGraph** | subagent 实现为**嵌套状态图**，或用 `Send` 做 fan-out |
| **CrewAI** | Agent（role/goal/backstory）+ Task + Crew；**Flows 层**负责路由与校验（"确定性骨干 + 局部智能"） |
| **AutoGen → MAF** | 五种编排模式：顺序、并发（fan-out/fan-in）、群聊、handoff、**magentic**（manager 维护动态任务 ledger） |

> ⚠️ **Anthropic 与 OpenAI 的一致建议**：**先把单 Agent 榨到极致**。多 Agent 有额外开销（路由的额外 LLM 调用、handoff 的上下文损失），仅当**工具数 >~10 且高度重叠**、或**任务域明显可分**时才拆分。
>
> 📖 长时任务（Ralph Loop、Initializer+Coding 双 Agent）见 **[9.6 子 Agent 编排与长时任务](06-subagents-longtasks.md)**。

---

## 十三、⑫ 生命周期管理（Lifecycle Management）

这是最容易被忽视、却直接决定"能不能上生产"的模块。

| 职责 | 具体内容 |
|------|----------|
| **启动** | 环境自检、依赖就绪检查、版本校验 |
| **健康监控** | 检测"是否卡在循环里"（调用次数异常增长）、内存/句柄泄漏 |
| **资源上限** | 最大轮数、最大 token、最大墙钟时间、最大成本 |
| **优雅关闭** | 保存状态、释放资源、标记未完成任务 |
| **崩溃恢复** | **带指数退避**的重启；恢复时**校验前置条件**（外部世界可能已变） |

### 13.1 死循环检测示例

```python
import hashlib
from collections import Counter


class LoopDetector:
    """启发式循环检测：识别重复的工具调用模式"""

    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self.history = Counter()

    def check(self, tool_name: str, args: dict) -> bool:
        sig = hashlib.md5(f"{tool_name}:{sorted(args.items())}".encode()).hexdigest()
        self.history[sig] += 1
        if self.history[sig] >= self.threshold:
            raise RuntimeError(
                f"检测到循环：{tool_name} 以相同参数被调用 {self.threshold} 次"
            )
        return True
```

### 13.2 生命周期状态机

```
INIT → RUNNING → ┬→ COMPLETED
                 ├→ FAILED（可重试，退避后回到 RUNNING）
                 ├→ SUSPENDED（等待人工输入 / 中断恢复）
                 └→ TERMINATED（超预算 / tripwire / 用户取消）
```

**每一种终态都必须：持久化状态 + 输出可诊断信息 + 释放资源。**

---

## 十四、真实框架实现对照

| 框架 | Harness 实现方式 | 特征 |
|------|------------------|------|
| **Anthropic Claude Agent SDK** | 单一 `query()` 函数创建 agent 循环，返回流式消息的异步迭代器 | "dumb loop"；Claude Code 走 **Gather-Act-Verify** 循环 |
| **OpenAI Agents SDK** | `Runner` 类，三种模式：async / sync / streamed | "code-first"，工作流用原生 Python 而非图 DSL；**Codex 三层架构**：Codex Core / App Server（双向 JSON-RPC）/ client 层 —— **所有客户端共享同一 harness** |
| **LangGraph** | 显式状态图：`llm_call` + `tool_node` 两节点 + 条件边 | 由 `AgentExecutor` 演化而来（后者 v0.2 因难扩展、缺多 agent 支持被废弃）；**Deep Agents** 明确使用 "agent harness" 术语 |
| **CrewAI** | 基于角色的多 agent | Agent / Task / Crew；Flows 层提供确定性骨干 |
| **Microsoft Agent Framework** | 对话驱动编排 | 五种编排模式；AutoGen + Semantic Kernel 合并 |

---

## 十五、循环之外：脚手架会变薄，但不会消失

> **共同演化原则**：模型现在是与特定 harness **一起 post-train** 的。Claude Code 的模型是与它那套 harness 一起训练出来的，**更换工具实现反而可能降低性能**（耦合极紧）。

**面向未来测试（Future-proofing Test）**：

```
换上更强的模型 → 不需要增加 harness 复杂度，性能就自动上来 → 设计正确 ✅
换上更强的模型 → 还要加一堆补丁才不崩                   → 设计有问题 ❌
```

**趋势**：模型进步 → Harness 走向**更薄**；但 **Harness 不会消失** —— 即便最强的模型，也需要一层东西来管理上下文窗口、执行工具调用、持久化状态、验证工作。

> 🔥 收尾金句：**"下次你的 Agent 出毛病时，别怪模型，去看看 Harness。"**

---

## 十六、本章总结

| 模块 | 一句话要点 |
|------|------------|
| ① 编排循环 | 就是一个 while 循环，复杂度在它管理的一切 |
| ② 工具 | 只读并发、写串行；**工具越多往往越差** |
| ③ 记忆 | 多时间尺度；索引常驻 + 详情按需；**记忆是 hint 不是事实** |
| ④ 上下文管理 | 对抗 context rot，目标是"最小高信号 token 集" |
| ⑤ Prompt 构造 | 分层组装，重要内容放首尾 |
| ⑥ 输出解析 | 用原生 `tool_calls`，不要解析自由文本 |
| ⑦ 状态管理 | checkpoint 恢复；文件系统也是一种状态载体 |
| ⑧ 错误处理 | 四类分类 + 重试上限；工具内捕获保证循环不中断 |
| ⑨ 护栏与安全 | 权限执行与推理解耦；tripwire 即停 |
| ⑩ 验证循环 | **生产级的分水岭** |
| ⑪ 子 Agent | 上下文防火墙；先榨干单 Agent |
| ⑫ 生命周期 | 健康检查、资源上限、优雅关闭、带退避恢复 |

---

## 📝 课后练习

1. **画图作业**：不看本章，凭记忆画出 Harness 十二大模块的关系图，并标注每个模块"输入什么、输出什么"。
2. **模块实现**：为 [9.8](08-build-your-harness.md) 中即将构建的 Harness 实现 ⑧ 错误处理的四类分类（写成一个 `classify_error()` 函数 + 对应处理表）。
3. **并发改造**：给出 5 个工具（`read_file`、`grep`、`write_file`、`run_tests`、`search_web`），写出一个批量执行调度器，满足"只读并发、写串行"。
4. **对照分析**：打开你常用的一个 Agent 工具，判断它的 ⑤ Prompt 构造顺序与 ⑨ 权限模型分别属于哪种设计，写出你的判断依据。
