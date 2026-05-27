"""
Agent 基类定义 - 消息驱动的 Agent 抽象层

参考 AgentScope 设计：所有 Agent 继承自统一的基类，
通过 reply() 方法实现消息驱动的交互模式。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence, Union
from pydantic import BaseModel, Field, ConfigDict
from langchain_core.language_models import BaseChatModel

from .message import Msg, MsgRole


class BaseAgent(ABC, BaseModel):
    """
    Agent 基类 - 所有 Agent 的通用接口与属性

    设计原则（参考 AgentScope）：
    - 消息驱动：所有交互通过 Msg 对象
    - 统一接口：reply() 是唯一的对外接口
    - 可组合：支持 Pipeline 串联、多 Agent 协作

    Attributes:
        name: Agent 唯一名称
        description: Agent 功能描述
        sys_prompt: 系统提示词（人设/角色指令）
        llm: LangChain 大模型实例
        max_retries: LLM 调用最大重试次数
        verbose: 是否输出调试日志
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(default="base_agent", description="Agent 名称")
    description: str = Field(default="基础 Agent", description="Agent 描述")
    sys_prompt: str = Field(default="你是一个有帮助的 AI 助手。", description="系统提示词")
    llm: Optional[BaseChatModel] = Field(default=None, description="LangChain LLM 实例")
    max_retries: int = Field(default=3, description="LLM 调用最大重试次数")
    verbose: bool = Field(default=False, description="是否开启调试日志")

    @abstractmethod
    def reply(self, msg: Union[Msg, Sequence[Msg]]) -> Msg:
        """
        Agent 核心接口：接收消息，返回响应

        所有子类必须实现此方法。

        Args:
            msg: 单条消息或消息序列

        Returns:
            Agent 响应消息
        """
        ...

    async def areply(self, msg: Union[Msg, Sequence[Msg]]) -> Msg:
        """
        异步版 reply，默认实现为调用同步版

        子类可重写以实现真正的异步逻辑。
        """
        return self.reply(msg)

    def __call__(self, msg: Union[Msg, Sequence[Msg]]) -> Msg:
        """支持直接调用 agent(msg)"""
        return self.reply(msg)

    def _to_msg_list(self, msg: Union[Msg, Sequence[Msg]]) -> List[Msg]:
        """统一将输入转换为消息列表"""
        if isinstance(msg, Msg):
            return [msg]
        return list(msg)

    def _log(self, message: str) -> None:
        """调试日志输出"""
        if self.verbose:
            print(f"[{self.name}] {message}")

    def get_info(self) -> Dict[str, Any]:
        """获取 Agent 元信息"""
        return {
            "name": self.name,
            "description": self.description,
            "sys_prompt": self.sys_prompt,
            "model": getattr(self.llm, "model_name", None),
            "max_retries": self.max_retries,
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name!r})>"
