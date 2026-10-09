AgentScope 2.0 是一次破坏性更新。下面按模块汇总相对 1.0 的差异。

## Agent

- 重构 `ReActAgent` 为新的 `Agent` 类实现。
- 用 `reply_stream` 与 `reply` 公共方法替换 1.0 中的 `__call__` 方法。
- 支持从 `reply_stream` 产出 agent event，提供更细粒度的可观测性与控制。
- 通过事件流支持 **permission 校验** 与 **human-in-the-loop** 确认。
- 通过新的 `Offloader` 接口支持压缩上下文与超大工具结果的 offload。
- 废弃 hook 机制，由新的 agent middleware 系统取代。
- 废弃 `state_dict` 与 `load_state_dict` 方法，转向通过新的 `AgentState` 类型显式管理状态。
- 废弃 agent 类的 `print` 接口，让 agent 成为纯生产者。
- 废弃 agent 类内部的 OpenTelemetry 集成，交由新的 middleware 实现承担。

## Event 🆕

- 新增 event 系统，更好地服务前端集成与 human-in-the-loop 场景。

## Message

Content block 重构：

- 重构所有 content block，统一继承自 Pydantic `BaseModel`，提升校验、序列化与扩展性。
- 将 `ImageBlock`、`AudioBlock`、`VideoBlock` 重构为统一的 `DataBlock`，通过 `media_type` 字段保留扩展性。
- 新增 `HintBlock`，用于 agent 引导与中间推理。
- 将 `ToolUseBlock` 重命名为 `ToolCallBlock`。
- 为 `ToolCallBlock` 新增 `state` 与 `suggested_rules` 字段，更完整地建模 tool-call 生命周期。
- 为 `ToolResultBlock` 新增 `state` 字段，更完整地建模 tool-call 生命周期。
- 为所有 block 新增 `id` 字段，提升可追踪性与引用能力。

`Msg` 类重构：

- 重构 `Msg`，继承自 `BaseModel` 并强制 content 校验。
- 为 `Msg` 类新增 `created_at`、`finished_at`、`usage` 字段，提升可观测性与计量能力。
- 为 `Msg` 新增 `append_event` 方法，用于从 agent 的 reply 流中产出 event。
- 新增 `UserMsg`、`AssistantMsg`、`SystemMsg` 工厂方法，便于按对应 role 创建消息。
- 为 `content` 字段加入与 `role` 类型对应的约束。

## Permission 🆕

- 新增权限系统，用于 tool 执行的细粒度门控、human-in-the-loop 确认以及 agent 整体自治度控制。

## Tool

- 新增 `ToolBase` 抽象，统一所有 tool 的基类。
- 重构内置 tool：
	- 新增 `Bash`、`Edit`、`Glob`、`Grep`、`Read`、`Write`，并接入权限控制。
	- 新增 `TaskCreate`、`TaskGet`、`TaskList`、`TaskUpdate`，用于任务管理。

`Toolkit` 重构：

- 在 `Toolkit` 抽象中将 tool、skill、MCP 与 tool group 作为一等公民统一支持。
- 新增 `ToolGroup`，支持按需激活，保留名 `basic` 组始终在线。
- 新增 `ResetTools` meta-tool，供 agent 在运行时切换 tool group。
- 新增 `MCPTool` 与 `FunctionTool` 适配器，统一 tool 注册方式。

## MCP

- 将 MCP 实现重构为单一的 `MCPClient` 类，提供统一的客户端接口。
- 新增 `StdioMCPConfig` 与 `HttpMCPConfig` 声明式配置类型，用于类型化 MCP 配置。

## Skill 🆕

- 新增 skill loader 抽象，支持从文件系统 / sandbox / web 即时加载 skill。
- 新增 `LocalSkillLoader`，支持基于目录的 skill 加载与监听。
- 支持将 skill 打包为 `ToolGroup`，便于按需激活与组织。

## Workspace 🆕

- 新增 workspace 抽象，通过统一接口提供 tool、MCP、skill 与上下文 offload 能力。
- 新增 `LocalWorkspace`、`DockerWorkspace`、`E2BWorkspace` 实现，共享同一份 agent 接口，支持执行后端无差别切换。
- 新增 `Offloader` protocol，由 `Agent` 消费，用于上下文压缩与超大工具结果处理。
- 新增 `LocalWorkspaceManager`、`DockerWorkspaceManager`、`E2BWorkspaceManager`，提供面向多租户服务的 **agent 级隔离**。
- 新增 in-workspace **MCP gateway**，让宿主侧 agent 能访问运行在容器与 sandbox 内部的 MCP server。

## Model

- 将 credential 管理从 model 类中解耦，集中到新的 `Credential` 模块。
- 支持基于 credential 的模型列举与获取。
- 支持 Kimi、Moonshot、DeepSeek、XAI 与 OpenAI Response API。
- 将 formatter 集成到 chat model 抽象中，并为不同 model provider 提供默认 formatter。
- 新增 `ModelCard` schema，描述模型身份、能力与参数覆盖。
- 新增类方法 `list_models`，便于前端进行模型列举与选择。
- 废弃 `Trinity` model wrapper。

## Middleware 🆕

- 将 hook 机制重构为更通用的 agent middleware 系统。
- 新增 `TracingMiddleware`，作为 OpenTelemetry tracing 的新入口，取代 agent 内部集成。

## Agent Service 🆕

- 在 `app` 模块下新增基于 FastAPI 的 agent service 与 sandbox 支持。
- 新增 `create_app` FastAPI factory，统一暴露 agent、chat、model、credential、session、schedule、workspace 与 background-task 路由。
- 新增 lifespan 周期内的 `SessionManager`、`SchedulerManager`、`BackgroundTaskManager` 与 workspace manager，用于多租户资源分配。
- 新增 `AGUIProtocolMiddleware` 处理流式输出，`ToolOffloadMiddleware` 处理超大负载。
- 新增基于 Redis 的存储后端。

## Memory

- 在 2.0 中废弃 memory 模块，原因是该模块与 agent 逻辑耦合过深。

## RAG & Long-Term Memory

- 将 RAG 与 long-term memory 统一到单一模块下。
- 从 1.0 到 2.0 的迁移正在进行中，knowledge base、document reader 与 store 将基于 2.0 架构在后续版本中陆续上线。