# 9.12 开源 Harness 源码解剖 —— 四个经典项目的架构启示

> 📅 更新至 2026-10 · 技术栈基线见 [教程大纲](../教程大纲.md)

## 📖 本章目标

- 从"用 Harness"进阶到"读懂 Harness"：知道一个成熟 Harness 内部到底怎么组织
- 逐个解剖四个**开源经典项目**的真实架构与关键设计：
  - **OpenHands** —— 事件驱动的平台化 Harness（Docker 沙箱 + 微代理）
  - **SWE-agent** —— **ACI（Agent-Computer Interface）**：界面设计即能力
  - **Aider** —— **repo map**：把整个仓库压缩成一张"地图"塞进上下文
  - **smolagents** —— **Code Agent**：让模型用代码而不是 JSON 表达动作
- 把四个项目的模式**映射回 [9.2 十二大模块](./02-十二大模块解剖.md)**，看清"设计"与"实现"的对应关系
- 动手：把这四种模式各挑一条，装进你自己的 [mini-harness](../../examples/09-mini-harness/)

> 📖 **前置阅读**：[9.2 十二大模块](./02-十二大模块解剖.md)（先有模块地图）、[9.3 上下文工程](./03-上下文工程与压缩.md)、[9.4 权限与沙箱](./04-权限护栏与沙箱.md)、[9.5 验证循环](./05-验证循环.md)。
>
> ⚠️ 四个项目迭代很快，具体 API、命令与数字请**以官方仓库为准**；本章聚焦**架构与设计思想**（这部分变化最慢）。

---

## 一、为什么必须读源码

[9.9 开源 Harness 全景](./09-开源Harness全景.md) 教你怎么**选**一个 Harness；本章教你怎么**读**一个 Harness。

这两件事的分水岭是：

> **会选型的人知道"用哪个"，会读源码的人知道"为什么它好用，以及我该抄哪一段"。**

Harness 的核心难点从来不是"调用模型"——那只有几行代码。难的是那 **98.4% 的操作性工程**（见 [9.9 Claude Code 一节](./09-开源Harness全景.md)）：上下文怎么裁、动作怎么表达、失败怎么反馈、权限怎么把关、长任务怎么不崩。

而这些问题的**最佳答案，往往已经被开源项目用几万行代码验证过了**。读它们，等于站在巨人肩膀上做设计决策。

读源码的正确姿势（本章对每个项目都按这个模板）：

| 步骤 | 问题 |
|:-----|:-----|
| ① 定位 | 它是什么形态？（平台 / CLI / 库） |
| ② 拆层 | 它的架构分成哪几层？ |
| ③ 抓关键 | 它最独到的 1–2 个设计是什么？ |
| ④ 抄走 | 我能把哪三条原则搬进自己的 Harness？ |

---

## 二、四个经典项目一览

| 项目 | 形态 | 语言 | 许可 | 一句话核心思想 | 最适合学什么 |
|:-----|:-----|:-----|:-----|:---------------|:-------------|
| **OpenHands** | 完整平台（Web + CLI + API） | Python | MIT | **事件驱动 + Docker 沙箱 + 微代理** | 平台化分层、沙箱隔离、事件流 |
| **SWE-agent** | CLI / 研究框架 | Python | MIT | **为模型设计界面（ACI）** | 工具/动作的接口设计、护栏 |
| **Aider** | CLI 结对编程 | Python | Apache-2.0 | **用 repo map 喂上下文** | 上下文选择与压缩 |
| **smolagents** | 极简库（~1000 行） | Python | Apache-2.0 | **动作即代码（Code Agent）** | 动作表达范式、最小实现 |

> 💡 **四个项目刚好覆盖 Harness 的四个不同切面**：OpenHands 讲**平台与沙箱**，SWE-agent 讲**接口设计**，Aider 讲**上下文**，smolagents 讲**动作表达**。四个都读完，[9.2 的十二大模块](./02-十二大模块解剖.md) 就有了四份"参考实现"。

---

## 三、OpenHands —— 事件驱动的平台化 Harness

### 3.1 它是什么

OpenHands（原 **OpenDevin**，All-Hands-AI 出品，MIT）是**最完整的开源软件工程 Agent 平台**：不只是命令行工具，而是包含 Web UI、API、微代理、沙箱与评测框架的整套基础设施。截至 2026 年初已积累数万 star，并有全职团队维护。

### 3.2 架构分层

OpenHands 的关键设计是**把"决策"和"执行"彻底解耦**，中间用一条**事件总线**连接：

```text
┌──────────────────────────────────────────────────────────┐
│  入口层：CLI  /  Web UI  /  REST API                       │
├──────────────────────────────────────────────────────────┤
│  会话层：Session Manager（生命周期、状态、恢复）            │
├──────────────────────────────────────────────────────────┤
│  决策层：Agent Controller（"想"：调模型、产出 Action）      │
│            ▲                              │                │
│            │  Action / Observation        │                │
│            ▼                              ▼                │
│  总线层：EventStream（事件流：一切皆事件）                  │
├──────────────────────────────────────────────────────────┤
│  执行层：Runtime（"做"：把 Action 变成 Observation）        │
│           ├─ Docker Sandbox（隔离容器，默认开启）           │
│           ├─ 本地 Runtime                                   │
│           └─ Browser Runtime（网页任务）                    │
└──────────────────────────────────────────────────────────┘
```

这套结构带来三个直接好处：

1. **Agent 与 Runtime 解耦**：同一份 Agent 逻辑，可以跑在本地，也可以跑在 Docker、远程沙箱里——只要替换 Runtime 实现。
2. **一切皆事件**：用户消息、模型回复、动作、观察、错误，全部是 EventStream 上的事件。这让**回放、审计、断点恢复**变得自然。
3. **沙箱是核心而非可选项**：`Safety by Default`——默认在 Docker 容器里执行，天然获得进程隔离、资源限制、环境可复现。

### 3.3 关键设计 ①：Docker 沙箱（默认开启）

OpenHands 的沙箱实现是"安全执行代码"的教科书级范本。它的容器启动参数几乎把能加的隔离都加上了：

```python
# 概念示意（简化自 OpenHands 的 Docker Runtime，细节以官方仓库为准）
self.container = client.containers.run(
    image_name,
    name=container_name,
    detach=True,
    # —— 资源限制：防止 Agent 跑飞把机器拖垮 ——
    mem_limit="4g",
    cpu_quota=100000,          # 约 1 CPU
    # —— 网络隔离 ——
    network="bridge",
    # —— 文件系统隔离：只挂载工作区，且可读写 ——
    volumes={"/workspace": {"bind": "/workspace", "mode": "rw"}},
    # —— 安全选项：禁止提权、丢弃全部 capability，只按需加回 ——
    security_opt=["no-new-privileges:true"],
    cap_drop=["ALL"],
    cap_add=["CHOWN", "SETGID", "SETUID"],
)
```

**这段参数值得逐条抄走**：

| 参数 | 作用 | 为什么重要 |
|:-----|:-----|:-----------|
| `mem_limit` / `cpu_quota` | 资源上限 | Agent 死循环时保护宿主机 |
| `network="bridge"` | 网络隔离 | 限制外联，降低数据外泄风险 |
| `volumes` 只挂 `/workspace` | 文件系统隔离 | 容器内看不到宿主机其它文件 |
| `security_opt: no-new-privileges` | 禁止提权 | 即使被利用也无法获得 root |
| `cap_drop: ALL` + 按需 `cap_add` | 最小权限 | 默认全禁，只开必要能力 |

> 🔗 这正是 [9.4 权限与沙箱](./04-权限护栏与沙箱.md) 讲的 **deny-first（默认拒绝）** 在容器层面的落地：不是"禁止危险的"，而是"默认什么都不能，只放开必需的"。

### 3.4 关键设计 ②：微代理（Micro-Agents）

OpenHands 不推崇"一个万能 Agent"，而是**可组合的微代理**：

```text
用户请求 → [Delegator 委派 Agent] → 任务分解
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   [CodeAct]   [Browsing]  [Verifier]
   改代码/跑命令  查网页      验证结果
        └───────────┼───────────┘
                    ▼
               结果整合
```

- **CodeActAgent**（默认）：通过"写代码 + 执行"来行动，用统一的 Action 空间覆盖读写文件、跑命令等；
- **BrowsingAgent**：专门处理网页任务，走 Browser Runtime；
- **DelegatorAgent**：负责判断复杂度、拆解任务、调度子代理。

> 🔗 这就是 [9.6 子 Agent 编排](./06-子Agent编排与长时任务.md) 的"平台级"版本：**主 Agent 只做分派与整合，专业活交给专业微代理**。

### 3.5 关键设计 ③：Condenser（上下文压缩器）

长任务必然撑爆上下文。OpenHands 用一个独立的 **Condenser（冷凝器）** 组件负责把历史"降温压缩"——把冗长的中间过程替换为摘要，保留决策与未解决问题。

> 🔗 与 [9.3 上下文工程与压缩](./03-上下文工程与压缩.md) 的"摘要压缩"策略完全同构，只是 OpenHands 把它做成了一个**可插拔的独立模块**。

### 3.6 从 OpenHands 抄走的三件事

| # | 原则 | 落到你的 Harness |
|:-:|:-----|:-----------------|
| 1 | **决策与执行解耦** | Agent 只产出 Action，执行交给可替换的 Runtime |
| 2 | **沙箱默认开启 + 最小权限** | 容器默认丢 capability、限资源、只挂工作区 |
| 3 | **把压缩做成独立组件** | 上下文压缩不散落在各处，集中成一个 Condenser |

---

## 四、SWE-agent —— ACI：界面设计就是能力

### 4.1 它是什么

SWE-agent（普林斯顿团队，论文 [arXiv:2405.15793](https://arxiv.org/abs/2405.15793)，NeurIPS 2024）为"自动修复 GitHub issue"而生。它最重要的贡献**不是模型技巧，而是一个观点**：

> **对 LM Agent 来说，"界面"（Agent-Computer Interface, ACI）与模型能力同等重要，是一等设计变量。**

论文的核心论证是：人用的 Linux shell 和 IDE 对**模型**并不友好——动作太细、反馈太长、噪音太多。给模型一套**为它量身定做**的命令与反馈，效果能显著提升。

### 4.2 ACI 的五个设计原则

| 原则 | 说明 | 反面教材 |
|:-----|:-----|:---------|
| **① 动作粒度适中** | 一条命令完成一件有意义的事（如"打开文件"），而非逼模型用 `cat`/`sed` 拼 | 让模型自己拼 `sed -n '10,20p'` |
| **② 反馈简洁** | 输出截断到合理长度（如若干行），附"还有 N 行"提示 | 一次 `cat` 整个大文件刷屏 |
| **③ 面向模型的命令集** | 提供 `open`/`search`/`edit`/`scroll` 这类语义化命令 | 只给裸 bash |
| **④ 护栏内建** | 编辑命令校验唯一匹配、禁止空编辑、拒绝非法参数 | 让模型瞎改导致文件损坏 |
| **⑤ 即时校验反馈** | 编辑后立刻跑语法检查（lint），把错误**马上**喂回去 | 等跑测试才发现语法错 |

**ACI 的命令集形态**（示意，具体命令名以官方为准）：

```text
search_dir <关键词>      # 在目录内搜索，返回命中文件与行号
search_file <关键词> <文件>  # 在文件内搜索
find_file <文件名>        # 按名字找文件
open <文件> [行号]        # 打开文件（可定位到行），输出带行号
edit <起> <止> <文件>     # 用替换文本编辑指定行范围（带唯一匹配校验）
scroll_down / scroll_up   # 在已打开文件内翻页
```

### 4.3 为什么"护栏 + 简洁反馈"能提升分数

论文报告：在 SWE-bench 上 pass@1 约 **12.5%**（当时用 GPT-4 Turbo 作决策核心），HumanEvalFix 上 **87.7%**，均超过此前的非交互式基线。更关键的结论是：

- 同样的模型，**换一套 ACI，分数明显变化**；
- **编辑护栏**（拒绝非法编辑、要求唯一匹配）显著减少"越改越乱"；
- **lint 即时反馈**让模型能在"下一步"就自我修正，而不是拖到最后。

> 🔗 这就是 [9.5 验证循环](./05-验证循环.md) 讲的 **back-pressure（背压）**：把失败的后果**尽可能早、尽可能小**地反馈给模型，逼它立刻修正。

### 4.4 从 SWE-agent 抄走的三件事

| # | 原则 | 落到你的 Harness |
|:-:|:-----|:-----------------|
| 1 | **工具是给模型用的产品** | 每个工具的输入/输出都为"模型好不好用"而设计，不是为"人好不好看" |
| 2 | **护栏放在工具内** | 编辑前校验、参数非法即拒绝，别指望模型自觉 |
| 3 | **反馈要短、要即时** | 截断长输出；每次动作后立刻给可行动的反馈 |

---

## 五、Aider —— repo map：把仓库压缩成一张地图

### 5.1 它是什么

Aider 是终端里的 AI 结对编程工具（Apache-2.0）。它的招牌设计是 **repo map（仓库地图）**。

### 5.2 要解决的问题

模型要改一个类，得先知道：**这个类在哪、它依赖谁、谁依赖它**。三种常见做法都有毛病：

| 做法 | 问题 |
|:-----|:-----|
| 把整个仓库塞进去 | 稍大的仓库就撑爆上下文 |
| 手动挑文件 | 要人肉判断，累且易漏 |
| 只给要改的文件 | 缺全局视野，改出来不"合群" |

### 5.3 Aider 的解法：tree-sitter + 图排序

Aider 的做法分两步：

**第一步：用 tree-sitter 抽取符号。** tree-sitter 把源码解析成 AST，从中找出**类、函数、方法及其签名**，以及它们之间的**定义与引用**关系。于是整个仓库被压成一张"符号地图"：

```text
aider/coders/base_coder.py:
⋮...
│class Coder:
│    abs_fnames = None
⋮...
│    @classmethod
│    def create(self, main_model, edit_format, io, ...):
⋮...
│    def run(self, with_message=None):
⋮...
```

**第二步：用图排序挑最相关的片段。** 把每个源文件当成图的一个节点，文件间的依赖当成边，然后跑**图排序算法**（PageRank 思路），选出"最重要、最常被引用"的部分，**按 token 预算**（`--map-tokens`，默认约 1k）装进上下文。

### 5.4 为什么这招高明

- **信息密度极高**：只给签名和关键行，不给实现细节——模型要的是"知道有什么"，而不是"读完所有"；
- **自动 + 可控**：默认自动选，但用户能用 token 预算调节详略；
- **给模型"按图索骥"的能力**：地图里没有的，模型可以自己要求"打开某文件"，Aider 再按需补进来。

> 🔗 这就是 [9.3 上下文工程](./03-上下文工程与压缩.md) 里 **"渐进式披露" + "信噪比优先"** 的一个极致实现：**先给地图，再按需给细节**。

### 5.5 从 Aider 抄走的三件事

| # | 原则 | 落到你的 Harness |
|:-:|:-----|:-----------------|
| 1 | **先给地图，再给细节** | 用结构化索引（符号/文件树）替代全量代码 |
| 2 | **按预算选上下文** | 上下文不是"能塞多少塞多少"，而是"给定预算选最高信号的" |
| 3 | **让模型主动要更多** | 提供"读取指定文件/范围"的工具，把细节留给模型按需拉取 |

---

## 六、smolagents —— 动作即代码（Code Agent）

### 6.1 它是什么

smolagents 是 Hugging Face 出品的**极简** Agent 库——整个 agent 逻辑压缩到约一千行。它的核心主张极具冲击力：

> **让模型用「写代码」来表达动作，而不是用 JSON 工具调用。**

### 6.2 两种 Agent 范式的对比

| 维度 | ToolCallingAgent（JSON 工具调用） | **CodeAgent（写代码动作）** |
|:-----|:--------------------------------|:---------------------------|
| 动作表达 | 结构化 JSON：`{"tool": "...", "args": {...}}` | 一段可执行代码，如 `result = search(q) + summarize(result)` |
| 可组合性 | 弱：一次只能调一个工具，组合要靠多轮 | **强**：函数嵌套、循环、条件、变量复用，一步到位 |
| 中间结果 | 每步都要回传模型 | 可在代码里本地处理，**不必回传** |
| 步数 | 多（工具越多越碎） | 少（一次生成搞定多步） |
| 安全要求 | 较低 | **高**：代码必须沙箱执行 |

### 6.3 为什么"代码动作"更强

看一个例子。任务："找出三家公司里员工数最多的那个，并抓取它的官网首页"。

- **JSON 工具调用**：调 A 拿数据 → 回传 → 调 B 拿数据 → 回传 → 调 C 拿数据 → 回传 → 模型比较 → 调 D 抓网页…… 五轮以上，每轮都占上下文。
- **Code Agent**：

```python
# 模型一次性写出的动作（概念示意）
data = [fetch_employees(c) for c in ["A", "B", "C"]]   # 循环，一次拿三个
best = max(zip(data, ["A", "B", "C"]))[1]              # 本地比较，不必回传
homepage = scrape(f"https://{best}.com")               # 直接抓取
```

**一轮动作干完了 JSON 版五轮的活**——中间数据留在代码执行环境里，不用来回搬运，上下文省了，步数少了。

代价是**必须沙箱执行**：smolagents 支持 **E2B / Docker / Modal / Blaxel** 等隔离后端。

> 🔗 这正是 [9.4 权限与沙箱](./04-权限护栏与沙箱.md) 说的："能力越强，边界越要硬"。Code Agent 把"可组合性"拉满，就必须把"执行隔离"同步拉满。

### 6.4 从 smolagents 抄走的三件事

| # | 原则 | 落到你的 Harness |
|:-:|:-----|:-----------------|
| 1 | **动作表达是一种设计选择** | 在高可组合场景，考虑"代码动作"而非"JSON 工具调用" |
| 2 | **中间结果留在执行侧** | 能在沙箱里算完的，别搬回上下文 |
| 3 | **极简是美德** | 约一千行也能做 Agent——先想清楚最少需要什么，再加 |

---

## 七、横向对比：四个项目 → 十二大模块

把四个项目的关键设计，映射回 [9.2 十二大模块](./02-十二大模块解剖.md)：

| 十二大模块 | OpenHands | SWE-agent | Aider | smolagents |
|:-----------|:----------|:----------|:------|:-----------|
| **编排循环** | Agent Controller + EventStream | ReAct 式"想 + 命令" | 对话式主循环 | ~1000 行极简循环 |
| **工具/动作** | 统一 Action 空间 | **ACI 命令集** | 文件/编辑工具 | **代码动作** |
| **上下文** | **Condenser** | 简洁反馈 + 截断 | **repo map** | 中间结果不出沙箱 |
| **权限/沙箱** | **Docker 默认开启** | 编辑护栏 | git 安全网（可回滚） | E2B/Docker/Modal |
| **验证** | 内置 SWE-bench 评测 | **lint 即时反馈** | 跑测试 | 执行即验证 |
| **子 Agent** | **微代理（Delegator）** | 单 Agent 为主 | 单 Agent | 可组合多 Agent |
| **生命周期** | Session Manager | 单次任务 | 会话 + git 历史 | 极简 |

**四个项目的共同点**（也是最该内化的）：

1. **都把"上下文"当第一等公民**——Condenser / 简洁反馈 / repo map / 不搬中间结果，四家在同一个问题上各有解法；
2. **都在"边界"上极度认真**——Docker 隔离 / 编辑护栏 / git 安全网 / 沙箱执行；
3. **都在"反馈"上做文章**——即时 lint / 截断输出 / 结构化 observation；
4. **都不追求"一个万能 Agent"**——要么拆微代理，要么把动作做粗，减少往返。

---

## 八、动手：把四种模式装进 mini-harness

打开 [mini-harness](../../examples/09-mini-harness/)（约 700 行、纯标准库、离线自检 19/19 通过），它有 `tools.py`（工具注册表）、`context.py`（上下文压缩）、`permissions.py`（权限）、`verify.py`（验证门）、`harness.py`（主循环）。下面四个练习，正好把四个项目各抄一条进去。

### 8.1 抄 Aider：给上下文加一个"仓库地图"

在 `context.py` 里增加一个"结构化索引"生成器，在压缩时**优先保留符号地图**而非原始文件内容：

```python
# context.py 的扩展思路（伪代码，示意）
def build_repo_map(cfg, max_tokens: int = 1000) -> str:
    """用正则/AST 抽取每个 .py 文件里的类名与函数签名，拼成一张地图。"""
    import ast, pathlib
    lines: list[str] = []
    for p in sorted(pathlib.Path(cfg.workspace).rglob("*.py")):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        sigs = [f"def {n.name}(...)" for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef)]
        classes = [f"class {n.name}" for n in ast.walk(tree)
                   if isinstance(n, ast.ClassDef)]
        if sigs or classes:
            lines.append(f"{p.relative_to(cfg.workspace)}:\n  "
                         + "\n  ".join(classes + sigs))
    return "\n".join(lines)[: max_tokens * 4]   # 粗略按字符折算 token
```

把它作为 `maybe_compress()` 的一级策略：**先给地图，细节让模型用 `read_file` 按需拉取**。

### 8.2 抄 SWE-agent：给 `read_file` 加护栏与即时校验

mini-harness 的 `read_file` 已经有 `offset/limit` 截断（对应 ACI 的"反馈简洁"）。再加一条**编辑护栏**：写文件前做语法校验，非法就**当场**把错误喂回去：

```python
# tools.py 的 write_file 增强思路（伪代码）
def write_file(path: str, content: str) -> str:
    p = reg._resolve(path)
    if path.endswith(".py"):
        import ast
        try:
            ast.parse(content)                 # 护栏：语法不过就拒绝写入
        except SyntaxError as e:
            return f"[拒绝写入] 语法错误：{e.msg}（第 {e.lineno} 行）。请修正后重试。"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"已写入 {path}（{len(content)} 字符）"
```

> 🔗 这正是 [9.5 验证循环](./05-验证循环.md) 的"编辑即验证"：把 lint 前移到写入之前。

### 8.3 抄 OpenHands：把沙箱做成可替换的 Runtime

mini-harness 目前直接在宿主机跑 `run_shell`。抄 OpenHands 的"决策/执行解耦"：把执行抽成 `Runtime` 接口，本地实现是默认，Docker 实现是可选项：

```python
# runtime.py（新文件，伪代码）
class Runtime:                     # 抽象：Agent 只认这个接口
    def execute(self, action: dict) -> str: ...

class LocalRuntime(Runtime):       # 默认：宿主机执行
    def execute(self, action): ...

class DockerRuntime(Runtime):      # 可选：容器内执行（参考 OpenHands 参数）
    def execute(self, action): ...  # mem_limit / cap_drop=ALL / 只挂 workspace
```

Agent 主循环只依赖 `Runtime` 接口——**换沙箱不用改 Agent**。

### 8.4 抄 smolagents：加一个"代码动作"工具

在 `tools.py` 里加一个 `run_python(code)` 工具，让模型**用一段代码**完成多步操作（而不是逐个调工具）。**注意**：它必须配合 [9.4 的权限层](./04-权限护栏与沙箱.md) 与沙箱执行，绝不能裸跑。

> ⚠️ **安全红线**：任何"任意代码执行"能力，都必须满足两个前提——**（1）默认拒绝**（不在白名单直接拦）、**（2）隔离执行**（容器/子进程 + 资源上限）。做不到就别开。

---

## 本章小结

| 要点 | 说明 |
|:-----|:-----|
| 📚 | 会**选** Harness 是入门，会**读** Harness 才是进阶——核心难点在那 98.4% 的工程 |
| 🐳 | **OpenHands**：事件驱动 + **Docker 沙箱默认开启** + 微代理；决策与执行解耦，Condenser 独立压缩 |
| 🎯 | **SWE-agent**：**ACI（界面设计）是一等变量**；动作粒度适中、反馈简洁、护栏内建、lint 即时 |
| 🗺️ | **Aider**：**repo map**——tree-sitter 抽符号 + 图排序按预算选上下文；先给地图再给细节 |
| 🧩 | **smolagents**：**动作即代码**（Code Agent）；可组合性强、步数少，但必须沙箱执行；极简约千行 |
| 🔗 | 四家殊途同归：都把**上下文、边界、反馈**当作一等公民，都不追求"一个万能 Agent" |
| 🛠️ | 四种模式都能装进 mini-harness：repo map、编辑护栏、可替换 Runtime、代码动作工具 |

---

## 📝 课后练习

1. **架构题（基础）**：画出 OpenHands 的分层图，标出"决策层"与"执行层"的分界，并说明这样解耦带来哪两个好处。
2. **设计题（进阶）**：假设你要给一个"自动改 bug"的 Agent 设计 ACI。参考 SWE-agent 的五条原则，写出 4–6 个命令（含参数与返回格式），并说明每个命令体现了哪条原则。
3. **对比题（进阶）**：同样是解决"上下文装不下"，Aider 的 repo map 与 [9.3](./03-上下文工程与压缩.md) 的摘要压缩分别适合什么场景？各举一个反例说明"用错会怎样"。
4. **动手题（挑战）**：完成第八节 8.1 的 repo map 扩展，让 mini-harness 在触发压缩时优先注入符号地图；用 `smoke_test.py` 验证不破坏原有 19 项自检，并记录压缩前后 token 变化。
5. **判断题（挑战）**：为什么 smolagents 的 Code Agent 必须沙箱执行，而 Aider 的 diff 编辑可以不那么严格？从"动作的能力边界"角度解释。

---

> 🔗 **下一步**：把本章的架构洞见，落到"清单与模板"上——对着 [9.13 Harness 实战清单与模板](./13-实战清单与模板.md) 逐项检查你的 Harness；想横向比较更多开源方案，回到 [9.9 开源 Harness 全景与选型](./09-开源Harness全景.md)。
