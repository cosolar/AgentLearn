## 概述

Tool 是 agent 与外部世界交互的方式 —— 执行 shell 命令、读写文件、调用 API。每个 tool 通过 JSON Schema 暴露给 LLM，agent 通过统一的流式接口完成调用。

AgentScope 把 tool 相关的构件组织成三个概念：

- **Tool** —— 任意实现 `ToolBase` 接口的类，包括 AgentScope 内置工具，以及把普通函数或 MCP 服务工具包装成 tool 的 `FunctionTool` / `MCPTool` 适配器。
- **Toolkit** —— 容器，负责注册 tool、MCP 客户端与 skill，向模型暴露它们的 JSON schema，并把每次工具调用分发到对应的 tool 对象。
- **Tool Group** —— 一组带名称的 tool / MCP / skill 集合，可以作为整体激活或停用。Agent 在运行时通过内置 meta tool 切换 group，让上下文保持聚焦。

```python
from agentscope.tool import Toolkit, Bash, Read, Write, Edit

toolkit = Toolkit(
    tools=[Bash(), Read(), Write(), Edit()],
)
```

只传 `tools` 时，这些 tool 都进入特殊的 `"basic"` 组 —— 该组始终激活。追加 `mcps`、`skills_or_loaders` 或额外的 `tool_groups` 即可拓展 agent 的能力 —— 见下文各节。

## Python Tool

Python tool 是任意满足 `ToolBase` 接口的对象。AgentScope 提供了一组内置工具覆盖常见操作，并对外暴露同一接口供开发者自定义。

### ToolBase 接口

`ToolBase` 是所有 tool 的抽象基类。下表列出其属性与方法。

向 agent 与运行时描述 tool 的属性：

| 属性 | 类型 | 说明 |
|---|---|---|
| `name` | `str` | 暴露给 agent 的 tool 名称 |
| `description` | `str` | 面向 agent 的功能描述 |
| `input_schema` | `dict` | 定义参数的 JSON Schema |
| `is_concurrency_safe` | `bool` | 是否可并发调用 |
| `is_read_only` | `bool` | 是否只读、不产生副作用 |
| `is_external_tool` | `bool` | 为 `True` 时执行委派给外部（见 [定义外部执行 Tool](#定义外部执行-tool)） |
| `is_state_injected` | `bool` | 为 `True` 时通过 `_agent_state` 参数注入 agent state |
| `is_mcp` | `bool` | 是否来自 MCP 服务 |
| `mcp_name` | `str \| None` | `is_mcp` 为 `True` 时所属 MCP 服务名 |

接入执行流程与权限系统的方法：

| 方法 | 必需 | 说明 |
|---|---|---|
| `check_permissions(tool_input, context)` | 是 | 执行前的运行时权限检查；返回 `PermissionDecision` |
| `match_rule(rule_content, tool_input)` | 可选 | 权限系统中的自定义规则匹配；返回 `bool` |
| `generate_suggestions(tool_input)` | 可选 | 基于本次工具调用生成建议规则；返回 `list[PermissionRule]` |
| `__call__(**kwargs)` | 可选 | tool 的执行逻辑；返回 `ToolChunk` 或 `AsyncGenerator[ToolChunk, None]`。外部执行 tool 不需要实现。 |

### 使用内置 Tool

AgentScope 预置了一组覆盖常见 agent 操作的 tool，实例化后传入 `Toolkit(tools=[...])` 即可：

| Tool | 说明 | 只读 |
|------|------|------|
| `Bash` | 执行 shell 命令 | 否 |
| `Read` | 按行号读取文件内容 | 是 |
| `Write` | 创建或覆写文件 | 否 |
| `Edit` | 在文件中做精确字符串替换 | 否 |
| `Glob` | 按 glob 模式查找文件 | 是 |
| `Grep` | 基于 ripgrep 搜索文件内容 | 是 |
| `TaskCreate` | 创建结构化任务以跟踪进度 | 否 |
| `TaskGet` | 按 ID 获取任务详情 | 是 |
| `TaskList` | 列出全部任务及其状态 | 是 |
| `TaskUpdate` | 更新任务状态或元数据 | 否 |

> **注意：** 另外两个 tool —— meta tool `reset_tools` 与 `Skill` 查看器 —— 在出现额外 tool group 或 skill 时由 `Toolkit` 自动注册，开发者无需手动实例化。详见 [自我管理 Tool](#自我管理-tool) 与 [Skill](#skill)。

#### Bash

`Bash` 工具执行 shell 命令并返回 stdout / stderr。它实现了所有可选接口方法，提供精细的权限控制。

`check_permissions()` 对命令字符串做分层安全分析：

1. **注入风险检测** —— 标记 `$(...)`、反引号、进程替换等无法静态分析的动态结构 → ASK
2. **只读命令检测** —— 自动放行安全命令（`git status`、`ls`、`cat`、`grep`、`docker ps` 等），包括所有子命令均只读的复合命令 → ALLOW
3. **危险命令模式** —— 识别破坏性操作（如 `chmod 777`、`mkfs`） → ASK
4. **Sed 约束检查** —— 阻止针对危险文件的就地 `sed -i` → ASK
5. **危险路径保护** —— 检查命令是否操作敏感配置文件（`.bashrc`、`.ssh/`、`.env`） → ASK
6. **危险删除检测** —— 捕获指向关键系统路径（`/`、`~`、`/usr`）的 `rm` / `rmdir` → ASK
7. **ACCEPT_EDITS 模式** —— 该模式下自动放行文件系统命令（`mkdir`、`touch`、`rm`、`mv`、`cp`、`sed`） → ALLOW

`match_rule()` 使用基于前缀的通配匹配：

| 模式 | 匹配 | 不匹配 |
|------|------|--------|
| `npm run:*` | `npm run build`、`npm run test` | `npm install` |
| `git commit:*` | `git commit -m "fix"` | `git push` |
| `rm:*` | `rm file.txt`、`rm -rf /tmp/x` | `ls` |

`generate_suggestions()` 抽取命令前缀（前两个 token）并给出前缀规则。例如 `git commit -m "fix bug"` 生成建议 `git commit:*`。

构造函数支持向危险路径列表追加自定义条目：

```python
from agentscope.tool import Bash

bash = Bash(
    additional_dangerous_files=[".secrets"],
    additional_dangerous_directories=[".credentials"],
)
```

#### 文件类工具（Read、Write、Edit）

文件类工具强制执行「先读后写」规则：`Write` 与 `Edit` 要求目标文件先经由 `Read` 读取过。这避免了盲目覆写，并保证 agent 总是基于最新内容操作。

| Tool | 操作 | 关键行为 |
|------|------|----------|
| `Read` | 读取文件内容 | 返回带行号的内容；支持 offset / limit 处理大文件；结果缓存在 agent state |
| `Write` | 创建或覆写文件 | 文件已存在但未被读取过则失败 |
| `Edit` | 替换文件中的精确字符串 | `old_string` 找不到或不唯一时失败（除非 `replace_all=True`）；要求先读取 |

`check_permissions()` —— `Write` 与 `Edit` 共用同一权限逻辑：

1. **危险路径保护**（不可绕过） —— 操作敏感文件（`.bashrc`、`.env`、`.ssh/`）始终触发 ASK，即使在 BYPASS 模式下亦然
2. **ACCEPT_EDITS 模式** —— 自动放行配置工作目录内的文件操作
3. **PASSTHROUGH** —— 交给权限引擎做规则匹配

`Read` 是只读工具，始终返回 PASSTHROUGH（EXPLORE 模式下的自动放行由引擎处理）。

`match_rule()` —— 三个 tool 都使用 `fnmatch` 对 `file_path` 参数做 glob 匹配：

| 模式 | 匹配 |
|------|------|
| `src/**` | `src/` 下任意文件 |
| `src/**/*.py` | `src/` 下的 Python 文件 |
| `config.json` | 精确匹配该文件 |

`generate_suggestions()` 提议覆盖父目录的 glob。例如编辑 `/project/src/main.py` 会生成建议 `src/**`。

### 自定义 Tool

继承 `ToolBase`，声明 schema，实现 `check_permissions` 与 `__call__` 即可创建自定义 tool：

```python
from agentscope.tool import ToolBase, ToolChunk
from agentscope.permission import (
    PermissionContext, PermissionDecision, PermissionBehavior,
)
from agentscope.message import TextBlock

class WebSearch(ToolBase):
    name = "WebSearch"
    description = "Search the web for information on a given query."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            },
        },
        "required": ["query"],
    }
    is_concurrency_safe = True
    is_read_only = True

    async def check_permissions(
        self, tool_input: dict, context: PermissionContext,
    ) -> PermissionDecision:
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="Web search is read-only.",
        )

    async def __call__(self, query: str) -> ToolChunk:
        results = await do_search(query)
        return ToolChunk(content=[TextBlock(text=results)])
```

### 把函数包装为 Tool

不值得为之单独写一个子类的轻量场景，可以用 `FunctionTool` 适配器包装一个普通 Python 函数 —— 它会自动从 `func.__name__` 取 tool 名、从 docstring 取描述、从类型注解推导 input schema。

```python
from agentscope.tool import FunctionTool, Toolkit

def get_weather(city: str, unit: str = "celsius") -> str:
    """Get the current weather for a city.

    Args:
        city: The city name to look up.
        unit: Temperature unit, either "celsius" or "fahrenheit".
    """
    return f"The weather in {city} is 22°{unit[0].upper()}"

toolkit = Toolkit(tools=[FunctionTool(get_weather)])
```

当自动推导的默认值不合适时，`FunctionTool` 支持显式覆盖：

| 参数 | 类型 | 说明 |
|------|------|------|
| `func` | `Callable` | 待包装的 Python 函数 |
| `name` | `str \| None` | 覆盖 tool 名（默认取 `func.__name__`） |
| `description` | `str \| None` | 覆盖描述（默认取 docstring） |
| `is_concurrency_safe` | `bool` | 是否可并发调用（默认 `True`） |
| `is_read_only` | `bool` | 是否无副作用（默认 `False`） |
| `is_state_injected` | `bool` | 是否通过 `_agent_state` 注入 agent state（默认 `False`） |

> **注意：** 被包装的函数默认走 `ASK` 权限行为 —— 用户必须为每次调用显式放行。需要自定义权限逻辑时，请直接继承 `ToolBase`。

### 定义外部执行 Tool

外部执行 tool 把实际执行委派给 agent 运行时之外 —— 通常是人工操作员或外部系统。Agent 调用此类 tool 时会发出 `RequireExternalExecutionEvent` 并暂停，直到结果通过 `ExternalExecutionResultEvent` 回传。

这种模式是 [human-in-the-loop](building-blocks/agent#人机交互.md) 工作流的基础 —— 某些动作需要人工确认或人工执行。

创建外部执行 tool 只需把 `is_external_tool` 设为 `True`，不必实现 `__call__`：

```python
from agentscope.tool import ToolBase
from agentscope.permission import (
    PermissionContext, PermissionDecision, PermissionBehavior,
)

class HumanApproval(ToolBase):
    name = "HumanApproval"
    description = "Request human approval for a sensitive operation."
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "The action requiring approval."},
            "reason": {"type": "string", "description": "Why this action needs approval."},
        },
        "required": ["action", "reason"],
    }
    is_concurrency_safe = True
    is_read_only = False
    is_external_tool = True

    async def check_permissions(
        self, tool_input: dict, context: PermissionContext,
    ) -> PermissionDecision:
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="External tool dispatch is always allowed.",
        )
```

## MCP

AgentScope 集成 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)，让 agent 可以接入任意 MCP 兼容的工具提供方。框架自动处理协议协商、工具发现与结果转换。

支持两种连接方式：

- **Stateful**（STDIO 或 HTTP） —— 持久会话，需显式 `connect()` / `close()` 生命周期
- **Stateless**（仅 HTTP） —— 每次调用临时建会话，无需生命周期管理

MCP tool 的命名空间为 `mcp__{server_name}__{tool_name}`，避免冲突；标注了 `readOnlyHint` 的 tool 会被权限系统自动放行。

### 注册 MCP Tool

构造一个或多个 `MCPClient`，传入 `Toolkit(mcps=[...])`。Stateful 客户端必须在构造 toolkit 之前完成连接。

##### Stateful (STDIO)

```python
from agentscope.mcp import MCPClient, StdioMCPConfig
from agentscope.tool import Toolkit

client = MCPClient(
    name="filesystem",
    is_stateful=True,
    mcp_config=StdioMCPConfig(
        command="mcp-server-filesystem",
        args=["--root", "/my/project"],
    ),
)

await client.connect()

toolkit = Toolkit(mcps=[client])
```

##### Stateful (HTTP)

```python
from agentscope.mcp import MCPClient, HttpMCPConfig
from agentscope.tool import Toolkit

client = MCPClient(
    name="weather",
    is_stateful=True,
    mcp_config=HttpMCPConfig(
        url="https://api.weather.com/mcp",
        headers={"Authorization": "Bearer xxx"},
    ),
)

await client.connect()

toolkit = Toolkit(mcps=[client])
```

##### Stateless (HTTP)

```python
from agentscope.mcp import MCPClient, HttpMCPConfig
from agentscope.tool import Toolkit

client = MCPClient(
    name="search",
    is_stateful=False,
    mcp_config=HttpMCPConfig(url="https://api.search.com/mcp"),
)

toolkit = Toolkit(mcps=[client])
```

要只暴露 MCP 服务的部分工具，在 client 上配置 `enable_tools` 或 `disable_tools`：

```python
client = MCPClient(
    name="search",
    is_stateful=False,
    mcp_config=HttpMCPConfig(url="https://api.search.com/mcp"),
    enable_tools=["web_search", "image_search"],
)
```

需要在 `Toolkit` 之外直接调用 MCP tool 时，调用 `await client.list_tools()` 拿到 `MCPTool` 适配器列表，像普通 `ToolBase` 一样使用即可。

## Skill

Skill 是基于 markdown 的指令集，无需写新工具代码即可拓展 agent 能力。每个 skill 是一个目录，包含一个带 frontmatter 元数据与详细指令的 `SKILL.md` 文件。

与 tool 不同，skill 不能被直接调用。Agent 通过自动注册的 `Skill` 查看器读取 skill 指令，再用现有的 tool 按指令执行。

### 注册 Skill

通过 `Toolkit` 的 `skills_or_loaders` 参数传入 skill 来源。每一项可以是目录路径字符串、`Skill` 对象，或 `SkillLoaderBase` 子类：

##### 目录路径（简单）

```python
from agentscope.tool import Toolkit

toolkit = Toolkit(
    skills_or_loaders=["/path/to/skills"],
)
```

##### LocalSkillLoader（含子目录扫描）

```python
from agentscope.tool import Toolkit
from agentscope.skill import LocalSkillLoader

loader = LocalSkillLoader(
    directory="/path/to/skills",
    scan_subdir=True,
)

toolkit = Toolkit(skills_or_loaders=[loader])
```

### Skill 的工作方式

`Toolkit` 在含 skill 时，注册与查看分两阶段进行。

初始化阶段：

- Toolkit 扫描所有注册的 skill 来源，收集每个 skill 的名称、描述与目录。
- 自动注册内置的 `Skill` 查看器。
- 组装一段 system prompt 片段，列出可用 skill（仅名称与描述），并指示 agent 通过 `Skill` 查看器读取完整内容。

运行时阶段：

- Agent 按名字选定一个 skill，调用 `Skill` 查看器。
- 查看器读取对应 `SKILL.md`，返回完整 markdown。
- Agent 用已装备的 tool 按这些指令执行。

> **注意：** Skill 不是 tool —— agent 不能直接调用 skill。它必须先用 `Skill` 查看器读取指令，再用其他 tool 按描述的步骤执行。

## 自我管理 Tool

内置 **meta tool**（`reset_tools`）让 agent 在运行时自我管理哪些 tool group 处于激活状态，从而保持上下文聚焦 —— 只有与当前任务相关的 tool 暴露给模型。

### 定义 Tool Group

`ToolGroup` 是带名称的 tool / MCP / skill 集合。把 group 传入 `Toolkit(tool_groups=[...])`。保留名 `"basic"` 由构造函数顶层的 `tools`、`mcps`、`skills_or_loaders` 自动构成，且始终激活。

```python
from agentscope.tool import Toolkit, ToolGroup, Bash, Read, Write, Edit

toolkit = Toolkit(
    tools=[Bash(), Read(), Write(), Edit()],
    tool_groups=[
        ToolGroup(
            name="database",
            description="Tools for database operations.",
            instructions="Always wrap mutations in a transaction.",
            tools=[db_query_tool, db_migrate_tool],
        ),
        ToolGroup(
            name="deployment",
            description="Tools for deploying services.",
            instructions="Confirm the target environment before deploying.",
            tools=[deploy_tool, rollback_tool],
        ),
    ],
)
```

`ToolGroup` 接收与 toolkit 相同的 `tools`、`mcps`、`skills_or_loaders` 参数，再加上一个用于 meta tool schema 中向 agent 描述本组的 `description`，以及激活时返回给 agent 的可选 `instructions`。

### 使用 Meta Tool

只要存在至少一个非 basic 的 tool group，`Toolkit` 就会自动注册 `reset_tools` 并把其 schema 暴露给 agent。每个非 basic group 在 schema 中表示为一个布尔字段，agent 调用 meta tool 时声明期望的最终状态。

运行时行为：

- `"basic"` 组中的 tool 始终暴露，meta tool 不会影响它们。
- 每次调用 `reset_tools` 都会**整体覆盖**激活集合 —— 任何未显式置为 `True` 的非 basic group 都会被停用，无论之前的状态。
- 对每个本次切换为激活的 group，其 `instructions`（若有）会被拼接进 meta tool 的返回值，告诉 agent 如何正确使用该组。
- 未激活 group 中的 tool 不会出现在 agent 的工具 schema 中，从而把上下文留给当前激活的工具集。

> **警告：** Meta tool 的输入表示所有 group 的**最终状态**而非增量。任何未显式置为 `True` 的 group 都会被停用，无论之前的状态如何。

## 延伸阅读

- [**Agent**](building-blocks/agent.md) — Agent 如何在 ReAct 循环中编排 tool 调用
- [**Permission System**](building-blocks/permission-system.md) — 精细控制哪个 tool 可以执行、何时执行
- [**Middleware**](building-blocks/middleware.md) — 用洋葱式 middleware 拦截并改写 tool 调用
- [**Human-in-the-Loop**](building-blocks/agent#人机交互.md) — 外部执行 tool 与人工审批工作流