"""harness.py —— mini-harness 主编排循环

把前面所有模块串起来：配置 / 权限 / 工具 / 上下文 / 验证 / 埋点。

内部消息使用"中立格式"（不绑定任何 SDK 的 wire format）：

    {"role": "system"|"user", "content": str}
    {"role": "assistant", "content": str, "tool_calls": [{"id","name","args": dict}]}
    {"role": "tool", "tool_call_id": str, "name": str, "content": str}

格式转换由 LLMBackend 负责（见 llm.py 的 OpenAIBackend._to_wire）。

依赖：仅标准库 + 本项目模块（不依赖 langchain）。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from config import HarnessConfig
from context import ContextManager
from llm import LLMBackend
from permissions import Decision, check_permission
from tools import ToolRegistry, build_default_tools
from trace import Tracer
from verify import StopGate

SYSTEM_PROMPT = """你是一个编码 Agent。

工作规则：
1. 动手前先用只读工具（read_file / list_dir）确认现状，不要凭记忆假设。
2. 修改文件后，必须调用 run_tests 验证。
3. 只有在验证通过后才宣布任务完成。
4. 遇到无法解决的阻塞，明确说明卡在哪里。

生产约定：
- 禁止修改测试用例来"让测试通过"。
- 每次只做最小必要的改动。
"""


@dataclass
class RunState:
    messages: list[dict] = field(default_factory=list)
    files_changed: bool = False
    turns: int = 0
    finished: bool = False
    finish_reason: str = ""
    final_text: str = ""


class Harness:
    def __init__(
        self,
        cfg: HarnessConfig,
        llm: LLMBackend,
        registry: ToolRegistry | None = None,
        tracer: Tracer | None = None,
        ask_human: Callable[[str, dict, str], bool] | None = None,
    ) -> None:
        self.cfg = cfg
        self.llm = llm
        self.tracer = tracer or Tracer()
        self.registry = registry or build_default_tools(cfg, self.tracer)
        self.context = ContextManager(
            cfg, self.tracer,
            summarizer=self._summarize_with_llm if cfg.use_llm_summary else None,
        )
        self.gate = StopGate(self.registry, self.tracer, cfg.max_consecutive_blocks)
        self.ask_human = ask_human or self._ask_human_default
        self._repeat: dict[str, int] = {}

    # ================================================================ 主循环
    def run(self, task: str) -> RunState:
        state = RunState(messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ])
        started = time.time()

        while not state.finished:
            # ---------- 终止条件（多道保险）----------
            if state.turns >= self.cfg.max_turns:
                return self._finish(state, f"达到最大轮数({self.cfg.max_turns})")
            if self.tracer.trace.total_tokens >= self.cfg.max_total_tokens:
                return self._finish(state, "token 预算耗尽")
            if time.time() - started > self.cfg.max_wall_seconds:
                return self._finish(state, "墙钟超时")

            state.turns += 1

            # ---------- 步骤 4：上下文压缩 ----------
            state.messages = self.context.maybe_compress(state.messages)

            # ---------- 步骤 1-2：组装 prompt + 调用模型 ----------
            with self.tracer.span("llm", "chat") as span:
                reply = self.llm.chat(state.messages, self.registry.schemas())
                span.tokens_in = reply.tokens_in
                span.tokens_out = reply.tokens_out

            state.messages.append(self._assistant_message(reply))

            # ---------- 步骤 3：输出分类 ----------
            if not reply.tool_calls:
                verdict = self.gate.check(state.__dict__)
                if verdict.passed:
                    state.final_text = reply.content
                    return self._finish(state, "任务完成")
                if verdict.detail.startswith("[强制终止]"):
                    return self._finish(state, verdict.detail)
                # 背压：把失败原因作为新 observation 注入，让模型自我修正
                state.messages.append({
                    "role": "user",
                    "content": f"[验证未通过，请继续修复]\n{verdict.detail}",
                })
                continue

            # ---------- 步骤 4-5：执行工具 + 结果打包 ----------
            for tc in reply.tool_calls:
                result = self._execute_one(state, tc["name"], tc.get("args", {}))
                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "name": tc["name"],
                    "content": result,
                })

        return state

    # ============================================================ 单次工具执行
    def _execute_one(self, state: RunState, name: str, args: dict) -> str:
        # ① 死循环检测（先于权限，避免无意义的重复审批）
        sig = f"{name}:{sorted((k, str(v)) for k, v in args.items())}"
        self._repeat[sig] = self._repeat.get(sig, 0) + 1
        if self._repeat[sig] >= self.cfg.max_repeat_calls:
            self.tracer.event("loop.detected", tool=name, times=self._repeat[sig])
            return (f"[Harness] 检测到重复调用（{name} 相同参数第 {self._repeat[sig]} 次），"
                    f"已拒绝。请换一种方式，或基于已有信息给出结论。")

        # ② 权限检查（deny-first，与模型推理解耦）
        perm = check_permission(name, args, self.cfg.permission_mode)
        if perm.decision is Decision.DENY:
            self.tracer.event("permission.deny", tool=name, reason=perm.reason)
            return f"[权限拒绝] {perm.reason}。该操作被硬性禁止，请改用其他方式。"
        if perm.decision is Decision.ASK:
            if not self.ask_human(name, args, perm.reason):
                return f"[用户拒绝] {perm.reason}。请不要重复尝试，改用其他方式。"
            self.tracer.event("permission.approved", tool=name)

        # ③ 执行 + 记录副作用
        if name in {"write_file", "edit_file"}:
            state.files_changed = True
        return self.registry.execute(name, args)

    # ================================================================ 辅助
    @staticmethod
    def _assistant_message(reply) -> dict:
        """转成中立格式（args 保持 dict，由后端负责序列化）"""
        msg: dict = {"role": "assistant", "content": reply.content}
        if reply.tool_calls:
            msg["tool_calls"] = [dict(c) for c in reply.tool_calls]
        return msg

    @staticmethod
    def _ask_human_default(name: str, args: dict, reason: str) -> bool:
        print(f"\n⚠️  需要确认：{name}({args})\n   原因：{reason}")
        try:
            return input("   允许执行吗？[y/N] ").strip().lower() == "y"
        except EOFError:                     # 非交互环境下默认拒绝（保守）
            return False

    def _summarize_with_llm(self, messages: list[dict]) -> str:
        prompt = [
            {"role": "system",
             "content": ("请把下面的 Agent 执行历史压缩为简洁摘要。"
                         "必须保留：架构决策、已修改的文件、未解决的问题、下一步计划。"
                         "可以丢弃：冗余的工具输出与重复的探索过程。")},
            {"role": "user",
             "content": "\n".join(f"{m.get('role')}: {str(m.get('content'))[:1200]}"
                                  for m in messages)},
        ]
        return self.llm.chat(prompt, []).content

    def _finish(self, state: RunState, reason: str) -> RunState:
        state.finished = True
        state.finish_reason = reason
        self.tracer.finish(reason)
        return state
