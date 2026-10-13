"""security.py —— 鉴权与限流（纯标准库，可离线测试）

设计要点：**把安全逻辑与 Web 框架解耦**。
main.py 只负责把它接到 FastAPI 的依赖注入上；本模块不 import fastapi，
因此可以用 `smoke_test.py` 离线验证，也便于复用（CLI / gRPC / 消息队列）。

依赖：仅标准库。
"""

from __future__ import annotations

import hmac
import time
from collections import defaultdict, deque
from typing import Callable


def verify_api_key(provided: str | None, expected: str) -> bool:
    """恒定时间比较，避免时序侧信道。空值一律拒绝。"""
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided, expected)


class RateLimiter:
    """按 Key 的滑动窗口限流。

    - `per_minute`：窗口内允许的最大请求数
    - `window`：窗口长度（秒），默认 60
    - `clock`：可注入的时钟（便于测试；生产用 time.monotonic）

    注意：内存实现只在**单实例**下准确；多实例部署应换成 Redis 等共享存储。
    """

    def __init__(
        self,
        per_minute: int,
        window: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.per_minute = per_minute
        self.window = window
        self.clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """返回 True 表示放行，False 表示超限。"""
        now = self.clock()
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.per_minute:
            return False
        q.append(now)
        return True

    def remaining(self, key: str) -> int:
        """当前窗口内剩余额度（供 X-RateLimit-Remaining 头使用）。"""
        now = self.clock()
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return max(0, self.per_minute - len(q))
