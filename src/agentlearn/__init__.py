"""
AgentLearn - AI Agent 从零开始构建智能体

参考 AgentScope 消息驱动架构，基于 LangChain + LangGraph 实现。

核心模块:
- message:  消息传递协议（Msg / MsgQueue）
- base:     Agent 基类（BaseAgent）
- agent:    Agent 实现（DialogAgent / ReActAgent / UserAgent）
- memory:   三层记忆系统（WorkingMemory / ShortTermMemory / LongTermMemory）
- tools:    工具注册（ServiceToolkit）
- pipeline: 多 Agent 编排（SequentialPipeline / ForLoopPipeline / LangGraphWorkflow 等）
- utils:    通用工具函数
"""

__version__ = "0.2.0"
__author__ = "AgentLearn Team"

# --- 消息模块 ---
from .message import Msg, MsgQueue, MsgRole

# --- Agent 基类 ---
from .base import BaseAgent

# --- Agent 实现 ---
from .agent import (
    DialogAgent,
    ReActAgent,
    UserAgent,
    create_agent,
)

# --- 记忆系统 ---
from .memory import (
    WorkingMemory,
    ShortTermMemory,
    LongTermMemory,
    AgentMemory,
    MemoryEntry,
)

# --- 工具系统 ---
from .tools import (
    ServiceToolkit,
    ToolResult,
    service_tool,
    get_default_toolkit,
)

# --- Pipeline 编排 ---
from .pipeline import (
    BasePipeline,
    SequentialPipeline,
    ForLoopPipeline,
    IfElsePipeline,
    WhileLoopPipeline,
    MultiAgentDebate,
    LangGraphWorkflow,
    AgentState,
)

# --- 工具函数 ---
from .utils import (
    count_tokens,
    truncate_text,
    format_msg,
    format_conversation,
    format_response,
    build_system_prompt,
    parse_json_response,
    generate_id,
    summarize_messages,
)

__all__ = [
    # 消息
    "Msg",
    "MsgQueue",
    "MsgRole",
    # Agent
    "BaseAgent",
    "DialogAgent",
    "ReActAgent",
    "UserAgent",
    "create_agent",
    # 记忆
    "WorkingMemory",
    "ShortTermMemory",
    "LongTermMemory",
    "AgentMemory",
    "MemoryEntry",
    # 工具
    "ServiceToolkit",
    "ToolResult",
    "service_tool",
    "get_default_toolkit",
    # Pipeline
    "BasePipeline",
    "SequentialPipeline",
    "ForLoopPipeline",
    "IfElsePipeline",
    "WhileLoopPipeline",
    "MultiAgentDebate",
    "LangGraphWorkflow",
    "AgentState",
    # 工具函数
    "count_tokens",
    "truncate_text",
    "format_msg",
    "format_conversation",
    "format_response",
    "build_system_prompt",
    "parse_json_response",
    "generate_id",
    "summarize_messages",
]
