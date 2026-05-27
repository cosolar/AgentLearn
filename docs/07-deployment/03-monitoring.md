# 7.3 监控与日志 —— 让 Agent 运行状态一目了然

## 📖 导读

> **没有监控的线上系统，就像没有仪表盘的飞机——你飞在天上，但不知道高度、速度和油量。**

Agent 上线后，你需要知道：它在正常运行吗？回答质量如何？响应快不快？成本高不高？出错多不多？本章将构建一个**完整的监控体系**，覆盖日志、指标、链路追踪和告警。

---

## 一、前置知识

| 概念 | 说明 |
|------|------|
| 日志（Logging） | 记录事件的文本信息 |
| 指标（Metrics） | 可量化的数值数据 |
| 链路追踪（Tracing） | 追踪请求的完整路径 |
| 告警（Alerting） | 异常时通知负责人 |

---

## 二、监控体系架构

```text
┌─────────────────────────────────────────────────────┐
│                      监控体系                          │
├─────────┬─────────────┬──────────────┬──────────────┤
│  日志    │    指标      │   链路追踪     │    告警      │
├─────────┼─────────────┼──────────────┼──────────────┤
│ 请求日志 │ Token 消耗   │ 请求→思考→工具 │ 错误率过高    │
│ 错误日志 │ 响应延迟     │ →回答 全流程  │ 延迟超阈值    │
│ 审计日志 │ QPS/并发    │              │ 成本超预算    │
│ 工具日志 │ 成本统计    │              │ 服务宕机      │
└─────────┴─────────────┴──────────────┴──────────────┘
```

---

## 三、日志系统

### 3.1 结构化日志

```python
import json
import logging
from datetime import datetime
from typing import Dict, Any


class StructuredLogger:
    """结构化日志：不再是纯文本，而是 JSON 格式"""
    
    def __init__(self, name: str = "agent"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # 添加 JSON 格式化器
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        self.logger.addHandler(handler)
    
    def log_request(self, session_id: str, message: str):
        self._log("request", {
            "session_id": session_id,
            "message_length": len(message),
        })
    
    def log_response(self, session_id: str, response: str, latency: float):
        self._log("response", {
            "session_id": session_id,
            "response_length": len(response),
            "latency_ms": round(latency * 1000, 2),
        })
    
    def log_tool_call(self, session_id: str, tool: str, args: dict, result: str):
        self._log("tool_call", {
            "session_id": session_id,
            "tool": tool,
            "args": args,
            "result_preview": result[:100],
        })
    
    def log_error(self, session_id: str, error: str, traceback: str = ""):
        self._log("error", {
            "session_id": session_id,
            "error": error,
            "traceback": traceback[:200],
        })
    
    def log_cost(self, session_id: str, model: str, tokens: int, cost: float):
        self._log("cost", {
            "session_id": session_id,
            "model": model,
            "tokens": tokens,
            "cost_usd": round(cost, 6),
        })
    
    def _log(self, event_type: str, data: Dict[str, Any]):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": event_type,
            **data,
        }
        self.logger.info(json.dumps(log_entry))


class JsonFormatter(logging.Formatter):
    """JSON 日志格式化器"""
    def format(self, record):
        return record.getMessage()


# 使用
logger = StructuredLogger()
logger.log_request("session_001", "什么是 RAG？")
```

### 3.2 日志级别

```python
import logging

# 不同级别的使用场景
logging.debug("模型输入输出详细内容")        # DEBUG: 调试用，生产关掉
logging.info("用户请求: session=abc")         # INFO: 常规信息
logging.warning("API 响应慢，耗时 5.2s")      # WARNING: 需要关注但不紧急
logging.error("LLM 调用失败: timeout")        # ERROR: 功能受损
logging.critical("知识库不可用")              # CRITICAL: 系统不可用
```

### 3.3 日志最佳实践

```python
# ✅ 好的：结构化、可搜索
logger.info(json.dumps({
    "event": "llm_call",
    "model": "gpt-4o",
    "input_tokens": 500,
    "output_tokens": 200,
    "latency_ms": 1500,
}))

# ❌ 差的：纯文本、难以解析
logger.info("调用 GPT-4o，输入 500 tokens，输出 200 tokens，耗时 1.5s")
```

---

## 四、指标监控

### 4.1 核心指标

```python
import time
from functools import wraps
from collections import defaultdict
from statistics import mean, median


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """重置所有指标"""
        self.request_count = 0
        self.error_count = 0
        self.token_counts = []
        self.latencies = []
        self.costs = []
        self.tool_calls = defaultdict(int)
        self.models_used = defaultdict(int)
    
    def record_request(self, latency: float, success: bool):
        """记录一次请求"""
        self.request_count += 1
        self.latencies.append(latency)
        if not success:
            self.error_count += 1
    
    def record_tokens(self, model: str, input_tokens: int, output_tokens: int):
        """记录 Token 消耗"""
        self.token_counts.append(input_tokens + output_tokens)
        self.models_used[model] += 1
        # 简化成本计算
        cost = (input_tokens * 0.000005 + output_tokens * 0.000015)
        self.costs.append(cost)
    
    def record_tool_call(self, tool_name: str):
        """记录工具调用"""
        self.tool_calls[tool_name] += 1
    
    def get_stats(self) -> dict:
        """获取统计摘要"""
        n = self.request_count
        if n == 0:
            return {"status": "no_data"}
        
        return {
            "total_requests": n,
            "error_rate": f"{self.error_count / n:.2%}",
            "avg_latency_ms": f"{mean(self.latencies) * 1000:.1f}",
            "p50_latency_ms": f"{median(self.latencies) * 1000:.1f}",
            "p95_latency_ms": f"{sorted(self.latencies)[int(n * 0.95)] * 1000:.1f}",
            "avg_tokens": int(mean(self.token_counts)) if self.token_counts else 0,
            "total_cost_usd": f"{sum(self.costs):.4f}",
            "tool_calls": dict(self.tool_calls),
            "models_used": dict(self.models_used),
        }


# 全局指标采集器
metrics = MetricsCollector()


def monitor(func):
    """监控装饰器：自动采集函数调用指标"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        success = True
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            success = False
            raise
        finally:
            latency = time.time() - start
            metrics.record_request(latency, success)
    return wrapper
```

### 4.2 Prometheus 集成

```python
# 安装: pip install prometheus-client

from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import FastAPI, Response

# 定义指标
REQUESTS_TOTAL = Counter(
    "agent_requests_total", "总请求数",
    ["model", "status"],  # 标签维度
)

LATENCY_HISTOGRAM = Histogram(
    "agent_request_duration_seconds", "请求延迟（秒）",
    ["model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

TOKEN_COUNTER = Counter(
    "agent_tokens_total", "Token 消耗",
    ["model", "type"],  # type: input / output
)

ACTIVE_REQUESTS = Gauge(
    "agent_active_requests", "当前处理中的请求数"
)

ERRORS_TOTAL = Counter(
    "agent_errors_total", "错误数",
    ["error_type"],
)

# 在 FastAPI 中暴露指标
app = FastAPI()

@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus 指标端点"""
    return Response(content=generate_latest(), media_type="text/plain")

# 使用中间件自动采集
@app.middleware("http")
async def metrics_middleware(request, call_next):
    ACTIVE_REQUESTS.inc()
    start = time.time()
    
    response = await call_next(request)
    
    latency = time.time() - start
    LATENCY_HISTOGRAM.observe(latency)
    REQUESTS_TOTAL.labels(
        model="gpt-4o-mini",
        status=response.status_code,
    ).inc()
    
    ACTIVE_REQUESTS.dec()
    return response
```

---

## 五、链路追踪

```python
import uuid
from contextvars import ContextVar
from datetime import datetime


# 每个请求的追踪 ID
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


class Tracer:
    """简单链路追踪器"""
    
    def __init__(self):
        self.spans = []
    
    def start_trace(self) -> str:
        """开始一个新的追踪"""
        trace_id = str(uuid.uuid4())[:8]
        trace_id_var.set(trace_id)
        self.spans = []
        return trace_id
    
    def add_span(self, name: str, metadata: dict = None):
        """添加一个追踪节点"""
        self.spans.append({
            "trace_id": trace_id_var.get(),
            "span": name,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        })
    
    def get_trace(self) -> list:
        """获取完整追踪链路"""
        return self.spans


# 使用示例
def process_request(message: str):
    tracer = Tracer()
    trace_id = tracer.start_trace()
    
    # 阶段 1: 理解问题
    tracer.add_span("understand_query", {"query_length": len(message)})
    
    # 阶段 2: 检索知识库
    tracer.add_span("retrieve_knowledge", {"retriever": "chroma"})
    
    # 阶段 3: 调用 LLM
    tracer.add_span("llm_call", {"model": "gpt-4o", "tokens": 500})
    
    # 阶段 4: 生成回答
    tracer.add_span("generate_response", {"response_length": 300})
    
    return trace_id, tracer.get_trace()
```

---

## 六、完整的监控中间件

```python
import time
import logging
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware


class MonitoringMiddleware(BaseHTTPMiddleware):
    """监控中间件：自动采集每个请求的指标"""
    
    async def dispatch(self, request: Request, call_next):
        # 开始计时
        start_time = time.time()
        
        # 请求处理
        response = await call_next(request)
        
        # 计算延迟
        latency = time.time() - start_time
        
        # 采集指标
        path = request.url.path
        method = request.method
        status = response.status_code
        
        REQUESTS_TOTAL.labels(model="gpt-4o-mini", status=status).inc()
        LATENCY_HISTOGRAM.observe(latency)
        
        # 日志
        logger.info(json.dumps({
            "event": "request",
            "path": path,
            "method": method,
            "status": status,
            "latency_ms": round(latency * 1000, 2),
        }))
        
        return response


# 添加到应用
app.add_middleware(MonitoringMiddleware)
```

---

## 七、告警配置

```python
class AlertManager:
    """简单的告警管理器"""
    
    def __init__(self):
        self.thresholds = {
            "error_rate": 0.05,          # 5% 错误率触发
            "p95_latency": 5.0,          # P95 延迟超过 5 秒
            "cost_per_hour": 10.0,       # 每小时成本超过 $10
        }
        self.alerts = []
    
    def check(self, metrics: dict) -> list:
        """检查是否需要告警"""
        alerts = []
        
        # 错误率检查
        error_rate = float(metrics.get("error_rate", "0%").rstrip("%")) / 100
        if error_rate > self.thresholds["error_rate"]:
            alerts.append({
                "level": "critical",
                "message": f"错误率 {error_rate:.1%} 超过阈值 {self.thresholds['error_rate']:.1%}",
            })
        
        # 延迟检查
        p95 = float(metrics.get("p95_latency_ms", "0").rstrip("ms"))
        if p95 / 1000 > self.thresholds["p95_latency"]:
            alerts.append({
                "level": "warning",
                "message": f"P95 延迟 {p95}ms 超过阈值 {self.thresholds['p95_latency']*1000}ms",
            })
        
        self.alerts.extend(alerts)
        return alerts
```

---

## 八、本章总结

| 组件 | 工具/方法 | 说明 |
|------|-----------|------|
| **日志** | JSON 结构化日志 | 方便搜索和分析 |
| **指标** | Prometheus + Grafana | 延迟、QPS、成本可视化 |
| **追踪** | 自定义 Tracer | 追踪请求全链路 |
| **告警** | 阈值检查 + 通知 | 异常时及时响应 |
| **监控端点** | `/health` + `/metrics` | 外部监控系统集成 |

---

## 📝 课后练习

1. **✅ 基础**：为你的 Agent 添加结构化日志，查看 JSON 格式的输出
2. **💡 改进**：添加 Prometheus 指标端点，在 Grafana 中可视化延迟和请求量
3. **🚀 挑战**：实现完整的请求追踪，记录"用户输入→检索→LLM→输出"每个阶段的耗时
4. **🔍 探索**：部署 Prometheus + Grafana，配置一个有意义的监控面板
