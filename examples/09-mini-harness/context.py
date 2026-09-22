"""context.py —— 上下文预算管理与压缩

目标（Anthropic 的定义）：
    找到最小的一组高信号 token，把达成期望结果的概率最大化。

三层策略：
    ① Observation 屏蔽  —— 保留工具调用本身，隐藏冗长的旧输出
    ② 摘要压缩          —— 保留决策与未解决问题，丢弃冗余过程
    ③ 硬裁剪            —— 兜底的 token 上限保护

依赖：仅标准库；tiktoken 若可用则用精确计数，否则用启发式估算。
"""

from __future__ import annotations

from typing import Callable

from config import HarnessConfig
from trace import Tracer

# ---------------------------------------------------------------- 计数

try:  # pragma: no cover - 取决于运行环境
    import tiktoken

    _ENC = tiktoken.get_encoding("cl100k_base")
    TOKENIZER = "tiktoken:cl100k_base"

    def count_tokens(text: str) -> int:
        return len(_ENC.encode(text))

except Exception:  # noqa: BLE001
    TOKENIZER = "heuristic:len/2"

    def count_tokens(text: str) -> int:
        """粗略估算：中文约 1.5 字符/token，英文约 4 字符/token，取折中值 2"""
        return max(1, len(text) // 2)


MASKED = "[旧工具输出已屏蔽]"


class ContextManager:
    def __init__(
        self,
        cfg: HarnessConfig,
        tracer: Tracer,
        summarizer: Callable[[list[dict]], str] | None = None,
    ) -> None:
        self.cfg = cfg
        self.tracer = tracer
        self.summarizer = summarizer      # 传入 LLM 摘要函数即可启用真摘要
        self.summary: str = ""            # 滚动摘要（结构化草稿本）

    # ---------------- 计数 ----------------
    def count(self, messages: list[dict]) -> int:
        return sum(count_tokens(self._text_of(m)) for m in messages)

    @staticmethod
    def _text_of(m: dict) -> str:
        parts = [str(m.get("content", ""))]
        for c in m.get("tool_calls", []) or []:
            parts.append(f"{c.get('name')}{c.get('args')}")
        return " ".join(parts)

    # ---------------- 主入口 ----------------
    def maybe_compress(self, messages: list[dict]) -> list[dict]:
        before = self.count(messages)
        if before < self.cfg.context_soft_limit:
            return messages

        self.tracer.event("context.compress.trigger", tokens=before)

        # ① Observation 屏蔽
        messages = self._mask_old_tool_outputs(messages)
        after_mask = self.count(messages)
        if after_mask < self.cfg.context_soft_limit:
            self.tracer.event("context.mask", before=before, after=after_mask)
            return messages

        # ② 摘要压缩
        messages = self._summarize(messages)
        self.tracer.event("context.summarize",
                          before=after_mask, after=self.count(messages))
        return messages

    # ---------------- 策略 ① ----------------
    def _mask_old_tool_outputs(self, messages: list[dict]) -> list[dict]:
        keep = self.cfg.keep_recent_messages
        if len(messages) <= keep + 1:
            return messages
        head, middle, recent = messages[0], messages[1:-keep], messages[-keep:]
        masked: list[dict] = []
        for m in middle:
            if m.get("role") == "tool" and len(str(m.get("content", ""))) > 200:
                masked.append({**m, "content": MASKED})
            else:
                masked.append(m)
        return [head, *masked, *recent]

    # ---------------- 策略 ② ----------------
    def _summarize(self, messages: list[dict]) -> list[dict]:
        keep = self.cfg.keep_recent_messages
        if len(messages) <= keep + 1:
            return messages
        head, middle, recent = messages[0], messages[1:-keep], messages[-keep:]

        if self.summarizer is not None:
            new_summary = self.summarizer(middle)
            self.summary = (self.summary + "\n" + new_summary).strip()
        else:
            # 离线兜底：不调用模型，直接丢弃中段并留下标记
            self.summary = (self.summary + f"\n[已裁剪 {len(middle)} 条历史]").strip()

        return [
            head,
            {"role": "system", "content": f"[历史摘要]\n{self.summary}"},
            *recent,
        ]
