# 8.10 MCP 协议完全指南 —— Agent 工具连接的"USB-C"

## 📖 本章目标

- 理解 MCP（Model Context Protocol）要解决的问题
- 掌握 MCP 的架构、核心原语与传输方式
- 了解 **2026-07-28 新规范** 的重大变化（无状态化）
- 学会编写 MCP Server 并在 LangChain / LangGraph 中接入
- 掌握 MCP 的安全实践

> 📅 内容同步至 **MCP 2026-07-28 规范**。

---

## 一、为什么需要 MCP？

在 MCP 出现之前，每接入一个工具/数据源，都要为每个框架单独写一份适配代码：

```text
没有 MCP 的世界：
  GitHub 工具 ──▶ 为 LangChain 写适配
              ──▶ 为 OpenAI Agents SDK 写适配
              ──▶ 为 MAF 写适配
              ──▶ ...（N 个框架 × M 个工具 = N×M 份适配）
```

**MCP（Model Context Protocol）** 由 Anthropic 于 2024 年底发起、现由社区共同维护，用一个开放协议统一"**Agent ↔ 工具/数据源**"的连接：

```text
有了 MCP：
  GitHub MCP Server ──┐
  数据库 MCP Server ───┼──▶ 任何支持 MCP 的 Agent（LangChain / Agents SDK / MAF ...）
  文件系统 MCP Server ─┘

（N + M 而不是 N × M）
```

> 💡 **类比**：MCP 之于 AI 应用，就像 **USB-C** 之于硬件 —— 一个标准接口，连接一切外设。

---

## 二、核心架构

```text
┌──────────────────────────────────────────────────────────┐
│  MCP Host（你运行的 Agent 应用，如 Claude Desktop / IDE）  │
│                                                            │
│   ┌────────────┐        ┌────────────┐                     │
│   │ MCP Client │        │ MCP Client │   （每个 Server 一个 │
│   └─────┬──────┘        └─────┬──────┘     独立 Client 连接）│
└─────────┼─────────────────────┼────────────────────────────┘
          │  JSON-RPC 2.0       │
          ▼                     ▼
   ┌─────────────┐       ┌─────────────┐
   │ MCP Server  │       │ MCP Server  │
   │ (本地/远程)  │       │ (本地/远程)  │
   └──────┬──────┘       └──────┬──────┘
          ▼                     ▼
      文件系统/数据库        第三方 API
```

| 角色 | 说明 |
|------|------|
| **Host** | 承载 Agent 的应用（IDE、桌面应用、你的服务） |
| **Client** | Host 内部与单个 Server 通信的连接器 |
| **Server** | 暴露工具/资源/提示词的服务 |

### 2.1 三大核心原语（Server 侧）

| 原语 | 作用 | 类比 |
|------|------|------|
| **Tools** | 可被模型调用的函数 | "动作" |
| **Resources** | 可读取的数据（文件、记录） | "数据" |
| **Prompts** | 预设的提示模板 | "指令模板" |

> 🆕 **注**：2026-07-28 规范起，`Logging`、`Roots`、`Sampling` 已被**弃用**（至少保留 12 个月兼容期），新实现不建议使用。

---

## 三、传输方式

| 传输 | 适用 | 状态 |
|------|------|------|
| **stdio** | 本地进程（Server 由 Host 启动） | ✅ 推荐 |
| **Streamable HTTP** | 远程 Server | ✅ 推荐 |
| **HTTP + SSE（旧）** | 旧版远程 | ⚠️ 已弃用（一年过渡期） |

---

## 四、2026-07-28 规范：无状态化革命

这是 MCP 自诞生以来**最大的一次架构调整**。

### 4.1 从"有状态会话"到"无状态请求"

| 变化 | 旧规范 | 2026-07-28 |
|------|--------|------------|
| **握手** | `initialize` / `initialized` | ❌ 取消 |
| **会话 ID** | `Mcp-Session-Id` 头 | ❌ 取消 |
| **协议版本/能力** | 握手时协商 | ✅ 每个请求放在 `_meta` 中 |
| **服务发现** | 隐式 | 可选 `server/discover` RPC |
| **负载均衡** | 需粘性会话/共享存储 | ✅ 任意实例，普通轮询即可 |

> 🎯 **意义**：MCP Server 可以像普通 HTTP 服务一样**水平扩展**，任何请求落到任意实例都能处理。

### 4.2 多轮往返请求（MRTR）

旧的"服务器主动向客户端提问"（需要长连接）被 **MRTR（Multi Round-Trip Requests）** 取代：

```text
Client ──调用工具──▶ Server
Client ◀── resultType: "input_required" ── Server   （需要补充信息/用户确认）
Client ──带上 inputResponses，重试原调用──▶ Server
Client ◀── 最终结果 ── Server
```

典型场景：工具执行中途需要**用户确认**或**补充缺失参数**。

### 4.3 基于 Header 的路由

Streamable HTTP 请求必须携带 `Mcp-Method` 与 `Mcp-Name`，网关/限流器/WAF 可**直接按 Header 路由与计量**，无需解析 JSON body。

### 4.4 列表结果可缓存

`tools/list`、`resources/list` 等响应携带 `ttlMs` 与 `cacheScope`，客户端可据此缓存工具目录，减少重复拉取。

### 4.5 授权加固

| 加固项 | 说明 |
|--------|------|
| **RFC 9207 签发者校验** | 客户端兑换 code 前必须校验 `iss`，防止授权服务器混淆 |
| **application_type** | DCR 时设置，避免桌面/CLI 应用 localhost 重定向被拒 |
| **凭证绑定签发者** | 客户端凭证不与跨 AS 复用 |
| **CIMD 取代 DCR** | 转向 Client ID Metadata Documents |

### 4.6 扩展框架

正式确立**扩展（extensions）机制**：

| 扩展 | 作用 |
|------|------|
| `io.modelcontextprotocol/tasks` | 长时任务（`tasks/get`、`tasks/update`） |
| **MCP Apps** | 让 Server 提供可交互 UI |
| **EMA**（Enterprise Managed Authorization） | 企业级授权 |

### 4.7 弃用策略

MCP 引入了正式的**弃用政策：最短 12 个月窗口**，便于生态规划升级。

---

## 五、实战一：编写一个 MCP Server

使用官方推荐的 **FastMCP** 风格：

```python
# server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("demo-server")


@mcp.tool()
def add(a: int, b: int) -> int:
    """把两个整数相加。"""
    return a + b


@mcp.resource("config://app")
def get_config() -> str:
    """返回应用配置。"""
    return "app_name=AgentLearn"


@mcp.prompt()
def review_code(code: str) -> str:
    """代码审查提示模板。"""
    return f"请审查以下代码：\n\n{code}"


if __name__ == "__main__":
    # stdio 传输（本地）
    mcp.run()
```

远程部署时改用 Streamable HTTP：

```python
# 以 Streamable HTTP 方式启动
mcp.run(transport="streamable_http", host="0.0.0.0", port=8000)
```

---

## 六、实战二：在 LangChain / LangGraph 中接入 MCP

```bash
uv add langchain-mcp-adapters
```

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent


async def main():
    client = MultiServerMCPClient({
        # 本地 stdio Server
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data"],
            "transport": "stdio",
        },
        # 远程 Streamable HTTP Server
        "github": {
            "url": "https://mcp.github.com/mcp",
            "transport": "streamable_http",
        },
    })

    tools = await client.get_tools()          # 把所有 MCP Server 的能力变成 LangChain 工具
    agent = create_agent("gpt-5.5", tools=tools, system_prompt="你是全能助手。")

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "列出 /data 目录下的文件"}]}
    )
    print(result["messages"][-1].content)


asyncio.run(main())
```

> 💡 更省事的做法：**直接用 LangChain 的工具适配器**，一行 `get_tools()` 就完成接入，无需理解 JSON-RPC 细节。

---

## 七、MCP 的安全实践

| 风险 | 说明 | 防御 |
|------|------|------|
| **工具投毒** | 恶意 Server 描述诱导模型调用 | 只连接可信 Server、审查工具描述 |
| **权限过大** | Server 拿到不必要的权限 | 最小权限、OAuth scope 收窄 |
| **提示注入** | 工具返回内容中藏指令 | 隔离工具输出、来源标注 |
| **数据外泄** | 敏感数据被送到不可信 Server | 输入脱敏、审计日志 |
| **供应链** | 第三方 Server 含恶意代码 | 固定版本、沙箱运行 |

```python
from langchain.agents.middleware import PIIMiddleware

agent = create_agent(
    "gpt-5.5",
    tools=mcp_tools,
    middleware=[PIIMiddleware(strategy="redact")],  # 发送给 MCP 前先脱敏
)
```

---

## 八、MCP 生态

- **官方 SDK**：TypeScript、Python、Go、C#（Tier 1），Rust（beta）
- **Server 数量**：官方 + 社区已达**十万级**
- **平台支持**：Amazon Bedrock AgentCore、Cloudflare Workers、Microsoft Foundry、Google Cloud 等均已支持新规范
- **常见 Server**：文件系统、GitHub、数据库、浏览器、Slack、Notion、搜索等

---

## 九、本章小结

| 要点 | 说明 |
|------|------|
| 🎯 | MCP 统一了 Agent 与工具/数据源的连接，避免 N×M 适配 |
| 🧩 | 三大原语：Tools / Resources / Prompts |
| 🔄 | 2026-07-28：**无状态化**，可像普通 HTTP 一样水平扩展 |
| 🔐 | OAuth 加固（RFC 9207、CIMD）+ 12 个月弃用窗口 |
| 🚀 | 用 `langchain-mcp-adapters` 一行接入 |
| 🛡️ | 可信 Server + 最小权限 + 脱敏审计 |

---

## 📝 课后练习

1. **入门**：写一个包含 2 个工具的 MCP Server，用 stdio 启动
2. **接入**：用 `MultiServerMCPClient` 把本地 Server 接入 `create_agent`
3. **远程**：把 Server 改为 Streamable HTTP 部署，并增加 OAuth 校验
4. **对比**：实现同一工具（如查天气）的 MCP 版与自写 `@tool` 版，比较复用性

---

> 🔗 **下一步**：当你的 Agent 需要与**其他 Agent**协作时，请阅读 [8.11 A2A 协议与 Agent 互操作](02-a2a.md)。
