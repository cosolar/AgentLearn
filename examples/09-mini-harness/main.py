"""main.py —— 真实运行入口（需要一个可用的模型 API）

用法：
    # 先准备好环境变量（二选一）
    #   OPENAI_API_KEY / OPENAI_API_BASE     （openai 原生变量）
    #   LLM_API_KEY    / LLM_BASE_URL        （本教程统一约定）
    uv run python main.py "把工作区里的校验脚本修好"

注意：这个入口会真的调用模型并可能修改 workspace/ 下的文件。
     默认权限模式是 default（每次写操作都会问你）。
"""

from __future__ import annotations

import sys
from pathlib import Path

# ⚠️ Windows 控制台默认 GBK，打印 emoji 会抛 UnicodeEncodeError，统一切 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import HarnessConfig          # noqa: E402
from harness import Harness               # noqa: E402
from llm import OpenAIBackend             # noqa: E402


def main() -> int:
    task = " ".join(sys.argv[1:]).strip() or "阅读工作区代码，让校验脚本通过。"

    cfg = HarnessConfig(
        model="gpt-5.5",
        workspace=Path(__file__).parent / "workspace",
        permission_mode="default",
        test_command=["python", "-m", "pytest", "-q"],
        use_llm_summary=True,          # 真实模型下启用摘要压缩
    )
    cfg.workspace.mkdir(parents=True, exist_ok=True)

    print(f"🚀 Harness 启动：{cfg.describe()}")
    print(f"📂 工作区：{cfg.workspace.resolve()}")
    print(f"📋 任务：{task}\n")

    harness = Harness(cfg, OpenAIBackend(model=cfg.model, temperature=cfg.temperature))
    state = harness.run(task)

    print(f"\n📄 最终输出：\n{state.final_text or '(无)'}")
    print(f"\n🏁 终止原因：{state.finish_reason}（共 {state.turns} 轮）")
    print(harness.tracer.trace.report(cfg.model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
