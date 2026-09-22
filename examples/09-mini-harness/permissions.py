"""permissions.py —— deny-first 权限判定

核心原则（对应 docs/09-agent-harness/04-permissions-sandbox.md）：

    权限执行与模型推理解耦：
      模型决定"想尝试做什么"，工具系统决定"什么被允许"。

    判定顺序不可颠倒：DENY → ALLOW → MODE
    deny 永远覆盖 allow（类似防火墙），这是「不依赖模型判断力的硬保证」。

本模块只依赖标准库，方便单独测试。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Decision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass
class PermissionResult:
    decision: Decision
    reason: str = ""

    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW


# ---------------------------------------------------------------- 规则表

# 硬性拒绝：命中即拒，工具"不可见"，模型无法绕过
DENY_RULES: list[tuple[str, str]] = [
    (r"rm\s+-rf\s+/", "禁止删除根目录"),
    (r"\bmkfs\b|\bdd\s+if=", "禁止磁盘级操作"),
    (r"curl[^|]*\|\s*(bash|sh)", "禁止管道执行远程脚本"),
    (r":\(\)\s*\{.*\};\s*:", "禁止 fork 炸弹"),
    (r"\bshutdown\b|\breboot\b", "禁止关机/重启"),
]

# 需要显式确认的高危模式
ASK_RULES: list[tuple[str, str]] = [
    (r"\brm\b", "删除操作"),
    (r"\bgit\s+push\b", "推送到远程"),
    (r"\bgit\s+reset\s+--hard\b", "硬重置"),
    (r"\bpip\s+install\b|\bnpm\s+install\b", "安装依赖"),
    (r"\bchmod\s+777\b", "过度开放权限"),
]

# 只读工具：永远允许（不会改变外部世界）
READ_ONLY_TOOLS: frozenset[str] = frozenset({"read_file", "list_dir", "grep", "search_web"})

# 会写文件的工具
WRITE_TOOLS: frozenset[str] = frozenset({"write_file", "edit_file"})

# 危险工具：即使在 auto 模式下也需要确认
DANGER_TOOLS: frozenset[str] = frozenset({"run_shell"})


# ---------------------------------------------------------------- 判定

def check_permission(tool_name: str, args: dict, mode: str = "default") -> PermissionResult:
    """deny-first 判定。

    Args:
        tool_name: 工具名
        args: 工具参数
        mode: 权限模式 plan / default / accept_edits / auto

    Returns:
        PermissionResult(decision, reason)
    """
    text = " ".join(str(v) for v in args.values())

    # ① DENY 优先：命中即拒
    for pattern, reason in DENY_RULES:
        if re.search(pattern, text, re.I):
            return PermissionResult(Decision.DENY, f"deny 规则命中：{reason}")

    # plan 模式：只读
    if mode == "plan" and tool_name not in READ_ONLY_TOOLS:
        return PermissionResult(Decision.DENY, "plan 模式仅允许只读操作")

    # ② ALLOW：只读工具直接放行
    if tool_name in READ_ONLY_TOOLS:
        return PermissionResult(Decision.ALLOW, "只读操作")

    # accept_edits：文件写入自动通过
    if mode == "accept_edits" and tool_name in WRITE_TOOLS:
        return PermissionResult(Decision.ALLOW, "accept_edits 模式允许写文件")

    # auto：尽力自动放行（但危险工具仍需确认）
    if mode == "auto" and tool_name not in DANGER_TOOLS:
        return PermissionResult(Decision.ALLOW, "auto 模式")

    # ③ 高危模式仍需人工确认
    for pattern, reason in ASK_RULES:
        if re.search(pattern, text, re.I):
            return PermissionResult(Decision.ASK, f"高危操作：{reason}")

    if tool_name in DANGER_TOOLS:
        return PermissionResult(Decision.ASK, f"危险工具：{tool_name}")

    return PermissionResult(Decision.ASK, f"{mode} 模式：需要确认")


def visible_tools(all_tools: list[str], mode: str = "default") -> list[str]:
    """返回模型"能看到"的工具清单。

    deny 命中的工具不会出现在模型面前 —— "看不见"比"总是被拒绝"更强。
    注意：这里只做静态过滤（按工具名），参数级 deny 在调用时判定。
    """
    if mode == "plan":
        return [t for t in all_tools if t in READ_ONLY_TOOLS]
    return list(all_tools)
