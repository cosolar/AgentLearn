# 9.4 权限、护栏与沙箱 —— 让 Agent 的双手"可托付"

## 📖 导读

上一章我们把上下文管理成了"最小高信号集"，Agent 的"脑子"清爽了。但真正决定一个 Agent 能否**交付给生产、交给团队、交给客户**的，是另一个问题：

> **当 Agent 的手可以真正"动"世界（读写文件、执行命令、发邮件、调 API）时，你凭什么敢放开它？**

本章的主题就是回答这个问题：**权限（Permissions）→ 护栏（Guardrails）→ 沙箱（Sandbox）**，三道层层递进的防线。

本章你将学到：

- 为什么必须**把权限执行与模型推理解耦**；
- **deny-first（拒绝优先）** 模型：为什么"模型永远看不到被拒的工具"才是硬保证；
- Claude Code 的**七级权限光谱**，以及"约 93% 审批被通过"说明了什么；
- 对约 40 个离散工具能力的**逐项设卡**与**三阶段**流程；
- OpenAI Agents SDK 的**三级护栏**与 **tripwire** 停机机制；
- **Hooks** 作为 Harness 的可编程接口（以及 stdout 为何"不进模型 context"）；
- **沙箱执行**：手段对比、资源限制与可运行的 Docker 执行器；
- 落到 LangChain v1 的**可运行代码**。

> 📚 **前置阅读**：[8.8 安全沙箱](../08-ecosystem/survey/08-security-sandbox.md)（威胁全景与多层防御）与 [6.4 安全与合规](../06-advanced/04-security.md)（安全基础概念）。

---

## 一、核心架构原则：权限执行与模型推理解耦

生产级 Agent 权限设计的第一原则，Anthropic 表述得非常清楚：

> **权限执行与模型推理必须解耦。**
> **模型决定"想尝试做什么"（what to attempt），工具系统决定"什么被允许"（what is permitted）。**

这句话拆开看有三层含义：

```text
┌────────────────────────────────────────────────────────────┐
│  ① 模型层（Model）                                          │
│     只负责"提议"：我想调用 run_shell("rm -rf /")             │
│     —— 它是一个"想法的来源"，不是一个"权威"                  │
└───────────────────────────┬────────────────────────────────┘
                            │ 工具调用请求（未经验证）
                            ▼
┌────────────────────────────────────────────────────────────┐
│  ② 权限层（Permission Layer，确定性代码）                   │
│     对每个请求做 allow / deny / ask 判定                    │
│     —— 不依赖模型的"判断力"，只依赖规则与状态                 │
└───────────────────────────┬────────────────────────────────┘
                            │ 已授权请求
                            ▼
┌────────────────────────────────────────────────────────────┐
│  ③ 执行层（Sandbox / Tool Runtime）                         │
│     真正动手；即使授权了，也受资源/网络/文件系统约束          │
└────────────────────────────────────────────────────────────┘
```

| 错误做法 | 正确做法 |
|----------|----------|
| 在系统提示里写"不要执行危险命令" | 在代码层做 deny 判定，直接拦截 |
| 让模型自己判断"这个命令安不安全" | 用确定性规则/分类器判定 |
| 只在最后一道门设卡 | 每类能力分别设卡 + 高风险显式确认 |
| 授权后不做资源限制 | 授权 ≠ 无限，沙箱继续约束 |

> ⚠️ **为什么"提示词约束"不够**：提示注入（prompt injection）可以诱导模型"自愿"违反系统提示。**能靠代码保证的事，绝不要寄希望于模型的自觉。**

---

## 二、deny-first 权限模型

### 2.1 判定顺序（不可颠倒）

```text
        工具调用请求
             │
             ▼
   ┌──────────────────────┐
   │ 1. 查 DENY 列表       │──命中──▶ ❌ 直接拒绝
   │    （显式禁止）        │          （模型甚至"看不到"该工具）
   └──────────┬───────────┘
              │ 未命中
              ▼
   ┌──────────────────────┐
   │ 2. 查 ALLOW 列表      │──命中──▶ ✅ 放行
   │    （显式允许）        │
   └──────────┬───────────┘
              │ 未命中
              ▼
   ┌──────────────────────┐
   │ 3. 按当前 MODE 决定    │──▶ 询问 / 自动放行 / 自动拒绝
   │    （default 等）      │
   └──────────────────────┘
```

### 2.2 三条铁律

| 铁律 | 含义 | 类比 |
|------|------|------|
| **deny 永远覆盖 allow** | 即使某工具在 allow 里，只要也命中 deny，**一律拒绝** | 防火墙的"拒绝规则优先" |
| **deny 的工具"不可见"** | 命中 deny 的工具**不会出现在模型可调用的工具清单里**，模型**永远看不到它** | 没装的插件不存在 |
| **未命中按 mode 兜底** | 既不 allow 也不 deny 时，由当前权限模式决定（如"每次确认"） | 默认保守 |

> 🔑 **"看不见"比"拒绝"更强**：如果模型能看到工具但总被拒绝，它会**反复尝试绕过**（比如换个写法再试）。而**根本不暴露**，模型就**不会起心动念**——这是"不依赖模型判断力的硬保证"。

### 2.3 最小实现（伪代码，可移植）

```python
from dataclasses import dataclass, field


@dataclass
class PermissionEngine:
    deny: list[str] = field(default_factory=list)    # 优先级最高
    allow: list[str] = field(default_factory=list)
    mode: str = "default"                            # default / accept_edits / auto / plan

    def visible_tools(self, all_tools: list[str]) -> list[str]:
        """模型"能看到"的工具 = 全部工具 − deny 命中项。"""
        return [t for t in all_tools if not self._match(t, self.deny)]

    def decide(self, tool: str, args: dict) -> str:
        """返回 allow / deny / ask。"""
        if self._match(tool, self.deny) or self._match_args(args, self.deny):
            return "deny"                     # ① deny 最优先，覆盖 allow
        if self._match(tool, self.allow):
            return "allow"                    # ② 显式允许
        return {"plan": "deny", "default": "ask",
                "accept_edits": "allow", "auto": "allow"}[self.mode]  # ③ 按 mode 兜底

    @staticmethod
    def _match(tool: str, patterns: list[str]) -> bool:
        import fnmatch
        return any(fnmatch.fnmatch(tool, p) for p in patterns)

    def _match_args(self, args: dict, patterns: list[str]) -> bool:
        import fnmatch
        values = " ".join(str(v) for v in args.values())
        return any(fnmatch.fnmatch(values, p) for p in patterns)
```

---

## 三、Claude Code 的七级权限光谱

Claude Code 把"权限严格程度"做成了一个**可比选的光谱**，从"只读"到"完全放开"：

| 级别 | 名称 | 行为 | 典型场景 |
|------|------|------|----------|
| 1 | **Plan（只读）** | 只探索、只读，绝不写 | 需求调研、代码审查 |
| 2 | **Default（每次确认）** | 每个潜在副作用操作都询问 | 日常默认、陌生仓库 |
| 3 | **Accept Edits（接受编辑）** | 文件编辑自动通过，命令仍确认 | 让 Agent 批量改代码 |
| 4 | **Auto（ML 分类器）** | 用分类器判断"是否安全"自动放行 | 熟练后的高频操作 |
| 5 | **Don't Ask（不再询问）** | 已确认过的同类操作不再弹窗 | 长任务、受控环境 |
| 6 | **Bypass（跳过权限）** | 基本不做权限判断 | 一次性可信脚本 |
| 7 | **Ultracode（完全放开）** | 无限制自主执行 | 实验/离线沙箱 |

```text
  严格 ◀──────────────────────────────────────────────▶ 宽松
  Plan   Default   Accept Edits   Auto   Don't Ask   Bypass   Ultracode
   只读   每次确认   编辑直通      分类器   不弹窗       跳过      全放开
   ▲                                    ▲                          ▲
 最安全                              平衡点                    最高风险
```

### 3.1 "约 93% 权限请求被 approve" 说明了什么？

有一组被广泛引用的观察：**用户对权限弹窗的批准率约为 93%**。表面看像"弹窗没用（用户总是点允许）"，但正确解读恰恰相反：

> **它说明权限设计"精准"**——只对**那 ~7% 真正值得犹豫**的高风险操作弹窗，用户才没被"弹窗疲劳"击垮。如果弹窗全是琐碎操作，用户会条件反射地一律点"允许"，权限系统就退化成摆设。

| 解读 | 结论 |
|------|------|
| ❌ "93% 都通过 → 弹窗是多余的" | 忽略了那 7% 的拦截价值 |
| ✅ "93% 通过 → 说明触发阈值调得好" | 高信噪比的确认，用户才愿意认真看 |

> 💡 **设计启示**：权限系统的目标不是"弹得越多越好"，而是**让每一次弹窗都值得一次认真的人类判断**。

---

## 四、逐项设卡与三阶段流程

### 4.1 为什么要"逐项"而不是"一刀切"

一个编码 Agent 大约暴露**约 40 个离散工具能力**（读文件、写文件、编辑、glob、grep、执行命令、访问网络、提交 git、安装依赖……）。把这些**当作一个整体**来授权是危险的：

| 一刀切做法 | 问题 |
|------------|------|
| "允许文件系统" | 连 `/etc/passwd` 和 `rm` 也能碰 |
| "允许执行命令" | `rm -rf /` 与 `ls` 同级放行 |
| "允许网络" | 数据外泄与拉取依赖同级 |

**逐项设卡**的意思是：**每一类能力单独评估其风险，单独设定 allow / deny / ask。** 例如：

| 能力 | 默认策略 | 理由 |
|------|----------|------|
| 读取文件（限定工作区） | allow | 低风险，高频 |
| 写入/编辑文件 | ask 或 accept_edits | 有副作用 |
| 执行任意命令 | ask（白名单外一律 ask） | 风险极高 |
| 网络访问 | deny（默认）或 ask | 外泄/供应链风险 |
| git push / 发布 | ask（强制人工） | 不可逆、影响他人 |
| 修改 linter/CI 配置 | deny | 防止"改规则骗过检查" |

### 4.2 三阶段：信任是**建立**出来的，不是假设的

```text
阶段一：项目加载时建立信任
  ├─ 读取项目级配置（如 CLAUDE.md / settings）
  ├─ 建立 allow/deny 基线
  └─ 明确"这个仓库里什么是危险的"
             │
             ▼
阶段二：每次工具调用前检查
  ├─ 逐项判定：deny → allow → mode
  ├─ 高风险操作 → 显式确认（await human）
  └─ 全程审计日志（谁 / 何时 / 做了什么）
             │
             ▼
阶段三：高风险操作显式确认
  └─ 不可逆操作（删除、发布、支付、外发）必须人工介入
```

> 🔗 **与 HITL 的衔接**：阶段三对应第 9.4 节后文的 `HumanInTheLoopMiddleware`，也与 [4.x LangGraph 人机协同](../04-langgraph/01-basics.md) 的 interrupt 机制一致。

---

## 五、三级护栏（OpenAI Agents SDK）与 tripwire

OpenAI Agents SDK 把护栏明确分成**三级**，覆盖 Agent 生命周期的三个位置：

```text
用户输入
   │
   ▼
┌───────────────────────┐
│ ① 输入护栏 Input       │  在"第一个 agent"上执行
│   Guardrail            │  检查用户输入是否合规
└───────────┬───────────┘
            │ 通过
            ▼
┌───────────────────────┐
│   Agent 循环           │
│   ┌─────────────────┐  │
│   │ ③ 工具护栏 Tool  │  │  每次工具调用都执行（不是每次任务！）
│   │   Guardrail      │  │
│   └─────────────────┘  │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ ② 输出护栏 Output      │  只对"最终输出"执行
│   Guardrail            │
└───────────────────────┘
```

| 护栏 | 执行时机 | 检查对象 | 典型用途 |
|------|----------|----------|----------|
| **输入护栏** | 进入第一个 Agent 前 | 用户输入 | 提示注入、越狱、违规请求 |
| **输出护栏** | 生成最终输出后 | 最终回答 | 有害内容、PII 泄露、幻觉 |
| **工具护栏** | **每次**工具调用前后 | 工具名 + 参数 + 返回值 | 危险命令、参数越界、外泄数据 |

### 5.1 tripwire（绊线）机制

**tripwire** 是护栏的"熔断"语义：

> 一旦某个护栏判定触发（trip），**Agent 立即停机（halt）**，不再继续执行后续步骤。

```text
工具护栏触发 tripwire：
  Agent ──调用 run_shell("rm -rf /")──▶ 护栏检查 ──❌ trip ──▶ ⛔ Agent 立即停机
  结果：抛出异常 / 返回安全兜底，绝不"继续往下走"
```

> ⚠️ **为什么必须"立即停机"而不能"换个方式重试"**：因为护栏触发往往意味着**出现了设计预期之外的输入或行为**，此时"继续"的每一步都可能扩大危害。tripwire 是**安全上的 fail-fast**。

| 概念 | 含义 |
|------|------|
| Guardrail | 一个可执行检查函数（可能调用 LLM 或规则） |
| Tripwire | 检查失败时抛出的"熔断"信号 |
| Fail-fast | 触发即停，不重试、不降级执行 |

---

## 六、Hooks：Harness 的可编程接口

**Hooks（钩子）** 是 Harness 暴露给开发者的**事件驱动扩展点**，让你在"关键生命周期节点"插入自己的逻辑。

| Hook | 触发时机 | 典型用途 |
|------|----------|----------|
| **PreToolUse** | 工具调用**前** | 拦截危险命令、改写参数、审计 |
| **PostToolUse** | 工具调用**后** | 自动格式化、校验产物、记录结果 |
| **Stop** | Agent 准备**结束**时 | 构建/测试未过 → 阻止结束 |
| **SubagentStart** | 子 Agent **启动**时 | 注入上下文、限制权限 |

### 6.1 关键细节：hook 的 stdout **不进入模型 context**

这是最容易踩坑、也最重要的一点：

> **Hook 在 exit 0（正常退出）时，其 stdout 不会进入模型的上下文（context）。**
> **只有通过 `hookSpecificOutput.additionalContext` 返回的 JSON，才会被模型"看到"。**

```text
❌ 常见误解：
   hook 里 print("请务必运行测试")  →  以为模型会看到  →  实际模型什么都没看到

✅ 正确做法：
   让 hook 输出结构化 JSON，把要注入的内容放进 additionalContext
```

依据不同实现，结构化输出的形状大致如下（**具体字段以官方文档为准**）：

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "additionalContext": "注意：本仓库禁止修改 lint 配置。"
  }
}
```

| 输出方式 | 是否进模型 context | 用途 |
|----------|-------------------|------|
| 普通 stdout（exit 0） | ❌ 不进 | 给人看的日志/调试信息 |
| `additionalContext`（JSON） | ✅ 进 | 给模型看的补充指令 |
| exit 非 0 | 触发 block/错误语义 | 阻止本次操作/结束 |

> 💡 **实践要点**：**"给机器看的"和"给人看的"要分开**。人看日志用 stdout；要让模型改变行为，必须走 `additionalContext`。

---

## 七、典型 Hook 场景

| 场景 | Hook | 逻辑 | 效果 |
|------|------|------|------|
| **编辑后自动格式化** | PostToolUse | 检测到 `.py` 被改 → 运行 `ruff format` | 代码风格始终一致 |
| **阻止 `rm -rf`** | PreToolUse | 命令命中 `/rm\s+-rf\s+\//` → 返回 deny | 杜绝灾难性删除 |
| **阻止改 linter 配置** | PreToolUse | 目标文件是 `ruff.toml`/`.eslintrc` → deny | 防止"改规则骗检查" |
| **构建不通过不许停** | Stop | 运行 `npm test && npm run build`，失败则 block | 保证交付质量 |
| **子 Agent 注入上下文** | SubagentStart | 返回 `additionalContext` 注入任务约束 | 子 Agent 不跑偏 |
| **审计与合规** | PreToolUse | 记录 who/when/what 到审计日志 | 可追溯 |

> 🔗 **与验证的衔接**：上表中"构建不通过不许停"正是下一章 [9.5 验证循环](05-verification.md) 的 **Stop Hook 确定性 gate**。

---

## 八、沙箱执行：授权之后的第二道墙

### 8.1 为什么"授权了"还要沙箱

即使一次工具调用**通过了权限检查**，也不代表它可以**不受限制地运行**：

| 风险 | 沙箱如何缓解 |
|------|--------------|
| 无限循环 / 死循环 | 超时（timeout）强制终止 |
| 内存爆炸（fork bomb） | 内存上限 + 进程数上限（pids_limit） |
| 挖矿 / 对外攻击 | 禁用网络（network_disabled） |
| 篡改宿主文件 | 只读文件系统 + 只挂载必要目录 |
| 逃逸后提权 | 非 root 用户运行（user 65534） |

> 🎯 **一句话**：**权限决定"能不能做"，沙箱决定"做了也伤不到我"。** 对**代码执行类 Agent**（编程、数据科学），沙箱从"可选"变成"必需"。

### 8.2 沙箱手段对比

| 手段 | 隔离强度 | 启动速度 | 资源开销 | 适用 |
|------|----------|----------|----------|------|
| **Docker（容器）** | ⭐⭐⭐⭐ | 快（秒级） | 中 | 通用自建，最常用 |
| **gVisor** | ⭐⭐⭐⭐⭐ | 中 | 中高 | 需更强系统调用隔离 |
| **Firecracker（microVM）** | ⭐⭐⭐⭐⭐ | 中 | 中 | 云原生多租户 |
| **WebAssembly（Wasm）** | ⭐⭐⭐⭐ | 极快（毫秒） | 低 | 沙箱内纯计算、插件 |
| **云沙箱（如 E2B）** | ⭐⭐⭐⭐⭐ | 中 | 按用量 | 免运维、可弹性扩缩 |
| **无服务器（Lambda 等）** | ⭐⭐⭐⭐⭐ | 冷启动慢 | 按用量 | 事件驱动、短任务 |

### 8.3 资源限制清单

| 限制项 | 参数示例 | 作用 |
|--------|----------|------|
| 内存 | `mem_limit="256m"` | 防内存爆炸 |
| CPU | `cpu_quota=50000` | 限 50% 单核 |
| 进程数 | `pids_limit=128` | 防 fork bomb |
| 网络 | `network_disabled=True` | 断外联 |
| 文件系统 | `read_only=True` | 防篡改宿主 |
| 用户 | `user="65534:65534"` | 非 root |
| 超时 | `timeout=20` | 防挂死 |
| 生命周期 | `remove=True` | 用完即毁 |

---

## 九、可运行代码

### 9.1 LangChain v1 护栏中间件（PII 脱敏 + 人工审批）

> 📌 类路径说明：以下导入来自 `langchain.agents.middleware`（在 LangChain v1 中 `PIIMiddleware`、`HumanInTheLoopMiddleware` 属于 Agent 中间件）。**不同版本的具体导入路径与参数名请以官方文档为准。**

```python
from langchain.agents import create_agent
from langchain.agents.middleware import (
    PIIMiddleware,
    HumanInTheLoopMiddleware,
)
from langchain.chat_models import init_chat_model

model = init_chat_model("gpt-5.5", model_provider="openai")

agent = create_agent(
    model=model,
    tools=[read_file, write_file, send_email, run_shell],
    middleware=[
        # ① 输入/输出脱敏：把邮箱、手机号、身份证等替换为占位符
        PIIMiddleware(strategy="redact"),
        # ② 高危工具在真正执行前需人类审批
        #    决策语义通常为 approve / edit / reject（以官方文档为准）
        HumanInTheLoopMiddleware(
            tools=["send_email", "run_shell"],
            # description="以下操作有副作用，请确认：",  # 参数名以官方文档为准
        ),
    ],
    system_prompt="你是安全的运维助手，绝不执行破坏性命令。",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "把今天的报告发给 alice@example.com"}]}
)
print(result["messages"][-1].content)
```

| 中间件 | 对应护栏级别 | 作用 |
|--------|--------------|------|
| `PIIMiddleware` | 输入 + 输出护栏 | 脱敏，防隐私泄露 |
| `HumanInTheLoopMiddleware` | 工具护栏（人工） | 高风险操作显式确认 |

### 9.2 真的能跑的 Docker 沙箱执行器

> 依赖：`uv add docker`；本机需有可用的 Docker 守护进程。镜像用官方 `python:3.12-slim`。

```python
# sandbox.py
import docker
from docker.errors import ContainerError, ImageNotFound, APIError


class DockerSandbox:
    """最小可用的代码执行沙箱：资源受限、无网络、只读文件系统。"""

    def __init__(self, image: str = "python:3.12-slim"):
        self.client = docker.from_env()
        self.image = image

    def run(self, code: str, timeout: int = 20) -> str:
        """在隔离容器里执行 Python 代码，返回 stdout/stderr 或错误说明。"""
        try:
            output = self.client.containers.run(
                self.image,
                command=["python", "-c", code],
                mem_limit="256m",           # 内存上限
                cpu_quota=50000,            # CPU 上限（50% 单核）
                pids_limit=128,             # 进程数上限，防 fork bomb
                network_disabled=True,      # 禁用网络
                read_only=True,             # 根文件系统只读
                tmpfs={"/tmp": "size=64m"}, # 仅 /tmp 可写且有上限
                user="65534:65534",         # 非 root 用户运行
                remove=True,                # 运行结束自动删除容器
                timeout=timeout,            # 超时自动 kill
                environment={"PYTHONDONTWRITEBYTECODE": "1"},
            )
            return output.decode("utf-8", "replace")
        except ContainerError as e:
            stderr = (e.stderr or b"").decode("utf-8", "replace")
            return f"[非零退出，exit={e.exit_status}]\n{stderr}"
        except ImageNotFound:
            return f"[错误] 找不到镜像 {self.image}，请先 docker pull"
        except APIError as e:
            return f"[Docker API 错误] {e}"
        except Exception as e:  # 超时等
            return f"[沙箱拒绝执行] {type(e).__name__}: {e}"


if __name__ == "__main__":
    sb = DockerSandbox()
    print(sb.run("print('hello from sandbox')"))
    # 故意测试网络与写入限制
    print(sb.run("import socket; socket.create_connection(('1.1.1.1', 53), 2)"))
```

**把它接成 LangChain 工具**：

```python
from langchain.tools import tool

sb = DockerSandbox()


@tool
def run_python(code: str) -> str:
    """在安全沙箱中执行一段 Python 代码，返回执行结果。"""
    return sb.run(code, timeout=20)
```

### 9.3 PreToolUse 式的工具拦截装饰器（allow/deny + 审计）

在 LangChain 工具的**最外层**套一层"权限 + 审计"，实现与 PreToolUse 等价的语义：

```python
# guard.py
import logging
import re
from functools import wraps

from langchain.tools import tool

audit = logging.getLogger("agent.audit")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── deny-first：先定义"绝对禁止"，优先级高于一切 allow ──
DENY_PATTERNS = [
    r"rm\s+-rf\s+/",          # 灾难性删除
    r":\(\)\s*\{.*\};\s*:",   # fork bomb
    r"curl\s+.*\|\s*(sh|bash)",  # 管道执行远程脚本
    r">\s*/etc/",             # 篡改系统配置
]

# 白名单前缀：仅这些命令可在"非沙箱"下直接执行
ALLOW_PREFIXES = ("ls", "cat", "head", "tail", "grep", "rg", "git status")


def pre_tool_use(deny_patterns: list[str]):
    """PreToolUse 风格装饰器：命中 deny 直接拦截并记审计。"""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            target = kwargs.get("command") or (args[0] if args else "")
            target = str(target)
            # ① 审计：先记录（who/when/what），脱敏后再落盘（此处仅示意）
            audit.info("tool=%s input=%r", fn.__name__, target[:200])
            # ② deny-first 判定
            for pattern in deny_patterns:
                if re.search(pattern, target):
                    audit.warning("DENIED tool=%s pattern=%r", fn.__name__, pattern)
                    return f"[BLOCKED] 命中 deny 规则：{pattern}（该操作已被权限层拒绝）"
            # ③ 未命中 deny 时，交由沙箱/白名单执行
            return fn(*args, **kwargs)

        return wrapper

    return decorator


@tool
@pre_tool_use(DENY_PATTERNS)
def run_shell(command: str) -> str:
    """执行一条 shell 命令（受权限层与沙箱双重约束）。"""
    # 生产环境应始终走沙箱；此处示意"白名单直通、其余走沙箱"
    if command.startswith(ALLOW_PREFIXES):
        return f"[白名单直通] {command}"
    return DockerSandbox().run(f"import subprocess;print(subprocess)")
```

> ⚠️ **装饰器顺序**：`@tool` 必须在**最外层**（写在最上面），它会读取下方 wrapper 的函数名与 docstring。由于使用了 `@wraps`，工具名与描述得以保留。

---

## 十、权限模式选型与落地建议

### 10.1 宽松 vs 严格选型表

| 维度 | 宽松（Auto / Bypass） | 严格（Plan / Default） |
|------|----------------------|------------------------|
| 适用环境 | 一次性沙箱、离线实验 | 生产仓库、共享环境 |
| 适用对象 | 可信、幂等、可回滚任务 | 不可逆、影响他人操作 |
| 效率 | 高（少打断） | 低（需人审） |
| 风险 | 高（误解会扩大） | 低 |
| 建议级别 | Don't Ask / Bypass | Default / Accept Edits |

### 10.2 落地建议：从"激进审批"开始，随信心逐步放宽

```text
信任曲线（推荐路径）
严格                                                          宽松
 │                                                             │
 │  Plan ──▶ Default ──▶ Accept Edits ──▶ Auto ──▶ Don't Ask    │
 │   │          │              │            │           │       │
 │   │          │              │            │           └ 对"已反复确认安全"的操作
 │   │          │              │            └ 用分类器自动放行低风险操作
 │   │          │              └ 让编辑自动化，命令仍确认
 │   │          └ 起点：每个副作用操作都问
 │   └ 起点：先只读，理解 Agent 会做什么
 │                                                             │
 └──────────── 时间 / 观测数据 / 信任积累 ────────────────────────┘
```

**四条落地原则**：

| 原则 | 说明 |
|------|------|
| **先严后松** | 从 Plan/Default 起步，用**观测数据**支撑放宽，而不是"觉得它应该没问题" |
| **不可逆操作永不自动** | 发布、删除、支付、外发，永远人工确认 |
| **deny 清单要常驻** | 危险模式（`rm -rf /`、改 CI 配置）写入 deny，不随 mode 放宽而解除 |
| **沙箱兜底** | 即使 mode 到了 Bypass，执行仍走沙箱（内存/网络/超时） |

> 🔗 **下一章预告**：权限与护栏保证了"不该做的做不了"，但要保证"该做的**做对了**"，还需要**验证循环**——见 [9.5 验证循环](05-verification.md)。

---

## 本章小结

| 要点 | 说明 |
|------|------|
| 🧩 **解耦原则** | 模型决定"想做什么"，工具系统决定"什么被允许" |
| 🛡️ **deny-first** | 先查 deny → 再 allow → 兜底 mode；**deny 永远覆盖 allow** |
| 👁️ **不可见即安全** | 被 deny 的工具**不暴露给模型**，模型不会反复尝试绕过 |
| 🌈 **七级光谱** | Plan → Default → Accept Edits → Auto → Don't Ask → Bypass → Ultracode |
| 🎯 **93% 批准率** | 说明弹窗精准，只对高价值风险打断用户 |
| 🧱 **逐项设卡** | 约 40 个离散能力分别设 allow/deny/ask；三阶段建立信任 |
| 🪢 **三级护栏** | 输入 / 输出 / 工具（每次调用）；**tripwire** 触发即停机 |
| 🪝 **Hooks** | PreToolUse / PostToolUse / Stop / SubagentStart；stdout **不进** context，须用 `additionalContext` |
| 📦 **沙箱** | 授权 ≠ 无限；Docker/gVisor/Firecracker/Wasm/云沙箱 + 资源限制 |
| 📈 **渐进放宽** | 从激进审批开始，用观测数据支撑逐步放宽 |

---

## 📝 课后练习

1. **✅ 基础**：为你的 Agent 增加一个 `PIIMiddleware`，构造含邮箱与手机号的输入，确认脱敏生效。
2. **💡 进阶**：用 `HumanInTheLoopMiddleware` 让 `send_email` 必须人工审批，并实现"拒绝后 Agent 优雅收尾"。
3. **🚀 挑战**：用 Docker SDK 实现 `DockerSandbox`，分别验证网络禁用、内存上限、只读文件系统三项限制确实生效（尝试越界并观察报错）。
4. **🔍 探索**：写一个 PreToolUse 式装饰器，实现"编辑后自动格式化"与"阻止修改 linter 配置"两条规则，并输出审计日志。

---

> 🔗 **下一步**：Agent 的手被管住了，接下来要让它**知道自己做对了没有**——请阅读 [9.5 验证循环](05-verification.md)。
