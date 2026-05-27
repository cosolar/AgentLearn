# 7.1 API 服务部署 —— 把 Agent 变成一个真正的后端服务

## 📖 导读

> **交互式 Notebook 里的 Agent 只是玩具。真正的 Agent 产品是一个 7×24 小时运行的后端服务。**

本章我们将把一个 Agent 封装成**标准的 REST API 服务**，支持并发请求、会话管理、状态持久化，并为前端、移动端或其他微服务提供统一的调用接口。我们将使用 **FastAPI** 构建这个服务——它是 Python 社区最快的 Web 框架之一，原生支持异步。

---

## 一、前置知识

| 概念 | 说明 |
|------|------|
| REST API | 基于 HTTP 的 API 设计风格 |
| FastAPI | Python 高性能 Web 框架 |
| Pydantic | Python 数据验证库 |
| Uvicorn | ASGI 服务器，运行 FastAPI |

---

## 二、为什么需要 API 封装？

```text
❌ 不好的方式（直接调用 SDK）：

用户 → 你的代码 → LangChain → LLM
        ↑ 需要安装 Python，配置环境
        ↑ 需要 API Key
        ↑ 代码耦合，无法复用
        ↑ 无法处理高并发

✅ 好的方式（API 服务）：

用户/前端 → HTTP → FastAPI 服务 → LangChain → LLM
                    ↑ 统一的 HTTP 接口
                    ↑ 语言无关（任何客户端可调用）
                    ↑ 支持高并发
                    ↑ 可监控、可扩展
```

---

## 三、完整 API 服务实现

### 3.1 项目结构

```
examples/07-api-service/
├── main.py              # FastAPI 主入口
├── agent.py             # Agent 核心逻辑
├── schemas.py           # 请求/响应模型
├── session.py           # 会话管理
├── config.py            # 配置
├── requirements.txt     # 依赖
└── Dockerfile           # 容器化
```

### 3.2 定义请求/响应模型

```python
# schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., min_length=1, max_length=4000, description="用户消息")
    session_id: Optional[str] = Field(None, description="会话 ID，不传则创建新会话")
    temperature: Optional[float] = Field(0.7, ge=0, le=2, description="生成温度")


class SourceInfo(BaseModel):
    """信息来源"""
    title: str
    content: str
    score: float


class ChatResponse(BaseModel):
    """聊天响应"""
    session_id: str
    message: str
    sources: Optional[List[SourceInfo]] = None
    processing_time: float


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    uptime: float
    model: str
```

### 3.3 实现 Agent 核心逻辑

```python
# agent.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings


class SupportAgent:
    """客服 Agent 核心逻辑"""
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        self.vectorstore = Chroma(
            embedding_function=self.embeddings,
            persist_directory="./kb_data",
        )
        self.chain = self._build_chain()
    
    def _build_chain(self):
        """构建问答链"""
        template = """你是智能客服助手，基于以下信息回答问题。

参考信息：
{context}

问题：{question}

回答要求：
1. 只基于参考信息回答
2. 如果不确定，说"未找到相关信息"
3. 引用信息来源

回答："""
        
        prompt = ChatPromptTemplate.from_template(template)
        retriever = self.vectorstore.as_retriever(search_kwargs={"k": 3})
        
        def format_docs(docs):
            return "\n\n".join([
                f"[{d.metadata.get('source', '未知')}]\n{d.page_content}"
                for d in docs
            ])
        
        return (
            {
                "context": retriever | format_docs,
                "question": RunnablePassthrough(),
            }
            | prompt
            | self.llm
            | StrOutputParser()
        )
    
    def answer(self, question: str) -> dict:
        """回答问题并返回来源"""
        # 获取检索结果
        retriever = self.vectorstore.as_retriever(search_kwargs={"k": 3})
        docs = retriever.invoke(question)
        
        # 生成回答
        answer = self.chain.invoke(question)
        
        # 构建来源信息
        sources = [
            {"title": d.metadata.get("source", "未知"), "content": d.page_content[:200], "score": 0.9}
            for d in docs
        ]
        
        return {"answer": answer, "sources": sources}
```

### 3.4 会话管理

```python
# session.py
import uuid
import time
from typing import Dict
from datetime import datetime


class Session:
    """单个会话"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = time.time()
        self.last_active = time.time()
        self.history: list = []
        self.metadata: dict = {}
    
    def add_message(self, role: str, content: str):
        self.history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        self.last_active = time.time()
    
    def get_history(self, limit: int = 10) -> list:
        return self.history[-limit:] if limit else self.history
    
    def is_expired(self, max_idle_minutes: int = 30) -> bool:
        idle = (time.time() - self.last_active) / 60
        return idle > max_idle_minutes


class SessionManager:
    """会话管理器（内存版，生产环境建议用 Redis）"""
    
    def __init__(self, session_timeout: int = 30):
        self.sessions: Dict[str, Session] = {}
        self.session_timeout = session_timeout
    
    def get_or_create(self, session_id: str = None) -> Session:
        """获取或创建会话"""
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            # 检查是否过期
            if not session.is_expired(self.session_timeout):
                return session
            else:
                # 过期了，创建新的
                del self.sessions[session_id]
        
        new_id = session_id or str(uuid.uuid4())[:8]
        self.sessions[new_id] = Session(new_id)
        return self.sessions[new_id]
    
    def cleanup_expired(self):
        """清理过期会话"""
        expired = [
            sid for sid, session in self.sessions.items()
            if session.is_expired(self.session_timeout)
        ]
        for sid in expired:
            del self.sessions[sid]
        return len(expired)
    
    def get_stats(self) -> dict:
        return {
            "active_sessions": len(self.sessions),
            "session_timeout_minutes": self.session_timeout,
        }
```

### 3.5 FastAPI 主服务

```python
# main.py
import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from schemas import ChatRequest, ChatResponse, HealthResponse, ErrorResponse
from agent import SupportAgent
from session import SessionManager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-api")

# 全局实例
agent: SupportAgent = None
session_manager: SessionManager = None
start_time: float = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global agent, session_manager
    
    logger.info("🚀 正在初始化 Agent 服务...")
    agent = SupportAgent()
    session_manager = SessionManager()
    logger.info("✅ Agent 服务启动完成")
    
    yield
    
    logger.info("🛑 服务关闭")


app = FastAPI(
    title="AI Agent API",
    description="AI Agent 智能客服 API 服务",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== API 端点 =====

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        uptime=time.time() - start_time,
        model="gpt-4o-mini",
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """聊天接口"""
    start = time.time()
    
    try:
        # 获取/创建会话
        session = session_manager.get_or_create(request.session_id)
        
        # 记录用户消息
        session.add_message("user", request.message)
        
        # Agent 回答
        result = agent.answer(request.message)
        
        # 记录助手回复
        session.add_message("assistant", result["answer"])
        
        # 计算处理时间
        processing_time = time.time() - start
        
        logger.info(
            f"会话 {session.session_id} | "
            f"处理时间 {processing_time:.2f}s | "
            f"来源 {len(result['sources'])} 个"
        )
        
        return ChatResponse(
            session_id=session.session_id,
            message=result["answer"],
            sources=result.get("sources"),
            processing_time=round(processing_time, 3),
        )
        
    except Exception as e:
        logger.error(f"处理请求失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式聊天接口"""
    
    async def generate():
        session = session_manager.get_or_create(request.session_id)
        session.add_message("user", request.message)
        
        # 模拟流式输出
        result = agent.answer(request.message)
        full_answer = result["answer"]
        
        # 逐字输出
        for char in full_answer:
            yield char
            await asyncio.sleep(0.01)  # 模拟延迟
    
    return StreamingResponse(generate(), media_type="text/plain")


@app.get("/sessions/stats")
async def session_stats():
    """会话统计"""
    return session_manager.get_stats()


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    return {"deleted": True}


# ===== 启动入口 =====
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式自动重载
        log_level="info",
    )
```

### 3.6 依赖和配置

```txt
# requirements.txt
fastapi==0.115.0
uvicorn[standard]==0.30.0
langchain==0.3.0
langchain-openai==0.2.0
langchain-community==0.3.0
chromadb==0.5.0
openai==1.50.0
pydantic==2.9.0
python-dotenv==1.0.0
```

---

## 四、运行和测试

### 4.1 启动服务

```bash
cd examples/07-api-service
pip install -r requirements.txt
python main.py
# 服务启动在 http://localhost:8000
```

### 4.2 自动生成 API 文档

FastAPI 自动生成交互式文档：

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 4.3 测试 API

```bash
# 健康检查
curl http://localhost:8000/health

# 聊天
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "什么是 AI Agent？"}'

# 带会话的聊天
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "user123", "message": "继续解释一下"}'
```

```python
# 用 Python 测试
import requests

BASE_URL = "http://localhost:8000"

# 创建会话
response = requests.post(f"{BASE_URL}/chat", json={
    "message": "你好，请问什么是 RAG？",
})
data = response.json()
print(f"会话: {data['session_id']}")
print(f"回答: {data['message'][:100]}...")

# 继续对话
response = requests.post(f"{BASE_URL}/chat", json={
    "session_id": data["session_id"],
    "message": "能举个例子吗？",
})
```

---

## 五、生产环境配置

| 配置项 | 开发环境 | 生产环境 |
|--------|----------|----------|
| **host** | `0.0.0.0` | `0.0.0.0` |
| **port** | `8000` | `8000` |
| **reload** | `True` | `False` |
| **workers** | `1` | `4+` |
| **log_level** | `info` | `warning` |
| **CORS** | `allow_origins=["*"]` | 限制具体域名 |

```python
# 生产环境启动
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=4,             # 多 worker 进程
        log_level="warning",   # 减少日志输出
        proxy_headers=True,    # 如果使用 nginx 反代
        forwarded_allow_ips="*",
    )
```

---

## 六、API 版本管理

```python
from fastapi import APIRouter

# v1 路由
v1_router = APIRouter(prefix="/v1")

@v1_router.post("/chat")
async def chat_v1(request: ChatRequest):
    """v1 版本聊天接口"""
    pass

# v2 路由（兼容旧版的同时迭代新版）
v2_router = APIRouter(prefix="/v2")

@v2_router.post("/chat")
async def chat_v2(request: ChatRequest):
    """v2 版本聊天接口（增强版）"""
    pass

# 注册到主应用
app.include_router(v1_router)
app.include_router(v2_router)
```

---

## 七、本章总结

| 组件 | 说明 |
|------|------|
| **FastAPI** | 高性能 Web 框架，自动生成文档 |
| **ChatRequest/Response** | Pydantic 模型，自动校验和文档 |
| **SessionManager** | 会话管理，支持多轮对话 |
| **SupportAgent** | Agent 核心逻辑，封装问答链 |
| **/health** | 健康检查端点 |
| **/chat** | 核心聊天端点 |
| **/chat/stream** | 流式输出端点 |

---

## 📝 课后练习

1. **✅ 基础**：启动 API 服务，通过浏览器访问 `/docs` 测试聊天接口
2. **💡 改进**：添加 `/chat/stream` 流式接口，让前端实现打字机效果
3. **🚀 挑战**：用 Redis 替代内存 SessionManager，使会话可在多 Worker 间共享
4. **🔍 探索**：使用 Locust 或 ab 对 API 进行压测，观察并发表现
