# 🧰 Mini Harness —— 最小可行 Harness（MVH）

> 配套教程：[docs/09-agent-harness/08-build-your-harness.md](../../docs/09-agent-harness/08-build-your-harness.md)

一个**约 700 行、纯标准库**的 Agent Harness 骨架，把「Harness 十二大模块」里的核心七件事真正跑了起来。

## ✨ 特点

| 特点 | 说明 |
|------|------|
| **零依赖可运行** | 核心逻辑只用标准库，**不需要 API Key** 就能跑通完整循环 |
| **模型解耦** | 只依赖一个极薄的 `LLMBackend` 接口，换模型不改 Harness |
| **可离线自检** | `smoke_test.py` 用脚本化 `FakeLLM` 端到端验证，19 项断言 |
| **deny-first 权限** | 权限执行与模型推理解耦，`deny` 永远覆盖 `allow` |
| **两段式上下文压缩** | 先「屏蔽旧工具输出」，仍超限再「摘要」 |
| **验证门 + 背压** | 不通过就 block 并把失败原因顶回去，连续失败有刹车 |
| **全链路埋点** | token / 延迟 / 成本 / 工具错误率 / 终止原因 |

## 📁 目录结构

```
09-mini-harness/
├── config.py        # 配置与三重预算（轮数 / token / 墙钟）
├── trace.py         # 埋点：Step / Trace / Tracer
├── permissions.py   # deny-first 权限判定
├── tools.py         # 工具注册表 + 受控执行 + 路径越界防护
├── context.py       # 上下文压缩（屏蔽 → 摘要 → 兜底）
├── verify.py        # 验证门 Stop Gate
├── llm.py           # LLM 抽象层：OpenAIBackend / FakeLLM
├── harness.py       # 主编排循环（串起全部模块）
├── main.py          # 真实运行入口（需要 API Key）
├── smoke_test.py    # 离线端到端自检（不需要 API Key）
└── eval/
    └── tasks.jsonl  # 可自动判定的评测集（参考 9.11）
```

## 🚀 运行

### 1. 离线自检（推荐先跑这个，零依赖）

```bash
cd examples/09-mini-harness
python smoke_test.py
```

预期输出（实测）：

```text
⏱  0.17s | 模型调用 8 | 工具调用 6 | tokens 1399 | 成本 $0.00166 | 工具错误率 0% | 终止原因 任务完成
✅ ① deny 拦截 `rm -rf /`
✅ ② 重复调用被循环检测拒绝
✅ ③ 验证失败后注入背压
✅ ④ 最终经验证通过而终止
...
✅ ⑬ 权限：deny 覆盖 allow（参数级）
通过 19/19
```

### 2. 真实运行（需要模型 API）

```bash
# macOS / Linux
export OPENAI_API_KEY=sk-...
export OPENAI_API_BASE=https://api.openai.com/v1

# Windows (PowerShell)
$env:OPENAI_API_KEY="sk-..."

python main.py "阅读工作区代码，让校验脚本通过"
```

> ⚠️ `main.py` 会**真的调用模型**并可能修改 `workspace/` 下的文件。
> 默认 `permission_mode="default"`，每次写操作都会向你确认。

## 🐛 实测踩到的坑（已修复，写进教程）

| 坑 | 现象 | 修复 |
|----|------|------|
| **Windows 控制台 GBK** | 打印 `⏱` 等 emoji 抛 `UnicodeEncodeError: 'gbk' codec can't encode character` | 入口统一 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` |
| **工具参数序列化** | 把 `arguments` 传成 dict，OpenAI wire 格式要求 **JSON 字符串** | 由 `LLMBackend` 在边界统一 `json.dumps` |
| **压缩策略是两段式** | 只断言"屏蔽"会在超限时失败——因为会升级为摘要 | 分别验证「屏蔽策略」与「升级为摘要」两个行为 |
| **本机 `python` 可能是商店占位符** | `test_command` 用 `"python"` 找不到解释器 | 用 `[sys.executable, "check.py"]`，避免依赖 PATH |

## 🔗 相关章节

| 主题 | 章节 |
|------|------|
| 十二大模块 | [9.2](../../docs/09-agent-harness/02-anatomy.md) |
| 上下文压缩 | [9.3](../../docs/09-agent-harness/03-context-engineering.md) |
| 权限与沙箱 | [9.4](../../docs/09-agent-harness/04-permissions-sandbox.md) |
| 验证循环 | [9.5](../../docs/09-agent-harness/05-verification.md) |
| 评测与可观测性 | [9.11](../../docs/09-agent-harness/11-evaluation-observability.md) |
