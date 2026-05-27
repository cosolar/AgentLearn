"""
测试 AgentLearn 核心模块

测试覆盖：
- Msg 消息系统
- AgentMemory 三层记忆
- ServiceToolkit 工具注册
- SequentialPipeline 顺序流水线
- Utils 工具函数
"""

import pytest
from agentlearn.message import Msg, MsgQueue, MsgRole
from agentlearn.memory import WorkingMemory, ShortTermMemory, LongTermMemory, AgentMemory
from agentlearn.tools import ServiceToolkit, ToolResult
from agentlearn.pipeline import SequentialPipeline
from agentlearn.utils import count_tokens, truncate_text, build_system_prompt, parse_json_response


# ---------------------------------------------------------------------------
# 消息模块测试
# ---------------------------------------------------------------------------
class TestMsg:
    """测试 Msg 消息对象"""

    def test_create_msg(self):
        msg = Msg(name="alice", role=MsgRole.USER, content="你好")
        assert msg.name == "alice"
        assert msg.role == MsgRole.USER
        assert msg.content == "你好"

    def test_factory_methods(self):
        user = Msg.user_msg("hello")
        assert user.role == MsgRole.USER

        agent = Msg.agent_msg("hi", name="bot")
        assert agent.role == MsgRole.AGENT
        assert agent.name == "bot"

        system = Msg.system_msg("系统指令")
        assert system.role == MsgRole.SYSTEM

    def test_to_dict(self):
        msg = Msg.user_msg("test")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "test"

    def test_to_langchain_message(self):
        msg = Msg.user_msg("hello")
        lc_msg = msg.to_langchain_message()
        assert lc_msg.content == "hello"


class TestMsgQueue:
    """测试消息队列"""

    def test_push_pop(self):
        q = MsgQueue()
        q.push(Msg.user_msg("1"))
        q.push(Msg.user_msg("2"))
        assert len(q) == 2
        assert q.pop().content == "1"
        assert len(q) == 1

    def test_filter_by_role(self):
        q = MsgQueue()
        q.push(Msg.user_msg("u"))
        q.push(Msg.agent_msg("a"))
        users = q.filter_by_role(MsgRole.USER)
        assert len(users) == 1


# ---------------------------------------------------------------------------
# 记忆系统测试
# ---------------------------------------------------------------------------
class TestAgentMemory:
    """测试三层记忆系统"""

    def test_working_memory(self):
        wm = WorkingMemory(max_messages=3)
        for i in range(5):
            wm.add(Msg.user_msg(f"msg-{i}"))
        assert len(wm) <= 3

    def test_short_term_memory(self):
        stm = ShortTermMemory()
        stm.save_pair("你好", "你好！")
        assert len(stm) == 2
        recent = stm.get_recent(1)
        assert len(recent) == 1

    def test_long_term_memory(self):
        ltm = LongTermMemory()
        ltm.save("python", "一种编程语言", category="tech")
        assert ltm.get("python") == "一种编程语言"
        results = ltm.search("编程")
        assert len(results) >= 1

    def test_agent_memory_integration(self):
        mem = AgentMemory()
        mem.add(Msg.user_msg("你好"))
        mem.add(Msg.agent_msg("你好！"))
        ctx = mem.get_context()
        assert len(ctx) >= 2
        stats = mem.get_stats()
        assert stats["working"] == 2


# ---------------------------------------------------------------------------
# 工具系统测试
# ---------------------------------------------------------------------------
class TestServiceToolkit:
    """测试 ServiceToolkit"""

    def test_register_decorator(self):
        tk = ServiceToolkit()

        @tk.register
        def greet(name: str) -> str:
            """打招呼"""
            return f"Hello, {name}"

        assert tk.has_tool("greet")
        assert len(tk) == 1

    def test_add_function(self):
        tk = ServiceToolkit()

        def add(a: int, b: int) -> int:
            """加法"""
            return a + b

        tk.add(add, name="add", description="加法计算")
        assert tk.has_tool("add")
        tools = tk.get_tools()
        assert len(tools) == 1

    def test_list_tools(self):
        tk = ServiceToolkit()

        @tk.register(name="my_tool", description="测试工具")
        def my_tool():
            pass

        info = tk.list_tools()
        assert info[0]["name"] == "my_tool"


# ---------------------------------------------------------------------------
# Pipeline 测试
# ---------------------------------------------------------------------------
class TestPipeline:
    """测试 Pipeline（使用 Mock Agent）"""

    def test_sequential_pipeline(self):
        """使用简单的 Mock Agent 测试顺序流水线"""
        from agentlearn.base import BaseAgent
        from typing import Sequence, Union

        class EchoAgent(BaseAgent):
            suffix: str = ""

            def reply(self, msg: Union[Msg, Sequence[Msg]]) -> Msg:
                msgs = self._to_msg_list(msg)
                content = msgs[-1].content + self.suffix
                return Msg.agent_msg(content=content, name=self.name)

        a = EchoAgent(name="a", suffix="_A")
        b = EchoAgent(name="b", suffix="_B")
        pipe = SequentialPipeline(agents=[a, b])
        result = pipe.run(Msg.user_msg("hello"))
        assert result.content == "hello_A_B"


# ---------------------------------------------------------------------------
# 工具函数测试
# ---------------------------------------------------------------------------
class TestUtils:

    def test_count_tokens(self):
        assert count_tokens("Hello, World!") > 0

    def test_truncate_text(self):
        long_text = "a" * 10000
        truncated = truncate_text(long_text, max_tokens=100)
        assert len(truncated) < len(long_text)

    def test_build_system_prompt(self):
        prompt = build_system_prompt(
            role="研究员",
            capabilities=["搜索", "分析"],
            constraints=["只输出事实"],
        )
        assert "研究员" in prompt
        assert "搜索" in prompt

    def test_parse_json_response(self):
        result = parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

        result = parse_json_response('```json\n{"a": 1}\n```')
        assert result == {"a": 1}

        assert parse_json_response("not json") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
