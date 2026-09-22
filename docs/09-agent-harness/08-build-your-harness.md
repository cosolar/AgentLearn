# 9.8 实战：从零构建最小可行 Harness —— 一个真的能跑的 mini-harness

## 📖 导读

> **最常见、也最致命的错误：在理解自己的失败模式之前就过度工程化。**

[9.1](01-intro.md)–[9.7](07-harness-engineering.md) 讲清了 Harness 的模块与方法论。本章我们**动手写一个最小可行 Harness（MVH, Minimum Viable Harness）**。

> ✅ **本章代码已实测可运行。**
> 完整工程位于 [`examples/09-mini-harness/`](../../examples/09-mini-harness/)，**约 700 行、纯标准库、离线自检 19 项断言全部通过**，不需要任何 API Key 就能跑通完整循环。
>
> ```bash
> cd examples/09-mini-harness && python smoke_test.py      # 输出：通过 19/19
> ```

---

## 一、先想清楚：不要一上来就造飞机

### 1.1 四阶段建设路径（按投入产出比排序）

| 阶段 | 加什么 | 为什么先做它 | 预期收益 |
|:--:|--------|--------------|----------|
| **Phase 1** | **验证循环** | 每工程小时的可靠性回报**最高** | 有团队 83% → 96% |
| **Phase 2** | **状态持久化** | 崩溃后从检查点续跑，而非重放整个任务 | 失败时 token 成本降 **30–50%** |
| **Phase 3** | **可观测性** | 不埋 trace 就是在盲操一个非确定性系统 | 可定位、可优化、可告警 |
| **Phase 4** | **人在回路** | 高风险操作的审批闸门 | 生产安全底线 |

> ⚠️ **时间预期**：生产级 Harness **需要数月而非数天**。本章给你的是**能跑起来的骨架**，不是生产系统。

### 1.2 工程结构（实际文件）

```
examples/09-mini-harness/
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
└── eval/tasks.jsonl # 可自动判定的评测集（配合 9.11）
```

**覆盖的 Harness 模块**（对照 [9.2 十二大模块](02-anatomy.md)）：

| 模块 | 本工程实现 |
|------|-----------|
| ① 编排循环 | `harness.py::Harness.run` |
| ② 工具 | `tools.py::ToolRegistry` |
| ④ 上下文管理 | `context.py::ContextManager` |
| ⑦ 状态管理 | `harness.py::RunState`（+ 可选 checkpointer） |
| ⑧ 错误处理 | `ToolRegistry.execute` 的统一错误格式 |
| ⑨ 护栏与安全 | `permissions.py` + 路径越界防护 |
| ⑩ 验证循环 | `verify.py::StopGate` |
| ⑫ 生命周期 | 三重预算 + 循环检测 + 终止原因 |

### 1.3 一个关键的架构决策：Harness 不与模型 SDK 耦合

本工程**不直接 import langchain / openai**，而是定义一层极薄的接口：

```python
# llm.py
@dataclass
class LLMReply:
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)   # [{"id","name","args"}]
    tokens_in: int = 0
    tokens_out: int = 0


class LLMBackend(Protocol):
    def chat(self, messages: list[dict], tools: list[dict]) -> LLMReply: ...
```

**为什么这么做**：

| 好处 | 说明 |
|------|------|
| 可离线验证 | 用 `FakeLLM` 脚本化回放，**测试 Harness 本身不需要 API** |
| 换模型不改 Harness | `OpenAIBackend` 换成任意厂商只是换个类 |
| 格式转换集中在边界 | wire 格式的坑只在一个地方踩 |
| 呼应本章主旨 | 与「权限执行与推理解耦」同一哲学 |

> 🔥 **这一条是实跑之后才确认有价值的**：因为离线可测，才能在没有 API Key 的环境里跑出 19 项断言。

---

## 二、第一步：配置与三重预算（`config.py`）

**Harness 的第一原则是"有预算"** —— 没有预算的 Agent 会烧钱，或者在循环里跑到天荒地老。

```python
@dataclass
class HarnessConfig:
    model: str = "gpt-5.5"
    temperature: float = 0.0

    # ---- 三重预算：任一触顶即终止 ----
    max_turns: int = 25
    max_total_tokens: int = 200_000
    max_wall_seconds: int = 600

    # ---- 上下文 ----
    context_soft_limit: int = 24_000     # 超过即触发压缩
    tool_output_limit: int = 4_000       # 单次工具输出最大字符数
    keep_recent_messages: int = 6        # 压缩时原样保留的最近条数
    use_llm_summary: bool = False        # True 则用模型摘要（离线模式关闭）

    # ---- 错误与循环 ----
    max_retries: int = 2                 # 单步重试上限（Stripe 生产实践）
    max_repeat_calls: int = 3            # 同工具同参数重复几次即判循环

    # ---- 验证 ----
    test_command: list[str] = field(default_factory=lambda: ["python", "-m", "pytest", "-q"])
    max_consecutive_blocks: int = 8      # 连续失败几次即强制终止（刹车）

    # ---- 权限 ----
    permission_mode: str = "default"     # plan | default | accept_edits | auto

    workspace: Path = field(default_factory=lambda: Path("./workspace"))
```

> 💡 **两个设计细节**：
> 1. `max_turns` 与 `max_total_tokens` **必须同时存在**。只有轮数上限时，模型可能用很少轮次烧掉巨量 token（例如一次读入整个仓库）。
> 2. `test_command` 用 **list 而不是 str**——避免 shell 引号转义问题；实测时还发现本机 `python` 可能是 Windows 商店占位符，所以自检里改用 `[sys.executable, "check.py"]`。

---

## 三、第二步：deny-first 权限模型（`permissions.py`）

**核心原则**（回顾 [9.4](04-permissions-sandbox.md)）：**权限执行与模型推理解耦；deny 永远覆盖 allow。**

```python
class Decision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


def check_permission(tool_name: str, args: dict, mode: str = "default") -> PermissionResult:
    text = " ".join(str(v) for v in args.values())

    # ① DENY 优先：命中即拒（模型甚至"看不到"该工具）
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

    # auto：尽力自动放行（危险工具除外）
    if mode == "auto" and tool_name not in DANGER_TOOLS:
        return PermissionResult(Decision.ALLOW, "auto 模式")

    # ③ 高危操作仍需人工确认
    for pattern, reason in ASK_RULES:
        if re.search(pattern, text, re.I):
            return PermissionResult(Decision.ASK, f"高危操作：{reason}")

    if tool_name in DANGER_TOOLS:
        return PermissionResult(Decision.ASK, f"危险工具：{tool_name}")

    return PermissionResult(Decision.ASK, f"{mode} 模式：需要确认")
```

规则表节选：

```python
DENY_RULES = [
    (r"rm\s+-rf\s+/", "禁止删除根目录"),
    (r"\bmkfs\b|\bdd\s+if=", "禁止磁盘级操作"),
    (r"curl[^|]*\|\s*(bash|sh)", "禁止管道执行远程脚本"),
    (r":\(\)\s*\{.*\};\s*:", "禁止 fork 炸弹"),
    (r"\bshutdown\b|\breboot\b", "禁止关机/重启"),
]
READ_ONLY_TOOLS = frozenset({"read_file", "list_dir", "grep", "search_web"})
WRITE_TOOLS     = frozenset({"write_file", "edit_file"})
DANGER_TOOLS    = frozenset({"run_shell"})       # auto 模式下仍需确认
```

> 🔑 **为什么 deny 必须最先判断**：这是**不依赖模型判断力的硬保证**。即使模型在 `auto` 模式下"自作主张"，`rm -rf /` 也永远跑不起来——**实测已验证**（自检第 ① 项）。

---

## 四、第三步：工具与路径安全（`tools.py`）

工具层职责链：**注册 → schema → 参数提取 → 权限检查 → 沙箱执行 → 结果捕获 → 格式化为 observation**。
其中权限检查在 `harness` 上游完成（解耦）。

```python
class ToolRegistry:
    def schemas(self, only: set[str] | None = None) -> list[dict]:
        """导出工具 schema。`only` 用于「按阶段动态收窄工具集」"""
        items = [s for s in self._tools.values() if only is None or s.name in only]
        return [s.schema() for s in items]

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
        except Exception as exc:
            result = f"[工具失败] {type(exc).__name__}: {exc}"
            ok = False

        self.tracer.trace.steps.append(Step(kind="tool", name=name,
                                            duration=time.time() - start, ok=ok))

        # 结果截断：超长 observation 是上下文杀手
        limit = self.cfg.tool_output_limit
        if len(result) > limit:
            result = result[:limit] + f"\n...[输出已截断，共 {len(result)} 字符]"
        return result
```

### 4.1 路径越界防护（容易漏掉的一环）

```python
    def _resolve(self, path: str) -> Path:
        """把相对路径解析到 workspace 内，阻止 ../../etc/passwd"""
        root = self.cfg.workspace.resolve()
        target = (root / path).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"路径越界，拒绝访问：{path}")
        return target
```

> ⚠️ **没有这一层**，模型一句 `read_file("../../.env")` 就能把密钥读出来——**权限规则是按参数文本匹配的，挡不住所有路径技巧**，必须在工具内部再做一次。

### 4.2 六个内置工具

| 工具 | 类型 | 说明 |
|------|:----:|------|
| `read_file` | 只读 | 按行范围读取 |
| `list_dir` | 只读 | 列目录 |
| `search_web` | 只读 | 搜索（示例桩） |
| `write_file` | 写 | 写入文件 |
| `run_tests` | 只读 | **验证门入口**，执行 `cfg.test_command` |
| `run_shell` | **危险** | 任意 shell，默认需确认 |

**生产替换点**：把 `run_tests` / `run_shell` 从本机 `subprocess` 换成容器沙箱（见 [9.4](04-permissions-sandbox.md) 的 Docker 执行器）。

---

## 五、第四步：两段式上下文压缩（`context.py`）

**目标**：维持"最小的高信号 token 集"（回顾 [9.3](03-context-engineering.md)）。

```python
class ContextManager:
    def maybe_compress(self, messages: list[dict]) -> list[dict]:
        before = self.count(messages)
        if before < self.cfg.context_soft_limit:
            return messages

        self.tracer.event("context.compress.trigger", tokens=before)

        # ① 先「屏蔽」：保留工具调用本身，只隐藏冗长的旧输出
        messages = self._mask_old_tool_outputs(messages)
        after_mask = self.count(messages)
        if after_mask < self.cfg.context_soft_limit:
            self.tracer.event("context.mask", before=before, after=after_mask)
            return messages

        # ② 仍超限，才升级为「摘要」
        messages = self._summarize(messages)
        self.tracer.event("context.summarize", before=after_mask,
                          after=self.count(messages))
        return messages
```

摘要是分层的：**保留架构决策、已改文件、未解决问题、下一步计划；丢弃冗余工具输出。**

> 📌 实测数据：一个 21 条消息、3,142 token 的历史 → 屏蔽后仍超限 → 摘要后 **325 token**（自检第 ⑨⑫ 项）。

### 5.1 token 计数的降级策略

```python
try:
    import tiktoken
    _ENC = tiktoken.get_encoding("cl100k_base")
    TOKENIZER = "tiktoken:cl100k_base"
    def count_tokens(text: str) -> int:
        return len(_ENC.encode(text))
except Exception:
    TOKENIZER = "heuristic:len/2"
    def count_tokens(text: str) -> int:
        return max(1, len(text) // 2)      # 中英折中估算
```

**为什么要降级**：`tiktoken` 未安装时，Harness 不应直接崩——**降级运行比崩溃好**。这也是"零依赖可跑"的关键。

---

## 六、第五步：验证门与背压（`verify.py`）

**这是把 Demo 变成生产级的那个模块。**

```python
class StopGate:
    def check(self, state: dict) -> VerifyResult:
        output = self.registry.execute("run_tests", {})
        self.tracer.event("verify.run", passed="exit=0" in output)

        if "exit=0" in output:
            self.blocks = 0
            return VerifyResult(True, "验证通过")

        self.blocks += 1
        if self.blocks >= self.max_blocks:
            # 刹车：连续失败达到上限，强制终止，避免"修不好又停不下来"
            return VerifyResult(False, f"[强制终止] 连续 {self.blocks} 次验证失败，"
                                       f"已停止自动修复，请人工介入。")

        hint = ""
        if not state.get("files_changed"):
            hint = "\n提示：本轮没有任何文件改动，请确认是否真的做了修改。"
        return VerifyResult(False, f"验证失败（第 {self.blocks}/{self.max_blocks} 次）：\n"
                                   f"{output[-800:]}{hint}")
```

验证结果的两种去向：

| 情况 | 处理 |
|------|------|
| 通过 | 允许结束 |
| 不通过 | **把失败输出作为新 observation 注入对话**，让模型继续修复（**背压 / back-pressure**） |

> 🔑 这就是「用机制强制质量」而不是「用 prompt 请求质量」——**模型无法自己宣布成功**。

---

## 七、第六步：可观测性（`trace.py`）

```python
@dataclass
class Trace:
    steps: list[Step] = field(default_factory=list)
    terminated_by: str = "unknown"

    def cost(self, model: str) -> float:
        pin, pout = PRICING.get(model, (0.001, 0.003))
        tin = sum(s.tokens_in for s in self.steps)
        tout = sum(s.tokens_out for s in self.steps)
        return round(tin / 1000 * pin + tout / 1000 * pout, 6)

    def summary(self, model: str) -> dict:
        lat = sorted(s.duration for s in self.steps) or [0.0]
        p95 = lat[min(int(len(lat) * 0.95), len(lat) - 1)]
        return {"turns": self.llm_calls, "tool_calls": self.tool_calls,
                "tokens": self.total_tokens, "cost_usd": self.cost(model),
                "p50_latency": round(statistics.median(lat), 3),
                "p95_latency": round(p95, 3),
                "tool_error_rate": self.tool_error_rate,
                "terminated_by": self.terminated_by}
```

**必须埋的三类埋点**：模型调用、工具调用、决策点（含终止原因）。

> 📌 生产环境请把它换成 **OpenTelemetry GenAI 语义约定**（`gen_ai.*`）导出到 Langfuse / LangSmith，见 [9.11](11-evaluation-observability.md)。

---

## 八、第七步：主编排循环（`harness.py`）

把前面所有模块串起来——**这就是完整的 Harness**。

### 8.1 内部使用"中立消息格式"

```python
{"role": "system"|"user", "content": str}
{"role": "assistant", "content": str, "tool_calls": [{"id","name","args": dict}]}
{"role": "tool", "tool_call_id": str, "name": str, "content": str}
```

格式转换由后端负责（`OpenAIBackend._to_wire`）：

```python
@staticmethod
def _to_wire(m: dict) -> dict:
    if m.get("role") == "assistant" and m.get("tool_calls"):
        return {
            "role": "assistant",
            "content": m.get("content") or None,
            "tool_calls": [
                {"id": c["id"], "type": "function",
                 "function": {"name": c["name"],
                              # ⚠️ 必须是 JSON **字符串**，传 dict 会直接报错
                              "arguments": json.dumps(c.get("args", {}), ensure_ascii=False)}}
                for c in m["tool_calls"]
            ],
        }
    if m.get("role") == "tool":
        return {"role": "tool", "tool_call_id": m.get("tool_call_id"),
                "content": m.get("content", "")}
    return {"role": m.get("role"), "content": m.get("content", "")}
```

> 🐛 **这个 `json.dumps` 是实测踩出来的坑**：OpenAI 的 wire 格式要求 `arguments` 是 JSON 字符串，LangChain 在把 dict 转成消息时会执行 `json.loads(arguments)`，传 dict 直接 `TypeError`。**把转换集中在边界，这个坑只需要踩一次。**

### 8.2 主循环

```python
def run(self, task: str) -> RunState:
    state = RunState(messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ])
    started = time.time()

    while not state.finished:
        # ---------- 三重终止条件 ----------
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
            span.tokens_in, span.tokens_out = reply.tokens_in, reply.tokens_out

        state.messages.append(self._assistant_message(reply))

        # ---------- 步骤 3：输出分类 ----------
        if not reply.tool_calls:
            verdict = self.gate.check(state.__dict__)
            if verdict.passed:
                state.final_text = reply.content
                return self._finish(state, "任务完成")
            if verdict.detail.startswith("[强制终止]"):
                return self._finish(state, verdict.detail)
            # 背压：把失败原因注入，继续循环
            state.messages.append({"role": "user",
                                   "content": f"[验证未通过，请继续修复]\n{verdict.detail}"})
            continue

        # ---------- 步骤 4-5：执行工具 + 结果打包 ----------
        for tc in reply.tool_calls:
            result = self._execute_one(state, tc["name"], tc.get("args", {}))
            state.messages.append({"role": "tool", "tool_call_id": tc.get("id"),
                                   "name": tc["name"], "content": result})

    return state
```

### 8.3 单次工具执行（权限 + 循环检测）

```python
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
```

---

## 九、运行与实测输出

### 9.1 离线自检（零依赖、无需 API Key）

```bash
cd examples/09-mini-harness
python smoke_test.py
```

**实测输出**：

```text
========================================================================
mini-harness 离线自检
========================================================================

---- 场景 A：主循环 trace 报告 ----
⏱  0.17s | 模型调用 8 | 工具调用 6 | tokens 1399 | 成本 $0.00166
   | 工具错误率 0% | 终止原因 任务完成
轮数=8 终止原因=任务完成

✅ ① deny 拦截 `rm -rf /`  —— 权限层应在模型之前拒绝
✅ ② 重复调用被循环检测拒绝  —— max_repeat_calls=3
✅ ③ 验证失败后注入背压  —— Stop Gate 打回并继续循环
✅ ④ 最终经验证通过而终止  —— 实际终止原因：任务完成
✅ ⑤ files_changed 被正确置位
✅ ⑥ 工作区确实产生了 PASS 文件
✅ ⑦ 埋点记录了权限拒绝与循环事件
     —— events=['chat','list_dir','loop.detected','permission.deny',
                'read_file','run_tests','verify.run','write_file']
✅ ⑧ token 与成本统计可用
✅ ⑨ 上下文超限触发压缩且 token 下降  —— 3142 → 325 tokens
✅ ⑩ 压缩保留了 system 头与最近消息  —— 压缩后消息数=4
✅ ⑪ 屏蔽策略：旧工具输出被替换而非删除
     —— 消息条数不变、工具调用仍可见，仅隐藏冗长输出
✅ ⑫ 超限时自动升级为摘要压缩  —— 屏蔽后 21 条 → 摘要后 4 条
✅ ⑬ 权限：run_shell 执行 rm -rf /  —— 期望 deny，实际 deny
✅ ⑬ 权限：plan 模式禁止写文件  —— 期望 deny，实际 deny
✅ ⑬ 权限：accept_edits 允许写文件  —— 期望 allow，实际 allow
✅ ⑬ 权限：只读工具始终放行  —— 期望 allow，实际 allow
✅ ⑬ 权限：auto 模式下危险工具仍需确认  —— 期望 ask，实际 ask
✅ ⑬ 权限：git push 需确认  —— 期望 ask，实际 ask
✅ ⑬ 权限：deny 覆盖 allow（参数级）  —— 期望 deny，实际 deny
------------------------------------------------------------------------
通过 19/19
```

> 💡 自检用的 `FakeLLM` 脚本是：
> `run_shell("rm -rf /")` → `list_dir ×3` → `read_file` → **声称完成（被验证门打回）** → `write_file("PASS")` → 声称完成（通过）。
>
> 这一条脚本**一次性覆盖了 deny / 循环检测 / 背压 / 验证通过**四条路径。

### 9.2 真实运行（需要 API Key）

```bash
export OPENAI_API_KEY=sk-...            # 或 LLM_API_KEY
python main.py "阅读工作区代码，让校验脚本通过"
```

`main.py` 默认 `permission_mode="default"`，每次写操作都会向你确认——**这是刻意设计的保守默认值。**

### 9.3 实测踩到的四个坑

**这四条都是"跑起来"才暴露的，不是写文档时能想到的。**

| # | 坑 | 现象 | 修复 |
|:-:|----|------|------|
| 1 | **Windows 控制台 GBK** | 打印 `⏱` 抛 `UnicodeEncodeError: 'gbk' codec can't encode character` | 入口统一 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` |
| 2 | **工具参数序列化** | `arguments` 传 dict → OpenAI wire 格式要求 JSON 字符串 | 在后端边界统一 `json.dumps` |
| 3 | **压缩是两段式** | 只断言"屏蔽"会失败——超限时会升级为摘要，中间态被覆盖 | 分别验证「屏蔽策略」与「升级为摘要」两个行为 |
| 4 | **`python` 可能是商店占位符** | `test_command=["python", ...]` 找不到解释器 | 用 `[sys.executable, ...]`，不依赖 PATH |

> 🔥 **这四条本身就是最好的 Harness 教学素材**：
> 坑 1 属于「环境适配」，坑 2 属于「格式边界」，坑 3 属于「测试断言设计」，坑 4 属于「可移植性」——
> **它们都不在模型里，全部在 Harness 里。**

---

## 十、逐阶段加固：从骨架到生产

| 阶段 | 把哪个模块换掉 | 换成什么 |
|------|----------------|----------|
| **Phase 1** | `verify.py` | Stop Hook + 对抗性子 Agent（[9.5](05-verification.md)） |
| **Phase 2** | `RunState` | LangGraph checkpointer / Postgres（[9.6](06-subagents-longtasks.md)） |
| **Phase 3** | `trace.py` | OpenTelemetry GenAI + Langfuse/LangSmith（[9.11](11-evaluation-observability.md)） |
| **Phase 4** | `permissions.py` | 完整权限光谱 + 容器沙箱（[9.4](04-permissions-sandbox.md)） |
| **Phase 5** | `context.py` | 五层压缩 + JIT 检索 + 子 Agent 委派（[9.3](03-context-engineering.md)） |
| **Phase 6** | `SYSTEM_PROMPT` | 外置为 `AGENTS.md` + Skills（[9.10](10-standards-skills.md)） |

### 10.1 常见坑对照（[9.1 五类失败模式](01-intro.md)）

| 坑 | 症状 | 本工程对应解法 | 自检编号 |
|----|------|----------------|:--------:|
| 上下文腐化 | 反复重解同一问题 | `ContextManager.maybe_compress` | ⑨⑩⑪⑫ |
| 工具爆炸 | 选错工具 | `schemas(only=...)` 按阶段收窄 | — |
| 静默失败 | 工具报错却继续 | `ToolRegistry.execute` 统一错误格式 | ⑦ |
| 无限循环 | 同一调用反复重试 | `_repeat` 检测 + 三重预算 | ② |
| 状态损坏 | 恢复后前置条件不成立 | 生产阶段用 checkpointer + 前置校验 | — |

---

## 十一、本章总结

| 要点 | 说明 |
|------|------|
| **先验证，后工程** | 四阶段顺序：验证 → 持久化 → 可观测 → 人在回路 |
| **必须有预算** | `max_turns` / `max_total_tokens` / `max_wall_seconds` 三重保险 |
| **Harness 不与模型 SDK 耦合** | 一层 `LLMBackend` 接口换来"可离线验证" |
| **deny 优先** | 权限判定顺序决定安全下限；实测拦住了 `rm -rf /` |
| **路径也要防** | 参数级规则挡不住 `../../`，工具内部必须再校验 |
| **两段式压缩** | 先屏蔽（便宜）→ 再摘要（贵）；实测 3142 → 325 token |
| **验证门是分水岭** | 不通过就把失败当 observation 注入（背压），并有刹车 |
| **能跑才算数** | 19 项断言实测通过；4 个坑全是"跑起来"才暴露的 |

---

## 📝 课后练习

1. **跑通并破坏**：运行 `smoke_test.py`，然后把 `HarnessConfig.max_turns` 改成 3，观察终止原因与 trace 报告如何变化。
2. **加一个工具**：给 `ToolRegistry` 新增 `git_diff`（只读），补齐 schema、加入 `READ_ONLY_TOOLS`，并写一条自检断言。
3. **改造压缩**：把 `_mask_old_tool_outputs` 的"保留最近 6 条"改为**按 token 阈值**动态决定，并在自检中对比压缩前后的 token 数。
4. **接入真实评测**：参考 [9.11](11-evaluation-observability.md) 的 A/B 思路，用 `eval/tasks.jsonl` 对 `max_repeat_calls=1` 与 `=3` 两个配置做对比，输出完成率与平均 token 表——注意 `judge_success` 必须**程序化判定**。
