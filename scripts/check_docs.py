#!/usr/bin/env python3
"""check_docs.py —— AgentLearn 文档质量统一校验

用法：
    python scripts/check_docs.py             # 运行全部检查
    python scripts/check_docs.py --links     # 只查相对链接
    python scripts/check_docs.py --code      # 只查 Python 代码块语法
    python scripts/check_docs.py --structure # 只查五段式结构

退出码：链接与代码检查失败返回 1（阻断 CI）；结构问题仅告警。仅依赖标准库。
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

# 第三方镜像目录（非本仓库作者维护），不参与校验
EXCLUDE_DIRS = (
    "08-生态全景/AgentScope教程",
    "08-生态全景/HiClaw实践",
)

# 跳过标记：可写在代码块内，也可写在围栏上一行（用于刻意的签名示意 / 伪代码 / 模板）
SKIP_MARK = "doc-check: skip"

LINK_RE = re.compile(r"\]\(([^)]+)\)")
FENCE_RE = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)
PY_BLOCK_RE = re.compile(r"```(?:python|py)[^\n]*\n(.*?)```", re.DOTALL)

STRUCTURE_HINTS = {
    "导读": ("📖 导读", "📖 本章目标", "## 导读", "本章目标"),
    "小结": ("本章小结", "本章总结", "## 小结", "## 总结"),
    "练习": ("课后练习", "📝 练习", "## 练习"),
}


def iter_markdown() -> list[Path]:
    out = []
    for md in sorted(DOCS.rglob("*.md")):
        rel = md.relative_to(DOCS).as_posix()
        if any(rel.startswith(d) for d in EXCLUDE_DIRS):
            continue
        out.append(md)
    return out


def _strip_skipped_blocks(text: str) -> str:
    """把带 `doc-check: skip` 标记的围栏代码块整体剔除。

    标记可写在块内，也可写在围栏的上一行（如 `<!-- doc-check: skip -->`）。
    用于模板 / 签名示意这类"链接与语法都不该被校验"的代码块。
    """
    out: list[str] = []
    last = 0
    for m in FENCE_RE.finditer(text):
        out.append(text[last:m.start()])
        before = text[:m.start()].rstrip("\n")
        prev_line = before.split("\n")[-1] if before else ""
        skipped = SKIP_MARK in prev_line or SKIP_MARK in m.group(0)
        out.append("" if skipped else m.group(0))
        last = m.end()
    out.append(text[last:])
    return "".join(out)


def _strip_blockquote(block: str) -> str:
    """去掉代码块里的 blockquote 前缀（`> `），使其可编译。"""
    lines = []
    for line in block.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(">"):
            idx = line.index(">")
            line = line[idx + 1:]
            if line.startswith(" "):
                line = line[1:]
        lines.append(line)
    return "\n".join(lines)


def check_links() -> int:
    missing: list[tuple[str, str]] = []
    checked = 0
    for md in iter_markdown():
        text = _strip_skipped_blocks(md.read_text(encoding="utf-8", errors="replace"))
        for m in LINK_RE.finditer(text):
            link = m.group(1).strip()
            if link.startswith(("http://", "https://", "#", "mailto:")):
                continue
            path = link.split("#")[0]
            if not path:
                continue
            checked += 1
            if not (md.parent / path).resolve().exists():
                missing.append((str(md.relative_to(ROOT)), link))

    print(f"[links] 检查 {checked} 个相对链接，缺失 {len(missing)} 个")
    for f, l in missing:
        print(f"  ✗ {f} -> {l}")
    return 1 if missing else 0


def check_code() -> int:
    total = failed = skipped = 0
    for md in iter_markdown():
        text = md.read_text(encoding="utf-8", errors="replace")
        for i, m in enumerate(PY_BLOCK_RE.finditer(text), 1):
            block = m.group(1)
            total += 1
            before = text[:m.start()].rstrip("\n")
            prev_line = before.split("\n")[-1] if before else ""
            if SKIP_MARK in block or SKIP_MARK in prev_line:
                skipped += 1
                continue
            src = _strip_blockquote(block)
            with tempfile.NamedTemporaryFile(
                "w", suffix=".py", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(src)
                path = tmp.name
            try:
                # 允许顶层 await（异步片段常见写法）
                compile(src, path, "exec",
                        flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT, dont_inherit=True)
            except SyntaxError as exc:
                failed += 1
                print(f"  ✗ {md.relative_to(ROOT)} block#{i}: "
                      f"{exc.__class__.__name__}: {exc.msg} (line {exc.lineno})")
            finally:
                Path(path).unlink(missing_ok=True)

    print(f"[code] 共 {total} 个 Python 代码块，失败 {failed}，跳过 {skipped}")
    return 1 if failed else 0


def check_structure() -> int:
    missing: list[tuple[str, list[str]]] = []
    checked = 0
    for md in iter_markdown():
        rel = md.relative_to(DOCS)
        parts = rel.parts
        if not re.match(r"^(0[1-9]|附录)-", parts[0]):
            continue
        name = parts[-1]
        if not re.match(r"^\d+-", name):
            continue
        if name.lower() in ("readme.md", "index.md"):
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        checked += 1
        lacks = [k for k, hints in STRUCTURE_HINTS.items()
                 if not any(h in text for h in hints)]
        if lacks:
            missing.append((str(rel), lacks))

    print(f"[structure] 检查 {checked} 个章节，结构不完整 {len(missing)} 个（仅告警）")
    for f, lacks in missing:
        print(f"  ⚠ {f} 缺少：{'、'.join(lacks)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AgentLearn 文档校验")
    parser.add_argument("--links", action="store_true", help="只查相对链接")
    parser.add_argument("--code", action="store_true", help="只查代码块语法")
    parser.add_argument("--structure", action="store_true", help="只查五段式结构")
    args = parser.parse_args()

    run_all = not (args.links or args.code or args.structure)
    rc = 0
    if run_all or args.links:
        rc |= check_links()
    if run_all or args.code:
        rc |= check_code()
    if run_all or args.structure:
        rc |= check_structure()

    print("\n结果：" + ("❌ 存在问题" if rc else "✅ 全部通过"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
