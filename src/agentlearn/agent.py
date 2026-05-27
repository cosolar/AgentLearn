"""
Agent 实现 - DialogAgent / ReActAgent / UserAgent

参考 AgentScope 的 Agent 类型设计，结合 LangChain 最新 API：
- DialogAgent: 对话型，支持多轮记忆
- ReActAgent:  推理+行动型，支持工具调用（LangChain tool-calling）
- UserAgent:   人类代理，用于 Human-in-the-Loop
"""

from typing import Any, Dict, Iterator, List, Optional, Sequence, Union

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import Field

from .base import BaseAgent
from .memory import AgentMemory
from .message import Msg, MsgRole
from .tools import ServiceToolkit


# ---------------------------------------------------------------------------
# DialogAgent - 对话型 Agent
# ---------------------------------------------------------------------------
class DialogAgent(BaseAgent):
    """
    对话型 Agent - 支持多轮对话和记忆

    特点：
    - 自动维护对话上下文（工作记忆）
    - 系统提示词（sys_prompt）定义 Agent 人设
    - 支持同步/异步调用

    Usage:
        from langchain_openai import ChatOpenAI
        agent = DialogAgent(
            name="assistant",
            sys_prompt="你是一个友好的 AI 助手。",
            llm=ChatOpenAI(model="gpt-4o-mini"),
        )
        response = agent.reply(Msg.user_msg("你好"))
        print(response.content)
    """
    name: str = Field(default="dialog_agent")
    description: str = Field(default="对话型 Agent")
    memory: AgentMemory = Field(default_factory=AgentMemory)

    def reply(self, msg: Union[Msg, Sequence[Msg]]) -> Msg:
        """处理消息并返回响应"""
        if self.llm is None:
            raise ValueError(f"[{self.name}] LLM 未配置，请设置 llm 参数")

        msgs = self._to_msg_list(msg)

        # 将输入消息存入记忆
        for m in msgs:
            self.memory.add(m)

        # 构建 LangChain 消息列表
        lc_messages = self._build_lc_messages(msgs)

        # 调用 LLM（含重试）
        response = self._invoke_llm(lc_messages)

        # 将响应存入记忆
        reply_msg = Msg.agent_msg(content=response, name=self.name)
        self.memory.add(reply_msg)

        self._log(f"回复: {response[:80]}...")
        return reply_msg

    def stream_reply(self, msg: Union[Msg, Sequence[Msg]]) -> Iterator[str]:
        """
        流式回复 — 逐 token 生成内容

        迭代此方法返回的生成器即可获得流式输出片段。
        流式完成后，Agent 会自动将完整回复保存到记忆系统中。

        Args:
            msg: 用户输入消息（单条或列表）

        Yields:
            内容片段（str），每次一个 token 或一段文本

        Example:
            agent = DialogAgent(name="bot", llm=llm)
            for chunk in agent.stream_reply(Msg.user_msg("你好")):
                print(chunk, end="", flush=True)
        """
        if self.llm is None:
            raise ValueError(f"[{self.name}] LLM 未配置，请设置 llm 参数")

        msgs = self._to_msg_list(msg)
        for m in msgs:
            self.memory.add(m)

        lc_messages = self._build_lc_messages(msgs)

        full_content = ""
        try:
            for chunk in self.llm.stream(lc_messages):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                full_content += token
                yield token
        except Exception as e:
            err_msg = f"\n[流式输出错误] {type(e).__name__}: {e}"
            full_content += err_msg
            yield err_msg

        # 将完整响应存入记忆
        reply_msg = Msg.agent_msg(content=full_content, name=self.name)
        self.memory.add(reply_msg)
        self._log(f"流式回复完成 ({len(full_content)} chars): {full_content[:80]}...")

    async def areply(self, msg: Union[Msg, Sequence[Msg]]) -> Msg:
        """异步版 reply"""
        if self.llm is None:
            raise ValueError(f"[{self.name}] LLM 未配置")

        msgs = self._to_msg_list(msg)
        for m in msgs:
            self.memory.add(m)

        lc_messages = self._build_lc_messages(msgs)
        response = await self.llm.ainvoke(lc_messages)
        content = response.content if hasattr(response, "content") else str(response)

        reply_msg = Msg.agent_msg(content=content, name=self.name)
        self.memory.add(reply_msg)
        return reply_msg

    def _build_lc_messages(self, new_msgs: List[Msg]) -> List[BaseMessage]:
        """将记忆上下文 + 新消息组装为 LangChain 消息列表"""
        result: List[BaseMessage] = [SystemMessage(content=self.sys_prompt)]
        # 工作记忆中的历史（不含刚加入的新消息，避免重复）
        context = self.memory.get_context()
        seen_ids = {id(m) for m in new_msgs}
        for m in context:
            if id(m) not in seen_ids:
                result.append(m.to_langchain_message())
        # 追加本次新消息
        for m in new_msgs:
            result.append(m.to_langchain_message())
        return result

    def _invoke_llm(self, messages: List[BaseMessage]) -> str:
        """带重试的 LLM 调用"""
        last_err: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.llm.invoke(messages)
                return resp.content if hasattr(resp, "content") else str(resp)
            except Exception as e:
                last_err = e
                self._log(f"LLM 调用失败 (第{attempt}次): {e}")
        raise RuntimeError(f"[{self.name}] LLM 调用失败，已重试 {self.max_retries} 次: {last_err}")


# ---------------------------------------------------------------------------
# ReActAgent - 推理 + 行动型 Agent（工具调用）
# ---------------------------------------------------------------------------
class ReActAgent(BaseAgent):
    """
    ReAct Agent - 推理+行动循环，支持工具调用

    基于 LangChain tool-calling 机制实现 ReAct 循环：
    1. LLM 思考并决定是否调用工具
    2. 执行工具，获取结果
    3. 将工具结果反馈给 LLM
    4. 重复直到 LLM 输出最终答案

    Usage:
        toolkit = ServiceToolkit()
        toolkit.add(my_search_func, name="search", description="搜索")

        agent = ReActAgent(
            name="researcher",
            sys_prompt="你是一个研究员，善于使用工具查找信息。",
            llm=ChatOpenAI(model="gpt-4o"),
            toolkit=toolkit,
        )
        response = agent.reply(Msg.user_msg("今天的新闻有哪些？"))
    """
    name: str = Field(default="react_agent")
    description: str = Field(default="ReAct 推理行动 Agent")
    toolkit: ServiceToolkit = Field(default_factory=ServiceToolkit)
    memory: AgentMemory = Field(default_factory=AgentMemory)
    max_steps: int = Field(default=10, description="最大推理步数")

    def reply(self, msg: Union[Msg, Sequence[Msg]]) -> Msg:
        """ReAct 循环：思考→行动→观察，直到得到最终答案"""
        if self.llm is None:
            raise ValueError(f"[{self.name}] LLM 未配置")

        msgs = self._to_msg_list(msg)
        for m in msgs:
            self.memory.add(m)

        # 绑定工具到 LLM
        tools = self.toolkit.get_tools()
        llm_with_tools = self.llm.bind_tools(tools) if tools else self.llm

        # 构建初始消息
        lc_messages = self._build_lc_messages(msgs)

        for step in range(self.max_steps):
            self._log(f"Step {step + 1}: 调用 LLM")

            # 调用 LLM
            response = self._invoke_llm_with_tools(lc_messages)

            # 判断是否有工具调用
            if not response.tool_calls:
                # 没有工具调用，直接返回最终答案
                final_content = response.content or ""
                reply_msg = Msg.agent_msg(content=final_content, name=self.name)
                self.memory.add(reply_msg)
                self._log(f"最终回答: {final_content[:80]}...")
                return reply_msg

            # 有工具调用，执行工具并将结果追加到消息列表
            lc_messages.append(response)
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]
                self._log(f"调用工具: {tool_name}({tool_args})")

                tool_result = self._execute_tool(tool_name, tool_args)
                from langchain_core.messages import ToolMessage
                lc_messages.append(ToolMessage(content=tool_result, tool_call_id=tool_id))

        # 超出最大步数
        fallback = Msg.agent_msg(
            content=f"[{self.name}] 已达到最大推理步数({self.max_steps})，请简化问题重试。",
            name=self.name,
        )
        self.memory.add(fallback)
        return fallback

    def _build_lc_messages(self, new_msgs: List[Msg]) -> List[BaseMessage]:
        result: List[BaseMessage] = [SystemMessage(content=self.sys_prompt)]
        context = self.memory.get_context()
        seen_ids = {id(m) for m in new_msgs}
        for m in context:
            if id(m) not in seen_ids:
                result.append(m.to_langchain_message())
        for m in new_msgs:
            result.append(m.to_langchain_message())
        return result

    def _invoke_llm_with_tools(self, messages: List[BaseMessage]) -> AIMessage:
        """调用带工具的 LLM"""
        tools = self.toolkit.get_tools()
        llm_with_tools = self.llm.bind_tools(tools) if tools else self.llm
        last_err: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = llm_with_tools.invoke(messages)
                return resp
            except Exception as e:
                last_err = e
                self._log(f"LLM 调用失败 (第{attempt}次): {e}")
        raise RuntimeError(f"[{self.name}] LLM 调用失败: {last_err}")

    def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """执行工具调用"""
        t = self.toolkit.get_tool(tool_name)
        if t is None:
            return f"[错误] 未找到工具: {tool_name}"
        try:
            return t.invoke(tool_args)
        except Exception as e:
            return f"[工具执行错误] {tool_name}: {e}"


# ---------------------------------------------------------------------------
# UserAgent - 人类代理（Human-in-the-Loop）
# ---------------------------------------------------------------------------
class UserAgent(BaseAgent):
    """
    用户代理 - 等待人类输入

    用于 Pipeline 中的人类参与节点，实现 Human-in-the-Loop。

    Usage:
        user = UserAgent(name="user")
        msg = user.reply(Msg.agent_msg("请确认是否继续？"))
        # 等待用户在终端输入...
    """
    name: str = Field(default="user")
    description: str = Field(default="人类用户代理")
    sys_prompt: str = Field(default="")
    input_prompt: str = Field(default="请输入 > ", description="终端输入提示符")

    def reply(self, msg: Union[Msg, Sequence[Msg]] = None) -> Msg:
        """等待用户输入"""
        if msg:
            msgs = self._to_msg_list(msg)
            for m in msgs:
                print(f"  {m}")

        user_input = input(self.input_prompt).strip()
        return Msg.user_msg(content=user_input, name=self.name)

    async def areply(self, msg: Union[Msg, Sequence[Msg]] = None) -> Msg:
        """异步等待用户输入（使用 asyncio 避免阻塞）"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.reply, msg)


# ---------------------------------------------------------------------------
# 工厂函数
# ---------------------------------------------------------------------------
def create_agent(
    agent_type: str = "dialog",
    *,
    name: str = "agent",
    sys_prompt: str = "你是一个有帮助的 AI 助手。",
    llm: Optional[BaseChatModel] = None,
    toolkit: Optional[ServiceToolkit] = None,
    max_steps: int = 10,
    verbose: bool = False,
) -> BaseAgent:
    """
    Agent 工厂函数 - 快速创建 Agent 实例

    Args:
        agent_type: Agent 类型 ("dialog" | "react" | "user")
        name: Agent 名称
        sys_prompt: 系统提示词
        llm: LangChain LLM 实例
        toolkit: 工具集（仅 react 类型需要）
        max_steps: 最大推理步数（仅 react 类型）
        verbose: 是否输出调试日志

    Returns:
        对应的 Agent 实例
    """
    if agent_type == "dialog":
        return DialogAgent(
            name=name, sys_prompt=sys_prompt, llm=llm, verbose=verbose
        )
    elif agent_type == "react":
        return ReActAgent(
            name=name, sys_prompt=sys_prompt, llm=llm,
            toolkit=toolkit or ServiceToolkit(),
            max_steps=max_steps, verbose=verbose,
        )
    elif agent_type == "user":
        return UserAgent(name=name)
    else:
        raise ValueError(f"未知 Agent 类型: {agent_type}，可选: dialog / react / user")
