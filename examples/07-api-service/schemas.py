"""schemas.py —— 请求 / 响应模型与统一错误契约

对应教程 7.1「请求 / 响应模型与错误契约」。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000, description="用户消息")
    thread_id: str = Field(default="default", description="会话 ID（同一 ID 共享记忆）")


class ChatResponse(BaseModel):
    reply: str
    thread_id: str
    request_id: str = ""


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    uptime: float
    model: str


class ErrorResponse(BaseModel):
    """所有错误都返回同一形状，便于客户端统一处理。"""

    error: str
    code: int
    request_id: str = ""
    detail: str | None = None
