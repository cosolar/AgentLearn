# 9.11 Harness 评测与可观测性 —— 如何证明你的 Harness 更好

## 📖 导读

> **Agent 一次请求往往包含 5–15 次 LLM 调用和若干次工具调用。没有追踪，等于在黑盒里调试。**

[9.7](07-harness-engineering.md) 讲了"要设计 Harness"，但**怎么知道你的设计是变好了还是变差了？** 本章给出 Harness 级别的评测方法论与可观测性落地方法。

> ⚠️ **核心区分**：**模型评测 ≠ Harness 评测**。本章关注的是后者。

---

## 一、最有力的证据：同一模型，不同 Harness

| 实验 | 结果 |
|------|------|
| **TerminalBench 2.0** | 同一模型、同一权重，**仅更换 Harness**，排名从 **30 名开外 → 第 5 名** |
| **LangChain（GPT-4）** | 只改 harness 不换模型，完成率 **52.8% → 66.5%** |
| **Token 效率测试** | 同一模型、同一 API，不同 Harness 完成同一任务的 token 消耗**相差约 70 倍** |
| **Meta-Harness 论文** | 自动优化 harness：比 ACE 高 **7.7pp**，上下文 token 减 **4×** |

### 1.1 Token 效率：最容易被忽视的 Harness 质量指标

| Harness / 模式 | 每任务 token（量级） | 说明 |
|----------------|:-------------------:|------|
| Aider（Architect 模式） | ~3,500 | 精简的 diff 驱动 |
| 主流终端 Harness | 1 万–5 万 | 视任务复杂度 |
| 低效 Harness | 十万级 | 反复整文件读取、无压缩、无缓存 |

> 🎯 **为什么 token 效率是核心指标**：它同时反映**成本**、**上下文管理质量**和**步数效率**。一个"能完成任务但烧 20 倍 token"的 Harness，在生产上不可接受。

---

## 二、Harness 级评测维度

### 2.1 四类指标

| 类型 | 指标 | 为什么重要 |
|------|------|-----------|
| **结果** | 任务完成率 | 最根本 |
| **效率** | 每任务 token、步数、工具调用次数 | 决定成本与可扩展性 |
| **质量** | 工具调用准确率、轨迹合理性、无幻觉率 | 决定可信度 |
| **系统** | p50/p95 延迟、失败率、每任务成本 | 决定能否上生产 |

### 2.2 必须同时看"结果"与"轨迹"

| 只看结果 ❌ | 结果 + 轨迹 ✅ |
|------------|---------------|
| "任务成功了" | "任务成功了，但用了 47 步、调错 3 次工具、烧了 8 万 token——**下次大概率会失败**" |

**轨迹指标**：

```text
├── 工具选择准确率 = 选对工具次数 / 总工具调用次数
├── 参数正确率     = 参数无错的比例
├── 无效步数占比   = （重复调用 + 走回头路）/ 总步数
├── 上下文峰值     = 单次请求的最大 token 数
└── 压缩触发次数   = 反映任务是否超出窗口
```

### 2.3 失败模式分布（最有价值的诊断）

不要只统计"失败率"，要统计**怎么失败的**——直接映射到 [9.1 的五类失败模式](01-intro.md)：

| 失败模式 | 统计信号 |
|----------|----------|
| 上下文腐化 | 重复工具调用占比上升、同一问题反复出现 |
| 工具爆炸 | 工具选择错误率上升 |
| 静默失败 | 工具返回错误但任务被标记为"成功" |
| 无限循环 | 步数分布出现离群长尾 |
| 状态损坏 | 恢复后立即失败的比例 |

---

## 三、评测基准（Benchmark）

| 基准 | 测什么 | 适用 | 局限 |
|------|--------|------|------|
| **TerminalBench 2.0** | 终端环境下的真实任务 | 编码类 Harness 横向对比 | 偏终端场景 |
| **SWE-bench Verified** | 真实 GitHub issue 修复 | 代码修改能力 | 单轮为主，不测长任务 |
| **AgentBench** | 多环境（OS / 网络 / 数据库 / 推理 / 代码 / 工具） | 综合能力 | 与生产场景有差距 |
| **自建评测集** ⭐ | **你的真实任务分布** | **最贴合实际** | 需要自己维护 |

> 💡 **强烈建议**：公开基准做"横向参考"，**自建评测集做"纵向回归"**。生产项目的胜负手在后者。

### 3.1 自建评测集的最小形态

```jsonl
{"id": "t001", "task": "修复登录接口的 500 错误", "expect": {"tests_pass": true, "files_touched": ["src/api/auth.py"]}}
{"id": "t002", "task": "为 utils.py 补单元测试，覆盖率 >80%", "expect": {"coverage_min": 0.8}}
{"id": "t003", "task": "把日志从 print 改为结构化 logging", "expect": {"no_print": true}}
```

| 要素 | 说明 |
|------|------|
| **数量** | 20–50 条起步；覆盖高频任务 + 已知难点 |
| **可自动判定** | 期望结果必须能**程序化判定**（测试是否通过、文件是否被改） |
| **版本化** | 评测集进 git，随项目演化 |

---

## 四、学术视角：Harness 正在成为研究对象

### 4.1 Meta-Harness 论文

《End-to-End Optimization of Model Harnesses》（arXiv **2603.28052**，2026-03-30，Stanford / KRAFTON / MIT）。

| 贡献 | 说明 |
|------|------|
| **核心思想** | 让 **harness 本身可被自动优化**（而非手工调参） |
| **结果** | 比 ACE 高 **7.7pp**，上下文 token 减 **4×** |

> 🎯 这印证了 [9.2](02-anatomy.md) 的判断：**harness 是一个可以被工程化、被度量、被优化的对象。**

### 4.2 循环原语分类论文

《A Source-Code Taxonomy of Coding Agent Architectures》（arXiv **2604.03515**）提出**五种循环原语**：

| 原语 | 机制 | 适用 | 代价 |
|------|------|------|------|
| **ReAct** | 思考-行动-观察交织 | 通用、探索性任务 | 每步都调模型 |
| **生成-测试-修复** | 生成 → 跑测试 → 按失败信息修复 | 有明确测试的任务 | 依赖可自动化的测试 |
| **计划-执行** | 先规划再逐步执行 | 步骤可预知的长任务 | 计划出错代价高 |
| **多次重试** | 独立多次尝试 + 择优 | 单次成功率低但可判定 | 成本线性放大 |
| **树搜索** | 分支探索 + 回溯 | 解空间大、可评估中间态 | 成本最高 |

> 💡 **实用建议**：**大多数生产 Harness 都是这五种原语的组合**。例如："计划-执行"做骨架 + "生成-测试-修复"做每步收敛 + "多次重试"兜底。

---

## 五、可观测性落地

### 5.1 标准：OpenTelemetry GenAI 语义约定

2026 年的事实标准。用统一 span 语义（`gen_ai.*` 属性）埋点，即可导出到任意后端：

```python
from opentelemetry import trace

tracer = trace.get_tracer("agent-harness")

with tracer.start_as_current_span("agent.run") as span:
    span.set_attribute("gen_ai.system", "anthropic")
    span.set_attribute("gen_ai.request.model", "claude-sonnet-4-6")
    span.set_attribute("gen_ai.usage.input_tokens", usage.input_tokens)
    span.set_attribute("gen_ai.usage.output_tokens", usage.output_tokens)
```

**好处**：换后端不用改代码（Langfuse / LangSmith / Grafana / Datadog 都支持 OTel）。

### 5.2 平台定位差异

| 平台 | 类型 | 最适合 |
|------|------|--------|
| **LangSmith** | 商用（有免费额度） | LangChain 技术栈，追踪 + 评估一体 |
| **Langfuse** | 开源可自托管 | 数据敏感、需私有化 |
| **Arize Phoenix** | 开源 | 本地分析、检索质量诊断 |
| **Braintrust** | 商用 | 数据集管理与实验对比 |

### 5.3 该埋什么（三类埋点）

| 类别 | 埋点内容 |
|------|----------|
| **模型调用** | model、input/output tokens、延迟、成本、是否触发压缩 |
| **工具调用** | 工具名、参数、耗时、成功/失败、**是否被权限拦截** |
| **决策点** | 轮次、终止原因（正常/超轮数/超预算/tripwire）、验证结果 |

> 📌 一个反直觉的细节（来自 Claude Code）：**hook 的 stdout 在 exit 0 时不进入模型上下文**。若希望 hook 结果被模型看到，必须通过 `hookSpecificOutput.additionalContext` 返回。**这既是 token 节省设计，也是埋点要注意的边界。**

---

## 六、动手：AgentTracer 与 A/B 对比

### 6.1 埋点收集器

```python
"""tracer.py —— 轻量埋点：token / 延迟 / 成本 / 步数"""
import statistics
import time
from contextlib import contextmanager
from dataclasses import dataclass, field


# 每 1K token 美元单价（量级示意，请以各厂商官网为准）
PRICING = {
    "gpt-5.5": (0.00125, 0.010),
    "gpt-5-mini": (0.00025, 0.002),
    "claude-sonnet-4-6": (0.003, 0.015),
}


@dataclass
class Step:
    kind: str            # "llm" | "tool" | "verify"
    name: str
    duration: float = 0.0
    tokens: int = 0
    ok: bool = True
    detail: str = ""


@dataclass
class Trace:
    steps: list = field(default_factory=list)
    t0: float = field(default_factory=time.time)
    terminated_by: str = "unknown"

    @property
    def llm_calls(self) -> int:
        return sum(1 for s in self.steps if s.kind == "llm")

    @property
    def tool_calls(self) -> int:
        return sum(1 for s in self.steps if s.kind == "tool")

    @property
    def total_tokens(self) -> int:
        return sum(s.tokens for s in self.steps)

    def cost(self, model: str) -> float:
        pin, pout = PRICING.get(model, (0.001, 0.003))
        # 简化：按 7:3 估算输入输出比例（真实应由 usage 分别累计）
        return self.total_tokens / 1000 * ((pin * 0.7) + (pout * 0.3))

    def summary(self, model: str) -> dict:
        lat = sorted(s.duration for s in self.steps) or [0.0]
        p95 = lat[min(int(len(lat) * 0.95), len(lat) - 1)]
        return {
            "turns": self.llm_calls,
            "tool_calls": self.tool_calls,
            "tokens": self.total_tokens,
            "cost_usd": round(self.cost(model), 5),
            "wall_seconds": round(time.time() - self.t0, 2),
            "p50_latency": round(statistics.median(lat), 3),
            "p95_latency": round(p95, 3),
            "tool_error_rate": round(
                sum(1 for s in self.steps if s.kind == "tool" and not s.ok)
                / max(self.tool_calls, 1), 3),
            "terminated_by": self.terminated_by,
        }


class AgentTracer:
    def __init__(self):
        self.trace = Trace()

    @contextmanager
    def step(self, kind: str, name: str, tokens: int = 0):
        t = time.time()
        entry = Step(kind=kind, name=name, tokens=tokens)
        try:
            yield entry
        except Exception as e:
            entry.ok = False
            entry.detail = f"{type(e).__name__}: {e}"
            raise
        finally:
            entry.duration = time.time() - t
            self.trace.steps.append(entry)
```

### 6.2 Harness A/B 对比脚本

```python
"""ab_compare.py —— 同一批任务，对比两个 Harness 配置"""
import json
from statistics import mean

from config import HarnessConfig
from harness import Harness
from tracer import AgentTracer


def load_tasks(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def judge_success(task: dict, final_text: str) -> int:
    """程序化判定（示例）：真实项目应跑测试 / 检查文件 / 校验 schema"""
    expect = task["expect"]
    if expect.get("tests_pass"):
        return int("FAILED" not in final_text and "错误" not in final_text)
    return int(bool(final_text.strip()))


def run_config(cfg: HarnessConfig, tasks: list) -> dict:
    rows = []
    for t in tasks:
        tracer = AgentTracer()
        h = Harness(cfg, tracer=tracer)
        final = h.run(t["task"])
        rows.append({"id": t["id"],
                     "success": judge_success(t, str(final)),
                     **tracer.trace.summary(cfg.model)})
    return {
        "success_rate": round(mean(r["success"] for r in rows), 3),
        "avg_tokens": round(mean(r["tokens"] for r in rows)),
        "avg_tool_calls": round(mean(r["tool_calls"] for r in rows), 1),
        "avg_cost_usd": round(mean(r["cost_usd"] for r in rows), 5),
        "details": rows,
    }


if __name__ == "__main__":
    tasks = load_tasks("eval/tasks.jsonl")

    configs = {
        "baseline(no-retry)": HarnessConfig(max_retries=0),
        "candidate(+retry+verify)": HarnessConfig(max_retries=2),
    }
    results = {name: run_config(cfg, tasks) for name, cfg in configs.items()}

    print(f"{'配置':<26}{'完成率':>9}{'平均token':>12}{'工具调用':>10}{'成本(USD)':>12}")
    for name, r in results.items():
        print(f"{name:<26}{r['success_rate']:>9.1%}"
              f"{r['avg_tokens']:>12}{r['avg_tool_calls']:>10}{r['avg_cost_usd']:>12.5f}")
```

**输出示例**：

```text
配置                        完成率    平均token   工具调用    成本(USD)
baseline(no-retry)          72.0%       18420       11.3      0.01310
candidate(+retry+verify)    96.0%       21380       13.8      0.01520
```

**怎么读这张表**：完成率 **+24pp**，token 只涨 **16%**，成本涨 16% —— **这笔交易非常划算**。
反过来，若完成率只涨 2pp 而 token 翻倍，就该重新设计。

> ⚠️ **重要**：`judge_success` 必须**程序化判定**（跑测试、检查文件、校验输出 schema），**不要用 LLM 打分**——否则评测本身就不可靠（回看 [9.5 验证循环](05-verification.md)）。

---

## 七、告警规则

```yaml
# alerts.yaml
alerts:
  - name: success_rate_drop
    condition: success_rate_1h < 0.80 and success_rate_7d_avg > 0.92
    action: notify_slack("#agent-alerts")
    note: 完成率突然下滑，通常是模型升级 / prompt 改动 / 上游工具变更

  - name: token_cost_spike
    condition: avg_cost_per_task_1h > avg_cost_per_task_7d * 2
    action: notify_slack("#agent-alerts")
    note: token 成本突增，检查是否出现死循环或上下文压缩失效

  - name: infinite_loop
    condition: p99_tool_calls_per_task > 40
    action: page_oncall
    note: 长尾步数异常，怀疑循环检测失效

  - name: latency_regression
    condition: p95_latency_1h > p95_latency_7d * 1.5
    action: notify_slack("#agent-alerts")

  - name: tool_error_rate
    condition: tool_error_rate_1h > 0.15
    action: notify_slack("#agent-alerts")
    note: 上游 API / 权限配置可能出了问题
```

### 7.1 三条必看指标（如果只监控三个）

1. **每任务 LLM / 工具调用次数** —— 异常增长往往是死循环前兆
2. **完成率 + p95 延迟** —— 按 Agent / 工具维度拆分
3. **单位任务成本**（token × 单价）—— 并设置阈值告警

---

## 八、上线评测流程（CI 集成）

```yaml
# .github/workflows/agent-eval.yml
name: Harness Evaluation
on: [pull_request]

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: uv sync

      - name: 跑评测集（当前分支）
        run: uv run python eval/run_eval.py --out current.json

      - name: 拉取基线结果
        run: git fetch origin main && git show origin/main:eval/baseline.json > baseline.json

      - name: 对比并阻断退化
        run: |
          uv run python eval/compare.py \
            --baseline baseline.json --current current.json \
            --max-success-drop 0.03 --max-token-increase 0.20
```

**阻断条件示例**：

| 指标 | 容忍度 | 理由 |
|------|:------:|------|
| 完成率下降 | > 3pp | 质量退化不可接受 |
| 平均 token 上涨 | > 20% | 成本退化 |
| 工具错误率 | > +5pp | 稳定性退化 |

---

## 九、常见坑

| 坑 | 后果 | 解法 |
|----|------|------|
| **只看最终答案不看轨迹** | 掩盖"勉强成功" | 同时统计步数、工具错误率、无效步数占比 |
| **评测集过小过旧** | 结论不可信 | 20–50 条起步，随业务演进 |
| **用 LLM 当裁判判定成功** | 评测本身不可靠 | **程序化判定优先**，LLM-judge 仅作补充 |
| **把模型评测结论套到 Harness** | 方向错误 | 换模型 vs 换 Harness 要分开做 A/B |
| **不做回归** | 改动悄无声息地退化 | CI 中强制对比基线，超阈值直接 block |
| **只测 Easy 任务** | 上线后发现严重问题 | 评测集必须包含已知难点与边界 |

---

## 十、本章总结

| 要点 | 说明 |
|------|------|
| **核心证据** | 同模型仅换 Harness：TerminalBench 30+ → 第 5；完成率 52.8% → 66.5% |
| **Token 效率** | 同一任务不同 Harness 可差 **~70 倍**，这是 Harness 质量的核心指标 |
| **评测维度** | 结果 / 效率 / 质量 / 系统，**结果与轨迹必须同时看** |
| **自建评测集** | 生产项目的胜负手；必须**程序化判定** |
| **五种循环原语** | ReAct / 生成-测试-修复 / 计划-执行 / 多次重试 / 树搜索 |
| **可观测性标准** | OpenTelemetry GenAI（`gen_ai.*`）；LangSmith / Langfuse / Arize |
| **三类埋点** | 模型调用、工具调用、决策点 |
| **CI 阻断** | 完成率下降 > 3pp、token 上涨 > 20% 直接 block |

---

## 📝 课后练习

1. **指标设计**：为一个"自动修复线上告警"的 Agent 设计 6 个评测指标，并说明每个指标"退化时的可能原因"。
2. **实现 AgentTracer**：把本章的 `tracer.py` 接入 [9.8](08-build-your-harness.md) 的 mini-harness，跑 3 个任务并输出 `summary()`，对比你观察到的最慢一步是谁。
3. **A/B 实验**：用 `ab_compare.py` 对比 `max_turns=10` 与 `max_turns=25` 两个配置，写出结论——是"轮数越多越好"吗？为什么？
4. **失败模式归因**：跑 10 次同一个任务，统计失败/勉强成功的案例属于[五类失败模式](01-intro.md)中的哪一类，并针对占比最高的那一类给出 Harness 改造方案。
