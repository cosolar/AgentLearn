"""
工具函数集合 - 通用辅助函数

提供消息格式化、Token 估算、Prompt 构建、JSON 解析等通用工具。
"""

import hashlib
import json
import textwrap
from datetime import datetime
from typing import Any, Dict, List, Optional

from .message import Msg, MsgRole


# ---------------------------------------------------------------------------
# Token 估算
# ---------------------------------------------------------------------------
def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """
    估算文本的 token 数量（简单近似）

    规则：约 4 个英文字符 ≈ 1 token；中文约 2 字符 ≈ 1 token
    """
    en_chars = sum(1 for c in text if ord(c) < 128)
    zh_chars = sum(1 for c in text if ord(c) >= 128)
    return en_chars // 4 + zh_chars // 2


def truncate_text(text: str, max_tokens: int = 4000) -> str:
    """截断文本以适应 token 限制"""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[内容已截断...]"


# ---------------------------------------------------------------------------
# 消息格式化
# ---------------------------------------------------------------------------
def format_msg(msg: Msg, style: str = "plain") -> str:
    """
    格式化单条消息

    Args:
        msg: 消息对象
        style: 格式风格 (plain / markdown / json)
    """
    if style == "json":
        return json.dumps(msg.to_dict(), indent=2, ensure_ascii=False)
    if style == "markdown":
        role_emoji = {
            MsgRole.USER: "👤", MsgRole.AGENT: "🤖",
            MsgRole.SYSTEM: "⚙️", MsgRole.TOOL: "🔧",
        }
        emoji = role_emoji.get(msg.role, "💬")
        return f"{emoji} **{msg.name}** ({msg.role.value})\n\n{msg.content}"
    return f"[{msg.name}]: {msg.content}"


def format_conversation(msgs: List[Msg], style: str = "plain") -> str:
    """格式化一组对话消息"""
    return "\n\n---\n\n".join(format_msg(m, style) for m in msgs)


def format_response(response: Dict[str, Any], format_type: str = "markdown") -> str:
    """格式化 Agent 响应字典"""
    if format_type == "json":
        return json.dumps(response, indent=2, ensure_ascii=False)
    if format_type == "markdown":
        lines = [
            "### 🤖 Agent 响应",
            "",
            f"**输入:** {response.get('input', 'N/A')}",
            "",
            "**输出:**",
            "```",
            f"{response.get('response', '')}",
            "```",
        ]
        if "model" in response:
            lines.append(f"**模型:** {response['model']}")
        return "\n".join(lines)
    return response.get("response", "")


# ---------------------------------------------------------------------------
# Prompt 构建
# ---------------------------------------------------------------------------
def build_system_prompt(
    role: str = "AI 助手",
    personality: str = "专业、友好、简洁",
    capabilities: Optional[List[str]] = None,
    constraints: Optional[List[str]] = None,
    examples: Optional[List[Dict[str, str]]] = None,
    output_format: Optional[str] = None,
) -> str:
    """
    结构化系统提示词构建器

    Args:
        role: Agent 角色定位
        personality: 性格/风格特征
        capabilities: 能力清单
        constraints: 约束条件
        examples: 示例对话 [{"input": ..., "output": ...}]
        output_format: 输出格式要求

    Returns:
        组装好的系统提示词字符串
    """
    parts = [
        f"# 角色",
        f"你是一个{role}。",
        f"",
        f"# 风格",
        f"{personality}",
    ]

    if capabilities:
        parts.append("")
        parts.append("# 能力")
        for i, cap in enumerate(capabilities, 1):
            parts.append(f"{i}. {cap}")

    if constraints:
        parts.append("")
        parts.append("# 约束")
        for i, con in enumerate(constraints, 1):
            parts.append(f"{i}. {con}")

    if output_format:
        parts.append("")
        parts.append("# 输出格式")
        parts.append(output_format)

    if examples:
        parts.append("")
        parts.append("# 示例")
        for i, ex in enumerate(examples, 1):
            parts.append(f"## 示例 {i}")
            parts.append(f"**用户:** {ex.get('input', '')}")
            parts.append(f"**助手:** {ex.get('output', '')}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# JSON 工具
# ---------------------------------------------------------------------------
def parse_json_response(text: str) -> Optional[Dict[str, Any]]:
    """从可能包含 Markdown 代码块的文本中提取并解析 JSON"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 代码块
    for marker in ("```json", "```"):
        start = text.find(marker)
        if start != -1:
            start += len(marker)
            end = text.find("```", start)
            if end != -1:
                try:
                    return json.loads(text[start:end].strip())
                except json.JSONDecodeError:
                    pass

    # 尝试提取第一个 {...} 块
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# ID 生成
# ---------------------------------------------------------------------------
def generate_id(prefix: str = "agent") -> str:
    """生成带时间戳的唯一 ID"""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = hashlib.md5(f"{ts}-{id(object())}".encode()).hexdigest()[:8]
    return f"{prefix}_{ts}_{rand}"


# ---------------------------------------------------------------------------
# 对话摘要
# ---------------------------------------------------------------------------
def summarize_messages(msgs: List[Msg], max_summary_tokens: int = 200) -> str:
    """
    对一组消息做简单摘要（用于记忆压缩）

    这是一个简单的截取式摘要，生产环境建议用 LLM 生成。
    """
    if not msgs:
        return "[空对话]"
    lines = [f"[{m.name}]: {m.content[:100]}" for m in msgs[:10]]
    summary = "\n".join(lines)
    if count_tokens(summary) > max_summary_tokens:
        summary = truncate_text(summary, max_summary_tokens)
    return f"对话摘要（{len(msgs)} 条消息）:\n{summary}"
