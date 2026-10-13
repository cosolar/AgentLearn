"""agent.py —— Agent 核心（LangChain v1）

对应教程 7.1「Agent 核心：create_agent + 异步 / 流式」。
把 Agent 的构建与调用与 Web 层解耦：main.py 只调用 SupportAgent 的方法。

依赖：langchain v1 / langchain-openai（模块级延迟导入，便于静态检查）。
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

from config import settings


class SupportAgent:
    """带会话记忆的客服 Agent。"""

    def __init__(self) -> None:
        from langchain.agents import create_agent
        from langchain_openai import ChatOpenAI
        from langgraph.checkpoint.memory import InMemorySaver

        model = ChatOpenAI(
            model=settings.llm_model_name,
            api_key=settings.llm_api_key or os.getenv("LLM_API_KEY"),
            base_url=settings.llm_base_url or os.getenv("LLM_BASE_URL"),
            temperature=0.3,
        )
        self._agent = create_agent(
            model=model,
            tools=[],                       # 生产环境在此挂载业务工具
            system_prompt=(
                "你是 ACME 公司的客服助手。用中文、简洁、礼貌地回答；"
                "不确定的信息不要编造，引导用户联系人工客服。"
            ),
            checkpointer=InMemorySaver(),   # thread_id 维度自动记忆
        )

    @staticmethod
    def _config(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    async def ainvoke(self, message: str, thread_id: str = "default") -> str:
        """一次性返回完整回答。"""
        result = await self._agent.ainvoke(
            {"messages": [{"role": "user", "content": message}]},
            self._config(thread_id),
        )
        return result["messages"][-1].content

    async def astream(self, message: str, thread_id: str = "default") -> AsyncIterator[str]:
        """逐块流式产出回答（供 SSE 使用）。"""
        async for chunk in self._agent.astream(
            {"messages": [{"role": "user", "content": message}]},
            self._config(thread_id),
            stream_mode="messages",
        ):
            message_chunk, _metadata = chunk
            content = getattr(message_chunk, "content", "")
            if content:
                yield content
