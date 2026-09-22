# 8.3 工具调用与编排生态

## 📖 本章目标

- 了解 2026 年工具调用生态的全景
- 掌握 LiteLLM 等关键工具的使用
- 学会构建企业级工具编排系统

---

## 工具调用生态概览

> 第 3.2 章已学习了基础的 `@tool` 装饰器和 `bind_tools()`，本章将这些技能放到更大的生态中。

```
工具调用生态分层：
┌─────────────────────────────────────────────────────────┐
│                    应用层                                │
│  LangChain Tools / Toolkit / MCP                          │
├─────────────────────────────────────────────────────────┤
│                    编排层                                │
│  LangGraph (条件路由) / MAF (企业级协作)                 │
├─────────────────────────────────────────────────────────┤
│                    调用层                                │
│  Functionary (精度优化) / ToolFormer (自动发现)          │
├─────────────────────────────────────────────────────────┤
│                    接入层                                │
│  LiteLLM (多模型统一) / LangChain LLM (单模型)           │
├─────────────────────────────────────────────────────────┤
│                    模型层                                │
│  OpenAI / Anthropic / Google / Ollama / vLLM             │
└─────────────────────────────────────────────────────────┘
```

---

## 核心工具项目

### 1. LangChain Tools — 700+ 开箱即用工具

> 你已在 3.2 章使用过，这里是生态全貌。

**内置工具类别：**

| 类别 | 示例工具 | 数量 |
|------|---------|------|
| 🔍 搜索 | DuckDuckGoSearch, TavilySearch, GoogleSearch | 20+ |
| 📊 数据 | PythonREPL, SQLDatabase, CSVLoader | 30+ |
| 🌐 网络 | RequestsGet, URLs, WebBrowser | 15+ |
| 📝 文档 | DocLoader, PDFParser, TextSplitter | 25+ |
| 📧 办公 | Gmail, Slack, Notion, Jira | 40+ |
| 🧮 计算 | Calculator, WolframAlpha | 10+ |
| 🖼️ 图像 | DALL-E, StableDiffusion, ImageCaption | 15+ |
| 🎵 媒体 | YouTube, Spotify, TTS, STT | 20+ |

```python
# 组合使用多个工具
from langchain_community.tools import DuckDuckGoSearchRun, YouTubeSearchTool
from langchain_core.tools import tool

@tool
def combined_search(query: str) -> str:
    """同时搜索网页和视频"""
    web = DuckDuckGoSearchRun().run(query)
    video = YouTubeSearchTool().run(query)
    return f"网页结果：{web}\n视频结果：{video}"
```

### 2. LiteLLM — 多模型统一接入

**解决的问题：** 不同模型提供商的 API 格式不同，切换模型需要改代码。

**核心能力：**
- **25+ 模型支持**：OpenAI、Anthropic、Google、Ollama、vLLM 等
- **统一接口**：所有模型用同一套 API
- **负载均衡**：自动在多个模型间分发请求
- **成本追踪**：自动记录 Token 消耗
- **零供应商锁定**：随时切换模型提供商

```python
# LiteLLM 统一接口
from litellm import completion

# 使用 OpenAI
response = completion(model="gpt-5.5", messages=[{"role": "user", "content": "Hello"}])

# 切换到 Claude - 只需改 model 名
response = completion(model="claude-sonnet-4-6", messages=[{"role": "user", "content": "Hello"}])

# 切换到本地模型
response = completion(model="ollama/llama3.2", messages=[{"role": "user", "content": "Hello"}])

# 负载均衡
response = completion(
    model="gpt-5.5", 
    messages=[...],
    fallbacks=["claude-sonnet-4-6", "gemini-3-pro"],
)
```

**在 LangChain 中使用 LiteLLM：**
```python
from langchain_community.chat_models import ChatLiteLLM

llm = ChatLiteLLM(model="gpt-5.5", temperature=0.7)
# 之后的用法和 ChatOpenAI 完全一样
```

### 3. Functionary — 函数调用精度优化

专注解决 Agent 调用工具时的**精度问题**（选错工具、参数错误）。

**核心特性：**
- **参数验证**：自动检查参数类型和合法性
- **自动补全**：智能填充缺失参数
- **工具选择优化**：减少工具误选率

```python
# 思路：在工具调用前后加一层校验（伪代码）
def safe_tool_call(tool, args):
    validate_schema(tool, args)          # 参数校验
    try:
        return tool.invoke(args)
    except Exception:
        return retry_with_fix(tool, args)  # 失败重试 / 修复
```

### 4. MCP — 工具接入标准（2026 首选）

**Model Context Protocol** 是 2026 年工具生态的事实标准：写一个 MCP Server，所有支持 MCP 的 Agent 都能用。

**核心能力：**
- **统一接入**：一次编写，跨框架复用（LangChain / OpenAI Agents SDK / MAF ...）
- **生态庞大**：官方 + 社区 MCP Server 数量已达十万级
- **能力可发现**：客户端可通过 `tools/list` 动态发现工具
- **安全可控**：OAuth 加固、权限最小化、可审计

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "github": {"url": "https://mcp.github.com/mcp", "transport": "streamable_http"},
})
tools = await client.get_tools()
```

> 📌 详见 [8.10 MCP 协议完全指南](../protocols/01-mcp.md)。

---

## 工具编排模式

### 模式一：顺序编排

```
工具A → 工具B → 工具C → 输出
```

最简单的模式，前一个工具的输出是后一个工具的输入。适合数据处理流水线。

### 模式二：条件路由（你已在 LangGraph 中学过）

```
         ┌── 条件成立 ──▶ 工具B
工具A ──┤
         └── 条件不成立 ─▶ 工具C
```

Agent 根据当前状态动态选择下一步调用的工具。这是 LangGraph 的核心能力。

### 模式三：并行编排

```
           ┌── 工具A ──┐
输入 ──▶ ──┼── 工具B ──┼── ▶ 汇总 ──▶ 输出
           └── 工具C ──┘
```

多个工具同时执行，结果汇总。适合需要多源信息的任务。

### 模式四：事件驱动（pub/sub 模式）

```
事件 → 触发规则 → 匹配工具 → 执行 → 产生新事件 → ...
```

工具通过事件自动触发，形成响应式系统。适合监控、告警等场景。

---

## 企业级工具治理

| 需求 | 解决方案 |
|------|---------|
| 团队协作 | Toolkit：多用户共享工具包 |
| 权限控制 | Toolkit：角色/工具级别权限 |
| 版本管理 | Toolkit：工具版本回溯 |
| 审计日志 | Toolkit：完整调用记录 |
| 成本控制 | LiteLLM：Token 追踪 + 预算限制 |
| 高可用 | LiteLLM：自动故障转移 |

```python
# 企业级工具治理示例
from toolkit import ToolkitManager
from litellm import cost_tracking

@cost_tracking
def enterprise_tool_call(tool_name: str, args: dict):
    """企业级工具调用（含审计和成本追踪）"""
    toolkit = ToolkitManager(team_id="engineering")
    
    # 权限检查
    if not toolkit.check_permission(user="dev_1", tool=tool_name):
        return "权限不足"
    
    # 调用并记录
    result = toolkit.invoke(tool_name, args)
    toolkit.log_call(user="dev_1", tool=tool_name, args=args, result=result)
    
    return result
```

---

## 本章小结

| 要点 | 说明 |
|------|------|
| 🛠️ | LangChain Tools 700+ 工具是最丰富的生态 |
| 🔌 | LiteLLM 解决多模型接入的碎片化问题 |
| 🎯 | Functionary 提升工具调用精度 |
| 📦 | MCP 提供标准化的工具发现与共享 |
| 🏢 | 企业级使用需要 Toolkit 治理 |

---

## 📝 课后练习

1. **实践题**：用 LiteLLM 替换项目中的 ChatOpenAI，测试切换模型
2. **集成题**：浏览 MCP Server 生态，找到 3 个有用的 Server 并接入到项目中
3. **设计题**：为一个电商客服场景设计工具调用流程（顺序/条件/并行混合）

