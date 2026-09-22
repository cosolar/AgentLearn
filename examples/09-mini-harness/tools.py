"""tools.py —— 工具注册表 + 受控执行

工具层职责链（对应 docs/09-agent-harness/02-anatomy.md）：

    注册 → schema 校验 → 参数提取 → 权限检查 → 沙箱执行 → 结果捕获 → 格式化为 observation

本模块负责 schema、执行、结果截断与路径越界防护；
权限检查由 harness 在上游完成（解耦）。

依赖：仅标准库。
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from config import HarnessConfig
from trace import Step, Tracer


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[..., Any]
    read_only: bool = False

    def schema(self) -> dict:
        """OpenAI function-calling 格式的工具定义"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self, cfg: HarnessConfig, tracer: Tracer) -> None:
        self.cfg = cfg
        self.tracer = tracer
        self._tools: dict[str, ToolSpec] = {}

    # ---------------- 注册 / 查询 ----------------
    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def names(self) -> list[str]:
        return list(self._tools)

    def read_only_names(self) -> list[str]:
        return [n for n, s in self._tools.items() if s.read_only]

    def schemas(self, only: set[str] | None = None) -> list[dict]:
        """导出工具 schema。

        `only` 参数用于「按任务阶段动态收窄工具集」——
        工具越多往往越差（Vercel 砍掉 80% 工具反而更好）。
        """
        items = [s for s in self._tools.values() if only is None or s.name in only]
        return [s.schema() for s in items]

    # ---------------- 执行 ----------------
    def execute(self, name: str, args: dict) -> str:
        spec = self._tools.get(name)
        if spec is None:
            return f"[错误] 未知工具：{name}。可用：{', '.join(self._tools)}"

        start = time.time()
        ok = True
        try:
            result = str(spec.fn(**args))
        except TypeError as exc:
            # 参数错误属于「LLM 可恢复」：返回可行动信息，让模型自己改
            result = f"[参数错误] {exc}。请检查参数名与类型后重试。"
            ok = False
        except Exception as exc:                      # noqa: BLE001
            result = f"[工具失败] {type(exc).__name__}: {exc}"
            ok = False

        self.tracer.trace.steps.append(
            Step(kind="tool", name=name, duration=time.time() - start, ok=ok)
        )

        # 结果截断：超长 observation 是上下文杀手
        limit = self.cfg.tool_output_limit
        if len(result) > limit:
            result = (result[:limit]
                      + f"\n...[输出已截断，共 {len(result)} 字符。"
                        f"如需后续内容请指定范围重读]")
        return result

    # ---------------- 路径安全 ----------------
    def _resolve(self, path: str) -> Path:
        """把相对路径解析到 workspace 内，阻止路径越界（../../etc/passwd）"""
        root = self.cfg.workspace.resolve()
        target = (root / path).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"路径越界，拒绝访问：{path}")
        return target


def build_default_tools(cfg: HarnessConfig, tracer: Tracer) -> ToolRegistry:
    """注册一组最小的 File / Search / Exec 工具"""
    reg = ToolRegistry(cfg, tracer)

    # ---------- 只读：文件 ----------
    def read_file(path: str, offset: int = 0, limit: int = 200) -> str:
        p = reg._resolve(path)
        lines = p.read_text(encoding="utf-8").splitlines()
        return "\n".join(lines[offset:offset + limit])

    def list_dir(path: str = ".") -> str:
        p = reg._resolve(path)
        if not p.exists():
            return f"[错误] 目录不存在：{path}"
        return "\n".join(sorted(x.name + ("/" if x.is_dir() else "")
                                for x in p.iterdir()))

    def search_web(query: str) -> str:
        return f"关于「{query}」的搜索结果（示例桩，实际应接入 Tavily/Bing 等）"

    # ---------- 写：文件 ----------
    def write_file(path: str, content: str) -> str:
        p = reg._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"已写入 {path}（{len(content)} 字符）"

    # ---------- 执行：验证入口 ----------
    def run_tests() -> str:
        """跑配置里的验证命令。这是验证循环（Stop Gate）的入口。"""
        cmd = list(cfg.test_command)
        try:
            proc = subprocess.run(cmd, cwd=str(cfg.workspace),
                                  capture_output=True, text=True, timeout=300)
        except FileNotFoundError as exc:
            return f"exit=127\n[无法执行验证命令] {exc}"
        except subprocess.TimeoutExpired:
            return "exit=124\n[验证超时]"
        return (f"exit={proc.returncode}\n"
                f"{proc.stdout[-2000:]}\n{proc.stderr[-1000:]}")

    # ---------- 危险：任意 shell（由权限层把关）----------
    def run_shell(command: str) -> str:
        """在工作区执行 shell 命令。危险操作会被权限层拦截。"""
        proc = subprocess.run(command, cwd=str(cfg.workspace), shell=True,
                              capture_output=True, text=True, timeout=120)
        return (f"exit={proc.returncode}\n"
                f"{proc.stdout[-2000:]}\n{proc.stderr[-1000:]}")

    reg.register(ToolSpec(
        "read_file", "读取文件内容。path 为相对工作区路径；offset/limit 控制行范围。",
        {"type": "object",
         "properties": {"path": {"type": "string"},
                        "offset": {"type": "integer", "default": 0},
                        "limit": {"type": "integer", "default": 200}},
         "required": ["path"]},
        read_file, read_only=True))

    reg.register(ToolSpec(
        "list_dir", "列出目录下的文件与子目录。",
        {"type": "object", "properties": {"path": {"type": "string", "default": "."}}},
        list_dir, read_only=True))

    reg.register(ToolSpec(
        "search_web", "搜索互联网获取实时信息。",
        {"type": "object", "properties": {"query": {"type": "string"}},
         "required": ["query"]},
        search_web, read_only=True))

    reg.register(ToolSpec(
        "write_file", "写入文件（覆盖）。会修改工作区内容，请谨慎使用。",
        {"type": "object",
         "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
         "required": ["path", "content"]},
        write_file))

    reg.register(ToolSpec(
        "run_tests", "运行项目验证命令，返回结果摘要。声明完成前必须调用。",
        {"type": "object", "properties": {}},
        run_tests, read_only=True))

    reg.register(ToolSpec(
        "run_shell", "在工作区执行 shell 命令。仅用于必要的系统操作。",
        {"type": "object", "properties": {"command": {"type": "string"}},
         "required": ["command"]},
        run_shell))

    return reg
