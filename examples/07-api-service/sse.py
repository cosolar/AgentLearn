"""sse.py —— Server-Sent Events 格式化（纯标准库，可离线测试）

SSE 的报文格式很简单，但有几个**必须记住**的细节：
    - 每条消息以 `\\n\\n`（空行）结束
    - 多行 data 要写成多行 `data:`，接收端会拼接
    - 事件类型用 `event:`，消息 id 用 `id:`
    - 结束标记通常用 `data: [DONE]`

依赖：仅标准库。
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator


def format_sse(data: str, event: str | None = None, event_id: str | None = None) -> str:
    """把一段文本格式化为一条 SSE 消息（含结尾空行）。

    多行文本会被拆成多行 `data:`，符合 SSE 规范。
    """
    lines: list[str] = []
    if event:
        lines.append(f"event: {event}")
    if event_id:
        lines.append(f"id: {event_id}")
    # 规范要求：每一行 data 都要单独加前缀
    for line in data.split("\n"):
        lines.append(f"data: {line}")
    return "\n".join(lines) + "\n\n"


def format_done() -> str:
    """流结束标记。"""
    return "data: [DONE]\n\n"


def stream_text(text: str, chunk_size: int = 8) -> Iterator[str]:
    """把一段文本切成若干块并逐块 yield（模拟流式输出）。

    真实场景中这里换成 Agent 的 token 流（agent.astream(..., stream_mode="messages")）。
    """
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]


def to_sse_stream(chunks: Iterable[str], event: str = "message") -> Iterator[str]:
    """把文本块迭代器转成 SSE 消息流，并在结尾附上 [DONE]。"""
    for chunk in chunks:
        yield format_sse(chunk, event=event)
    yield format_done()
