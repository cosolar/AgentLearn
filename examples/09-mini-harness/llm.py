"""llm.py —— 极薄的 LLM 接口与两个后端

设计要点：**Harness 不应该强绑定某个模型 SDK。**

我们只定义一个最小接口：

    class LLMBackend(Protocol):
        def chat(self, messages: list[dict], tools: list[dict]) -> LLMReply: ...

于是：
  - `OpenAIBackend`：真实使用（懒加载 openai SDK，未安装也不影响导入本模块）
  - `FakeLLM`：离线确定性后端，用于验证 Harness 本身
    （这正是 docs 9.11 强调的「评测要能离线跑」）

依赖：仅标准库（真实后端在实例化时才导入 openai）。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class LLMReply:
    """模型返回的标准化结果"""

    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)   # [{"id","name","args"}]
    tokens_in: int = 0
    tokens_out: int = 0


class LLMBackend(Protocol):
    def chat(self, messages: list[dict], tools: list[dict]) -> LLMReply: ...


# ---------------------------------------------------------------- 真实后端

class OpenAIBackend:
    """openai SDK 后端（兼容任何 OpenAI 协议的网关）

    懒加载：只有在真正实例化时才 import openai，
    因此本模块可以在未安装依赖的环境下被导入与测试。
    """

    def __init__(
        self,
        model: str = "gpt-5.5",
        temperature: float = 0.0,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "未安装 openai SDK。请执行 `uv sync`（langchain-openai 会带上它）。"
            ) from exc

        self.model = model
        self.temperature = temperature
        self.client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_API_BASE") or os.getenv("LLM_BASE_URL"),
        )

    def chat(self, messages: list[dict], tools: list[dict]) -> LLMReply:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[self._to_wire(m) for m in messages],
            tools=tools or None,
            temperature=self.temperature,
        )
        choice = resp.choices[0].message
        calls = [
            {
                "id": tc.id,
                "name": tc.function.name,
                # 注意：wire 格式里 arguments 是 JSON 字符串，这里解回 dict
                "args": json.loads(tc.function.arguments or "{}"),
            }
            for tc in (choice.tool_calls or [])
        ]
        usage = getattr(resp, "usage", None)
        return LLMReply(
            content=choice.content or "",
            tool_calls=calls,
            tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_out=getattr(usage, "completion_tokens", 0) or 0,
        )

    # ---------------- 内部：中立格式 → OpenAI wire 格式 ----------------
    @staticmethod
    def _to_wire(m: dict) -> dict:
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            return {
                "role": "assistant",
                "content": m.get("content") or None,
                "tool_calls": [
                    {
                        "id": c["id"],
                        "type": "function",
                        # ✅ 关键：arguments 必须是 JSON **字符串**
                        "function": {
                            "name": c["name"],
                            "arguments": json.dumps(c.get("args", {}), ensure_ascii=False),
                        },
                    }
                    for c in m["tool_calls"]
                ],
            }
        if role == "tool":
            return {
                "role": "tool",
                "tool_call_id": m.get("tool_call_id"),
                "content": m.get("content", ""),
            }
        return {"role": role, "content": m.get("content", "")}


# ---------------------------------------------------------------- 离线后端

class FakeLLM:
    """按脚本回放的离线后端，用于验证 Harness 逻辑（不需要任何 API Key）"""

    def __init__(self, script: list[LLMReply]) -> None:
        self.script = list(script)
        self.calls: list[list[dict]] = []      # 记录每次收到的消息，便于断言
        self.exhausted_reply = LLMReply(content="[脚本已耗尽] 任务结束。")

    def chat(self, messages: list[dict], tools: list[dict]) -> LLMReply:
        self.calls.append(list(messages))
        if self.script:
            reply = self.script.pop(0)
        else:
            reply = self.exhausted_reply
        # 模拟 token 用量，便于验证预算与成本统计
        reply.tokens_in = sum(len(str(m.get("content", ""))) // 2 for m in messages)
        reply.tokens_out = len(reply.content) // 2 + 20 * len(reply.tool_calls)
        return reply


def call(name: str, **args) -> LLMReply:
    """便捷构造：一次只调用一个工具"""
    return LLMReply(tool_calls=[{"id": f"call_{name}_{abs(hash(str(args))) % 10**6}",
                                 "name": name, "args": args}])


def finish(text: str = "已完成。") -> LLMReply:
    """便捷构造：不调用工具（即模型认为完成）"""
    return LLMReply(content=text)
