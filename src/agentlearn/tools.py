"""
工具/服务函数注册 - ServiceToolkit 风格的工具管理

参考 AgentScope ServiceToolkit 设计：
- ServiceToolkit 将普通函数注册为 LLM 可调用的工具
- 支持函数自动转 LangChain Tool
- 支持工具链、结果格式化、错误处理
"""

import functools
import traceback
from typing import Any, Callable, Dict, List, Optional, Type, get_type_hints

from langchain_core.tools import BaseTool, StructuredTool, tool
from pydantic import BaseModel, Field, create_model


# ---------------------------------------------------------------------------
# 工具结果封装
# ---------------------------------------------------------------------------
class ToolResult(BaseModel):
    """工具执行结果统一封装"""
    success: bool = Field(description="是否执行成功")
    content: str = Field(default="", description="结果内容")
    error: Optional[str] = Field(default=None, description="错误信息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加信息")

    def __str__(self) -> str:
        if self.success:
            return self.content
        return f"[工具错误] {self.error}"


# ---------------------------------------------------------------------------
# ServiceToolkit：工具注册与管理
# ---------------------------------------------------------------------------
class ServiceToolkit(BaseModel):
    """
    服务工具集 - 管理和注册 Agent 可用的工具/服务函数

    参考 AgentScope ServiceToolkit 设计，支持：
    1. 普通函数 → LangChain Tool 自动转换
    2. 装饰器注册
    3. 安全执行（自动捕获异常）
    4. 工具列表查询

    Usage:
        toolkit = ServiceToolkit()

        # 方式一：装饰器注册
        @toolkit.register
        def search(query: str) -> str:
            '''搜索互联网信息'''
            return f"结果: {query}"

        # 方式二：直接添加函数
        toolkit.add(calculate, name="calc", description="计算器")

        # 获取 LangChain 工具列表（用于 bind_tools）
        tools = toolkit.get_tools()
    """

    _tools: Dict[str, BaseTool] = {}

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        super().__init__(**data)
        object.__setattr__(self, "_tools", {})

    # -- 注册方式 --

    def register(
        self,
        func: Optional[Callable] = None,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Callable:
        """
        装饰器注册工具函数

        可直接 @toolkit.register 或 @toolkit.register(name="xxx")
        """
        def decorator(fn: Callable) -> Callable:
            tool_name = name or fn.__name__
            tool_desc = description or fn.__doc__ or f"工具: {tool_name}"
            wrapped = self._wrap_function(fn)
            lc_tool = StructuredTool.from_function(
                func=wrapped,
                name=tool_name,
                description=tool_desc,
            )
            self._tools[tool_name] = lc_tool
            return fn
        if func is not None:
            return decorator(func)
        return decorator

    def add(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """直接添加函数为工具"""
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or f"工具: {tool_name}"
        wrapped = self._wrap_function(func)
        lc_tool = StructuredTool.from_function(
            func=wrapped,
            name=tool_name,
            description=tool_desc,
        )
        self._tools[tool_name] = lc_tool

    def add_tool(self, tool_instance: BaseTool) -> None:
        """添加已有的 LangChain Tool 实例"""
        self._tools[tool_instance.name] = tool_instance

    # -- 查询 --

    def get_tools(self) -> List[BaseTool]:
        """获取所有 LangChain Tool（用于 llm.bind_tools()）"""
        return list(self._tools.values())

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取指定工具"""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, str]]:
        """列出所有工具的名称和描述"""
        return [
            {"name": t.name, "description": t.description or ""}
            for t in self._tools.values()
        ]

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def remove(self, name: str) -> bool:
        return self._tools.pop(name, None) is not None

    def clear(self) -> None:
        self._tools.clear()

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    # -- 内部工具 --

    @staticmethod
    def _wrap_function(fn: Callable) -> Callable:
        """包装函数：自动捕获异常，返回 ToolResult 字符串"""
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> str:
            try:
                result = fn(*args, **kwargs)
                return str(result)
            except Exception as e:
                return ToolResult(
                    success=False,
                    error=f"{type(e).__name__}: {e}",
                ).model_dump_json()
        return wrapper


# ---------------------------------------------------------------------------
# 快捷装饰器（模块级别）
# ---------------------------------------------------------------------------
_default_toolkit = ServiceToolkit()


def service_tool(
    func: Optional[Callable] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Callable:
    """
    模块级装饰器：注册到全局默认 ServiceToolkit

    Usage:
        @service_tool
        def my_tool(x: str) -> str:
            '''描述'''
            return x
    """
    def decorator(fn: Callable) -> Callable:
        _default_toolkit.register(fn, name=name, description=description)
        return fn
    if func is not None:
        return decorator(func)
    return decorator


def get_default_toolkit() -> ServiceToolkit:
    """获取全局默认工具集"""
    return _default_toolkit


# ---------------------------------------------------------------------------
# 预置工具（示例）
# ---------------------------------------------------------------------------
@service_tool(name="get_current_time", description="获取当前日期时间")
def get_current_time() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@service_tool(name="calculator", description="执行数学计算表达式，如 '2+3*4'")
def calculator(expression: str) -> str:
    safe_ns = {"__builtins__": {}, "abs": abs, "round": round, "min": min, "max": max}
    try:
        result = eval(expression, safe_ns, {})
        return f"计算结果: {result}"
    except Exception as e:
        return f"计算错误: {e}"


@service_tool(name="search_web", description="搜索互联网信息（模拟）")
def search_web(query: str) -> str:
    return f"[模拟搜索结果] 关键词: {query} — 找到 10 条相关结果"
