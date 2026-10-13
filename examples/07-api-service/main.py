"""main.py —— FastAPI 主服务：路由 + 鉴权 + 限流 + 错误契约

对应教程 7.1「FastAPI 主服务」。鉴权与限流逻辑放在 security.py，
SSE 格式化放在 sse.py，二者均为纯标准库，便于离线测试。

运行：
    uv pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from agent import SupportAgent
from config import settings
from schemas import ChatRequest, ChatResponse, ErrorResponse, HealthResponse
from security import RateLimiter, verify_api_key
from sse import format_done, format_sse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("agent-api")

START_TIME = time.time()
agent: SupportAgent | None = None
rate_limiter = RateLimiter(settings.rate_limit_per_minute)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """启动时初始化 Agent，避免每个请求重复加载。"""
    global agent
    logger.info("initializing agent service...")
    agent = SupportAgent()
    logger.info("agent service ready")
    yield
    logger.info("agent service shutting down")


app = FastAPI(title="AI Agent API", version=settings.version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== 请求 ID：贯穿日志与错误响应 =====
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


# ===== 鉴权 + 限流（依赖注入）=====
async def auth_dep(x_api_key: str | None = Header(default=None)) -> str:
    if not verify_api_key(x_api_key, settings.service_api_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid api key")
    return x_api_key  # type: ignore[return-value]


async def rate_limit_dep(api_key: str = Depends(auth_dep)) -> None:
    if not rate_limiter.allow(api_key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate limit exceeded")


def get_agent() -> SupportAgent:
    if agent is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "agent not ready")
    return agent


# ===== 统一错误契约 =====
def _error(request: Request, code: int, error: str, detail: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content=ErrorResponse(
            error=error,
            code=code,
            request_id=getattr(request.state, "request_id", ""),
            detail=detail,
        ).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return _error(request, exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return _error(request, 422, "validation_error", detail=str(exc.errors()))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled error")
    return _error(request, 500, "internal_error")


# ===== 端点 =====
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查（供负载均衡 / K8s 探针使用）。"""
    return HealthResponse(
        status="ok",
        version=settings.version,
        uptime=round(time.time() - START_TIME, 3),
        model=settings.llm_model_name,
    )


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(rate_limit_dep)])
async def chat(body: ChatRequest, request: Request):
    """同步问答（等待完整回答后返回）。"""
    reply = await get_agent().ainvoke(body.message, body.thread_id)
    return ChatResponse(
        reply=reply,
        thread_id=body.thread_id,
        request_id=getattr(request.state, "request_id", ""),
    )


@app.post("/chat/stream", dependencies=[Depends(rate_limit_dep)])
async def chat_stream(body: ChatRequest):
    """流式问答（SSE）。"""

    async def event_gen():
        yield format_sse("", event="start")
        async for piece in get_agent().astream(body.message, body.thread_id):
            yield format_sse(piece, event="message")
        yield format_done()

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
