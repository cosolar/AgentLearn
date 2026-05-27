# 8.7 评估与监控工具

## 📖 本章目标

- 了解 Agent 评估的全维度指标体系
- 掌握 DeepEval 等评估工具的使用
- 学会构建生产级监控系统

---

## 为什么需要评估与监控？

> 第 6.2 章介绍了评估基础概念，第 7.3 章介绍了监控基础。本章从生态视角看完整的可观测性体系。

```
开发阶段                 生产阶段
─────────               ─────────
单元测试       →       实时监控
离线评估       →       在线评估
人工审查       →       自动告警
Benchmark      →       Dashboard
```

**缺乏评估监控的后果：**
```
❌ Agent 表现下降无法感知
❌ Token 成本失控
❌ 用户遇到幻觉得不到纠正
❌ 问题排查困难
❌ 无法量化改进效果
```

---

## 评估工具全景

| 工具 | ⭐ GitHub | 核心能力 | 特色 |
|------|-----------|---------|------|
| **DeepEval** | 8K+ | 全维度评估框架 | Agent 专项测试、自定义指标 |
| **TruLens** | 5K+ | LLM 可解释性 | 端到端追踪、反馈函数 |
| **RAGAS** | 10K+ | RAG 质量评估 | 检索/生成/幻觉 三维度 |
| **AgentBench** | 6K+ | 标准任务集 | 多 Agent 性能排名 |
| **AgentScore** | 3K+ | 自动评分 | 轻量级、快速评估 |
| **LangSmith** | 闭源 | 全链路追踪 | LangChain 官方、最完善 |

---

## DeepEval — 全维度评估框架

DeepEval 是目前最全面的 Agent 评估工具，支持从单元测试到端到端评估。

### 安装

```bash
pip install deepeval
```

### 评估维度

```python
from deepeval import evaluate
from deepeval.metrics import (
    AnswerRelevancyMetric,    # 答案相关性
    FaithfulnessMetric,       # 忠实度（幻觉检测）
    ContextualPrecisionMetric,# 上下文精确度
    ContextualRecallMetric,   # 上下文召回率
    HallucinationMetric,      # 幻觉评估
    ToxicityMetric,           # 有害内容检测
    BiasMetric,               # 偏见检测
    CostMetric,               # 成本评估
    LatencyMetric,            # 延迟评估
)

# 定义评估指标
metrics = [
    AnswerRelevancyMetric(),
    FaithfulnessMetric(),
    HallucinationMetric(),
]

# 执行评估
test_results = evaluate(
    test_cases=[
        {"input": "美国的首都是什么？", "actual_output": "华盛顿", "expected_output": "华盛顿"},
        {"input": "1+1=?", "actual_output": "2", "expected_output": "2"},
    ],
    metrics=metrics,
)
print(test_results)
```

### Agent 专项测试

```python
from deepeval.test_case import LLMTestCase
from deepeval.dataset import EvaluationDataset

# 定义测试数据集
dataset = EvaluationDataset(
    test_cases=[
        LLMTestCase(
            input="查询北京天气",
            actual_output="北京的天气：晴，25°C",
            tools_used=["search_weather"],
            retrieval_context=["北京当前天气数据"],
            expected_tools=["search_weather"],
        ),
    ]
)

# Agent 特定指标
from deepeval.metrics import (
    ToolCallAccuracyMetric,   # 工具调用准确率
    ReasoningQualityMetric,   # 推理质量
)
```

---

## TruLens — 可解释性监控

TruLens 通过 **反馈函数 (Feedback Functions)** 实现可解释的 Agent 评估。

### 核心概念

```python
from trulens_eval import Feedback, TruLlama
from trulens_eval.feedback import Groundedness

# 定义反馈函数
f_groundedness = (
    Feedback(Groundedness().groundedness_measure_with_cot_reasons)
    .on_input_output()
)

f_qa_relevance = (
    Feedback(Relevance().relevant_against_context)
    .on_input()
    .on_output()
)

# 包装 Agent
tru_agent = TruLlama(
    agent,
    app_id="research-agent",
    feedbacks=[f_groundedness, f_qa_relevance]
)

# 记录和监控
with tru_agent as recording:
    agent.reply("什么是 RAG 技术？")

# 查看仪表盘
from trulens_eval import Tru
Tru().run_dashboard()
```

### TruLens vs DeepEval

| 对比维度 | DeepEval | TruLens |
|---------|----------|---------|
| 定位 | 评估框架 | 可解释性监控 |
| 评估方式 | 离线/CI 测试 | 在线/实时 |
| 反馈机制 | 指标计算 | 反馈函数链 |
| Dashboard | CLI | Web UI |
| CI 集成 | ✅ Pytest | ⚠️ 间接 |
| 学习曲线 | 低 | 中 |

---

## AgentBench — 标准化 Benchmark

AgentBench 提供标准化的任务集和评分体系，用于 **横向对比** 不同 Agent 的性能。

```
AgentBench 测试维度：
┌──────────────────────────────────────────────────────────┐
│  操作系统     ─── 文件管理、命令执行                       │
│  网络服务     ─── HTTP 请求、API 调用                      │
│  数据库       ─── SQL 查询、数据操作                       │
│  知识问答     ─── 开放域 Q&A                              │
│  推理         ─── 逻辑推理、数学                           │
│  代码         ─── 编程任务                                │
│  工具使用     ─── 多工具编排                              │
└──────────────────────────────────────────────────────────┘
```

```bash
# 使用 AgentBench
pip install agentbench
agentbench run --agent your_agent --task web_browsing
```

---

## 生产级监控体系

### LangSmith — LangChain 官方监控

虽然闭源，但是 LangChain/LangGraph 生态中最完善的监控方案。

```python
# 使用 LangSmith 追踪（免费版可用）
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "ls_..."

# 所有 LangChain 调用自动追踪
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o")
llm.invoke("Hello")  # 自动记录到 LangSmith Dashboard
```

### 自建监控体系

```python
# 核心监控指标采集器
class AgentMonitor:
    def __init__(self):
        self.metrics = {
            "latency": [],
            "token_count": [],
            "cost": [],
            "tool_calls": [],
            "error_rate": [],
        }
    
    def record_call(self, func_name: str, start_time: float, 
                    tokens: int, success: bool):
        """记录一次 Agent 调用"""
        latency = time.time() - start_time
        self.metrics["latency"].append(latency)
        self.metrics["token_count"].append(tokens)
        self.metrics["error_rate"].append(0 if success else 1)
    
    def get_report(self) -> dict:
        """生成监控报告"""
        return {
            "avg_latency": statistics.mean(self.metrics["latency"]),
            "p95_latency": statistics.quantiles(self.metrics["latency"], n=20)[18],
            "total_tokens": sum(self.metrics["token_count"]),
            "estimated_cost": self._calculate_cost(),
            "error_rate": statistics.mean(self.metrics["error_rate"]),
        }
```

### 告警规则

```yaml
# 告警配置示例
alerts:
  - name: high_latency
    condition: p95_latency > 10s
    action: notify_slack("#alerts")
    
  - name: cost_spike
    condition: daily_cost > $100
    action: notify_email("admin@company.com")
    
  - name: error_rate
    condition: error_rate > 5%
    action: auto_rollback(last_deployment)
```

---

## 评估与监控的 CI/CD 集成

```yaml
# .github/workflows/agent-eval.yml
name: Agent Evaluation
on: [pull_request]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install deepeval
      
      - name: Run Agent Tests
        run: deepeval test run tests/agent_eval.py
        
      - name: Compare with Baseline
        run: |
          deepeval compare --baseline main --current ${{ github.sha }}
          
      - name: Block if Quality Drops
        if: ${{ steps.eval.outputs.quality_score < 0.8 }}
        run: exit 1
```

---

## 本章小结

| 要点 | 说明 |
|------|------|
| 📊 | DeepEval 最全面的离线评估框架 |
| 🔍 | TruLens 提供可解释性监控 |
| 🏆 | AgentBench 用于横向 Benchmark 对比 |
| 📈 | LangSmith 是 LangChain 生态最佳监控方案 |
| 🔔 | 生产环境必须配置告警规则 |
| 🔄 | 评估应集成到 CI/CD 流程 |

---

## 📝 课后练习

1. **实践题**：用 DeepEval 为你的 Agent 编写 5 个测试用例并运行
2. **集成题**：在项目中集成 AgentMonitor 类，添加延迟和成本追踪
3. **自动化题**：配置 GitHub Actions 在 PR 时自动运行 Agent 评估

