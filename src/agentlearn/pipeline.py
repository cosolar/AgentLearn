"""
Pipeline 编排模块 - 基于 LangGraph 的多 Agent 工作流

参考 AgentScope Pipeline 设计模式，结合 LangGraph 状态图实现：
- SequentialPipeline: 顺序执行（A → B → C）
- ForLoopPipeline:    固定次数循环
- IfElsePipeline:     条件分支
- WhileLoopPipeline:  条件循环（直到满足终止条件）
- MultiAgentDebate:   多 Agent 辩论模式
- LangGraphWorkflow:  完整 LangGraph 状态图工作流
"""

from typing import Any, Callable, Dict, List, Optional, Sequence, TypedDict, Union
from typing_extensions import Annotated
import operator

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from .base import BaseAgent
from .message import Msg, MsgRole


# ---------------------------------------------------------------------------
# Pipeline 基类
# ---------------------------------------------------------------------------
class BasePipeline(BaseModel):
    """Pipeline 基类"""

    class Config:
        arbitrary_types_allowed = True

    def __call__(self, msg: Msg) -> Msg:
        return self.run(msg)

    def run(self, msg: Msg) -> Msg:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# SequentialPipeline - 顺序执行
# ---------------------------------------------------------------------------
class SequentialPipeline(BasePipeline):
    """
    顺序流水线 - Agent 依次执行，前一个的输出作为后一个的输入

    参考 AgentScope SequentialPipeline 设计。

    Usage:
        pipeline = SequentialPipeline(agents=[agent_a, agent_b, agent_c])
        result = pipeline.run(Msg.user_msg("开始任务"))
        # agent_a → agent_b → agent_c → 返回结果
    """
    agents: List[BaseAgent] = Field(default_factory=list)

    def run(self, msg: Msg) -> Msg:
        current = msg
        for agent in self.agents:
            current = agent.reply(current)
        return current


# ---------------------------------------------------------------------------
# ForLoopPipeline - 固定次数循环
# ---------------------------------------------------------------------------
class ForLoopPipeline(BasePipeline):
    """
    固定次数循环 - 将 Agent（或 Pipeline）执行 N 次

    Usage:
        loop = ForLoopPipeline(agent=agent, max_loops=3)
        result = loop.run(Msg.user_msg("开始"))
    """
    agent: BaseAgent
    max_loops: int = Field(default=3, description="循环次数")

    def run(self, msg: Msg) -> Msg:
        current = msg
        for i in range(self.max_loops):
            current = self.agent.reply(current)
        return current


# ---------------------------------------------------------------------------
# IfElsePipeline - 条件分支
# ---------------------------------------------------------------------------
class IfElsePipeline(BasePipeline):
    """
    条件分支 - 根据条件函数选择执行路径

    Usage:
        branch = IfElsePipeline(
            condition=lambda msg: "是" in msg.content,
            if_agent=agent_yes,
            else_agent=agent_no,
        )
        result = branch.run(user_msg)
    """
    condition: Callable[[Msg], bool]
    if_agent: BaseAgent
    else_agent: BaseAgent

    class Config:
        arbitrary_types_allowed = True

    def run(self, msg: Msg) -> Msg:
        if self.condition(msg):
            return self.if_agent.reply(msg)
        return self.else_agent.reply(msg)


# ---------------------------------------------------------------------------
# WhileLoopPipeline - 条件循环
# ---------------------------------------------------------------------------
class WhileLoopPipeline(BasePipeline):
    """
    条件循环 - 持续执行直到条件满足或达到最大次数

    Usage:
        loop = WhileLoopPipeline(
            agent=agent,
            stop_condition=lambda msg: "完成" in msg.content,
            max_loops=10,
        )
        result = loop.run(initial_msg)
    """
    agent: BaseAgent
    stop_condition: Callable[[Msg], bool]
    max_loops: int = Field(default=10)

    class Config:
        arbitrary_types_allowed = True

    def run(self, msg: Msg) -> Msg:
        current = msg
        for _ in range(self.max_loops):
            current = self.agent.reply(current)
            if self.stop_condition(current):
                break
        return current


# ---------------------------------------------------------------------------
# MultiAgentDebate - 多 Agent 辩论
# ---------------------------------------------------------------------------
class MultiAgentDebate(BasePipeline):
    """
    多 Agent 辩论模式 - 多个 Agent 轮流发言，达成共识

    参考 AgentScope 多 Agent 对话设计，支持：
    - 多 Agent 轮流发言
    - 设置最大轮数
    - 自定义终止条件

    Usage:
        debate = MultiAgentDebate(
            agents=[agent_a, agent_b, agent_c],
            max_rounds=3,
        )
        result = debate.run(Msg.user_msg("讨论话题：AI 是否会取代人类？"))
    """
    agents: List[BaseAgent] = Field(default_factory=list)
    max_rounds: int = Field(default=3, description="辩论轮数")
    stop_condition: Optional[Callable[[List[Msg]], bool]] = Field(
        default=None, description="自定义终止条件"
    )

    def run(self, msg: Msg) -> Msg:
        all_msgs: List[Msg] = [msg]
        current = msg

        for round_num in range(self.max_rounds):
            for agent in self.agents:
                current = agent.reply(current)
                all_msgs.append(current)

            # 检查终止条件
            if self.stop_condition and self.stop_condition(all_msgs):
                break

        # 返回最后一条消息
        return current


# ---------------------------------------------------------------------------
# LangGraph Workflow - 完整状态图工作流
# ---------------------------------------------------------------------------
class AgentState(TypedDict):
    """LangGraph 状态定义"""
    messages: Annotated[List[Msg], operator.add]
    current_agent: str
    step: int
    final_answer: str
    metadata: Dict[str, Any]


class LangGraphWorkflow:
    """
    基于 LangGraph 的完整工作流编排

    使用 LangGraph StateGraph 构建有向图，支持：
    - 条件路由（根据 Agent 输出决定下一步）
    - 循环（ReAct 推理循环）
    - 多 Agent 协作

    Usage:
        # 构建简单工作流
        workflow = LangGraphWorkflow(name="my_workflow")
        workflow.add_agent("planner", planner_agent)
        workflow.add_agent("executor", executor_agent)
        workflow.add_agent("reviewer", reviewer_agent)

        workflow.set_entry("planner")
        workflow.add_route("planner", route_fn)  # 决定下一个节点
        workflow.add_edge("executor", "reviewer")

        graph = workflow.compile()
        result = graph.invoke({"messages": [msg], ...})
    """

    def __init__(self, name: str = "workflow"):
        self.name = name
        self._agents: Dict[str, BaseAgent] = {}
        self._graph = StateGraph(AgentState)
        self._entry: Optional[str] = None
        self._compiled = None

    def add_agent(self, key: str, agent: BaseAgent) -> "LangGraphWorkflow":
        """添加 Agent 节点"""
        self._agents[key] = agent

        def node_fn(state: AgentState, _agent=agent, _key=key) -> AgentState:
            msgs = state.get("messages", [])
            last_msg = msgs[-1] if msgs else Msg.user_msg("开始")
            result = _agent.reply(last_msg)
            return {
                "messages": [result],
                "current_agent": _key,
                "step": state.get("step", 0) + 1,
                "final_answer": result.content,
                "metadata": state.get("metadata", {}),
            }

        self._graph.add_node(key, node_fn)
        return self

    def set_entry(self, key: str) -> "LangGraphWorkflow":
        """设置入口节点"""
        self._entry = key
        self._graph.set_entry_point(key)
        return self

    def add_edge(self, from_key: str, to_key: str) -> "LangGraphWorkflow":
        """添加固定边"""
        self._graph.add_edge(from_key, to_key)
        return self

    def add_route(
        self,
        from_key: str,
        route_fn: Callable[[AgentState], str],
        path_map: Optional[Dict[str, str]] = None,
    ) -> "LangGraphWorkflow":
        """
        添加条件路由

        Args:
            from_key: 源节点
            route_fn: 路由函数，接收 State 返回下一个节点 key
            path_map: 路径映射（可选）
        """
        def conditional_edge(state: AgentState) -> str:
            next_key = route_fn(state)
            if path_map and next_key in path_map:
                return path_map[next_key]
            return next_key

        self._graph.add_conditional_edges(from_key, conditional_edge)
        return self

    def add_finish_edge(self, from_key: str) -> "LangGraphWorkflow":
        """添加终止边"""
        self._graph.add_edge(from_key, END)
        return self

    def compile(self):
        """编译工作流图"""
        self._compiled = self._graph.compile()
        return self._compiled

    def invoke(self, msg: Msg, **kwargs) -> AgentState:
        """执行工作流"""
        if self._compiled is None:
            self.compile()
        initial_state = AgentState(
            messages=[msg],
            current_agent=self._entry or "",
            step=0,
            final_answer="",
            metadata=kwargs,
        )
        return self._compiled.invoke(initial_state)

    def stream(self, msg: Msg, **kwargs):
        """流式执行工作流"""
        if self._compiled is None:
            self.compile()
        initial_state = AgentState(
            messages=[msg],
            current_agent=self._entry or "",
            step=0,
            final_answer="",
            metadata=kwargs,
        )
        return self._compiled.stream(initial_state)


# ---------------------------------------------------------------------------
# 快捷构建器
# ---------------------------------------------------------------------------
def build_react_graph(
    agent: BaseAgent,
    tools: List[Any],
    name: str = "react_workflow",
) -> LangGraphWorkflow:
    """
    快捷构建 ReAct 工作流（LangGraph 版）

    自动创建 "agent → tools → agent" 的循环图：
    - agent 节点：调用 LLM
    - tools 节点：执行工具
    - 条件路由：有工具调用 → tools，否则 → END
    """
    from langchain_core.messages import ToolMessage as LCToolMessage

    workflow = LangGraphWorkflow(name=name)

    # Agent 节点
    def agent_node(state: AgentState) -> AgentState:
        msgs = state.get("messages", [])
        last_msg = msgs[-1] if msgs else Msg.user_msg("开始")
        result = agent.reply(last_msg)
        return {"messages": [result], "step": state.get("step", 0) + 1,
                "final_answer": result.content}

    workflow._graph.add_node("agent", agent_node)
    workflow._agents["agent"] = agent
    workflow._entry = "agent"
    workflow._graph.set_entry_point("agent")
    workflow._graph.add_edge("agent", END)

    return workflow
