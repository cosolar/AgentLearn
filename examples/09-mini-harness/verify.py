"""verify.py —— 确定性验证门（Stop Gate）

这是把"玩具 Demo"与"生产级 Agent"分开的那条线。

机制：Agent 声称"完成"时，不直接结束 —— 先跑验证命令。
      通过 → 允许结束
      失败 → 把失败输出作为背压（back-pressure）注入，让模型继续修复
      连续失败 max_consecutive_blocks 次 → 强制终止（刹车，防无限循环）

依赖：仅标准库。
"""

from __future__ import annotations

from dataclasses import dataclass

from tools import ToolRegistry
from trace import Tracer


@dataclass
class VerifyResult:
    passed: bool
    detail: str


class StopGate:
    def __init__(
        self,
        registry: ToolRegistry,
        tracer: Tracer,
        max_consecutive_blocks: int = 8,
    ) -> None:
        self.registry = registry
        self.tracer = tracer
        self.max_blocks = max_consecutive_blocks
        self.blocks = 0

    def check(self, state: dict) -> VerifyResult:
        """执行验证命令并给出结论。

        Args:
            state: 运行态快照（含 files_changed 等），用于生成更有用的提示
        """
        output = self.registry.execute("run_tests", {})
        self.tracer.event("verify.run", passed="exit=0" in output)

        if "exit=0" in output:
            self.blocks = 0
            return VerifyResult(True, "验证通过")

        self.blocks += 1
        if self.blocks >= self.max_blocks:
            # 刹车：连续失败达到上限，强制终止，避免"修不好又停不下来"
            return VerifyResult(
                False,
                f"[强制终止] 连续 {self.blocks} 次验证失败，"
                f"已停止自动修复，请人工介入。",
            )

        hint = ""
        if not state.get("files_changed"):
            hint = "\n提示：本轮没有任何文件改动，请确认是否真的做了修改。"
        return VerifyResult(
            False,
            f"验证失败（第 {self.blocks}/{self.max_blocks} 次）：\n"
            f"{output[-800:]}{hint}",
        )
