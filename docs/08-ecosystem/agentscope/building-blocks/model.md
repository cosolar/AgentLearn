## 概述

模型层采用两层结构：上层是 **Credential**，下层是该提供商支持的若干模型族 —— **Chat Model**、**TTS**、**Embedding** 与 **Realtime Model**。

  <ul><li>📁 Credential<ul>
    <ul><li>📁 ChatModelBase<ul>
      <li>📄 OpenAIChatModel</li>
      <li>📄 AnthropicChatModel</li>
      <li>📄 DashScopeChatModel</li>
      <li>📄 ...</li>
    </ul></li></ul>
    <ul><li>📁 TTSModelBase (coming soon)<ul>
    <ul><li>📁 EmbeddingModelBase (coming soon)<ul>
    <ul><li>📁 RealtimeModelBase (coming soon)<ul>
  </ul></li></ul>

**Credential** 承载某个提供商的 API 认证字段（`api_key`、`base_url` 等）。从一个凭证出发，可以列出该提供商在每个模型族下支持的全部可用模型。

这种分层与前端的自然交互流程一致 —— 先注册凭证，再从凭证下挑选模型 —— 让界面只需鉴权一次，就能展示该提供商支持的所有模型族。

## Chat Model

**Chat Model** 是驱动 agent 对话与工具调用的 LLM，输入输出可以是文本之外的多模态内容。AgentScope 当前提供以下 Chat Model 类：

| 提供商 | 模型类 | 说明 |
|--------|--------|------|
| OpenAI | `OpenAIChatModel` | Chat Completions API，兼容 vLLM 与 OpenAI 兼容端点 |
| OpenAI (Responses) | `OpenAIResponseModel` | Responses API，原生支持推理（o3、o4-mini） |
| Anthropic | `AnthropicChatModel` | Claude 模型，支持 extended thinking 与 prompt 缓存 |
| DashScope | `DashScopeChatModel` | Qwen 模型，多模态（视觉/音频/视频）、推理 |
| DeepSeek | `DeepSeekChatModel` | OpenAI 兼容，带 prompt cache 命中 token |
| Gemini | `GeminiChatModel` | Google Gemini 模型，支持多模态 |
| Moonshot | `MoonshotChatModel` | Kimi 模型（OpenAI 兼容） |
| xAI | `XAIChatModel` | Grok 模型，原生 reasoning effort |
| Ollama | `OllamaChatModel` | 本地 LLM 托管，凭证可选 |

### 创建 Chat Model

每个 Chat Model 接收一个凭证、一个模型名，以及可选的提供商专属 `Parameters` 对象。下面三个 tab 分别展示流式、工具调用与推理三种典型初始化场景：

##### Streaming

```python
import os
from agentscope.model import DashScopeChatModel
from agentscope.credential import DashScopeCredential

model = DashScopeChatModel(
    credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
    model="qwen-plus",
    stream=True,
)
```

##### Tools

```python
import os
from agentscope.model import DashScopeChatModel
from agentscope.credential import DashScopeCredential

model = DashScopeChatModel(
    credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
    model="qwen-plus",
    stream=False,
    parameters=DashScopeChatModel.Parameters(
        parallel_tool_calls=False,
    ),
)
```

##### Reasoning

```python
import os
from agentscope.model import DashScopeChatModel
from agentscope.credential import DashScopeCredential

model = DashScopeChatModel(
    credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
    model="qwen3-235b-a22b-thinking-2507",
    parameters=DashScopeChatModel.Parameters(
        thinking_enable=True,
        thinking_budget=2048,
    ),
)
```

所有 Chat Model 共享的构造参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| `credential` | `CredentialBase` | 提供商专属凭证 |
| `model` | `str` | 模型标识符（例如 `"qwen-plus"`） |
| `parameters` | `Parameters \| None` | 提供商专属参数，例如 `temperature`、`thinking_enable`、`parallel_tool_calls` |
| `stream` | `bool` | 是否流式输出 |
| `max_retries` | `int` | API 失败时的最大重试次数 |
| `context_size` | `int` | 上下文窗口大小，用于上下文压缩 |
| `formatter` | `FormatterBase \| None` | 覆盖默认的消息 formatter |

### 调用 Chat Model

通过传入一组 `Msg` 对象（以及可选的 `tools` 和 `tool_choice`）调用模型：

```python
async def __call__(
    self,
    messages: list[Msg],
    tools: list[dict] | None = None,
    tool_choice: ToolChoice | None = None,
    **kwargs: Any,
) -> ChatResponse | AsyncGenerator[ChatResponse, None]:
```

返回类型取决于模型的 `stream` 设置：

- **`stream=False`** —— 返回单个 `ChatResponse`，承载完整输出。
- **`stream=True`** —— 返回 `AsyncGenerator[ChatResponse, None]`。中间 chunk（`is_last=False`）只携带本步生成的**增量**内容。为了让调用方无需自行累积增量，AgentScope 会在末尾追加一个 `is_last=True` 的 chunk，承载**完整的累积内容**。

```python
import asyncio
import os
from agentscope.model import DashScopeChatModel
from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg

async def main():
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
        stream=True,
    )
    msgs = [UserMsg(name="user", content="Count from 1 to 5.")]

    async for chunk in await model(msgs):
        if chunk.is_last:
            print("Final:", chunk.content)   # 完整累积内容
        else:
            print("Delta:", chunk.content)   # 仅增量

asyncio.run(main())
```

一段典型的流式输出示例，展示「增量 → 累积」的模式：

```
Delta: [TextBlock(text='1')]
Delta: [TextBlock(text=', 2,')]
Delta: [TextBlock(text=' 3, ')]
Delta: [TextBlock(text='4, 5')]
Final: [TextBlock(text='1, 2, 3, 4, 5')]
```

每个 `ChatResponse` 包含若干 content block（`TextBlock`、`ThinkingBlock`、`ToolCallBlock`、`DataBlock`）、一个 `is_last` 标志，以及记录 token 数与耗时的 `ChatUsage`。

### 生成结构化输出

当需要返回符合 Pydantic 模型或 JSON schema 的结构化结果时，调用 `generate_structured_output` 而非 `__call__`。它返回一个 `StructuredResponse`，其 `content` 是经过 schema 校验的 dict：

```python
import asyncio
import os
from pydantic import BaseModel
from agentscope.model import DashScopeChatModel
from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg

class WeatherInfo(BaseModel):
    city: str
    temperature: float
    unit: str

async def main():
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
        stream=False,
    )
    response = await model.generate_structured_output(
        messages=[UserMsg(name="user", content="What's the weather in Shanghai?")],
        structured_model=WeatherInfo,
    )
    print(response.content)  # 符合 WeatherInfo 的 dict

asyncio.run(main())
```

> **信息：** `generate_structured_output` 会基于 schema 合成一个强制工具调用，再对模型输出做校验与修复。

### Formatter

**Formatter** 负责把 AgentScope 的 `Msg` 对象转换为各提供商 API 期望的 `list[dict]` 载荷。它通过 Chat Model 构造函数中可选的 `formatter` 参数配置。每个提供商内置两种 formatter：

| 类型 | 适用场景 |
|------|----------|
| **ChatFormatter**（默认） | 标准的单 agent 对话。每条 `Msg` 1:1 映射为一条 API 消息，保留原始角色（`user`、`assistant`、`system`）。 |
| **MultiAgentFormatter** | 多 agent 场景，例如辩论、moderator 等。连续的 agent 消息会被聚合，并用 `<history>` 标签包裹，标注发送者名字；工具调用 / 结果序列保持原 API 格式。 |

切换到多 agent 模式只需传入 MultiAgent 变体，无需修改 agent 代码：

```python
import os
from agentscope.model import OpenAIChatModel
from agentscope.credential import OpenAICredential
from agentscope.formatter import OpenAIMultiAgentFormatter

model = OpenAIChatModel(
    credential=OpenAICredential(api_key=os.environ["OPENAI_API_KEY"]),
    model="gpt-4.1",
    formatter=OpenAIMultiAgentFormatter(),
)
```

如果提供商的载荷格式不属于 OpenAI 或 Anthropic 风格，开发者可以继承 `FormatterBase` 实现自定义 formatter，并通过同一个 `formatter` 参数传入。

### 自定义 Provider

开发者可以通过实现一个 credential 与一个 chat model，并注册该 credential，把自定义模型提供商接入 AgentScope。

#### 步骤 1：定义 Credential

继承 `CredentialBase`，使用唯一的 `type` 判别字段，并实现 `get_chat_model_class()`：

```python
from typing import Literal, Type, TYPE_CHECKING
from pydantic import ConfigDict, Field, SecretStr
from agentscope.credential import CredentialBase

if TYPE_CHECKING:
    from agentscope.model import ChatModelBase

class MyProviderCredential(CredentialBase):
    model_config = ConfigDict(title="My Provider API")
    type: Literal["my_provider_credential"] = "my_provider_credential"

    api_key: SecretStr = Field(description="API key for My Provider.")
    base_url: str = Field(default="https://api.myprovider.com/v1")

    @classmethod
    def get_chat_model_class(cls) -> Type["ChatModelBase"]:
        from .my_model import MyProviderChatModel
        return MyProviderChatModel
```

#### 步骤 2：实现 Chat Model

继承 `ChatModelBase`，定义内部 `Parameters` 类，并实现 `_call_api`：

```python
from typing import Literal, Any, AsyncGenerator
from pydantic import BaseModel, Field
from agentscope.model import ChatModelBase, ChatResponse
from agentscope.message import Msg
from agentscope.tool import ToolChoice
from agentscope.formatter import FormatterBase, OpenAIChatFormatter

class MyProviderChatModel(ChatModelBase):
    class Parameters(BaseModel):
        max_tokens: int | None = Field(default=None, gt=0)
        temperature: float | None = Field(default=None, ge=0, le=2)

    type: Literal["my_provider_chat"] = "my_provider_chat"

    def __init__(
        self,
        credential: "MyProviderCredential",
        model: str,
        parameters: Parameters | None = None,
        stream: bool = True,
        max_retries: int = 3,
        context_size: int = 128000,
        formatter: FormatterBase | None = None,
    ) -> None:
        super().__init__(
            credential=credential,
            model=model,
            parameters=parameters or self.Parameters(),
            stream=stream,
            max_retries=max_retries,
            context_size=context_size,
        )
        # 如果 API 兼容 OpenAI 格式，复用 OpenAIChatFormatter；
        # 否则自行实现 FormatterBase 子类。
        self.formatter = formatter or OpenAIChatFormatter()

    async def _call_api(
        self,
        model_name: str,
        messages: list[Msg],
        tools: list[dict] | None = None,
        tool_choice: ToolChoice | None = None,
        **kwargs: Any,
    ) -> ChatResponse | AsyncGenerator[ChatResponse, None]:
        formatted_messages = await self.formatter.format(messages)
        # 用 self.credential.api_key 等调用提供商 API
        ...
```

#### 步骤 3：添加 Model Card（可选）

把 YAML 文件放在模型实现旁边的 `_models/` 目录里。每个文件描述一个模型 —— 它的能力（`input_types`、`output_types`）、上限（`context_size`、`output_size`），以及该模型专属的 `parameter_overrides`：

```yaml
name: my-model-v1
label: My Model V1
status: active
input_types:
  - text/plain
output_types:
  - text/plain
context_size: 128000
output_size: 4096
parameter_overrides:
  max_tokens: {"maximum": 4096}
```

`MyProviderChatModel.list_models()` 会加载该目录下的所有 YAML。如果想从其他位置（例如应用自己维护的模型注册表）拉取 Model Card，传入 `custom_yaml_dir`：

```python
cards = MyProviderChatModel.list_models(custom_yaml_dir="/path/to/cards")
```

## 前端集成

### 什么是 ModelCard

`ModelCard` 是对模型能力与约束的声明式描述，用于驱动前端 —— 模型选择器、参数表单、能力开关都可以基于它动态渲染，无需在前端硬编码任何提供商相关的逻辑。

每个 `ModelCard` 包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 模型标识符（例如 `"claude-sonnet-4-6"`） |
| `label` | `str` | 用于展示的可读名称（例如 `"Claude Sonnet 4.6"`） |
| `status` | `"active" \| "deprecated" \| "sunset"` | 模型生命周期状态 |
| `input_types` | `list[str]` | 接受的输入 MIME 类型 —— 前端据此过滤附件上传组件（例如仅在支持 `image/*` 时显示图片按钮） |
| `output_types` | `list[str]` | 模型可输出的 MIME 类型 —— 用于标注模型能力（例如出现 `application/x-thinking` 时启用思考开关） |
| `context_size` | `int` | 最大上下文窗口（token 数） |
| `output_size` | `int` | 最大输出 token 数 |
| `parameter_schema` | `dict` | 最终用于渲染参数表单的 JSON Schema —— 由基础 schema 与 per-model override 合并而来（见下文） |
| `parameters_overrides` | `dict[str, dict]` | 合并前的原始 per-model override |

`input_types` 与 `output_types` 都用 MIME 类型描述模态，常见取值如下：

| MIME 类型 | 含义 |
|-----------|------|
| `text/plain` | 文本 |
| `application/x-thinking` | 推理 / 思考链 |
| `image/*`（如 `image/png`、`image/jpeg`） | 图片 |
| `audio/*`（如 `audio/wav`、`audio/mp3`） | 音频 |
| `video/*`（如 `video/mp4`） | 视频 |

`claude-sonnet-4-6` 的典型 YAML：

```yaml
name: claude-sonnet-4-6
label: Claude Sonnet 4.6
status: active

input_types:
  - text/plain
  - image/jpeg
  - image/png
  - image/gif
  - image/webp

output_types:
  - text/plain
  - application/x-thinking

context_size: 1000000
output_size: 65536

parameter_overrides:
  max_tokens: {"maximum": 65536}
```

#### 参数 schema 与 override

暴露给前端的 `parameter_schema` 由两层叠加而成：

1. **基础 schema** —— 由 Chat Model 的 `Parameters` 类通过 `model_json_schema()` 自动生成，列出全部可调参数（`temperature`、`max_tokens`、`thinking_enable` 等），并给出类型与 API 通用范围。
2. **per-model override** —— YAML 中的 `parameter_overrides` 块会按字段叠加在基础 schema 之上。

override 之所以重要，是因为同一个 API 下不同模型的可调范围并不一致：每个 Qwen 模型都接受 `max_tokens`，但上限各不相同。借助 override，Model Card 可以收紧某个范围、固定默认值，或隐藏某个不适用的参数。

| Override 写法 | 效果 |
|---------------|------|
| `param: { ... }` | 浅合并到基础字段（例如 `max_tokens: {maximum: 16384}`） |
| `param: { hidden: true }` | 在前端隐藏该参数 |
| `param: null` | 完全移除该参数 |

### 获取 ModelCard

通过 credential 类或 model 类调用 `list_models()` 获取 Model Card。`CredentialBase.list_models()` 内部会委托到与之关联的 `ChatModelBase` 子类（通过 `get_chat_model_class()` 拿到），后者会从其 `_models/` 目录加载 YAML。

```python
from agentscope.credential import DashScopeCredential
from agentscope.model import AnthropicChatModel

# 通过 credential 类
cards = DashScopeCredential.list_models()

# 也可以直接通过 model 类
cards = AnthropicChatModel.list_models()

for card in cards:
    print(f"{card.name}: context={card.context_size}, inputs={card.input_types}")
```

`get_chat_model_class()` 返回对应的 `ChatModelBase` 子类，该子类知道如何定位它的 Model Card YAML：

```python
model_cls = DashScopeCredential.get_chat_model_class()  # -> DashScopeChatModel
cards = model_cls.list_models()                          # -> list[ModelCard]
```

这种设计让前端只需一个 credential，就能发现所有可用模型、它们的能力与合法参数范围 —— 无需任何硬编码的提供商逻辑。

## TTS

> **提示：** 即将上线 —— TTS 支持正在从 v1.0 迁移到 v2.0。

## Embedding

> **提示：** 即将上线 —— Embedding 支持正在从 v1.0 迁移到 v2.0。

## Realtime Model

> **提示：** 即将上线 —— Realtime Model 支持正在从 v1.0 迁移到 v2.0。