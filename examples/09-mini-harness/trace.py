"""trace.py —— 轻量埋点：token / 延迟 / 成本 / 步数

为什么必须有它：
Agent 一次请求往往包含 5~15 次模型调用和若干次工具调用。
没有追踪，等于在黑盒里调试一个非确定性系统。

依赖：仅标准库（不依赖 OpenTelemetry，便于本地验证；
     生产环境请改为 OTel GenAI 语义约定导出，见 docs 9.11）。
"""

from __future__ import annotations

import statistics
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

# 每 1K token 的美元单价（量级示意，请以各厂商官网为准）
PRICING: dict[str, tuple[float, float]] = {
    "gpt-5.5": (0.00125, 0.010),
    "gpt-5-mini": (0.00025, 0.002),
    "claude-sonnet-4-6": (0.003, 0.015),
}


@dataclass
class Step:
    """一条埋点记录"""

    kind: str                    # "llm" | "tool" | "verify" | "context" | "permission"
    name: str
    duration: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    ok: bool = True
    detail: str = ""

    @property
    def tokens(self) -> int:
        return self.tokens_in + self.tokens_out


@dataclass
class Trace:
    """一次完整运行的轨迹"""

    steps: list[Step] = field(default_factory=list)
    t0: float = field(default_factory=time.time)
    terminated_by: str = "unknown"

    # ---------- 聚合指标 ----------
    @property
    def llm_calls(self) -> int:
        return sum(1 for s in self.steps if s.kind == "llm")

    @property
    def tool_calls(self) -> int:
        return sum(1 for s in self.steps if s.kind == "tool")

    @property
    def total_tokens(self) -> int:
        return sum(s.tokens for s in self.steps)

    @property
    def tool_error_rate(self) -> float:
        if self.tool_calls == 0:
            return 0.0
        bad = sum(1 for s in self.steps if s.kind == "tool" and not s.ok)
        return round(bad / self.tool_calls, 3)

    def cost(self, model: str) -> float:
        pin, pout = PRICING.get(model, (0.001, 0.003))
        tin = sum(s.tokens_in for s in self.steps)
        tout = sum(s.tokens_out for s in self.steps)
        return round(tin / 1000 * pin + tout / 1000 * pout, 6)

    def summary(self, model: str) -> dict:
        lat = sorted(s.duration for s in self.steps) or [0.0]
        p95 = lat[min(int(len(lat) * 0.95), len(lat) - 1)]
        return {
            "turns": self.llm_calls,
            "tool_calls": self.tool_calls,
            "tokens": self.total_tokens,
            "cost_usd": self.cost(model),
            "wall_seconds": round(time.time() - self.t0, 2),
            "p50_latency": round(statistics.median(lat), 3),
            "p95_latency": round(p95, 3),
            "tool_error_rate": self.tool_error_rate,
            "terminated_by": self.terminated_by,
        }

    def report(self, model: str) -> str:
        s = self.summary(model)
        return (f"⏱  {s['wall_seconds']}s | 模型调用 {s['turns']} | 工具调用 {s['tool_calls']} "
                f"| tokens {s['tokens']} | 成本 ${s['cost_usd']:.5f} "
                f"| 工具错误率 {s['tool_error_rate']:.0%} | 终止原因 {s['terminated_by']}")


class Tracer:
    """埋点收集器：用法 with tracer.span("llm", "chat"): ..."""

    def __init__(self) -> None:
        self.trace = Trace()

    @contextmanager
    def span(self, kind: str, name: str, tokens_in: int = 0, tokens_out: int = 0):
        start = time.time()
        entry = Step(kind=kind, name=name, tokens_in=tokens_in, tokens_out=tokens_out)
        try:
            yield entry
        except Exception as exc:                     # noqa: BLE001 - 埋点必须记录一切失败
            entry.ok = False
            entry.detail = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            entry.duration = time.time() - start
            self.trace.steps.append(entry)

    def event(self, name: str, **detail) -> None:
        """记录一个瞬时事件（无耗时）"""
        self.trace.steps.append(Step(kind=name.split(".")[0], name=name,
                                     duration=0.0, detail=str(detail)))

    def finish(self, reason: str) -> None:
        self.trace.terminated_by = reason
