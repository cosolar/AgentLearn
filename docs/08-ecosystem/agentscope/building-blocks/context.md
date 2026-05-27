## 概述

Context 是 agent 的工作记忆 —— LLM 在每一步推理时看到的全部消息（用户输入、assistant 回复、工具调用、工具结果）。随着对话变长，原始上下文最终会超出模型的窗口。AgentScope 通过三种机制让 agent 持续运行下去：

- **上下文压缩** —— 当 token 用量逼近模型上限时，把较早的消息汇总成一段摘要。
- **工具结果截断** —— 在过大的工具输出进入上下文之前先截断。
- **上下文 offload** —— 把已经从上下文中移除的内容持久化到外部存储，供 agent 后续检索。

每次模型调用前，agent 会把三层内容拼成单次 API 输入。下图展示这次调用所包含的结构：

  <ul><li>📁 Model API Input<ul>
    <ul><li>📁 System Prompt<ul>
      <li>📄 基础 system prompt</li>
      <li>📄 Skill 指令（来自 Toolkit）</li>
      <li>📄 on_system_prompt middleware 转换</li>
    </ul></li></ul>
    <li>📄 Summary（已压缩历史，若存在）</li>
    <li>📄 Context（最近未压缩消息）</li>
  </ul></li></ul>

每一层的构成方式：

1. **System prompt** —— 以创建 agent 时传入的 `system_prompt` 为起点，拼接 skill 指令（每个 skill 的名称与描述，来自 toolkit），再依次执行所有 `on_system_prompt` [middleware](building-blocks/middleware.md) 钩子。
2. **Summary** —— 较早消息被压缩后的摘要；只有发生过压缩之后才存在。
3. **Context** —— 最近的、尚未压缩的消息（用户输入、assistant 回复、工具调用、工具结果）。

> **提示：** 通过 `on_system_prompt` middleware 钩子注入动态上下文 —— 工作目录指令、时效性信息、环境细节 —— 无需改写基础 prompt。

## 紧凑化上下文

当上下文窗口被填满时，AgentScope 会通过 `ContextConfig` 控制的两套自动机制保持其形态：**上下文压缩**（汇总较早消息）与**工具结果截断**（截断过大的工具输出）。两者均透明运行 —— agent 不会因此中断。

### 配置 ContextConfig

`ContextConfig` 在创建 agent 时传入：

```python
from agentscope import Agent
from agentscope.agent import ContextConfig

agent = Agent(
    name="my_agent",
    system_prompt="...",
    model=model,
    toolkit=toolkit,
    context_config=ContextConfig(
        trigger_ratio=0.8,
        reserve_ratio=0.1,
        tool_result_limit=3000,
    ),
)
```

可用字段：

| 参数                  | 类型      | 说明                                                                       |
|----------------------|-----------|----------------------------------------------------------------------------|
| `trigger_ratio`      | `float`   | 当 token 用量超过该比例 × 模型上下文长度时触发压缩（上限 `0.9`）             |
| `reserve_ratio`      | `float`   | 压缩后作为最近消息保留的上下文 token 比例                                  |
| `tool_result_limit`  | `int`     | 单条工具结果的最大 token 数，超出则截断                                    |
| `compression_prompt` | `str`     | 引导模型生成摘要的 prompt                                                  |
| `summary_template`   | `str`     | 把摘要拼回上下文时使用的字符串模板                                         |
| `summary_schema`     | `dict`    | 约束模型结构化摘要输出的 JSON Schema                                       |

### 压缩 Context

压缩在每次推理步骤前自动执行，流程如下：

1. **计算 token 数**

Agent 累计 system prompt、summary、context 与工具 schema 的全部 token。

2. **判断阈值**

若总数超过 `trigger_ratio × context_size`，触发压缩；否则跳过此步，正常发起模型调用。

3. **切分消息**

较早消息标记为待压缩；落在 `reserve_ratio × context_size` 内的最近消息保留。工具调用 / 结果对在切分时保持成对，不会被拆开。

4. **生成摘要**

模型基于较早消息生成一份结构化摘要，包含五个字段：`task_overview`、`current_state`、`important_discoveries`、`next_steps`、`context_to_preserve`。

5. **更新状态**

摘要替换被压缩的消息，保留下来的最近消息成为新的 context。Agent 随后继续完成本次推理步骤。

> **注意：** `trigger_ratio`（最高 `0.9`）与完整上下文之间的剩余 10% 是给压缩调用本身预留的 —— 模型需要空间生成摘要。

也可以调用 agent 的 `compress_context()` 方法手动触发压缩。不传参数时使用 agent 自身的 `context_config`；可通过传入一份临时的 `ContextConfig` 进行覆盖：

```python
# 使用 agent 默认配置进行检查
await agent.compress_context()

# 或针对单次调用覆盖配置（例如更激进地压缩）
from agentscope.agent import ContextConfig

await agent.compress_context(
    context_config=ContextConfig(trigger_ratio=0.5, reserve_ratio=0.1),
)
```

当 token 用量低于 `trigger_ratio × context_size` 时该方法为空操作，因此可以安全地在轮次之间或自定义检查点处随时调用。

### 截断工具结果

每次工具调用之后，agent 会比较结果的 token 数与 `tool_result_limit`。超出限额时，结果被切分为保留部分（留在上下文中）与 offload 部分（如挂载了 offloader，则交由其持久化 —— 见 [Offload Context](#offload-context)）。

保留部分会追加一段截断标记，让 agent 知道输出已被截断：

```
<<<TRUNCATED>>>
<system-reminder>The remaining content has been omitted for limited context.</system-reminder>
```

挂载了 offloader 时，标记还会指向已持久化的完整输出：

```
<<<TRUNCATED>>>
<system-reminder>The remaining content has been omitted for limited context. You can refer to the file in '/path/to/tool_result-<id>.txt' for the truncated content if needed.</system-reminder>
```

> **警告：** `tool_result_limit` 设置过低会让 agent 错过关键的工具输出；过高则可能让一次结果填满整个上下文。

## Offload Context

Context offload 是把 agent 已经从上下文中移除的内容 —— 被压缩的消息、被截断的工具输出 —— 写入外部存储，方便 agent 之后通过文件工具（Read、Grep、Glob）回查那些被压缩走的细节。

### 使用 Offloader 协议

Offload 通过 `Offloader` 协议接入 —— 该协议是结构化的，仅有两个方法：

| 方法 | 说明 |
|------|------|
| `offload_context(session_id, msgs)` | 持久化被压缩的消息；返回一个引用（例如文件路径） |
| `offload_tool_result(session_id, tool_result)` | 持久化被截断的工具结果；返回一个引用 |

任何实现该协议的对象都可以传入 agent 的 `offloader` 参数。AgentScope 的 [`workspace`](building-blocks/workspace.md) 模块提供了开箱即用的实现：

```python
from agentscope import Agent
from agentscope.workspace import LocalWorkspace

workspace = LocalWorkspace(workdir="/tmp/agent_workspace")
await workspace.initialize()

agent = Agent(
    name="my_agent",
    system_prompt="...",
    model=model,
    toolkit=toolkit,
    offloader=workspace,
)
```

未提供 `offloader` 时，被压缩的消息与被截断的工具结果在离开上下文窗口后即被丢弃。

### 使用 LocalWorkspace

`LocalWorkspace` 把 offload 的内容写到 `workdir` 之下，并按 `session_id` 隔离每次 agent 运行：

  <ul><li>📁 {workdir}<ul>
    <ul><li>📁 data<ul>
      <li>📄 {sha256}.png</li>
    </ul></li></ul>
    <ul><li>📁 sessions<ul>
      <ul><li>📁 {session_id}<ul>
        <li>📄 context.jsonl</li>
        <li>📄 tool_result-{tool_id}.txt</li>
      </ul></li></ul>
    </ul></li></ul>
    <ul><li>📁 skills<ul>
      <li>📄 ...</li>
    </ul></li></ul>
  </ul></li></ul>

内容布局如下：

- **`sessions/{session_id}/`** —— 每个 agent session 一个目录，避免并发 agent 互相干扰。被压缩的消息以追加方式写入 `context.jsonl`；每条被截断的工具结果对应一份独立的 `tool_result-{tool_id}.txt`。
- **`data/`** —— 被 offload 的消息所引用的多模态文件（图片、音频），按 SHA-256 内容哈希去重。
- **`skills/`** —— 与 offload 无关；workspace 同时承担 agent 的 skill 目录职责。

### 创建自定义 Offloader

需要接入本地文件系统以外的后端（数据库、对象存储、向量库等）时，开发者只需实现 `Offloader` 协议 —— 该协议是结构化的，无需继承：

```python
from typing import Any
from agentscope.message import Msg, ToolResultBlock

class S3Offloader:
    def __init__(self, bucket: str, prefix: str) -> None:
        self.bucket = bucket
        self.prefix = prefix

    async def offload_context(
        self,
        session_id: str,
        msgs: list[Msg],
        **kwargs: Any,
    ) -> str:
        key = f"{self.prefix}/sessions/{session_id}/context.jsonl"
        content = "\n".join(m.model_dump_json() for m in msgs)
        await self._upload(self.bucket, key, content)
        return f"s3://{self.bucket}/{key}"

    async def offload_tool_result(
        self,
        session_id: str,
        tool_result: ToolResultBlock,
        **kwargs: Any,
    ) -> str:
        key = f"{self.prefix}/sessions/{session_id}/tool_result-{tool_result.id}.txt"
        # 从工具结果块中抽取文本并上传
        ...
        return f"s3://{self.bucket}/{key}"
```

像使用任何内置 workspace 一样，把实例传入 `Agent(offloader=...)` 即可。

## 延伸阅读

- [**Workspace**](building-blocks/workspace.md) — 内置的 offloader 实现，以及 agent 的工作环境
- [**Agent**](building-blocks/agent.md) — ReAct 循环以及上下文如何在推理步骤间流转
- [**Middleware**](building-blocks/middleware.md) — 通过 middleware 钩子拦截模型调用与 system prompt 组装
- [**Tool**](building-blocks/tool.md) — 会被压缩处理的工具结果来源