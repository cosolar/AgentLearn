"""
三层记忆系统 - 工作记忆 / 短期记忆 / 长期记忆

参考 AgentScope 的记忆设计 + 多 Agent 系统的三层记忆架构：
- WorkingMemory: 当前任务上下文（滑动窗口），直接注入 prompt
- ShortTermMemory: 会话级历史，支持摘要压缩
- LongTermMemory: 跨会话持久化知识，支持语义检索
"""

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from datetime import datetime
from pydantic import BaseModel, Field

from .message import Msg, MsgRole


# ---------------------------------------------------------------------------
# 工作记忆：当前上下文窗口
# ---------------------------------------------------------------------------
class WorkingMemory(BaseModel):
    """
    工作记忆 - 维护当前任务的上下文窗口

    采用滑动窗口策略，保留最近 N 条消息。
    超出窗口时自动触发摘要压缩（若配置了摘要函数）。
    """
    messages: List[Msg] = Field(default_factory=list)
    max_messages: int = Field(default=20, description="窗口大小（消息条数）")
    summary_func: Optional[Callable[[List[Msg]], str]] = Field(
        default=None, description="摘要压缩函数（可选）"
    )
    _summary: str = ""

    class Config:
        arbitrary_types_allowed = True

    def add(self, msg: Msg) -> None:
        """添加一条消息，超出窗口时自动压缩"""
        self.messages.append(msg)
        if len(self.messages) > self.max_messages:
            self._compress()

    def extend(self, msgs: Sequence[Msg]) -> None:
        """批量添加消息"""
        for m in msgs:
            self.add(m)

    def _compress(self) -> None:
        """压缩历史消息：将旧消息摘要化"""
        overflow = self.messages[: len(self.messages) - self.max_messages]
        self.messages = self.messages[-self.max_messages:]
        if self.summary_func:
            self._summary += self.summary_func(overflow)
        else:
            self._summary += (
                f"[历史摘要：{len(overflow)} 条早期消息已被压缩]\n"
            )

    def get_context(self) -> List[Msg]:
        """获取当前上下文（摘要 + 窗口内消息）"""
        result = []
        if self._summary:
            result.append(Msg.system_msg(content=f"[历史摘要] {self._summary}"))
        result.extend(self.messages)
        return result

    def clear(self) -> None:
        """清空工作记忆"""
        self.messages.clear()
        self._summary = ""

    def __len__(self) -> int:
        return len(self.messages)


# ---------------------------------------------------------------------------
# 短期记忆：会话级历史
# ---------------------------------------------------------------------------
class ShortTermMemory(BaseModel):
    """
    短期记忆 - 保存完整会话历史

    用于回顾当前会话的所有交互，支持与 WorkingMemory 联动。
    """
    records: List[Msg] = Field(default_factory=list)
    max_records: int = Field(default=200, description="最大记录数")

    def save(self, msg: Msg) -> None:
        """保存一条消息"""
        self.records.append(msg)
        if len(self.records) > self.max_records:
            self.records = self.records[-self.max_records:]

    def save_pair(self, user_input: str, agent_response: str,
                 user_name: str = "user", agent_name: str = "agent") -> None:
        """保存一对用户/Agent 消息"""
        self.save(Msg.user_msg(content=user_input, name=user_name))
        self.save(Msg.agent_msg(content=agent_response, name=agent_name))

    def get_recent(self, n: int = 10) -> List[Msg]:
        """获取最近 n 条消息"""
        return self.records[-n:]

    def get_all(self) -> List[Msg]:
        """获取全部记录"""
        return list(self.records)

    def search(self, keyword: str, top_k: int = 5) -> List[Msg]:
        """关键词搜索"""
        matches = [m for m in self.records if keyword.lower() in m.content.lower()]
        return matches[-top_k:]

    def clear(self) -> None:
        self.records.clear()

    def __len__(self) -> int:
        return len(self.records)


# ---------------------------------------------------------------------------
# 长期记忆：跨会话持久化知识
# ---------------------------------------------------------------------------
class MemoryEntry(BaseModel):
    """长期记忆条目"""
    key: str = Field(description="记忆键")
    value: Any = Field(description="记忆内容")
    category: str = Field(default="general", description="分类标签")
    timestamp: datetime = Field(default_factory=datetime.now)
    access_count: int = Field(default=0, description="访问次数")


class LongTermMemory(BaseModel):
    """
    长期记忆 - 存储跨会话的结构化知识

    支持：
    - 键值存取
    - 分类管理
    - 关键词检索
    - 访问频率追踪
    """
    entries: Dict[str, MemoryEntry] = Field(default_factory=dict)

    def save(self, key: str, value: Any, category: str = "general") -> None:
        """保存知识条目"""
        self.entries[key] = MemoryEntry(key=key, value=value, category=category)

    def get(self, key: str) -> Optional[Any]:
        """按 key 获取，同时增加访问计数"""
        entry = self.entries.get(key)
        if entry:
            entry.access_count += 1
            return entry.value
        return None

    def search(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        """关键词模糊搜索（key + value + category）"""
        query_lower = query.lower()
        scored: List[Tuple[int, MemoryEntry]] = []
        for entry in self.entries.values():
            score = 0
            if query_lower in entry.key.lower():
                score += 3
            if query_lower in str(entry.value).lower():
                score += 2
            if query_lower in entry.category.lower():
                score += 1
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:top_k]]

    def get_by_category(self, category: str) -> List[MemoryEntry]:
        """按分类获取"""
        return [e for e in self.entries.values() if e.category == category]

    def delete(self, key: str) -> bool:
        """删除指定条目"""
        return self.entries.pop(key, None) is not None

    def clear(self) -> None:
        self.entries.clear()

    def __len__(self) -> int:
        return len(self.entries)


# ---------------------------------------------------------------------------
# 统一记忆管理器
# ---------------------------------------------------------------------------
class AgentMemory(BaseModel):
    """
    Agent 统一记忆管理器

    封装三层记忆，对外提供统一的读写接口，
    Agent 可直接引用而无需关心内部层级细节。

    Usage:
        memory = AgentMemory()
        memory.add(Msg.user_msg("你好"))
        context = memory.get_context()  # 返回工作记忆中的消息列表
    """

    working: WorkingMemory = Field(default_factory=WorkingMemory)
    short_term: ShortTermMemory = Field(default_factory=ShortTermMemory)
    long_term: LongTermMemory = Field(default_factory=LongTermMemory)

    # 是否自动将消息同步到短期记忆
    auto_sync_short_term: bool = Field(default=True)

    def add(self, msg: Msg) -> None:
        """添加消息：同步写入工作记忆 + 短期记忆"""
        self.working.add(msg)
        if self.auto_sync_short_term:
            self.short_term.save(msg)

    def get_context(self) -> List[Msg]:
        """获取当前上下文（来自工作记忆）"""
        return self.working.get_context()

    def save_knowledge(self, key: str, value: Any, category: str = "general") -> None:
        """保存长期知识"""
        self.long_term.save(key, value, category)

    def recall(self, query: str, top_k: int = 3) -> List[MemoryEntry]:
        """从长期记忆中召回相关知识"""
        return self.long_term.search(query, top_k=top_k)

    def clear_working(self) -> None:
        self.working.clear()

    def clear_all(self) -> None:
        self.working.clear()
        self.short_term.clear()
        self.long_term.clear()

    def get_stats(self) -> Dict[str, int]:
        """获取记忆统计"""
        return {
            "working": len(self.working),
            "short_term": len(self.short_term),
            "long_term": len(self.long_term),
        }
