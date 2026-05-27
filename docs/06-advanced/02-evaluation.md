# 6.2 Agent 评估与优化 —— 用数据驱动 Agent 进化

## 📖 导读

> **不能衡量，就无法改进。Agent 开发不能靠"感觉"决定好坏。**

当一个 Agent 开发完成后，如何判断它"好不好"？如何知道优化方向？本章将介绍 Agent 系统的评估方法、评估指标、常用工具和优化策略，帮助你**用数据驱动 Agent 的持续改进**。

---

## 一、前置知识

| 概念 | 说明 |
|------|------|
| 准确率 | 回答正确的比例 |
| 召回率 | 正确信息被覆盖的比例 |
| Token | LLM 的计量单位，影响成本 |
| 延迟 | 从输入到输出所需时间 |

---

## 二、评估维度

一个 Agent 系统的评估应该覆盖以下维度：

| 维度 | 衡量什么 | 关键指标 |
|------|----------|----------|
| **准确性** | 回答是否正确、可靠 | 准确率、幻觉率 |
| **完整性** | 信息是否全面覆盖 | 召回率、覆盖率 |
| **相关性** | 回答是否针对问题 | 相关度评分 |
| **响应速度** | 用户等待时间 | P50/P95 延迟 |
| **用户体验** | 交互是否自然流畅 | 用户满意度 |
| **成本效率** | 每次对话的消耗 | Token 消耗、API 费用 |

---

## 三、评估方法

### 3.1 自动化评估

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate


class AutoEvaluator:
    """自动化评估 Agent 回答质量"""
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    def evaluate_accuracy(self, question: str, answer: str, ground_truth: str) -> dict:
        """评估回答准确性（与标准答案对比）"""
        prompt = f"""
        对比以下两个答案，评估 AI 回答的准确性。
        
        问题：{question}
        
        标准答案：{ground_truth}
        AI 回答：{answer}
        
        请评估：
        1. 信息准确度（0-10）：AI 回答的信息是否与标准答案一致？
        2. 完整性（0-10）：是否遗漏了重要信息？
        3. 额外信息（0-10）：是否包含不准确或幻觉信息？（越低越好）
        
        输出 JSON 格式：
        {{
            "accuracy_score": 0-10,
            "completeness_score": 0-10,
            "hallucination_score": 0-10,
            "overall_score": 0-10,
            "issues": ["问题1", "问题2"],
            "suggestions": ["建议1"]
        }}
        """
        
        result = self.llm.invoke(prompt)
        return result.content
    
    def evaluate_relevance(self, question: str, answer: str) -> dict:
        """评估回答相关性"""
        # ... 评估回答是否针对问题
        pass


# 批量评估
def batch_evaluate(test_cases: list, agent_func) -> dict:
    """批量评估 Agent 性能"""
    evaluator = AutoEvaluator()
    results = []
    
    for case in test_cases:
        question = case["question"]
        ground_truth = case["answer"]
        
        # Agent 回答
        agent_answer = agent_func(question)
        
        # 评估
        evaluation = evaluator.evaluate_accuracy(
            question, agent_answer, ground_truth
        )
        results.append({
            "question": question,
            "agent_answer": agent_answer,
            "evaluation": evaluation,
        })
    
    # 汇总
    return summarize_results(results)
```

### 3.2 人工评估

```python
def human_evaluation_template() -> str:
    """人工评估模板"""
    return """
## Agent 回答评估表

### 问题
{question}

### Agent 回答
{answer}

### 评分（1-5）
1. **准确性**：回答中的事实是否正确？[1/2/3/4/5]
2. **相关性**：回答是否针对问题？[1/2/3/4/5]
3. **完整性**：信息是否全面？[1/2/3/4/5]
4. **清晰度**：表达是否易懂？[1/2/3/4/5]
5. **有用性**：对解决问题是否有帮助？[1/2/3/4/5]

### 反馈
- 好的方面：
- 需要改进：
- 其他意见：
"""
```

### 3.3 评估工具

| 工具 | 用途 | 安装 |
|------|------|------|
| **RAGAS** | RAG 系统评估框架 | `pip install ragas` |
| **LangSmith** | LangChain 官方可观测平台 | 云服务 |
| **Phoenix** | Arize 开源的 LLM 可观测 | `pip install arize-phoenix` |
| **DeepEval** | 单元测试风格的 LLM 评估 | `pip install deepeval` |

---

## 四、Agent 优化策略

### 4.1 Prompt 优化

```python
# 优化前
system_prompt = "你是一个 AI 助手。"

# 优化后
system_prompt = """
你是一个知识库问答助手。回答规则：
1. 只基于提供的文档内容回答
2. 如果不确定，说"未找到相关信息"
3. 引用信息来源
4. 回答控制在 200 字以内
5. 如果问题是问候语，简单打招呼即可
"""
```

### 4.2 工具优化

| 优化点 | 做法 | 效果 |
|--------|------|------|
| **工具描述** | 写清楚工具的用途和参数 | Agent 选择更准确 |
| **工具粒度** | 粗→中粒度的工具 | 减少误调用 |
| **工具数量** | 控制在 5-10 个 | 降低决策复杂度 |
| **错误处理** | 工具调用失败时给出友好提示 | 提升鲁棒性 |

### 4.3 模型优化

```python
# 不同场景使用不同模型
def select_model(task_type: str):
    """根据任务类型选择模型"""
    models = {
        "简单问答": "gpt-4o-mini",  # 快速，便宜
        "复杂推理": "gpt-4o",       # 强大，较贵
        "代码生成": "gpt-4o",       # 需要强大能力
        "翻译": "gpt-4o-mini",      # 简单任务够用
        "总结": "gpt-4o-mini",      # 性价比高
    }
    return models.get(task_type, "gpt-4o-mini")
```

### 4.4 成本优化

```python
class CostTracker:
    """成本跟踪器"""
    
    MODEL_COSTS = {
        "gpt-4o": {"input": 0.005, "output": 0.015},  # 每 1K tokens 美元
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "text-embedding-3-small": {"input": 0.00002, "output": 0.0},
    }
    
    def __init__(self):
        self.total_cost = 0.0
        self.call_count = 0
    
    def track_call(self, model: str, input_tokens: int, output_tokens: int):
        """记录一次 API 调用成本"""
        costs = self.MODEL_COSTS.get(model, {"input": 0.01, "output": 0.03})
        cost = (input_tokens / 1000 * costs["input"] +
                output_tokens / 1000 * costs["output"])
        self.total_cost += cost
        self.call_count += 1
        return cost
    
    def get_stats(self) -> dict:
        return {
            "total_calls": self.call_count,
            "total_cost_usd": round(self.total_cost, 4),
            "avg_cost_per_call": round(self.total_cost / max(self.call_count, 1), 6),
        }
```

---

## 五、完整评估和优化流程

```python
class AgentOptimizer:
    """Agent 评估与优化管理器"""
    
    def __init__(self, agent):
        self.agent = agent
        self.test_cases = []
        self.results = []
    
    def add_test_cases(self, cases: list):
        """添加测试用例"""
        self.test_cases.extend(cases)
    
    def run_evaluation(self) -> dict:
        """运行完整评估"""
        print("🔬 开始 Agent 评估...")
        
        passed = 0
        failed = 0
        details = []
        
        for i, case in enumerate(self.test_cases, 1):
            print(f"  [{i}/{len(self.test_cases)}] 测试: {case['question'][:30]}...")
            
            try:
                start_time = time.time()
                answer = self.agent.run(case["question"])
                latency = time.time() - start_time
                
                # 检查是否包含预期关键词
                has_key = any(kw in answer for kw in case.get("keywords", [case["question"]]))
                
                if has_key:
                    passed += 1
                    status = "✅"
                else:
                    failed += 1
                    status = "❌"
                
                details.append({
                    "question": case["question"],
                    "expected_keywords": case.get("keywords", []),
                    "answer_preview": answer[:100],
                    "passed": has_key,
                    "latency": round(latency, 2),
                })
                
            except Exception as e:
                failed += 1
                status = "💥"
                details.append({
                    "question": case["question"],
                    "error": str(e),
                    "passed": False,
                })
            
            print(f"    {status}")
        
        accuracy = passed / max(len(self.test_cases), 1)
        
        return {
            "total": len(self.test_cases),
            "passed": passed,
            "failed": failed,
            "accuracy": accuracy,
            "details": details,
        }
    
    def suggest_optimizations(self, eval_result: dict) -> list:
        """基于评估结果提出优化建议"""
        suggestions = []
        
        if eval_result["accuracy"] < 0.8:
            suggestions.append("🔧 准确率低于 80%，建议：")
            suggestions.append("   - 优化 system prompt，增加明确的规则")
            suggestions.append("   - 检查知识库中的文档质量")
            suggestions.append("   - 增加测试用例覆盖更多场景")
        
        # 检查失败案例的共同模式
        failed_cases = [d for d in eval_result["details"] if not d["passed"]]
        if failed_cases:
            failed_questions = [c["question"] for c in failed_cases]
            suggestions.append(f"📋 失败案例共 {len(failed_cases)} 个，共性分析可帮助定位问题")
        
        return suggestions


# 使用
def demo_optimization():
    """演示评估和优化流程"""
    
    # 准备好 Agent（假设已实现）
    agent = lambda q: f"关于'{q}'的回答..."
    
    optimizer = AgentOptimizer(agent)
    
    # 添加测试用例
    optimizer.add_test_cases([
        {"question": "什么是 AI Agent？", "keywords": ["AI", "Agent"]},
        {"question": "RAG 是什么？", "keywords": ["检索", "生成"]},
        {"question": "Python 列表怎么用？", "keywords": ["列表"]},
    ])
    
    # 运行评估
    result = optimizer.run_evaluation()
    
    # 输出报告
    print(f"\n📊 评估报告:")
    print(f"总测试数: {result['total']}")
    print(f"通过: {result['passed']}")
    print(f"失败: {result['failed']}")
    print(f"准确率: {result['accuracy']:.1%}")
    
    # 优化建议
    suggestions = optimizer.suggest_optimizations(result)
    for s in suggestions:
        print(s)
```

---

## 六、持续监控

```python
class MonitoringDashboard:
    """Agent 监控面板"""
    
    def __init__(self):
        self.metrics = {
            "total_queries": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "avg_latency": 0.0,
            "error_count": 0,
        }
    
    def log_query(self, tokens: int, cost: float, latency: float, success: bool):
        """记录一次查询的指标"""
        self.metrics["total_queries"] += 1
        self.metrics["total_tokens"] += tokens
        self.metrics["total_cost"] += cost
        self.metrics["avg_latency"] = (
            (self.metrics["avg_latency"] * (self.metrics["total_queries"] - 1) + latency)
            / self.metrics["total_queries"]
        )
        if not success:
            self.metrics["error_count"] += 1
    
    def get_report(self) -> dict:
        m = self.metrics
        return {
            "总查询数": m["total_queries"],
            "总 Token 消耗": m["total_tokens"],
            "总成本(USD)": f"${m['total_cost']:.4f}",
            "平均延迟(s)": f"{m['avg_latency']:.2f}",
            "错误数": m["error_count"],
            "错误率": f"{m['error_count']/max(m['total_queries'],1):.1%}",
        }
```

---

## 七、本章总结

| 知识点 | 一句话说明 |
|--------|------------|
| **评估维度** | 准确性、完整性、速度、成本 |
| **自动化评估** | LLM 对比标准答案打分 |
| **RAGAS** | RAG 系统的专业评估框架 |
| **优化方向** | Prompt / 工具 / 模型选择 / 成本 |
| **持续监控** | 记录每次调用，关注趋势变化 |

---

## 📝 课后练习

1. **✅ 基础**：为你的 Agent 编写 5 个测试用例，运行自动化评估
2. **💡 改进**：使用 RAGAS 框架评估你的 RAG 系统的检索质量
3. **🚀 挑战**：实现一个 A/B 测试框架，对比两个不同 Prompt 的效果
4. **🔍 探索**：为你的 Agent 添加成本跟踪功能，统计每次对话的平均成本
