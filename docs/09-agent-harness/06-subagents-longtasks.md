# 9.6 子 Agent 编排与长时任务 —— 突破上下文窗口的边界

## 📖 导读

> **子 Agent 是上下文的防火墙。**
>
> 一个子 Agent 可以读 30 个文件、跑 50 次搜索，然后把**结论压缩成 1,000–2,000 token** 交回主 Agent——主 Agent 的上下文因此始终保持在高信号状态。

本章解决 Harness 最大的工程难题：**当任务远超单个上下文窗口时，怎么办？**

---

## 一、为什么需要子 Agent

### 1.1 上下文是稀缺资源

回顾 [9.3](03-context-engineering.md)：模型性能随上下文长度增长而**下降**（Chroma 研究；"Lost in the Middle"）。

```text
❌ 单体 Agent 探索一个陌生代码库：
   读 30 个文件 → 上下文 12 万 token → 关键信息淹没在噪声里 → 决策质量下降

✅ 子 Agent 探索：
   主 Agent 派出 Subagent("搞清楚鉴权模块怎么工作的")
   Subagent 读 30 个文件（消耗 12 万 token）
   Subagent 只回传 800 token 的结论
   主 Agent 上下文只增加 800 token，决策质量不降
```

### 1.2 子 Agent 的三种用途

| 用途 | 说明 | 代表 |
|------|------|------|
| **上下文隔离** | 让"脏活"在子 Agent 里做完，只回传结论 | 代码库探索、日志分析 |
| **专业化** | 每个子 Agent 有专属提示词与工具集 | 规划者 / 执行者 / 评审者 |
| **并行加速** | 多个独立子任务同时跑 | 多文件重构、多源研究 |

---

## 二、Claude Code 的三种执行模型

这是目前最成熟的工程实现，值得作为设计参考。

| 模型 | 机制 | 隔离级别 | 适用场景 |
|------|------|:--------:|----------|
| **Fork** | 父上下文的**字节级副本** | 低（共享历史） | 需要完整上下文的分支探索（"如果用另一种方案会怎样？"） |
| **Teammate** | 独立终端 pane，通过**基于文件的邮箱**通信 | 中 | 长期并行的多个 Agent 互相协作 |
| **Worktree** | 每个 agent 拥有自己的 **git worktree** 与隔离分支 | **高**（文件系统隔离） | 并行改代码不冲突；可独立提交、独立回滚 |

### 2.1 Fork：复制而不是共享

```text
主 Agent 上下文：[system][task][探索 A][探索 B][探索 C]
                                 │
                         Fork ───┴─── Fork
                         │             │
              字节级副本（含全部历史）  字节级副本
                         │             │
                    尝试方案 1      尝试方案 2
                         │             │
                    返回结论 A      返回结论 B
```

**优点**：子 Agent 拥有完整上下文，不需要重复探索。**缺点**：每个 Fork 都复制全部 token，成本高。

### 2.2 Teammate：文件邮箱通信

```text
┌─────────────┐   inbox/     ┌─────────────┐
│  Teammate A │ ───────────▶ │  Teammate B │
│  (pane 1)   │ ◀─────────── │  (pane 2)   │
└─────────────┘   files      └─────────────┘
```

**为什么用文件而不是内存队列？** 因为**文件天然持久化**——进程崩溃后消息还在，符合 Harness 的"状态可恢复"原则（回看 [9.2 状态管理](02-anatomy.md)）。

```python
"""基于文件的邮箱（简化实现）"""
import json
from pathlib import Path


class FileMailbox:
    def __init__(self, root: Path, agent_id: str):
        self.root = root / "mailbox" / agent_id
        self.root.mkdir(parents=True, exist_ok=True)

    def send(self, to: str, payload: dict) -> None:
        target = self.root.parent / to
        target.mkdir(parents=True, exist_ok=True)
        msg_id = f"{time.time_ns()}.json"
        (target / msg_id).write_text(json.dumps(payload, ensure_ascii=False))

    def receive(self) -> list[dict]:
        msgs = []
        for f in sorted(self.root.glob("*.json")):
            msgs.append(json.loads(f.read_text()))
            f.unlink()                      # 读后即删（at-least-once）
        return msgs
```

### 2.3 Worktree：文件系统级隔离

```bash
# 为每个子 Agent 创建独立的 git worktree
git worktree add ../wt-feature-a -b feature-a
git worktree add ../wt-feature-b -b feature-b
```

| 优势 | 说明 |
|------|------|
| **文件不冲突** | 每个 Agent 在自己的目录里改 |
| **可独立回滚** | 某个分支搞砸了，直接丢弃 worktree |
| **可独立评审** | 每个分支单独提 PR |
| **人类可介入** | 直接 `cd` 进去看 |

> 💡 这是"并行改代码"目前最干净的方案——**用 git 的能力，而不是自己造隔离机制**。

---

## 三、其他框架的子 Agent 实现

| 框架 | 机制 | 特点 |
|------|------|------|
| **OpenAI Agents SDK** | `agents-as-tools`（专家处理**受限子任务**，控制权仍在主 Agent）<br>`handoffs`（专家**接管全部控制权**，主 Agent 退出） | 两种模式语义清晰，按"是否交权"选择 |
| **LangGraph** | subagent 实现为**嵌套状态图**；或用 `Send` 做 fan-out | 精细可控，可持久化 |
| **CrewAI** | Agent（role/goal/backstory/tools）+ Task + Crew；**Flows 层**负责路由与校验 | "**确定性骨干 + 局部智能**" |
| **Microsoft Agent Framework** | 五种编排模式：顺序、并发（fan-out/fan-in）、群聊、handoff、**magentic**（manager 维护动态任务 ledger） | 覆盖最全 |

### 3.1 agents-as-tools vs handoffs

```python
# 模式 A：agents-as-tools —— 主 Agent 保持控制权
#   主 Agent: "让专家算一下" → 专家返回 → 主 Agent 决定下一步
#   适合：主 Agent 需要多次调用专家、汇总多份结果

# 模式 B：handoffs —— 交权给专家
#   主 Agent: "这是退款问题，交给退款专家" → 自己退出
#   适合：明确的分诊场景（客服分流）
```

---

## 四、跨上下文窗口的长时任务

这是 Harness 最硬核的部分：**任务需要跑几十轮、跨越多个上下文窗口**。

### 4.1 Claude Code 的"Ralph Loop"

**问题**：模型接近上下文极限时会**提前收尾**（Anthropic 称之为 **Context Anxiety，上下文焦虑**，在 Sonnet 4.5 上尤其明显）。

**Ralph Loop 的解法**：拦截模型的"退出"意图，**重注入提示词，强制在新的上下文窗口中继续**。

```python
def ralph_loop(task: str, progress_file: Path, max_windows: int = 10):
    """跨上下文窗口持续推进，直到任务真正完成"""
    for window in range(max_windows):
        # 每个窗口都是全新的、干净的上下文
        result = run_agent(
            system=CLEAN_SYSTEM_PROMPT,
            task=task,
            context_files=[progress_file],   # ← 唯一跨窗口的连续性载体
        )

        progress = read_progress(progress_file)
        if progress.get("all_done"):
            return f"✅ 在第 {window + 1} 个窗口完成"

        # 拦截退出：把"继续"重新注入
        task = (
            f"上一轮已完成：{progress['completed']}\n"
            f"尚未完成：{progress['remaining']}\n"
            "请继续完成下一个最高优先级的未完成项。"
        )
    return "❌ 达到窗口上限"
```

### 4.2 Initializer + Coding 双 Agent 模式（Anthropic 官方方案）

这是目前最被推荐的**长时应用开发**架构：

```text
第 1 个会话（Initializer Agent）—— 只做一次，搭建"可恢复的环境"
├── 写 init.sh                （环境初始化脚本，幂等）
├── 写 claude-progress.txt    （进度文件 / 结构化草稿本）
├── 写 feature-list.json      （特性清单，标注完成状态）
└── 初始 git commit           （建立基线）

第 2..N 个会话（Coding Agent）—— 每次都是全新上下文
├── ① 读 git log + 进度文件，自我定位"我在哪"
├── ② 从 feature-list 挑最高优先级的未完成项
├── ③ 实现它
├── ④ 跑验证（测试 / 构建）
├── ⑤ git commit
└── ⑥ 更新进度文件与 feature-list
```

> 🔑 **核心洞察**：**文件系统充当跨上下文窗口的连续性载体。**
>
> 上下文窗口会被清空，但**磁盘上的文件不会**。所以 Harness 的关键设计是：**把"记忆"放在文件系统里，而不是放在对话历史里。**

### 4.3 医院交接班的类比

```
医生交接班：
  ❌ "你自己看看病历"                    ← 不可靠
  ✅ "3 号床病人，昨天做了 X，今天要注意 Y，下一步计划是 Z"  ← 结构化交接
```

**结构化交接三要素**：

| 要素 | 对应文件 |
|------|----------|
| **明确状态**（现在到哪了） | `progress.md` |
| **已完成**（做过什么、为什么这么做） | `git log` + `DECISIONS.md` |
| **清晰下一步**（接下来干什么） | `feature-list.json` 中最高优先级项 |

### 4.4 完整实现：可恢复的长任务 Harness

```python
"""long_task.py —— 用文件系统承载跨窗口连续性"""
import json
import subprocess
from pathlib import Path


class ProgressStore:
    """进度即状态：所有跨窗口信息都落盘"""

    def __init__(self, root: Path):
        self.root = root
        self.progress = root / "progress.md"
        self.features = root / "feature-list.json"

    def init(self, task: str, features: list[str]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.features.write_text(json.dumps(
            [{"name": f, "status": "todo"} for f in features],
            ensure_ascii=False, indent=2))
        self.progress.write_text(f"# 任务\n{task}\n\n# 日志\n")

    def load(self) -> dict:
        return json.loads(self.features.read_text())

    def next_todo(self) -> str | None:
        for f in self.load():
            if f["status"] == "todo":
                return f["name"]
        return None

    def complete(self, name: str, note: str) -> None:
        items = self.load()
        for f in items:
            if f["name"] == name:
                f["status"] = "done"
        self.features.write_text(json.dumps(items, ensure_ascii=False, indent=2))
        with self.progress.open("a") as fp:
            fp.write(f"\n## {name}\n{note}\n")

    def recent_git_log(self, n: int = 10) -> str:
        return subprocess.run(
            ["git", "log", f"-{n}", "--oneline"],
            cwd=self.root, capture_output=True, text=True,
        ).stdout


def run_session(agent, store: ProgressStore) -> bool:
    """一个上下文窗口内的完整工作循环"""
    # ① 自我定位（这是长任务最关键的一步）
    context = (
        f"## 最近的提交\n{store.recent_git_log()}\n\n"
        f"## 进度记录\n{store.progress.read_text()[-3000:]}\n\n"
        f"## 特性清单状态\n{json.dumps(store.load(), ensure_ascii=False)}"
    )

    # ② 挑最高优先级的未完成项
    todo = store.next_todo()
    if todo is None:
        return True

    # ③④⑤ 实现 → 验证 → 提交
    result = agent.invoke({"messages": [{"role": "user", "content":
        f"{context}\n\n请完成这一项：**{todo}**\n"
        "完成后必须跑测试；测试通过后 git commit 并更新进度文件。"}]})

    # 验证（复用 9.5 的 Stop Gate 思路）
    if not run_tests(store.root):
        return False

    store.complete(todo, result["messages"][-1].content[:1500])
    subprocess.run(["git", "add", "-A"], cwd=store.root)
    subprocess.run(["git", "commit", "-m", f"feat: {todo}"], cwd=store.root)
    return False                    # 还有活，开下一个窗口
```

---

## 五、LangGraph 实战：两种子 Agent 编排

### 5.1 嵌套子图（推荐，最可控）

```python
from langgraph.graph import StateGraph, START, END


# --- 子 Agent：研究员（自己的状态与工具集）---
def build_researcher():
    g = StateGraph(ResearchState)
    g.add_node("plan", plan_node)
    g.add_node("search", search_node)       # 只读工具
    g.add_node("summarize", summarize_node) # ← 关键：压缩成 800 token 回传
    g.add_edge(START, "plan")
    g.add_edge("plan", "search")
    g.add_edge("search", "summarize")
    g.add_edge("summarize", END)
    return g.compile()


# --- 主图：把子图当成一个节点 ---
main = StateGraph(MainState)
main.add_node("research", build_researcher())   # 子图作为节点
main.add_node("write", write_node)
main.add_edge(START, "research")
main.add_edge("research", "write")
main.add_edge("write", END)
app = main.compile(checkpointer=checkpointer)
```

**优点**：子 Agent 的中间过程**不会污染主图状态**，只有最终摘要回传。

### 5.2 `Send` API：动态 fan-out（并行子 Agent）

```python
from langgraph.types import Send


def dispatch(state: MainState):
    """根据任务动态派发 N 个并行子 Agent"""
    return [Send("worker", {"source": s, "topic": state["topic"]})
            for s in state["sources"]]        # sources 是运行时才知道的


builder.add_conditional_edges("plan", dispatch, ["worker"])
builder.add_edge("worker", "aggregate")       # fan-in：所有 worker 完成后汇总
```

```text
              ┌──▶ worker(source=1) ──┐
plan ──Send──┼──▶ worker(source=2) ──┼──▶ aggregate ──▶ END
              └──▶ worker(source=3) ──┘
                     （并行执行）
```

| 场景 | 用哪种 |
|------|--------|
| 子任务数量**固定** | 嵌套子图 |
| 子任务数量**运行时才知** | `Send` fan-out |
| 需要**地图/归约**式并行 | `Send` + 汇总节点 |

---

## 六、反模式与注意事项

### 6.1 先榨干单 Agent

> **Anthropic 与 OpenAI 一致建议：先把单 Agent 榨到极致。**

多 Agent 有明确的额外开销：

| 开销 | 说明 |
|------|------|
| **路由成本** | 每次分派都是一次额外 LLM 调用 |
| **上下文损失** | handoff 时子 Agent 不继承完整历史，可能丢失关键信息 |
| **协调复杂** | 需要设计终止条件，否则 Agent 之间会"无限对话" |
| **调试困难** | 跨 Agent 的因果链难追踪 |
| **成本放大** | N 个 Agent × M 轮 = N×M 次调用 |

**判断门槛**：

| 条件 | 建议 |
|------|------|
| 工具数 < 10，任务域单一 | ✅ 单 Agent |
| 工具数 >~10 且**高度重叠** | 考虑按领域拆分 |
| 任务域**明显可分**（前端/后端/测试） | 考虑多 Agent |
| 只是"想让效果更好" | ❌ 先优化单 Agent 的上下文与验证 |

### 6.2 其他坑

| 坑 | 后果 | 解法 |
|----|------|------|
| 子 Agent 回传原始输出 | 上下文照样爆炸 | **强制回传结构化的浓缩摘要**（限制 token 数） |
| 子 Agent 无预算 | 单个子 Agent 烧光预算 | 每个子 Agent 独立预算限额 |
| 没有终止条件 | 多 Agent 无限对话 | 轮次上限 + 预算上限 + 明确 done 条件 |
| 共享可变状态 | 竞态、状态污染 | 只在 fan-in 节点合并；子 Agent 状态隔离 |
| Fork 滥用 | token 成本线性膨胀 | Fork 只用于"必须完整上下文"的场景 |

---

## 七、本章总结

| 要点 | 说明 |
|------|------|
| **核心价值** | 子 Agent 是**上下文的防火墙**，只回传 1,000–2,000 token 结论 |
| **三种执行模型** | Fork（字节级副本）/ Teammate（文件邮箱）/ Worktree（git 隔离） |
| **两种交权语义** | agents-as-tools（保留控制权）vs handoffs（交权） |
| **长任务关键** | **文件系统充当跨上下文窗口的连续性载体** |
| **Ralph Loop** | 拦截退出、重注入提示、强制新窗口继续（对抗 Context Anxiety） |
| **双 Agent 模式** | Initializer（搭环境）+ Coding Agent（读 git log + 进度文件自我定位） |
| **LangGraph 实现** | 嵌套子图（数量固定）/ `Send` fan-out（数量动态） |
| **铁律** | **先榨干单 Agent**；仅当工具 >~10 且高度重叠、或任务域明显可分时才拆 |

---

## 📝 课后练习

1. **设计题**：为一个"给 50 个遗留文件补单元测试"的任务设计子 Agent 编排方案。你需要决定：用哪种执行模型？分几个子 Agent？如何避免它们互相冲突？如何汇总？
2. **实现题**：实现本章的 `ProgressStore`，并用它 + [9.8](08-build-your-harness.md) 的 mini-harness 跑一个"跨越 3 个上下文窗口"的任务，验证进度文件确实能让新会话"接上"上一会话。
3. **对比题**：分别用"嵌套子图"与"单体 Agent"完成同一个代码库探索任务，记录并对比：主 Agent 上下文 token 峰值、总 token 消耗、结论质量。
4. **思考题**：Ralph Loop 用"强制继续"对抗 Context Anxiety，但也可能让 Agent 在错误方向上越走越远。请设计一个**安全阀**：在什么条件下应当停止强制继续，转而请求人类介入？
