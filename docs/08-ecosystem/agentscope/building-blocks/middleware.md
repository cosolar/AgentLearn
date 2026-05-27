## 概述

Agent middleware 是在不修改 agent 或 model 代码的前提下，向 agent 执行流程中的关键位置注入自定义逻辑（日志、追踪、输入改写、访问控制等）的机制。

AgentScope 中，可以在 5 个位置上设置 hook，覆盖了从外层 reply 流程一路下沉到底层模型 API 调用的全链路：

| 位置 | 类型 | 说明 |
|------|------|------|
| `on_reply` | Onion | 包裹一次完整的 reply 流程，覆盖其中所有 ReAct 轮次、工具执行与最终输出 |
| `on_reasoning` | Onion | 包裹一轮 ReAct 中的推理步骤（输入组装 → 模型调用 → 流式解码） |
| `on_acting` | Onion | 包裹一次工具调用的执行 |
| `on_model_call` | Onion | 包裹一次底层 `ChatModel` API 调用，最贴近模型 |
| `on_system_prompt` | Transformer | 在每次组装 system prompt 时触发；多个 middleware 串行接力，每一个把上一个的输出再做一次变换 |

两种类型的差别：

- **Onion**（洋葱式）—— middleware 包裹下一层 handler，可以在 `next_handler()` 前后插入逻辑、观察中间事件流。
- **Transformer**（变换式）—— middleware 之间串成流水线，前一个的输出作为后一个的输入，不存在「内层」概念。

下图展示这些 hook 在 agent 生命周期中的嵌套关系。`on_system_prompt` 嵌入在 `on_reasoning` 内部，因为它在 reasoning 步骤组装 system prompt 时被触发：

  <ul><li>📁 on_reply<ul>
    <ul><li>📁 ReAct loop（每一轮）<ul>
      <ul><li>📁 on_reasoning<ul>
        <li>📄 on_system_prompt（组装 system prompt）</li>
        <li>📄 on_model_call（模型 API 调用）</li>
      </ul></li></ul>
      <ul><li>📁 on_acting（每个工具调用一次）<ul>
    </ul></li></ul>
  </ul></li></ul>

> **注意：** 当前 `on_acting` 只包裹 agent 运行时内部的工具执行；通过 external execution 在 agent 外部执行的工具不会被 `on_acting` 追踪到。

## 装备 Middleware

AgentScope 把一组 hook 装在一个类里 —— 同一个 middleware 类可以同时实现 5 个位置中任意子集的 hook。把实例传入 `Agent(middlewares=[...])` 即可装备：

```python
from agentscope import Agent
from agentscope.middleware import TracingMiddleware

agent = Agent(
    name="assistant",
    system_prompt="You are a helpful assistant.",
    model=model,
    toolkit=toolkit,
    middlewares=[TracingMiddleware()],
)
```

构造时 agent 会扫描每个 middleware 实例，按它实际实现了哪些 hook，把它分配到对应位置的执行列表中。未实现的位置自动跳过，不产生任何调用开销。

## 内置 Middleware

### TracingMiddleware

`TracingMiddleware` 为 agent 全生命周期接入 [OpenTelemetry](https://opentelemetry.io/docs/specs/semconv/gen-ai/) 追踪。它在 `on_reply`、`on_model_call`、`on_acting` 三个位置打点，按层级生成 span。

使用前先在进程中注册 `TracerProvider` 与 OTLP 导出器：

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")),
)
trace.set_tracer_provider(provider)
```

随后把 `TracingMiddleware` 装到 agent 上即可：

```python
from agentscope import Agent
from agentscope.middleware import TracingMiddleware

agent = Agent(
    name="assistant",
    system_prompt="You are a helpful assistant.",
    model=model,
    toolkit=toolkit,
    middlewares=[TracingMiddleware()],
)
```

每次 reply 会产出一棵嵌套 span 树，每个层级捕获的关键属性如下：

#### Agent Reply Span

来自 `on_reply`：
  - Agent 名称、session ID、reply ID
  - 输入消息与最终输出消息
  - HITL 等待中的工具调用
  - External execution 等待中的工具调用

#### Model Call Span

来自 `on_model_call`：
  - 模型名、提供商、输入 / 输出 token 数
  - 请求与响应的消息内容
  - 对流式响应做包装，在最终 chunk 上写入属性

#### Tool Execution Span

来自 `on_acting`：
  - 工具名、调用 ID、入参
  - 工具执行结果

未配置 `TracerProvider` 时，所有 hook 会直接短路到 `next_handler()`，不创建 span 也不计算属性 —— 几乎零开销。

> **信息：** Agent 收到 `ExternalExecutionResultEvent`（外部执行的工具结果）时，`TracingMiddleware` 会为每条外部执行结果合成一个补偿 span，让外部系统执行的工具也能保留完整可观测性。

## 自定义 Middleware

继承 `MiddlewareBase`，只实现需要的 hook 即可，其它的不用管。

下面的示例用一个 middleware 覆盖了 4 个位置。每个 onion hook 都会收到一个 `input_kwargs` 字典，承载流入下一层的字段，通过 `next_handler(**input_kwargs)` 透传，也可以用关键字参数覆写其中某些字段：

```python
from typing import AsyncGenerator, Awaitable, Callable

from agentscope import Agent
from agentscope.event import AgentEvent
from agentscope.message import Msg
from agentscope.middleware import MiddlewareBase
from agentscope.model import ChatResponse

class FullObservabilityMiddleware(MiddlewareBase):
    """同时观察 reply、reasoning、model_call、system_prompt 四个位置。"""

    async def on_reply(
        self,
        agent: Agent,
        # {"inputs": Msg | list[Msg] | UserConfirmResultEvent | ExternalExecutionResultEvent | None}
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator[AgentEvent | Msg, None]],
    ) -> AsyncGenerator[AgentEvent | Msg, None]:
        print(f"[reply] start for {agent.name}")
        async for item in next_handler(**input_kwargs):
            yield item
        print(f"[reply] end for {agent.name}")

    async def on_reasoning(
        self,
        agent: Agent,
        # {"tool_choice": ToolChoice | None}
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator[AgentEvent, None]],
    ) -> AsyncGenerator[AgentEvent, None]:
        print("[reasoning] start")
        async for event in next_handler(**input_kwargs):
            yield event
        print("[reasoning] end")

    async def on_model_call(
        self,
        agent: Agent,
        # {"messages": list[Msg], "tools": list[dict], "tool_choice": ToolChoice | None, "current_model": ChatModelBase}
        input_kwargs: dict,
        next_handler: Callable[
            ..., Awaitable[ChatResponse | AsyncGenerator[ChatResponse, None]]
        ],
    ) -> ChatResponse | AsyncGenerator[ChatResponse, None]:
        print(f"[model_call] {input_kwargs['current_model'].model}")
        result = await next_handler(**input_kwargs)
        print("[model_call] done")
        return result

    async def on_system_prompt(
        self,
        agent: Agent,
        current_prompt: str,
    ) -> str:
        print(f"[system_prompt] length={len(current_prompt)}")
        return current_prompt
```

### 执行顺序

Onion 类 hook（`on_reply`、`on_reasoning`、`on_acting`、`on_model_call`）—— **列表中第一个 middleware 处于最外层**：

```python
middlewares = [mw1, mw2]
# 调用顺序：
# mw1 前 → mw2 前 → 内部逻辑 → mw2 后 → mw1 后
```

对于流式 / 产出事件的 hook，内层 middleware 先看到每一个 yield 出的事件：

```
mw1_pre → mw2_pre → mw2_event → mw1_event → ... → mw2_post → mw1_post
```

Transformer 类 hook（`on_system_prompt`）—— middleware **从左到右串行接力**：

```python
middlewares = [mw1, mw2]
# original_prompt → mw1.on_system_prompt() → mw2.on_system_prompt() → final
```

一次 reply 中各 hook 的整体执行顺序遵循 agent 生命周期：

```
on_reply
  └── 每一轮 ReAct：
        ├── compress_context() → on_system_prompt（统计 token 时）
        ├── on_reasoning
        │     ├── _prepare_model_input() → on_system_prompt
        │     └── on_model_call
        └── on_acting（本轮每个工具调用一次）
```

## 实用示例

### 计时 middleware

下面的 middleware 记录每次模型调用的耗时：

```python
import time
from agentscope.middleware import MiddlewareBase

class TimingMiddleware(MiddlewareBase):
    async def on_model_call(self, agent, input_kwargs, next_handler):
        model_name = input_kwargs["current_model"].model
        start = time.time()

        result = await next_handler()

        elapsed = time.time() - start
        print(f"[timing] {agent.name} → {model_name}: {elapsed:.2f}s")
        return result
```

### 限速 middleware

下面的 middleware 在两次模型调用之间强制留出最小间隔：

```python
import asyncio
import time
from agentscope.middleware import MiddlewareBase

class RateLimitMiddleware(MiddlewareBase):
    def __init__(self, min_interval: float = 1.0):
        self._last_call = 0.0
        self._min_interval = min_interval

    async def on_model_call(self, agent, input_kwargs, next_handler):
        now = time.time()
        wait = self._min_interval - (now - self._last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_call = time.time()
        return await next_handler()
```

### 动态 system prompt middleware

下面的 middleware 在 system prompt 中注入实时上下文：

```python
from datetime import datetime
from agentscope.middleware import MiddlewareBase

class DynamicContextMiddleware(MiddlewareBase):
    def __init__(self, context_fn):
        self._context_fn = context_fn

    async def on_system_prompt(self, agent, current_prompt):
        context = self._context_fn()
        return f"{current_prompt}\n\n## Current Context\n{context}"

agent = Agent(
    ...
    middlewares=[
        DynamicContextMiddleware(
            lambda: f"Time: {datetime.now().isoformat()}"
        ),
    ],
)
```

### 模型回退 middleware

下面的 middleware 在主模型失败时切换到备用模型：

```python
from agentscope.middleware import MiddlewareBase

class ModelFallbackMiddleware(MiddlewareBase):
    def __init__(self, fallback_model):
        self._fallback = fallback_model

    async def on_model_call(self, agent, input_kwargs, next_handler):
        try:
            return await next_handler()
        except Exception as e:
            print(f"Primary model failed: {e}, switching to fallback")
            return await next_handler(
                current_model=self._fallback,
            )
```