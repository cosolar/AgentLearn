"""smoke_test.py —— 离线自检（无需 fastapi / API Key）

只检验与 Web 框架解耦的纯标准库部分：鉴权、限流、SSE 格式化。
运行：python smoke_test.py
"""

from __future__ import annotations

import sys

from security import RateLimiter, verify_api_key
from sse import format_done, format_sse, stream_text, to_sse_stream

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"✅ {name}" + (f"  —— {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"❌ {name}  —— {detail}")


class FakeClock:
    """可推进的假时钟，用于测试限流窗口。"""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def main() -> int:
    # ---------- 鉴权 ----------
    check("① 鉴权：正确 Key 通过", verify_api_key("secret", "secret") is True)
    check("② 鉴权：错误 Key 拒绝", verify_api_key("bad", "secret") is False)
    check("③ 鉴权：None 拒绝", verify_api_key(None, "secret") is False)
    check("④ 鉴权：服务端未配置 Key 时一律拒绝",
          verify_api_key("secret", "") is False)

    # ---------- 限流 ----------
    clock = FakeClock()
    rl = RateLimiter(per_minute=3, window=60.0, clock=clock)
    allowed = [rl.allow("k1") for _ in range(5)]
    check("⑤ 限流：窗口内放行 3 次后拒绝",
          allowed == [True, True, True, False, False], f"实际 {allowed}")
    check("⑥ 限流：remaining() 归零", rl.remaining("k1") == 0,
          f"实际 {rl.remaining('k1')}")

    clock.advance(61)                      # 窗口滑过
    check("⑦ 限流：窗口过期后重新放行", rl.allow("k1") is True)

    check("⑧ 限流：不同 Key 互不影响",
          RateLimiter(per_minute=1, clock=FakeClock()).allow("other") is True)
    rl2 = RateLimiter(per_minute=1, clock=FakeClock())
    rl2.allow("a")
    check("⑧ 限流：Key 之间独立计数", rl2.allow("b") is True)

    # ---------- SSE ----------
    check("⑨ SSE：单行消息格式正确",
          format_sse("hi") == "data: hi\n\n")
    check("⑩ SSE：带 event 字段",
          format_sse("hi", event="message").startswith("event: message\ndata: hi"))
    multi = format_sse("line1\nline2")
    check("⑪ SSE：多行拆成多个 data:",
          multi == "data: line1\ndata: line2\n\n", f"实际 {multi!r}")
    check("⑫ SSE：结束标记",
          format_done() == "data: [DONE]\n\n")
    check("⑬ SSE：带 id 字段",
          "id: 42" in format_sse("x", event_id="42"))

    # ---------- 流式工具 ----------
    text = "这是一段用于演示流式输出的文本。"
    rejoined = "".join(stream_text(text, chunk_size=5))
    check("⑭ 流式：分块后拼接可还原原文", rejoined == text)
    stream = "".join(to_sse_stream(stream_text("abc", chunk_size=2)))
    check("⑮ 流式：SSE 流以 [DONE] 结尾",
          stream.endswith("data: [DONE]\n\n") and stream.count("data:") >= 3)

    print("-" * 60)
    print(f"通过 {PASS}/{PASS + FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
