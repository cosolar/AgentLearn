# 9.5 验证循环 —— 区分玩具 Demo 与生产级 Agent 的那条线

## 📖 导读

> **Agent 说"我完成了"，你敢信吗？**
>
> Harness 的十二大模块里，[验证循环](02-anatomy.md)是**投入产出比最高**的一个。有团队仅靠加入结构化验证，就把任务完成率从 **83% 提升到 96%**。

[9.4](04-permissions-sandbox.md) 解决了"Agent 不能做什么"，本章解决另一半：**如何确认 Agent 做对了**。

---

## 一、为什么验证是最高 ROI 的模块

### 1.1 错误复合的数学

```
10 步流程，每步 99% 成功率：
  0.99^10 ≈ 90.4%      ← 看起来还行

20 步流程，每步 95% 成功率：
  0.95^20 ≈ 36%        ← 三分之二的任务会失败
```

模型越强，单步成功率越高，但**长任务的复合误差依然能把成功率拉垮**。验证循环的作用就是**在每一步之间插入"质量闸门"**，让错误暴露在变成灾难之前。

### 1.2 来自一线的数据

| 来源 | 结论 |
|------|------|
| **Claude Code 作者 Boris Cherny** | 给模型一个**自我验证的办法**，质量提升 **2–3 倍** |
| 企业实践（结构化验证） | 任务完成率 **83% → 96%** |
| HumanLayer | **Back-Pressure（背压）**：测试 / 构建 / 类型检查构成自我验证回路 |
| Martin Fowler 团队 | 验证闭环 = **安灯绳（Andon Cord）**：Lint → Review → UnitTest → E2E |

### 1.3 验证与"提示词祈祷"的区别

| 做法 | 机制 | 是否可靠 |
|------|------|:--------:|
| ❌ "请在完成前仔细检查你的工作" | 依赖模型自觉 | 不可靠 |
| ✅ "任务结束前必须跑 `npm test`，不通过就继续修" | **确定性 gate** | 可靠 |

> 🔑 **一句话**：**用机制强制质量，而不是用 prompt 请求质量**（[9.7](07-harness-engineering.md) 会展开这条原则）。

---

## 二、三条验证路径

Anthropic 推荐三条路径，各有擅长：

| 路径 | 手段 | 擅长发现 | 成本 | 可靠性 |
|------|------|----------|:----:|:------:|
| **① 基于规则的反馈** | 单元测试、lint、类型检查、构建、schema 校验 | 逻辑错误、类型错误、格式错误 | 低 | ⭐⭐⭐⭐⭐（确定性 ground truth） |
| **② 视觉反馈** | Playwright / 截图 / 像素比对 | UI 布局、样式错位、渲染异常 | 中 | ⭐⭐⭐⭐ |
| **③ LLM-as-judge** | 专门的评审 subagent | 语义问题：需求理解偏差、可读性差、遗漏边界 | 高 | ⭐⭐⭐（有主观性） |

### 2.1 组合策略（推荐）

```text
快速闸门（每次改动必跑，毫秒~秒级）
  └── lint + 类型检查 + 单元测试        ← 规则型，成本极低

阶段闸门（完成一个子任务后跑）
  └── 集成测试 / 构建                  ← 规则型

终局闸门（宣布完成前跑）
  ├── E2E / Playwright 截图            ← 视觉型
  └── 独立评审 subagent                ← 推理型，最贵
```

---

## 三、四档验证强度（从轻到重）

### 档位 1：内联验证（最轻量）

把验证要求写进系统提示词/AGENTS.md：

```markdown
## 完成标准（Definition of Done）
1. 修改代码前，先写一个能复现问题的失败测试
2. 修复后，运行 `pytest -q` 直到全部通过
3. 只有在测试通过后才允许宣布完成
4. 禁止为了让测试通过而修改测试用例本身
```

| 优点 | 缺点 |
|------|------|
| 零工程成本，立刻可用 | **依赖模型记住并遵守**，长对话中容易被遗忘 |

**适用**：原型阶段、低风险任务。

### 档位 2：`/goal` 式持续条件

把"完成条件"变成**每轮结束都要检查的断言**：

```python
GOAL_CONDITIONS = [
    "所有测试通过",
    "lint 零错误",
    "没有未提交的文件改动",
]


def evaluate_goal(state) -> tuple[bool, str]:
    """每轮结束由独立 evaluator 检测；不满足则继续工作"""
    results = run_checks(GOAL_CONDITIONS)
    failed = [r for r in results if not r.passed]
    if failed:
        return False, "未满足：" + "；".join(f.reason for f in failed)
    return True, "全部满足"
```

| 优点 | 缺点 |
|------|------|
| 比"内联"强制得多，模型无法"自己宣布成功" | 需要 evaluator 独立于主 Agent |

**关键设计**：evaluator **不能由主 Agent 自己充当**，否则等于"自己给自己打分"。

### 档位 3：Stop Hook（确定性 gate）⭐ 推荐起点

在"Agent 准备结束"这个事件上挂钩子，**不通过就 block，把失败原因塞回去继续干**：

```python
class StopHook:
    """确定性验证门：Agent 想停，先过这一关"""

    def __init__(self, commands: list[str], max_consecutive_blocks: int = 8):
        self.commands = commands                 # 如 ["npm test", "npm run build"]
        self.max_blocks = max_consecutive_blocks # 防死循环的刹车
        self.blocks = 0

    def on_stop(self, workspace: str) -> dict:
        for cmd in self.commands:
            proc = subprocess.run(cmd, shell=True, cwd=workspace,
                                  capture_output=True, text=True, timeout=600)
            if proc.returncode != 0:
                self.blocks += 1
                if self.blocks >= self.max_blocks:
                    return {"decision": "terminate",
                            "reason": f"连续 {self.blocks} 次验证失败，强制终止"}
                return {"decision": "block",
                        "reason": f"`{cmd}` 失败，请修复后重试：\n{proc.stdout[-1500:]}"}
        self.blocks = 0
        return {"decision": "allow"}
```

> ⚠️ **必须有刹车**：Claude Code 的实现是**连续 block 8 次后强制终止**。没有这个上限，"验证失败 → 修复 → 再失败"会变成无限循环。

### 档位 4：对抗性子 Agent（最重、最强）

Spawn 一个**看不到主 Agent 推理过程**的独立子 Agent，只给它：
- 最终的 **diff**
- **验证标准**（spec / 需求文档）

```python
REVIEWER_PROMPT = """你是一个独立的代码评审员。

你只能看到：
1. 原始需求
2. 最终代码变更（diff）

你**看不到**实现者的思考过程与解释——这是刻意的，
因为你要给出**独立**的第二意见。

请输出 JSON：
{
  "verdict": "approve" | "reject",
  "issues": [{"severity": "high|medium|low", "file": "...", "desc": "...", "fix": "..."}],
  "spec_compliance": [{"requirement": "...", "satisfied": true|false, "evidence": "..."}]
}
"""
```

**为什么"看不到推理"很关键**：如果评审者能看到实现者的解释，就会被"说服"，退化成自我确认。Anthropic 的 Dynamic Workflows 正是这么设计的——Phase 1 做研究，Phase 2 由另一组 agent **独立审查 Phase 1 的结论**（上下文隔离）。

### 3.1 四档对比

| 档位 | 强制力 | 工程成本 | 延迟/成本 | 推荐场景 |
|:----:|:------:|:--------:|:---------:|----------|
| 1 内联 | 低 | 极低 | 无 | 原型、低风险 |
| 2 `/goal` | 中 | 低 | 低 | 有明确验收标准的任务 |
| 3 **Stop Hook** | **高** | 中 | 中 | **生产默认** |
| 4 对抗性子 Agent | 最高 | 高 | 高 | 高风险改动、对外发布 |

---

## 四、Generator–Evaluator 架构与 Sprint 合同

### 4.1 两种角色分离

```text
┌──────────────┐        ① 协商"done 长什么样"        ┌──────────────┐
│  Generator   │ ─────────────────────────────────▶ │  Evaluator   │
│  （实现者）   │ ◀───────────────────────────────── │  （验收者）   │
└──────┬───────┘        ② 确认验收标准                └──────┬───────┘
       │                                                      │
       │ ③ 实现                                               │ ④ 验收
       ▼                                                      ▼
   代码/产出 ─────────────────────────────────────────▶ 通过 / 打回 + 理由
```

**Sprint 合同（Sprint Contract）** 是 Anthropic 的提法：**在开始编码之前**，Generator 与 Evaluator 先协商"完成长什么样"。这避免了两个经典陷阱：

| 陷阱 | 后果 |
|------|------|
| 验收标准由实现者单方面定义 | 实现者会"就低不就高" |
| 验收标准事后才定 | 需求理解偏差无法暴露 |

### 4.2 用 LangChain v1 实现

```python
from langchain.agents import create_agent
from langchain.tools import tool
from pydantic import BaseModel, Field


class Review(BaseModel):
    verdict: str = Field(description="approve 或 reject")
    issues: list[str] = Field(default_factory=list, description="问题列表")
    spec_compliance: list[str] = Field(default_factory=list, description="逐条对照需求")


@tool
def run_tests() -> str:
    """运行项目测试并返回结果。"""
    proc = subprocess.run(["pytest", "-q"], capture_output=True, text=True, timeout=300)
    return f"exit={proc.returncode}\n{proc.stdout[-2000:]}"


@tool
def read_diff() -> str:
    """读取当前工作区的代码变更（git diff）。"""
    proc = subprocess.run(["git", "diff", "HEAD"], capture_output=True, text=True)
    return proc.stdout[:8000]


# ① 实现者：可以改代码、可以跑测试
generator = create_agent(
    model="gpt-5.5",
    tools=[run_tests, write_file, edit_file],
    system_prompt="你是实现者。完成前必须运行 run_tests 并通过。",
)

# ② 验收者：只能读，不能改
evaluator = create_agent(
    model="gpt-5.5",
    tools=[read_diff, run_tests],
    system_prompt=REVIEWER_PROMPT,
    response_format=Review,
)


def develop_with_verification(requirement: str, max_rounds: int = 5) -> str:
    # --- Sprint 合同：先约定验收标准 ---
    contract = evaluator.invoke({
        "messages": [{"role": "user",
                      "content": f"请为下面的需求写出可验证的验收标准（不要实现）：\n{requirement}"}]
    })

    for round_no in range(1, max_rounds + 1):
        # --- 实现 ---
        generator.invoke({"messages": [{"role": "user", "content": requirement}]})

        # --- 独立验收（Evaluator 看不到 Generator 的推理）---
        review: Review = evaluator.invoke({
            "messages": [{"role": "user", "content": "请基于 diff 与验收标准给出评审结论"}]
        })["structured_response"]

        if review.verdict == "approve":
            return f"✅ 第 {round_no} 轮通过验收"

        # --- 打回：把问题作为背压注入下一轮 ---
        requirement = (requirement
                       + "\n\n[上一轮被验收打回，请修复以下问题]\n"
                       + "\n".join(f"- {i}" for i in review.issues))

    return "❌ 达到最大轮数仍未通过验收"
```

---

## 五、Back-Pressure（背压）与安灯绳

### 5.1 背压：让失败自然"顶回来"

> **核心思想**：不要试图"阻止"模型犯错，而是**让错误产生的后果立刻反馈回去**，迫使模型自我修正。

```
传统做法（脆弱）：
  模型输出 → 检查 → 发现问题 → 人工介入

背压做法（自愈）：
  模型输出 → 执行测试 → 测试失败（红） → 失败输出作为新的 observation
         → 模型看到"红了" → 自己改 → 再跑 → 直到绿
```

**人类工程师的工作方式本来就是这样**：写代码 → 跑测试 → 看报错 → 改 → 再跑。**Harness 只是把它自动化并强制化。**

### 5.2 安灯绳（Andon Cord）

来自丰田生产系统：任何工人发现问题都可以拉绳停线。

映射到 Agent：

| 环节 | 拉绳条件 |
|------|----------|
| **Lint** | 有任何 error 级问题 |
| **Review** | 评审 verdict = reject |
| **UnitTest** | 任一测试失败 |
| **E2E** | 关键路径失败 |

**任何一环拉绳，都不允许"继续往下走"。** 这是防止"静默失败"累积的关键。

### 5.3 自定义 linter：把规则变成永久记忆

**这是 Harness 复利效应最直观的体现。** 一个真实的洞察：

> **"Add one linter rule and every session from here on out avoids that mistake."**
> （加一条 linter 规则，从此以后每个会话都不会再犯这个错。）

因此，**当 Agent 犯了一个新错误，正确的反应不是"下次提醒它"，而是"写一条规则"。**

```python
# 自定义 lint 规则模板：每条规则都带"修复指令"
RULE_TEMPLATE = """
[{code}] {title}
ERROR: {error_message}
WHY:   {why_it_matters}
FIX:   {how_to_fix}
EXAMPLE:
       ❌ {bad_example}
       ✅ {good_example}
"""

# 示例：禁止在 async 函数中使用阻塞 IO
RULE_ASYNC_BLOCKING = RULE_TEMPLATE.format(
    code="AG001",
    title="async 函数中禁止阻塞 IO",
    error_message="在 async def 中调用了阻塞函数 requests.get()",
    why_it_matters="会阻塞事件循环，导致整个服务吞吐下降",
    how_to_fix="改用 httpx.AsyncClient() 或 aiohttp",
    bad_example="async def fetch(): return requests.get(url)",
    good_example="async def fetch(): async with httpx.AsyncClient() as c: ...",
)
```

**四段式（ERROR / WHY / FIX / EXAMPLE）的价值**：让 Agent 不仅知道"错了"，还知道"为什么错、怎么改"——**这是把人类经验固化进 Harness 的最佳载体**。

---

## 六、常见坑

| 坑 | 症状 | 解法 |
|----|------|------|
| **验证走过场** | 规则太弱，永远通过 | 验证规则必须能"抓得住"真实错误（先故意制造一个 bug 测试能否被抓到） |
| **验证标准过弱** | "测试通过"但功能不对 | 验收标准要覆盖**需求条目**，而不只是"测试绿了" |
| **验证成本超过收益** | 每轮跑 10 分钟 E2E | 分层：快速闸门每次都跑，重闸门只在关键节点跑 |
| **模型自评偏乐观** | Agent 说"已修复"，实际没修 | Evaluator 必须**独立**且**看不到实现的推理过程** |
| **无限修复循环** | 修不好，反复重试 | 连续 block 上限（如 8 次）+ 总预算上限 |
| **改测试来通过** | 改 `assert` 而不是改代码 | 在 AGENTS.md 中明确禁止，并用 `PreToolUse` hook 拦截测试文件写入 |
| **验证与实现同源** | 用同一个模型同一上下文自评 | 上下文隔离 + 不同 prompt 角色 |

---

## 七、本章总结

| 要点 | 说明 |
|------|------|
| **验证是最高 ROI** | 83% → 96% 的完成率提升；质量提升 2–3 倍 |
| **三条路径** | 规则（确定性）/ 视觉（UI）/ LLM-judge（语义） |
| **四档强度** | 内联 → `/goal` → **Stop Hook** → 对抗性子 Agent |
| **必须有刹车** | 连续 block 上限（参考：8 次）防止无限修复 |
| **Sprint 合同** | 先协商"done 长什么样"，再开始实现 |
| **背压** | 让失败自然顶回来，迫使模型自我修正 |
| **安灯绳** | Lint → Review → UnitTest → E2E，任一拉绳即停 |
| **规则复利** | 犯一次错 → 加一条 linter 规则 → 永久免疫 |

---

## 📝 课后练习

1. **设计验证矩阵**：为一个"自动修复线上 bug"的 Agent 设计三层验证（快速/阶段/终局），列出每层跑什么、耗时预算、失败后怎么处理。
2. **实现 Stop Hook**：用 Python 实现本章的 `StopHook`，并故意让测试失败 3 次，验证"block → 修复 → 通过"的完整链路以及连续 block 8 次后的强制终止。
3. **对抗性评审实验**：为同一个任务写两个 Evaluator prompt——一个能看到实现者的解释，一个只看到 diff。比较两者的挑错能力差异，写出结论。
4. **规则沉淀**：回顾你最近一次 Agent 犯的错，把它写成一条四段式（ERROR/WHY/FIX/EXAMPLE）linter 规则，并说明它如何阻止同类错误再次发生。
