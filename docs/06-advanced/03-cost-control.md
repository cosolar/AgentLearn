# 6.3 成本控制策略 —— 花最少的钱，做最好的 Agent

## 📖 导读

> **LLM API 是按 Token 计费的。一个不加控制的 Agent，一天可能烧掉几百美元的成本。**

成本控制是 Agent 从"实验"走向"生产"时必须面对的挑战。有效的成本管理不是简单地限制使用，而是**在质量和成本之间找到最佳平衡**。本章将系统讲解 LLM 的成本构成、测量方法和优化策略。

---

## 一、成本构成

### 1.1 API 计费模型

```text
每次 API 调用的费用 = 
    输入 Token 数 × 输入单价 +
    输出 Token 数 × 输出单价

示例（GPT-4o）：
输入：500 tokens × $0.005/1K tokens = $0.0025
输出：200 tokens × $0.015/1K tokens = $0.0030
总费用：$0.0055 ≈ 0.04 元
```

### 1.2 主流模型价格对比

| 模型 | 输入价格 ($/1K tokens) | 输出价格 ($/1K tokens) | 相对成本 |
|------|----------------------|-----------------------|----------|
| **GPT-4o** | $0.005 | $0.015 | 高 |
| **GPT-4o-mini** | $0.00015 | $0.0006 | ⭐ 极低 |
| **GPT-3.5-turbo** | $0.0015 | $0.002 | 中 |
| **Claude-3-Haiku** | $0.00025 | $0.00125 | ⭐ 低 |
| **Claude-3-Sonnet** | $0.003 | $0.015 | 中高 |

> 💡 **GPT-4o-mini 比 GPT-4o 便宜 30 倍**，在很多场景下效果已经足够好。

### 1.3 成本来源分析

```text
Agent 系统的成本构成：

                    ┌──────────────────────┐
                    │    LLM 调用 (70-80%)   │
                    │    ┌──────────────┐   │
                    │    │ System Prompt │   │ ← 每次调用都包含
                    │    │ Context/记忆  │   │ ← 随着对话增长
                    │    │ Agent 思考过程│   │ ← ReAct 循环
                    │    │ 输出内容      │   │ ← 最终回答
                    │    └──────────────┘   │
                    ├──────────────────────┤
                    │  Embedding (5-10%)   │ ← 文档索引
                    ├──────────────────────┤
                    │  向量存储 (5-10%)    │ ← 数据库服务
                    ├──────────────────────┤
                    │  搜索 API (5-10%)    │ ← 外部工具
                    └──────────────────────┘
```

---

## 二、成本测量

```python
import tiktoken


class CostCalculator:
    """Token 和成本计算器"""
    
    MODEL_PRICING = {
        "gpt-4o":           {"input": 0.005, "output": 0.015},
        "gpt-4o-mini":      {"input": 0.00015, "output": 0.0006},
        "gpt-3.5-turbo":    {"input": 0.0015, "output": 0.002},
        "text-embedding-3-small": {"input": 0.00002, "output": 0.0},
    }
    
    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self.pricing = self.MODEL_PRICING.get(model, {"input": 0.01, "output": 0.03})
    
    def count_tokens(self, text: str) -> int:
        """统计文本的 token 数"""
        try:
            encoding = tiktoken.encoding_for_model(self.model)
            return len(encoding.encode(text))
        except:
            # 备用估算：中文 2 token/字，英文 1 token/字
            return int(len(text) * 1.5)
    
    def calculate_cost(self, input_text: str, output_text: str) -> dict:
        """计算单次调用的成本"""
        input_tokens = self.count_tokens(input_text)
        output_tokens = self.count_tokens(output_text)
        
        input_cost = (input_tokens / 1000) * self.pricing["input"]
        output_cost = (output_tokens / 1000) * self.pricing["output"]
        
        return {
            "model": self.model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "input_cost_usd": round(input_cost, 6),
            "output_cost_usd": round(output_cost, 6),
            "total_cost_usd": round(input_cost + output_cost, 6),
        }
    
    def estimate_monthly_cost(self, daily_queries: int, avg_input: int, avg_output: int) -> dict:
        """估算月成本"""
        per_query = self.calculate_cost("x" * avg_input, "x" * avg_output)
        daily = per_query["total_cost_usd"] * daily_queries
        monthly = daily * 30
        
        return {
            "per_query": per_query["total_cost_usd"],
            "daily_cost": round(daily, 2),
            "monthly_cost": round(monthly, 2),
            "annual_cost": round(monthly * 12, 2),
        }


# 使用
calc = CostCalculator("gpt-4o")

# 算一次对话的成本
dialog_cost = calc.calculate_cost(
    input_text="你是一个AI助手。用户：什么是RAG？",
    output_text="RAG是检索增强生成...",
)
print(f"单次对话: ${dialog_cost['total_cost_usd']:.6f}")

# 预估月成本
monthly = calc.estimate_monthly_cost(
    daily_queries=1000,
    avg_input=1000,
    avg_output=500,
)
print(f"月成本预估: ${monthly['monthly_cost']}")
```

---

## 三、成本优化策略

### 3.1 策略一：模型选择

```python
class SmartModelRouter:
    """智能模型路由：根据任务复杂度选择模型"""
    
    def __init__(self):
        self.cheap_model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.expensive_model = ChatOpenAI(model="gpt-4o", temperature=0)
    
    def classify_task(self, task: str) -> str:
        """判断任务复杂度"""
        simple_patterns = [
            "你好", "hi", "hello", "再见",
            "你是谁", "谢谢",
            "翻译", "总结", "分类",
        ]
        
        for pattern in simple_patterns:
            if pattern in task.lower():
                return "simple"
        
        complex_patterns = [
            "分析", "对比", "推理", "代码",
            "计算", "规划", "生成报告",
        ]
        
        for pattern in complex_patterns:
            if pattern in task.lower():
                return "complex"
        
        # 默认用长度判断
        if len(task) < 20:
            return "simple"
        return "complex"
    
    def get_model(self, task: str):
        """根据任务选择合适的模型"""
        complexity = self.classify_task(task)
        
        if complexity == "simple":
            return self.cheap_model
        else:
            return self.expensive_model
```

### 3.2 策略二：Token 压缩

```python
class TokenCompressor:
    """Token 压缩器：减少不必要的 token 消耗"""
    
    def compress_memory(self, history: list, max_tokens: int = 2000) -> list:
        """压缩对话历史"""
        total = 0
        compressed = []
        
        for msg in reversed(history):
            tokens = len(msg.content) * 1.5  # 估算
            if total + tokens > max_tokens:
                # 添加一个压缩提示
                compressed.insert(0, {
                    "role": "system",
                    "content": f"[早期对话摘要: {len(history)} 轮前的历史...]"
                })
                break
            compressed.insert(0, msg)
            total += tokens
        
        return compressed
    
    def shorten_prompt(self, prompt: str, max_length: int = 2000) -> str:
        """缩短过长 Prompt"""
        if len(prompt) <= max_length:
            return prompt
        return prompt[:max_length - 100] + "\n...(截断)..."
    
    def remove_redundant_context(self, messages: list) -> list:
        """移除冗余的上下文（如重复的系统提示）"""
        seen_system = False
        cleaned = []
        
        for msg in messages:
            if msg["role"] == "system":
                if not seen_system:
                    cleaned.append(msg)
                    seen_system = True
            else:
                cleaned.append(msg)
        
        return cleaned
```

### 3.3 策略三：缓存

```python
import hashlib
import json
from functools import lru_cache


class ResponseCache:
    """智能缓存：避免重复的 LLM 调用"""
    
    def __init__(self, max_size: int = 1000):
        self.cache = {}
        self.max_size = max_size
    
    def _make_key(self, prompt: str, model: str) -> str:
        """生成缓存 key"""
        return hashlib.md5(f"{prompt}:{model}".encode()).hexdigest()
    
    def get(self, prompt: str, model: str) -> str | None:
        """获取缓存"""
        key = self._make_key(prompt, model)
        return self.cache.get(key)
    
    def set(self, prompt: str, model: str, response: str):
        """设置缓存"""
        key = self._make_key(prompt, model)
        self.cache[key] = response
        
        # LRU 淘汰
        if len(self.cache) > self.max_size:
            # 移除最早的 key
            oldest = next(iter(self.cache))
            del self.cache[oldest]
    
    def get_stats(self) -> dict:
        return {
            "cache_size": len(self.cache),
            "max_size": self.max_size,
        }


# 带缓存的 LLM 调用
class CachedLLM:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model)
        self.cache = ResponseCache()
        self.hit_count = 0
        self.miss_count = 0
    
    def invoke(self, prompt: str) -> str:
        cached = self.cache.get(prompt, self.llm.model)
        if cached:
            self.hit_count += 1
            return cached
        
        self.miss_count += 1
        response = self.llm.invoke(prompt)
        self.cache.set(prompt, self.llm.model, response.content)
        return response.content
    
    def cache_hit_rate(self) -> float:
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0
```

### 3.4 策略四：限制输出长度

```python
# 在 Prompt 中指定输出长度
SYSTEM_PROMPTS = {
    "简洁模式": "回答控制在 50 字以内，只给出核心答案。",
    "标准模式": "回答控制在 200 字以内，包含关键信息。",
    "详细模式": "回答控制在 500 字以内，提供完整解释。",
}

# 使用 max_tokens 参数
def chat_with_token_limit(question: str, mode: str = "standard") -> str:
    """带 Token 上限的对话"""
    max_output = {
        "concise": 100,
        "standard": 300,
        "detailed": 800,
    }
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        max_tokens=max_output.get(mode, 300),  # 关键参数！
    )
    return llm.invoke(question)
```

---

## 四、成本优化对比

| 策略 | 降低成本 | 实现难度 | 对质量影响 |
|------|---------|----------|-----------|
| **用小模型** | 60-90% | ⭐ 低 | 小任务几乎无影响 |
| **Token 压缩** | 20-40% | ⭐⭐ 中 | 可能会丢失细节 |
| **缓存** | 30-70% | ⭐⭐ 中 | 无影响 |
| **限制输出** | 10-30% | ⭐ 低 | 信息量减少 |
| **批量处理** | 10-20% | ⭐⭐⭐ 高 | 无影响 |

---

## 五、成本监控面板

```python
class CostDashboard:
    """成本监控仪表盘"""
    
    def __init__(self):
        self.logs = []
    
    def log_call(self, model: str, input_tokens: int, output_tokens: int, 
                 task: str, success: bool):
        """记录一次 API 调用"""
        self.logs.append({
            "timestamp": "...",
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "task": task,
            "success": success,
        })
    
    def get_daily_report(self) -> dict:
        """生成日报"""
        total_tokens = sum(l["input_tokens"] + l["output_tokens"] for l in self.logs)
        total_cost = sum(self._calculate_cost(l) for l in self.logs)
        
        # 按模型分组
        by_model = {}
        for log in self.logs:
            model = log["model"]
            if model not in by_model:
                by_model[model] = {"calls": 0, "tokens": 0}
            by_model[model]["calls"] += 1
            by_model[model]["tokens"] += log["input_tokens"] + log["output_tokens"]
        
        return {
            "total_calls": len(self.logs),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "by_model": by_model,
        }
    
    def _calculate_cost(self, log: dict) -> float:
        # 简化计算
        return (log["input_tokens"] + log["output_tokens"]) * 0.00001
```

---

## 六、本章总结

| 要点 | 建议 |
|------|------|
| **模型选择** | 简单任务用 GPT-4o-mini，复杂任务用 GPT-4o |
| **Token 压缩** | 减少不必要的上下文，压缩 Prompt |
| **缓存重复查询** | 相同的提问直接返回缓存结果 |
| **限制输出长度** | 设置 max_tokens，按需控制输出 |
| **监控和预警** | 实时跟踪 Token 消耗和费用 |

---

## 📝 课后练习

1. **✅ 基础**：用 tiktoken 统计你一段对话的 token 数，计算成本
2. **💡 改进**：为你的 Agent 添加缓存功能，测试缓存命中率
3. **🚀 挑战**：实现一个"智能模型路由"，根据问题复杂度选择 GPT-4o 或 GPT-4o-mini
4. **🔍 探索**：对比优化前后（使用缓存+小模型+限制输出）的月成本估算
