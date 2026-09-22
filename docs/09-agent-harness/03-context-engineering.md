# 9.3 上下文工程与压缩流水线 —— Harness 的第一性资源

## 📖 导读

如果说模型是 Agent 的"大脑"，工具是 Agent 的"双手"，那么**上下文（Context）就是血液**——大脑再聪明，一旦血液被稀释、被污染、被堵塞，整个系统就会失灵。

本章聚焦 Harness（智能体外壳）中最核心、也最容易被低估的一环：**上下文工程（Context Engineering）** 与它背后的**压缩流水线（Compaction Pipeline）**。

> 🎯 **一句话结论**：在长时程（long-horizon）任务里，**"管好上下文"比"换更强的模型"往往更能提升成功率**。上下文是 Harness 真正意义上的**第一性资源**——它不是"越多越好"，而是"越准越好"。

本章你将学到：

- 为什么上下文变长会**主动伤害**性能（context rot）；
- Anthropic 提出的上下文工程目标函数；
- 生产级五种上下文策略（机制 / 代码 / 场景 / 代价）；
- Claude Code 的五层压缩流水线（逐层拆解）；
- prompt cache 与压缩之间的**根本冲突**及应对；
- ACON 研究：为什么"保留推理、丢弃原始输出"是正解；
- 渐进式披露（Progressive Disclosure）；
- 可直接落地的 LangChain v1 实现代码。

> 📚 **前置阅读**：建议先读 [3.1 LangChain v1 核心组件](../03-langchain/01-core-components.md)（了解 `create_agent` 与 Middleware），以及 [2.4 记忆机制](../02-fundamentals/04-memory.md)（了解会话状态）。

---

## 一、上下文腐化（Context Rot）：越多≠越好

### 1.1 一个反直觉的发现

长期以来我们默认"上下文窗口越大越好"。但自 2023 年斯坦福的 **"Lost in the Middle"** 研究起，一个结论被反复验证：

> 当**关键信息位于上下文的中间段**时，模型的检索与推理表现会显著下降——**降幅可达 30% 以上**，形成一条两头高、中间低的"U 形曲线"。

2025 年 Chroma 团队发布的 **Context Rot（上下文腐化）** 报告与之一致：**即使任务所需的全部信息都在窗口内、模型也"看得到"，只要上下文变长，性能依然会退化。** 换句话说，这不是"窗口不够大"的问题，而是"注意力被稀释"的问题。

```text
性能
 ▲
 │  ●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●       ← 信息在开头 / 结尾：表现好
 │   ╲                                ╱
 │    ╲                              ╱
 │     ╲____________________________╱
 │         ── 信息在"中段" ──             ← 中段：注意力衰减，性能下降 30%+
 └──────────────────────────────────────────▶ 关键信息在上下文中的位置
   开头            中间            结尾
```

### 1.2 为什么"百万 token 窗口"也没能救场

一个常见误解是："等 1M / 10M token 窗口普及了，就不用压缩了。" 现实恰恰相反：

| 现象 | 说明 |
|------|------|
| **注意力预算有限** | Transformer 的注意力是**软性**的，token 越多，单个 token 分到的"注意力权重"越薄 |
| **指令遵循退化** | 上下文越长，模型对"不要做 X"这类约束的遵守程度**单调下降** |
| **噪声占比上升** | 冗余的工具输出、重复的日志会**挤占**真正高信号的信息 |
| **成本与延迟** | 每轮都要重算超长上下文，token 费用与首字延迟（TTFT）线性甚至二次上升 |

> 💡 **Harness 视角**：上下文窗口是"内存"，但**内存不等于缓存**。把所有东西都塞进窗口，就像把所有变量都放在全局作用域——能跑，但脆弱、昂贵、难维护。

---

## 二、第一性原理：最小的高信号 token 集

Anthropic 在其上下文工程（Effective Context Engineering）文章中给出了一个堪称"目标函数"的定义：

> **上下文工程的目标 = 找到最小的一组高信号 token（the smallest set of high-signal tokens），把达成期望结果的概率最大化。**

把它写成一个优化问题：

```text
        maximize   P(达成期望结果 | context)
        subject to  |context| ≤ 窗口上限
                    info_signal(context) / |context| 最大化   ← 信噪比
```

这句话带来的三个实操推论：

| 推论 | 含义 | 反例（常见错误） |
|------|------|------------------|
| **信噪比优先** | 宁要 10 条高信号，不要 1000 条中信号 | 把整个仓库塞进 prompt |
| **按需加载** | 先给"目录"，需要时再取"正文" | 一开始就读入所有文件全文 |
| **可回收** | 压缩前先确保信息**没有被真正删除** | 直接丢弃工具输出，事后无法复原 |

> 🧭 记住这个心智模型：**上下文不是"仓库"，而是"工作台（workbench）"**。工作台上只放"此刻要用"的东西，其余的按索引去取。

---

## 三、生产级五种上下文策略

下面五种策略几乎是当今所有生产级 Agent（Claude Code、Cursor、Devin、Junie、Aider…）的公共配方。每种都给出：**机制 → 代码 → 适用场景 → 代价**。

### 3.1 策略总览

| # | 策略 | 核心动作 | 触发动机 | 主要代价 |
|---|------|----------|----------|----------|
| 1 | **压缩 Compaction** | 接近上限时把历史总结成摘要 | token 用量阈值 | 细节丢失、需重读 |
| 2 | **观察屏蔽 Observation Masking** | 隐藏旧工具输出，保留工具调用 | 工具输出膨胀 | 模型需重跑工具 |
| 3 | **即时检索 JIT** | 只存标识符，用时动态加载 | 大文件/大仓库 | 增加往返轮次 |
| 4 | **子 Agent 委派** | 子 Agent 探索，回传浓缩结论 | 搜索爆炸 | 委派开销、信息损失 |
| 5 | **结构化笔记** | 显式维护进度文件/草稿本 | 长任务跨压缩 | 需模型自律维护 |

### 3.2 策略一：压缩（Compaction）

**机制**：当对话接近上下文上限时，调用一次 LLM 把"较早的历史"总结为一段**结构化摘要**，并用摘要替换原始消息。Claude Code 的做法具有代表性：**保留架构决策与未解决的 bug，丢弃冗余的工具输出**。

```python
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain.chat_models import init_chat_model

model = init_chat_model("gpt-5.5", model_provider="openai")

agent = create_agent(
    model=model,
    tools=[search_web, read_file, run_shell],
    middleware=[
        # 接近上限时自动总结；保留最近一段原文不压缩
        SummarizationMiddleware(
            model=model,
            trigger={"tokens": 120_000},   # 达到阈值触发压缩
            keep={"tokens": 20_000},       # 最近 2 万 token 保留原文
            # 具体参数名以官方文档为准
        ),
    ],
    system_prompt="你是一名软件工程 Agent，优先保留架构决策与未解决 bug。",
)
```

- **适用场景**：长对话、长任务、需要跨小时/跨天延续的工作。
- **代价**：摘要是一次"有损压缩"，被丢掉的细节若再次需要，必须**重新读取原始来源**。因此**摘要必须保留"指针"**（文件路径、命令、ID），而不仅是结论。

### 3.3 策略二：观察屏蔽（Observation Masking）

**机制**：JetBrains 的 Junie 采用的做法是——**隐藏旧的工具输出（observation），但保留工具调用（tool call）本身可见**。这样模型仍知道"我调用过什么"，但不必反复阅读巨大的原始返回。

```python
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage


class ObservationMaskingMiddleware(AgentMiddleware):
    """隐藏较早的工具输出，但保留工具调用的"存在感"。

    注意：这只是"投影到模型看到的消息"，
    底层完整结果仍应保存在持久化状态中，以便模型重新调用工具取回。
    """

    def __init__(self, keep_last: int = 2):
        super().__init__()
        self.keep_last = keep_last

    def before_model(self, state, runtime):
        messages = state["messages"]
        tool_positions = [
            i for i, m in enumerate(messages) if isinstance(m, ToolMessage)
        ]
        # 工具输出还不够多，不需要屏蔽
        if len(tool_positions) <= self.keep_last:
            return None

        keep = set(tool_positions[-self.keep_last:])
        masked = []
        for i, m in enumerate(messages):
            if isinstance(m, ToolMessage) and i not in keep:
                masked.append(
                    ToolMessage(
                        content="[旧工具输出已省略；如需该信息请重新调用对应工具]",
                        tool_call_id=m.tool_call_id,
                    )
                )
            else:
                masked.append(m)
        return {"messages": masked}
```

- **适用场景**：工具返回体积大（网页、日志、数据表）、需要多轮迭代的 Agent。
- **代价**：模型可能"忘记"已获得的事实，导致**重复调用工具**；需配合"已获取事实清单"缓解。

### 3.4 策略三：即时检索（Just-in-Time, JIT）

**机制**：不把"全部内容"放进来，而是**只放轻量标识符（路径、ID、URL、符号名）**，需要时再**动态加载**。用类 Unix 的 `grep` / `glob` / `head` / `tail` 做**渐进式取用**，而不是一次性整文件读入。

```text
❌ 一次性读入（浪费）                ✅ JIT 渐进取用（省 token）
─────────────────────────            ─────────────────────────
read_file("big_module.py")           glob("src/**/*.py")        → 拿到文件清单
  → 8000 行直接进窗口                grep("def handle_", paths)  → 定位目标函数
                                     read_file(path, 120, 160)   → 只读那 40 行
```

| 手法 | 命令/工具 | 用途 |
|------|-----------|------|
| 找文件 | `glob` | 先拿"地图"，不读正文 |
| 找符号 | `grep` | 定位到具体行号 |
| 看上下文 | `head` / `tail` / 区间读 | 只取需要的片段 |
| 看结构 | 目录树 / 大纲 | 理解骨架而非血肉 |

- **适用场景**：大型代码库、超长文档、数据库探索。
- **代价**：增加**工具往返轮次**；若 Agent 检索能力弱，可能"找不到"而反复试错。Claude Code 大量依赖此模式，因此它把 `grep` 与 `glob` 做成了**一等公民工具**。

### 3.5 策略四：子 Agent 委派（Sub-agent Delegation）

**机制**：主 Agent 遇到"需要大量探索"的子问题时，**派生一个子 Agent** 去"脏活累活"（搜索、试错、海量读文件），子 Agent 只把 **1000–2000 token 的浓缩总结** 回传给主 Agent。

```text
              ┌─────────────────────────────┐
              │        主 Agent              │
              │  context 保持"干净"          │
              └───────────────┬─────────────┘
                    派发任务  │  回传 ◀── 1000~2000 token 浓缩总结
                              ▼
              ┌─────────────────────────────┐
              │  子 Agent（独立 context）     │
              │  大量 grep / 读文件 / 试错    │
              │  消耗的是"它自己的"窗口       │
              └─────────────────────────────┘
```

> 🔑 **关键点**：子 Agent 的价值不在于"并行"，而在于**上下文隔离（context isolation）**——把探索产生的"噪声"留在子 Agent 的窗口里，只把"信号"带回主线程。

- **适用场景**：大型调研、跨模块改造、根因排查。
- **代价**：委派本身有开销；摘要若不到位，主 Agent 会"两眼一抹黑"，需要设计清晰的**回传格式**（结论 / 证据 / 阻塞点）。

### 3.6 策略五：结构化笔记 / 进度文件

**机制**：让 Agent 主动维护一个**外部化的"草稿本"**（NOTES.md、progress.md、todo.md）。它既是给"压缩后的自己"留下的备忘，也是给"人类协作者"的交付物。

```python
# scratchpad.py —— 进度文件（结构化笔记）模式
from pathlib import Path
from langchain.tools import tool

SCRATCH = Path("./agent_scratchpad.md")


@tool
def update_progress(note: str) -> str:
    """把当前进展追加到进度文件，用于跨压缩保留关键上下文。"""
    with SCRATCH.open("a", encoding="utf-8") as f:
        f.write(f"- {note}\n")
    return "已记录到进度文件"


@tool
def read_progress() -> str:
    """读取进度文件；压缩发生后可用于恢复关键决策与未完成事项。"""
    if not SCRATCH.exists():
        return "(进度文件为空)"
    return SCRATCH.read_text(encoding="utf-8")
```

| 写到笔记里的东西 | 不要写进去的东西 |
|------------------|------------------|
| 已确认的架构决策 | 冗长的工具原始输出 |
| 未解决的 bug / 阻塞点 | 可随时重查的公开文档 |
| 下一步计划、待验证假设 | 已经作废的中间尝试（除结论外） |
| 关键文件路径与命令 | 大段复制粘贴的代码 |

- **适用场景**：跨小时/跨天的长任务、压缩频繁发生的场景。
- **代价**：需要模型**自律**维护；可通过 `Stop`/`after_agent` 钩子强制落盘（见 [9.4 权限与护栏](04-permissions-sandbox.md)）。

---

## 四、Claude Code 的五层压缩流水线

Claude Code 之所以能在"超长会话"中保持可用，靠的不是单一机制，而是一套**分层、由轻到重**的压缩流水线。下面逐层拆解（社区逆向分析 + 官方分享的综合模型，**具体实现细节以官方文档为准**）。

```text
                    Claude Code 上下文压缩流水线
    ┌───────────────────────────────────────────────────────────┐
    │ Layer 1  Budget Reduction   —— 截断展示，不删原始数据        │
    │ Layer 2  工具结果清理        —— 清理/精简工具输出            │
    │ Layer 3  Microcompact       —— 优先压缩"靠后"内容，保护前缀  │
    │ Layer 4  Context Collapse   —— 生成"只读投影"，可 /rewind    │
    │ Layer 5  Auto-compact       —— 约 50% 触发，全局摘要         │
    └───────────────────────────────────────────────────────────┘
         ▲ 越往上越轻、越频繁、越不破坏信息
         ▼ 越往下越重、越少见、信息损失越大
```

### 4.1 Layer 1：Budget Reduction（预算削减）

**做法**：当某条工具结果特别大时，**截断显示**给模型的部分，但**原始结果仍写入本地 JSONL 日志**。

> 🔑 **精髓在于"截断 ≠ 删除"**：模型看到的是"前 N 行 + …（已截断）"，而完整内容仍在磁盘上。模型若需要更多，可以**再次用 `read` 工具**按区间取回。

| 维度 | 说明 |
|------|------|
| 触发 | 单条工具输出超过阈值（如几千行） |
| 动作 | 只把头部/尾部投影给模型 |
| 可逆性 | ✅ 高（原始结果仍可读） |
| 风险 | 模型误以为"输出就这么短" |

### 4.2 Layer 2：工具结果清理（Tool Result Cleanup）

**做法**：对"已经用完"的工具结果做清理或精简——典型如把大段日志折叠成统计摘要、把重复的目录列表去重。它比 Layer 1 更主动，但通常**不改变工具调用的存在**。

- 与策略二"观察屏蔽"同源，但发生在**流水线内部**而非提示词层。

### 4.3 Layer 3：Microcompact（微压缩）

**做法**：**优先压缩"靠后"的内容**，刻意保护"靠前"的前缀。

> 🎯 **为什么要保护前缀？** 因为 **prompt cache** 是**前缀匹配**的（见第五节）。前缀一旦改变，整个缓存的 KV 都要**重算**，成本骤增。因此压缩要**从后往前**——只动尾部，前缀保持不变，缓存仍可命中。

| 对比 | 破坏前缀的压缩 | 保护前缀的压缩（Microcompact） |
|------|----------------|-------------------------------|
| 缓存 | 前缀变了 → **全量重算** | 前缀不变 → **复用命中** |
| 成本 | 高（每轮都像"冷启动"） | 低 |
| 做法 | 从头改写历史 | 只压靠后段落 |

### 4.4 Layer 4：Context Collapse（上下文折叠）

**做法**：生成一份"**只读投影（read-only projection）**"——**不改动底层 JSONL**，只是在"模型看到的世界"里把长历史折叠成更短的表示。

> 🔑 **关键特性**：因为**底层数据未被修改**，用户可以用 `/rewind`（回退）回到折叠前的状态。这是一种"**视图层压缩**"——类似数据库的**物化视图**，底层数据仍在。

| 维度 | 说明 |
|------|------|
| 本质 | 视图层（view-level）压缩，而非数据层 |
| 可逆性 | ✅ 高（`/rewind` 可回到折叠前） |
| 代价 | 实现复杂，需要区分"投影"与"真源" |

### 4.5 Layer 5：Auto-compact（自动压缩）

**做法**：当上下文使用量达到**约 50%** 时，触发全局自动压缩，把历史总结成一段摘要。这是**最重**的一层，信息损失也最大。

> ⚠️ **必须知道的副作用**：Auto-compact 之后，**path-scoped rules（按路径生效的规则）与子目录里的 `CLAUDE.md` 会"丢失"**——因为它们不在摘要里。
>
> **两条缓解措施**：
> 1. 把**关键规则放到项目根目录的 `CLAUDE.md`**（根级内容通常更早、更稳定地被保留）；
> 2. 用 **`/compact focus on XXX`** 显式告诉它"压缩时重点保留 XXX"。

| Layer | 动作 | 可逆性 | 触发频率 | 主要风险 |
|-------|------|--------|----------|----------|
| 1 Budget Reduction | 截断展示 | 高 | 高 | 误以为输出短 |
| 2 工具结果清理 | 精简输出 | 中 | 中 | 细节丢失 |
| 3 Microcompact | 压靠后内容 | 中 | 中 | 尾部信息损失 |
| 4 Context Collapse | 只读投影 | 高 | 中 | 实现复杂 |
| 5 Auto-compact | 全局摘要 | 低 | ~50% 触发 | 规则/子目录记忆丢失 |

---

## 五、Prompt Cache 与压缩的根本冲突

### 5.1 为什么这是一个"架构级"问题

**Prompt cache（提示缓存）** 的命中条件是：**从第一个 token 开始的前缀必须逐字节一致**。一旦你在历史**中间**插入、删除或改写内容，缓存前缀被破坏，**整个上下文的 KV 需要重新计算**。

```text
命中缓存（理想）：                      破坏前缀（灾难）：
┌──────────────────────┐               ┌──────────────────────┐
│ [系统提示][历史 1..K] │ ← 不变         │ [系统提示][历史 1..K']│ ← 改了历史 3
│ [本轮新增]            │                │ [本轮新增]            │
└──────────────────────┘               └──────────────────────┘
   ✅ 复用 KV，省钱省时                    ❌ 全量重算，成本飙升
```

### 5.2 由此推出的三条工程原则

| 原则 | 说明 |
|------|------|
| **追加优先（Append-only）** | 尽量只在**尾部追加**新消息，不改写历史 |
| **从后往前压缩** | 压缩只动"尾部"，保护稳定前缀（对应 Layer 3 Microcompact） |
| **稳定内容前置** | 系统提示、工具定义、稳定规则放在**最前**且**不轻易变动** |

> ⚠️ **隐蔽陷阱**：动态注入"当前时间""随机 ID"到系统提示里，会**每轮都破坏前缀缓存**。正确做法是把这类易变信息放到**消息尾部**，或使用结构化字段而非拼接进系统提示。

---

## 六、ACON：保留推理、丢弃原始输出

**ACON**（Agent Context Optimization）的研究给出了一个与直觉相悖但非常有用的结论：

> 在压缩 Agent 的上下文时，**优先保留"推理轨迹（reasoning traces）"，优先丢弃"原始工具输出（raw tool outputs）"**，可在 **减少 26%–54% token** 的同时**保持 95%+ 的准确率**。

### 6.1 为什么"推理 > 原始输出"

| 内容类型 | 信息密度 | 可重新获取性 | 压缩优先级 |
|----------|----------|--------------|------------|
| **推理轨迹**（为什么这么做） | 高 | ❌ 不可重得 | **保留（高）** |
| **决策与结论** | 高 | ❌ 不可重得 | **保留（高）** |
| **原始工具输出**（网站原文/日志） | 低 | ✅ 可重新调用 | **丢弃（低）** |
| 寒暄、重复确认 | 极低 | — | 丢弃 |

```text
压缩前（3200 token）                         压缩后（900 token，−72%）
┌──────────────────────────────────────┐   ┌────────────────────────────┐
│ 工具原始输出：网页全文 2000 token      │   │ 推理：需要先确认版本兼容性   │
│ 推理：应该先确认版本兼容性             │   │ 结论：v1 用 create_agent    │
│ 工具原始输出：文档全文 900 token       │   │ 证据指针：docs/…（可重取）  │
│ 推理：因此应改用 create_agent          │   └────────────────────────────┘
└──────────────────────────────────────┘
```

> 💡 **落地启示**：压缩时**不要把推理过程一起抹掉**。很多"暴力摘要"把"为什么"和"做了什么"一起压成一句话，反而让 Agent 丢掉"意图"，后续行为变得盲目。

---

## 七、渐进式披露（Progressive Disclosure）

**渐进式披露**：**先披露"元信息/入口"，在需要时再层层展开细节**——这与 JIT 检索同源，但更强调"**接口设计**"。

在这一模式中，**Skills（技能）就是按需加载的典型**：Agent 一开始只看到技能的**名称与一句话描述**（≈目录），只有当任务真的用得上时，才把技能的**完整指令与资源**加载进来。

```text
Tier 0（常驻，极小）: 技能名 + 描述      →  "pdf-processing: 处理 PDF 文件"
        │  需要时
        ▼
Tier 1（按需）      : 技能正文指令       →  具体步骤、约束、示例
        │  再需要时
        ▼
Tier 2（更深）      : 引用脚本/模板/数据  →  tools/*.py、templates/*.md
```

| 层级 | 内容 | 何时加载 | token 成本 |
|------|------|----------|-----------|
| 元信息 | 名称 + 一句描述 | 始终 | 极低 |
| 指令 | 技能主体说明 | 命中任务时 | 中 |
| 资源 | 脚本、模板、样例 | 真正执行时 | 高（但可执行而非"阅读"） |

> 🔗 **延伸**：MCP 的 `tools/list` **可缓存**（携带 `ttlMs`/`cacheScope`）也是同一思路——先把"能力目录"缓存住，避免每轮重复拉取（见 [8.10 MCP 协议](../08-ecosystem/protocols/01-mcp.md)）。

---

## 八、实战代码

### 8.1 组合式上下文中间件（压缩 + 手动裁剪）

`SummarizationMiddleware` 负责"自动压缩"，`trim_messages` 负责"精确控制窗口内保留哪些消息"，两者可叠加使用。

```python
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain.chat_models import init_chat_model
from langchain.messages import trim_messages   # v1 重导出；亦可从 langchain_core.messages 导入


def build_agent(model, tools):
    def prepare_messages(state):
        # 强制保留系统消息，从"人类消息"开始裁剪，避免把 tool_call 切断
        return trim_messages(
            state["messages"],
            max_tokens=8_000,
            strategy="last",          # 优先保留最近的消息
            token_counter=model,
            include_system=True,
            start_on="human",
        )

    # 说明：不同版本的中间件钩子名称可能不同，具体以官方文档为准
    agent = create_agent(
        model=model,
        tools=tools,
        middleware=[
            SummarizationMiddleware(
                model=model,
                trigger={"tokens": 80_000},
                keep={"tokens": 12_000},
            ),
        ],
    )
    return agent


model = init_chat_model("gpt-5.5", model_provider="openai")
agent = build_agent(model, tools=[read_file, run_shell])
```

> 📌 **裁剪的坑**：裁剪时必须以 `start_on="human"` 之类的边界开始，**否则会把 `tool_call` 与对应的 `ToolMessage` 拆开**，导致模型收到"孤儿工具结果"而报错。

### 8.2 观察屏蔽 + 进度文件（完整可运行骨架）

把"屏蔽旧观察"和"结构化笔记"组合，形成最实用的长任务上下文方案。

```python
from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langchain_core.messages import ToolMessage

SCRATCH = Path("./agent_scratchpad.md")


class ObservationMaskingMiddleware(AgentMiddleware):
    """保留最近 keep_last 个工具输出，其余替换为可重取的占位符。"""

    def __init__(self, keep_last: int = 3):
        super().__init__()
        self.keep_last = keep_last

    def before_model(self, state, runtime):
        msgs = state["messages"]
        positions = [i for i, m in enumerate(msgs) if isinstance(m, ToolMessage)]
        if len(positions) <= self.keep_last:
            return None
        keep = set(positions[-self.keep_last:])
        out = [
            ToolMessage(
                content="[已省略，如需请重新调用工具]",
                tool_call_id=m.tool_call_id,
            )
            if isinstance(m, ToolMessage) and i not in keep
            else m
            for i, m in enumerate(msgs)
        ]
        return {"messages": out}


@tool
def update_progress(note: str) -> str:
    """追加一条进展到草稿本（跨压缩保留关键决策）。"""
    with SCRATCH.open("a", encoding="utf-8") as f:
        f.write(f"- {note}\n")
    return "ok"


@tool
def read_progress() -> str:
    """读取草稿本；压缩后恢复到关键上下文。"""
    return SCRATCH.read_text(encoding="utf-8") if SCRATCH.exists() else "(空)"


model = init_chat_model("gpt-5.5", model_provider="openai")

agent = create_agent(
    model=model,
    tools=[update_progress, read_progress, read_file],
    middleware=[ObservationMaskingMiddleware(keep_last=3)],
    system_prompt=(
        "你是长任务助手。每完成一个里程碑，调用 update_progress 记录。"
        "在开始新一轮工作前，若不确定上下文，先 read_progress 恢复关键决策。"
    ),
)
```

### 8.3 上下文预算监控（可观测性）

没有度量就没有优化。建议对每次模型调用的 token 做**埋点**，把"上下文是否在膨胀"变成可见指标。

```python
from langchain.agents.middleware import AgentMiddleware


class ContextBudgetMiddleware(AgentMiddleware):
    """粗略统计每次模型调用前的消息规模，用于观测上下文膨胀。"""

    def __init__(self, soft_limit_chars: int = 120_000):
        super().__init__()
        self.soft_limit = soft_limit_chars

    def before_model(self, state, runtime):
        chars = sum(len(str(m.content)) for m in state["messages"])
        ratio = chars / self.soft_limit
        if ratio >= 0.8:
            print(f"⚠️ 上下文接近预算：{chars} 字符（{ratio:.0%}）")
        else:
            print(f"🧭 上下文规模：{chars} 字符（{ratio:.0%}）")
        return None
```

> 💡 生产环境应把该指标接入 LangSmith / Langfuse（见 [7.3 可观测性](../07-deployment/03-monitoring.md)），并设置"上下文膨胀"告警。

---

## 九、策略选型与代价权衡

| 场景 | 首选策略 | 组合建议 |
|------|----------|----------|
| 长对话客服 | 压缩 Compaction | + 稳定前缀保缓存 |
| 代码库大规模改造 | JIT 检索 | + 子 Agent 委派 |
| 研究/调研型任务 | 子 Agent 委派 | + 结构化笔记 |
| 工具输出巨大（网页/日志） | 观察屏蔽 | + 重取占位符 |
| 跨天长任务 | 结构化笔记 | + Auto-compact 兜底 |
| 技能/工具繁多 | 渐进式披露 | + MCP 目录缓存 |

**"代价"总表**：

| 策略 | 省 token | 保真度 | 可逆性 | 实现复杂度 |
|------|---------|--------|--------|-----------|
| 压缩 | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | 低（内置） |
| 观察屏蔽 | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | 低 |
| JIT 检索 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 中 |
| 子 Agent 委派 | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | 高 |
| 结构化笔记 | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 低 |

---

## 本章小结

| 要点 | 说明 |
|------|------|
| 🧠 **Context Rot** | 关键信息落在中段时性能下降 30%+；窗口变大≠问题消失 |
| 🎯 **目标函数** | 找到最小的高信号 token 集，最大化达成期望结果的概率 |
| 🗜️ **五策略** | 压缩 / 观察屏蔽 / JIT / 子 Agent / 结构化笔记 |
| 🪜 **五层流水线** | Budget Reduction → 工具清理 → Microcompact → Context Collapse → Auto-compact |
| 🔒 **保留前缀** | prompt cache 前缀匹配，压缩要"从后往前" |
| 📉 **ACON** | 保留推理轨迹、丢弃原始输出，省 26%–54% token 且保 95%+ 准确率 |
| 🪟 **渐进式披露** | 先给目录，按需展开；Skills 是典型实现 |
| ⚠️ **Auto-compact 副作用** | path-scoped rules 与子目录 CLAUDE.md 会丢失，需根级规则或 `/compact focus on` |

---

## 📝 课后练习

1. **✅ 基础**：为你的 Agent 加上 `SummarizationMiddleware`，构造一段 200 轮的对话，观察何时触发压缩、摘要是否保留了关键决策。
2. **💡 进阶**：实现一个 `ObservationMaskingMiddleware`，对比"全量保留"与"屏蔽旧输出"两种模式下同类任务的 token 消耗与成功率。
3. **🚀 挑战**：实现"JIT 检索"版代码阅读 Agent——只允许 `glob` / `grep` / 区间 `read`，禁止整文件读入，测量平均 token 降幅。
4. **🔍 探索**：搭建一个"上下文预算看板"，把每轮的上下文规模与任务成功率画在同一张图上，找出你的场景的"性能拐点"。

---

> 🔗 **下一步**：上下文管好了，接下来要给 Agent 的"双手"上锁——请阅读 [9.4 权限、护栏与沙箱](04-permissions-sandbox.md)。
