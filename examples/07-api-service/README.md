# Agent API 服务示例（07-api-service）

一个**可运行、可离线自检**的 FastAPI 服务示例，对应教程 [第七部分：生产部署](../../docs/07-生产部署/)，尤其是 [7.1 API 服务部署](../../docs/07-生产部署/01-API服务部署.md)。

它把 Agent 封装成真正的后端服务：**健康检查 + 同步问答 + SSE 流式问答 + API Key 鉴权 + 滑动窗口限流 + 统一错误契约**。

## 设计要点：Web 层与核心逻辑解耦

```
main.py (FastAPI)  ──依赖注入──▶  security.py   # 鉴权 + 限流（纯标准库）
                   ──格式化────▶  sse.py        # SSE 报文（纯标准库）
                   ──调用──────▶  agent.py      # Agent 核心（LangChain v1）
                                 schemas.py    # 请求/响应模型
                                 config.py     # pydantic-settings 配置
```

| 文件 | 说明 | 是否需要第三方依赖 |
|:-----|:-----|:------------------:|
| `security.py` | 恒定时间鉴权 + 滑动窗口限流 | 否 |
| `sse.py` | SSE 消息格式化与流式工具 | 否 |
| `config.py` | `pydantic-settings` 读取 `LLM_*` / 服务配置 | 是 |
| `schemas.py` | 请求 / 响应 / 错误模型 | 是 |
| `agent.py` | `create_agent` + `InMemorySaver`，异步与流式 | 是 |
| `main.py` | FastAPI 应用（路由、中间件、异常处理） | 是 |
| `smoke_test.py` | **16 项离线断言**（鉴权 / 限流 / SSE） | 否 |

> 💡 **为什么这样拆？** 把安全与协议逻辑从 Web 框架里剥离，好处是：① 可**离线测试**（`python smoke_test.py` 无需安装 fastapi）；② 可**复用**到 CLI / gRPC / 消息队列；③ 限流时钟可注入，测试不必真的等 60 秒。

## 快速开始

```bash
# 1) 离线自检（无需任何依赖）
python smoke_test.py
#   → 通过 16/16

# 2) 安装依赖并启动服务
uv pip install -r requirements.txt
cp .env.example .env          # 填入 LLM_API_KEY 等
uvicorn main:app --reload --port 8000
```

## 接口

| 方法 | 路径 | 说明 | 鉴权 |
|:-----|:-----|:-----|:----:|
| GET | `/health` | 健康检查（含 uptime、模型名） | 否 |
| POST | `/chat` | 同步问答 | 是 |
| POST | `/chat/stream` | SSE 流式问答 | 是 |

调用示例：

```bash
# 健康检查
curl http://127.0.0.1:8000/health

# 同步问答
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-secret-key" \
  -d '{"message":"你们的退货政策是什么？","thread_id":"u1"}'

# 流式问答（SSE）
curl -N -X POST http://127.0.0.1:8000/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-secret-key" \
  -d '{"message":"介绍一下 Atlas 产品","thread_id":"u1"}'
```

## 错误契约

所有错误返回同一形状，便于客户端统一处理：

```json
{ "error": "invalid api key", "code": 401, "request_id": "…", "detail": null }
```

| 状态码 | 场景 |
|:------:|:-----|
| 401 | 缺少或错误的 `X-API-Key` |
| 422 | 请求体校验失败 |
| 429 | 触发限流 |
| 500 | 未捕获的服务端错误（`request_id` 便于对日志） |

## 注意事项

- `InMemorySaver` 只在**单进程**内保留会话记忆；多副本部署请换 `PostgresSaver`（见 [7.1](../../docs/07-生产部署/01-API服务部署.md)）。
- 内存限流同样只在单实例下准确；多实例请换 Redis。
- 生产环境请务必替换 `SERVICE_API_KEY`，并通过密钥管理服务注入，不要写进代码或镜像。
- `X-Accel-Buffering: no` 用于避免 Nginx 缓冲导致 SSE 不实时；部署时记得在网关侧也关闭缓冲。
