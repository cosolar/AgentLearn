"""config.py —— Harness 配置与资源预算

设计原则：Harness 的第一原则是"有预算"。
没有预算的 Agent 会烧钱，或者在循环里跑到天荒地老。
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HarnessConfig:
    # ---------------- 模型 ----------------
    model: str = "gpt-5.5"
    temperature: float = 0.0

    # ---------------- 预算（三个上限，任一触顶即终止）----------------
    max_turns: int = 25                 # 最大循环轮数
    max_total_tokens: int = 200_000     # 累计 token 预算
    max_wall_seconds: int = 600         # 墙钟时间上限（秒）

    # ---------------- 上下文 ----------------
    context_soft_limit: int = 24_000    # 超过该 token 数即触发压缩
    tool_output_limit: int = 4_000      # 单次工具输出的最大字符数
    keep_recent_messages: int = 6       # 压缩时原样保留的最近消息条数
    use_llm_summary: bool = False       # True 则用模型做摘要压缩（需真实模型）

    # ---------------- 错误 ----------------
    max_retries: int = 2                # 单步重试上限
    max_repeat_calls: int = 3           # 同一工具+参数重复调用多少次即判定循环

    # ---------------- 验证 ----------------
    # 验证门执行的命令。用 list 而不是 str 可以避免 shell 引号转义问题
    test_command: list[str] = field(
        default_factory=lambda: ["python", "-m", "pytest", "-q"]
    )
    max_consecutive_blocks: int = 8             # 连续验证失败多少次即强制终止

    # ---------------- 权限 ----------------
    # plan(只读) | default(需确认) | accept_edits(写文件自动通过) | auto(尽力自动)
    permission_mode: str = "default"

    # ---------------- 环境 ----------------
    workspace: Path = field(default_factory=lambda: Path("./workspace"))

    def __post_init__(self) -> None:
        if not isinstance(self.workspace, Path):
            self.workspace = Path(self.workspace)

    def describe(self) -> str:
        return (f"model={self.model} | turns<={self.max_turns} "
                f"| tokens<={self.max_total_tokens} | mode={self.permission_mode}")
