# 7.1 API 服务部署 —— 把 Agent 变成一个真正的后端服务

> 📅 更新至 2026-10 · 技术栈基线见 [教程大纲](../教程大纲.md)

## 📖 导读

> **交互式脚本里的 Agent 只是玩具。真正的产品是一个 7×24 小时运行、能并发、能鉴权、能限流的后端服务。**

本章把 `create_agent` 构建的 Agent 封装成**标准 REST API**：用 **FastAPI** 提供 HTTP 接口，用 **SSE** 做流式输出，并补齐**鉴权、限流、错误契约**三块生产必备能力。前端、移动端、其他微服务都能以语言无关的方式调用。

---

## 一、前置知识

| 概念 | 说明 |
|------|------|
| REST API | 基于 HTTP 的接口设计风格 |
| FastAPI | 高性能异步 Web 框架，自动生成文档 |
| Pydantic / pydantic-settings | 数据校验 / 配置管理 |
| Uvicorn | ASGI 服务器 |
| SSE | Server-Sent Events，服务端单向流式推送 |

---

## 二、为什么封装成 API 服务

```text
❌ 直接分发脚本：
用户 → 你的代码 → LangChain → LLM
        需要装 Python、配环境、带 API Key；代码耦合、无法并发

✅ 封装成 API：
用户 / 前端 → HTTP → FastAPI 服务 → Agent → LLM
             统一接口 · 语言无关 · 高并发 · 可监控 · 可鉴权
```

---

## 三、项目结构

> 📌 本章代码即完整示例，可直接复制为独立项目；仓库中也提供了可直接运行的版本：[`examples/07-api-service/`](../../examples/07-api-service/)（含 **16 项离线自检**）。

```text
agent-api/
├── main.py            # FastAPI 入口（路由、中间件、错误契约）
├── agent.py           # Agent 核心（create_agent + 异步/流式）
├── schemas.py         # 请求/响应模型
├── config.py          # 配置（pydantic-settings，读取 LLM_*）
├── security.py        # 鉴权 + 限流（纯标准库，可离线测试）
├── sse.py             # SSE 报文格式化（纯标准库）
├── smoke_test.py      # 离线自检（无需 fastapi / API Key）
├── requirements.txt   # 依赖
└── .env               # 环境变量（勿提交）
```

> 💡 **为什么把 `security.py` / `sse.py` 单独拆出来？** 它们不依赖任何 Web 框架，好处有三：① 可**离线单测**（`python smoke_test.py` 无需安装 fastapi）；② 可**复用**到 CLI / gRPC / 消息队列；③ 限流时钟可注入，测试不必真等 60 秒。这也是"Web 层与核心逻辑解耦"的一个具体落点。

---

## 四、配置：统一读取 `LLM_*`

```python
# config.py
"""应用配置：pydantic-settings 自动读取环境变量 / .env"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """字段名小写，自动映射到同名大写环境变量（LLM_MODEL_NAME 等）"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 模型配置（与教程统一约定）
    llm_model_name: str = "gpt-5.5"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"

    # 服务配置
    service_api_key: str = "change-me"       # 客户端调用本服务所需的 Key
    rate_limit_per_minute: int = 60
    cors_origins: list[str] = ["*"]


settings = Settings()
```

---

## 五、请求 / 响应模型与错误契约

```python
# schemas.py
"""请求 / 响应模型：Pydantic 自动校验并生成文档"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """聊天请求"""

    message: str = Field(..., min_length=1, max_length=4000, description="用户消息")
    session_id: str | None = Field(None, description="会话 ID，不传则新建")


class SourceInfo(BaseModel):
    """引用来源"""

    title: str
    content: str
    score: float = 0.0


class ChatResponse(BaseModel):
    """聊天响应"""

    session_id: str
    message: str
    sources: list[SourceInfo] | None = None
    processing_time: float


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str
    version: str
    uptime: float
    model: str


class ErrorResponse(BaseModel):
    """统一错误契约：所有非 2xx 响应都遵循此结构"""

    error: str
    code: int
    request_id: str
    detail: str | None = None
```

> 💡 **错误契约的价值**：客户端只需按 `{error, code, request_id, detail}` 解析错误，配合 `X-Request-ID` 可一键定位服务端日志。

---

## 六、Agent 核心：`create_agent` + 异步 / 流式

```python
# agent.py
"""Agent 核心：基于 LangChain v1 的 create_agent，支持异步与流式"""
from __future__ import annotations

from collections.abc import AsyncIterator

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from config import settings


@tool
def search_knowledge_base(query: str) -> str:
    """在知识库中检索与问题相关的资料，返回匹配片段。"""
    # 演示用内存知识库；真实项目替换为 Chroma / 向量库检索
    kb = {
        "退款": "退款将在 7 个工作日内原路退回。",
        "发票": "订单完成后可申请发票，电子发票 24 小时内开具。",
        "物流": "默认顺丰发货，48 小时内发出。",
    }
    hits = [text for key, text in kb.items() if key in query]
    return "\n".join(hits) if hits else "未找到相关信息"


class SupportAgent:
    """客服 Agent：create_agent 封装，内置工具循环与会话记忆"""

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            model=settings.llm_model_name,
            api_key=settings.llm_api_key or None,
            base_url=settings.llm_base_url or None,
            temperature=0.3,
        )
        self.checkpointer = InMemorySaver()  # 生产环境换成 PostgresSaver
        self.agent = create_agent(
            model=self.llm,
            tools=[search_knowledge_base],
            system_prompt=(
                "你是智能客服助手，基于知识库检索结果回答问题。\n"
                "要求：1) 只基于检索到的信息回答；"
                "2) 不确定时回复“未找到相关信息”；3) 引用来源。"
            ),
            checkpointer=self.checkpointer,
        )

    @staticmethod
    def _config(thread_id: str) -> dict:
        """thread_id 即会话 ID，同一 thread 自动保持记忆"""
        return {"configurable": {"thread_id": thread_id}}

    async def answer(self, question: str, thread_id: str) -> str:
        """异步一次性回答"""
        result = await self.agent.ainvoke(
            {"messages": [{"role": "user", "content": question}]},
            self._config(thread_id),
        )
        return result["messages"][-1].content

    async def astream(self, question: str, thread_id: str) -> AsyncIterator[str]:
        """流式产出增量文本（用于 SSE）"""
        async for chunk in self.agent.astream(
            {"messages": [{"role": "user", "content": question}]},
            self._config(thread_id),
            stream_mode="messages",
        ):
            message_chunk, _meta = chunk
            text = getattr(message_chunk, "content", "")
            if text:
                yield text
```

---

## 七、FastAPI 主服务

```python
# main.py
"""FastAPI 主服务：路由 + 鉴权 + 限流 + 错误契约"""
from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from agent import SupportAgent
from config import settings
from schemas import ChatRequest, ChatResponse, ErrorResponse, HealthResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("agent-api")

START_TIME = time.time()
agent: SupportAgent | None = None


def get_agent() -> SupportAgent:
    """确保 Agent 已初始化"""
    if agent is None:
        raise HTTPException(status_code=503, detail="agent not ready")
    return agent


@asynccontextmanager
async def lifespan(_: FastAPI):
    """启动时初始化 Agent（避免每个请求重复加载）"""
    global agent
    logger.info("initializing agent service...")
    agent = SupportAgent()
    logger.info("agent service ready")
    yield
    logger.info("agent service shutting down")


app = FastAPI(title="AI Agent API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== 请求 ID 中间件：贯穿日志与错误响应 =====
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


# ===== 鉴权：校验 X-API-Key =====
async def verify_api_key(x_api_key: str | None = Header(default=None)) -> str:
    if not x_api_key or x_api_key != settings.service_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key"
        )
    return x_api_key


# ===== 限流：内存滑动窗口（生产建议换 Redis 以支持多实例）=====
class RateLimiter:
    """按 Key 的每分钟滑动窗口限流"""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.time()
        window = self._hits[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.per_minute:
            return False
        window.append(now)
        return True


rate_limiter = RateLimiter(settings.rate_limit_per_minute)


async def rate_limit_dep(api_key: str = Depends(verify_api_key)) -> None:
    if not rate_limiter.allow(api_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="rate limit exceeded"
        )


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
    """健康检查（供负载均衡 / K8s 探针使用）"""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        uptime=round(time.time() - START_TIME, 3),
        model=settings.llm_model_name,
    )


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(rate_limit_dep)])
async def chat(request: ChatRequest):
    """同步聊天接口"""
    start = time.time()
    thread_id = request.session_id or f"sess-{uuid.uuid4().hex[:8]}"
    answer = await get_agent().answer(request.message, thread_id)
    return ChatResponse(
        session_id=thread_id,
        message=answer,
        processing_time=round(time.time() - start, 3),
    )


def _sse(payload: dict) -> str:
    """把字典序列化为一条 SSE 消息"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/chat/stream", dependencies=[Depends(rate_limit_dep)])
async def chat_stream(request: ChatRequest):
    """流式聊天接口（SSE）"""
    thread_id = request.session_id or f"sess-{uuid.uuid4().hex[:8]}"

    async def event_generator():
        yield _sse({"type": "session", "session_id": thread_id})
        try:
            async for token in get_agent().astream(request.message, thread_id):
                yield _sse({"type": "token", "content": token})
            yield _sse({"type": "done"})
        except Exception as exc:  # noqa: BLE001
            logger.exception("stream failed")
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

---

## 八、依赖

```txt
# requirements.txt
fastapi>=0.143.0
uvicorn[standard]>=0.54.0
langchain>=1.4.5
langchain-core>=1.6.10
langchain-openai>=1.7.1
langgraph>=1.2.15
langgraph-checkpoint>=4.3.0
pydantic>=2.14.1
pydantic-settings>=2.15.0
python-dotenv>=1.2.4
```

> 💡 用 `uv` 安装更快：`uv venv && uv pip install -r requirements.txt`。如需向量库检索，再追加 `langchain-chroma` 与 `chromadb>=1.5.9`。

---

## 九、运行与测试

```bash
# Start the service
export LLM_API_KEY=sk-xxx
export LLM_MODEL_NAME=gpt-5.5
export SERVICE_API_KEY=dev-secret
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

```bash
# Health check
curl http://localhost:8000/health

# Synchronous chat (with auth)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-secret" \
  -d '{"message": "退款要多久？"}'

# Streaming chat (SSE)
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-secret" \
  -d '{"session_id": "user-1", "message": "发票怎么开？"}'
```

- Swagger UI：`http://localhost:8000/docs`
- ReDoc：`http://localhost:8000/redoc`

```python
# 用 Python 客户端测试
import httpx

BASE = "http://localhost:8000"
HEADERS = {"X-API-Key": "dev-secret"}

with httpx.Client(base_url=BASE, headers=HEADERS, timeout=30) as client:
    r = client.post("/chat", json={"message": "你好，退款要多久？"})
    data = r.json()
    print("session:", data["session_id"], "->", data["message"][:60])
```

---

## 十、生产环境配置

| 配置项 | 开发 | 生产 |
|--------|------|------|
| `reload` | `True` | `False` |
| `workers` | `1` | `4+`（或交给容器编排扩副本） |
| `log_level` | `info` | `warning` |
| `CORS` | `["*"]` | 限定具体域名 |
| 会话存储 | `InMemorySaver` | `PostgresSaver` / Redis |
| 限流 | 内存 | Redis（多实例共享） |
| 鉴权 | 固定 Key | 网关 / OAuth2 / JWT |

```bash
# Production start (multiple workers)
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 --log-level warning
```

---

> 💻 **配套代码**：完整可运行版本见 [`examples/07-api-service/`](../../examples/07-api-service/)。其中 `python smoke_test.py` 可**离线自检 16 项**（鉴权 / 限流 / SSE，无需 fastapi 与 API Key），启动后可用 `curl` 直接验证 `/health`、`/chat`、`/chat/stream` 三个端点。

## 十一、本章小结

| 组件 | 说明 |
|------|------|
| **config.py** | `pydantic-settings` 统一读取 `LLM_*` 与服务配置 |
| **schemas.py** | 请求/响应模型 + 统一错误契约 |
| **agent.py** | `create_agent` 封装，`ainvoke` / `astream` 异步与流式 |
| **security.py** | 恒定时间鉴权 + 滑动窗口限流（与 Web 框架解耦，可离线测） |
| **sse.py** | SSE 报文格式化与流式工具（与 Web 框架解耦，可离线测） |
| **鉴权** | `X-API-Key` 依赖注入 |
| **限流** | 滑动窗口，按 Key 限制 QPS |
| **/chat/stream** | SSE 流式输出，前端可做打字机效果 |
| **错误契约** | `{error, code, request_id, detail}` + `X-Request-ID` |

---

## 📝 课后练习

1. **✅ 基础**：启动服务，用 `/docs` 调用 `/chat` 与 `/chat/stream`，观察流式输出。
2. **💡 改进**：把 `RateLimiter` 换成 Redis 实现，使多 worker 共享限流状态。
3. **🚀 挑战**：把 `InMemorySaver` 换成 `PostgresSaver`，实现跨重启的会话持久化。
4. **🔍 探索**：用 Locust 或 `ab` 压测 `/chat`，观察并发下的 P95 延迟与错误率。
