"""
消息模块 - Agent 间通信的核心数据结构

参考 AgentScope 的 Msg 设计，定义统一的消息传递协议。
所有 Agent 通过 Msg 对象进行交互，实现松耦合的消息驱动架构。
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class MsgRole(str, Enum):
    """消息角色枚举"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    AGENT = "agent"


class Msg(BaseModel):
    """
    Agent 消息对象

    所有 Agent 之间通信的基础单元，参考 AgentScope Msg 设计。
    每条消息包含发送者、角色、内容和可选的元数据。

    Attributes:
        name: 发送者名称（Agent 名或用户名）
        role: 消息角色（system/user/assistant/tool/agent）
        content: 消息内容
        metadata: 附加元数据（工具调用结果、状态信息等）
        timestamp: 消息创建时间
    """
    name: str = Field(default="unknown", description="发送者名称")
    role: MsgRole = Field(default=MsgRole.USER, description="消息角色")
    content: str = Field(default="", description="消息内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="创建时间")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "name": self.name,
            "role": self.role.value,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_langchain_message(self):
        """
        转换为 LangChain 消息对象

        Returns:
            LangChain BaseMessage 子类实例
        """
        from langchain_core.messages import (
            SystemMessage, HumanMessage, AIMessage, ToolMessage
        )
        role_map = {
            MsgRole.SYSTEM: SystemMessage,
            MsgRole.USER: HumanMessage,
            MsgRole.ASSISTANT: AIMessage,
            MsgRole.AGENT: AIMessage,
            MsgRole.TOOL: lambda content, **kw: ToolMessage(
                content=content,
                tool_call_id=kw.get("tool_call_id", "unknown"),
            ),
        }
        msg_cls = role_map[self.role]
        if self.role == MsgRole.TOOL:
            return msg_cls(
                content=self.content,
                tool_call_id=self.metadata.get("tool_call_id", "unknown"),
            )
        return msg_cls(content=self.content)

    def __str__(self) -> str:
        return f"[{self.name}({self.role.value})]: {self.content}"

    @classmethod
    def user_msg(cls, content: str, name: str = "user") -> "Msg":
        """快捷创建用户消息"""
        return cls(name=name, role=MsgRole.USER, content=content)

    @classmethod
    def agent_msg(cls, content: str, name: str = "agent", **metadata) -> "Msg":
        """快捷创建 Agent 消息"""
        return cls(name=name, role=MsgRole.AGENT, content=content, metadata=metadata)

    @classmethod
    def system_msg(cls, content: str, name: str = "system") -> "Msg":
        """快捷创建系统消息"""
        return cls(name=name, role=MsgRole.SYSTEM, content=content)

    @classmethod
    def tool_msg(cls, content: str, tool_call_id: str = "unknown",
                 name: str = "tool") -> "Msg":
        """快捷创建工具调用结果消息"""
        return cls(
            name=name, role=MsgRole.TOOL, content=content,
            metadata={"tool_call_id": tool_call_id},
        )


class MsgQueue(BaseModel):
    """
    消息队列 - 用于多 Agent 之间的消息缓冲与分发

    支持按角色过滤、历史记录查询和消息广播。
    """
    messages: List[Msg] = Field(default_factory=list)
    max_size: int = Field(default=1000, description="队列最大容量")

    def push(self, msg: Msg) -> None:
        """推送消息到队列"""
        self.messages.append(msg)
        if len(self.messages) > self.max_size:
            self.messages = self.messages[-self.max_size:]

    def pop(self) -> Optional[Msg]:
        """弹出最早的消息"""
        if self.messages:
            return self.messages.pop(0)
        return None

    def peek(self) -> Optional[Msg]:
        """查看最早的消息（不移除）"""
        return self.messages[0] if self.messages else None

    def filter_by_role(self, role: MsgRole) -> List[Msg]:
        """按角色过滤消息"""
        return [m for m in self.messages if m.role == role]

    def filter_by_name(self, name: str) -> List[Msg]:
        """按发送者名称过滤"""
        return [m for m in self.messages if m.name == name]

    def recent(self, n: int = 10) -> List[Msg]:
        """获取最近 n 条消息"""
        return self.messages[-n:]

    def clear(self) -> None:
        """清空队列"""
        self.messages.clear()

    def __len__(self) -> int:
        return len(self.messages)

    def __iter__(self):
        return iter(self.messages)
