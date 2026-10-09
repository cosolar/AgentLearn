## 安装

AgentScope 需要 Python 3.11 及以上版本，可以通过 PyPI 或源码进行安装。

推荐使用 [uv](https://github.com/astral-sh/uv) 来安装 AgentScope。

### 通过 PyPI 安装

```bash
uv pip install agentscope
```

### 通过源码安装

```bash
git clone -b main https://github.com/agentscope-ai/agentscope
cd agentscope
uv pip install -e .
```

### 验证安装

安装完成后，可以执行以下代码确认是否安装成功：

```python
import agentscope

print(agentscope.__version__)
```

## 第一个智能体

下面的示例构建了一个最简智能体：一个 DashScope 凭据、对应的聊天模型、一个空工具集，以及一个 `Agent` 实例。智能体提供两个调用入口 —— `reply` 返回最终消息，`reply_stream` 则以流式方式逐步产出事件，适合展示推理和工具调用的中间过程。

```python
import asyncio
import os

from agentscope.agent import Agent
from agentscope.credential import DashScopeCredential
from agentscope.event import EventType
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit, Bash, Read, Write, Edit

async def main() -> None:
    agent = Agent(
        name="Friday",
        system_prompt="You are a helpful assistant named Friday.",
        model=DashScopeChatModel(
            credential=DashScopeCredential(
                api_key=os.getenv("DASHSCOPE_API_KEY"),
            ),
            model="qwen-plus",
        ),
        toolkit=Toolkit(tools=[Bash(), Read(), Write(), Edit()]),
    )

    user_msg = UserMsg(name="user", content="Hello, who are you?")

    # 方式一：等待最终的助手消息。
    reply_msg = await agent.reply(user_msg)
    # `reply_msg` 是一个 `AssistantMsg`，其 `content` 是一组内容块。
    # 可按需检查文本块、工具调用等。
    ...

    # 方式二：流式获取增量事件（文本片段、工具调用等）。
    async for event in agent.reply_stream(user_msg):
        # 根据 `event.type` 分发处理 —— 每个分支对应一种事件类型。
        match event.type:
            case EventType.TEXT_BLOCK_DELTA:
                # 模型返回的流式文本片段 —— 追加到界面或标准输出。
                ...
            case EventType.TOOL_CALL_START:
                # 智能体即将调用工具 —— 展示调用信息。
                ...
            case _:
                # 其他事件：思考块、工具结果、回复结束等。
                ...

asyncio.run(main())
```

> **提示：** 运行脚本前，需要在环境变量中设置 `DASHSCOPE_API_KEY`。如果想切换到其他模型提供商，将 `DashScopeCredential` 和 `DashScopeChatModel` 替换为对应的配对即可，例如 `OpenAICredential` 和 `OpenAIChatModel`。

## 额外依赖

为了满足不同功能的需求，AgentScope 提供了可按需安装的额外依赖包。

- **full**：包含模型 API、工具函数等额外依赖。
- **dev**：开发依赖，包含测试和文档工具。

以安装完整依赖为例，安装命令因操作系统而有所不同。

- Windows 用户：

```bash
uv pip install agentscope[full]
```

- Mac 和 Linux 用户：

```bash
uv pip install agentscope\[full\]
```