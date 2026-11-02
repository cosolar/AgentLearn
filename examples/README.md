# 📦 示例代码索引

> 教程里每段能跑的代码，在这里都有一份**完整、可运行**的版本。
> 建议边读章节边跑对应示例——**先跑通，再改动，最后拆开看**。

## 一、按学习顺序排列

| 目录 | 对应章节 | 你能学到 | 运行方式 | 需要 API Key |
|:-----|:---------|:---------|:---------|:------------:|
| [`01-hello-agent`](./01-hello-agent/) | [1.3 第一个 Agent](../docs/01-入门基础/03-第一个Agent.md) | `create_agent` 最小闭环、消息模型 | `python examples/01-hello-agent/main.py` | ✅ |
| [`02-tool-use`](./02-tool-use/) | [2.3 Agent 核心架构](../docs/02-核心概念/03-Agent核心架构.md)、[3.2 模型调用与工具](../docs/03-LangChain实战/02-模型调用与工具.md) | `@tool` 定义、工具选择、参数校验 | `python examples/02-tool-use/main.py` | ✅ |
| [`03-chat-agent`](./03-chat-agent/) | [3.4 构建聊天 Agent](../docs/03-LangChain实战/04-构建聊天Agent.md) | `checkpointer` 多轮记忆、流式输出 | `python examples/03-chat-agent/main.py` | ✅ |
| [`04-research-agent`](./04-research-agent/) | [3.5 实战：研究助手](../docs/03-LangChain实战/05-实战研究助手.md) | 多工具协作、结构化报告生成 | `python examples/04-research-agent/main.py` | ✅ |
| [`05-streamlit-chat`](./05-streamlit-chat/) | [3.4 构建聊天 Agent](../docs/03-LangChain实战/04-构建聊天Agent.md) | 把 Agent 包成可视化聊天界面 | `streamlit run examples/05-streamlit-chat/main.py` | ✅ |
| [`05-rag-kb`](./05-rag-kb/) | [第五部分：RAG 系统](../docs/05-RAG系统/) | 切分 → 混合检索 → 父块回溯 → Agentic RAG / GraphRAG | `cd examples/05-rag-kb && python smoke_test.py` | ❌ 离线 |
| [`06-multi-agent`](./06-multi-agent/) | [6.1 多 Agent 协作](../docs/06-高级主题/01-多Agent协作.md) | Supervisor 分工、Agent 间交接 | `python examples/06-multi-agent/main.py` | ✅ |
| [`07-api-service`](./07-api-service/) | [7.1 API 服务部署](../docs/07-生产部署/01-API服务部署.md) | FastAPI + SSE 流式 + 鉴权 + 限流 + 错误契约 | `cd examples/07-api-service && python smoke_test.py` | ❌ 离线 |
| [`09-mini-harness`](./09-mini-harness/) | [9.8 构建最小可行 Harness](../docs/09-驾驭工程/08-构建最小可行Harness.md) | 约 700 行纯标准库 Harness：编排循环 / 权限 / 压缩 / 验证门 | `cd examples/09-mini-harness && python smoke_test.py` | ❌ 离线 |

> 💡 **没有 API Key 也能开始**：带「❌ 离线」的三个示例用脚本化假模型（`FakeLLM`）跑完整链路，自检分别是 **18 / 16 / 19 项**，全部无需联网、无需密钥。建议第一次接触本仓库就先跑它们。

## 二、三个离线自检示例（零门槛）

```bash
# 1) RAG 全链路：切分 → 混合检索 → 父块回溯 → 问答（18 项断言）
cd examples/05-rag-kb && python smoke_test.py

# 2) Agent API 服务：鉴权 / 限流 / SSE / 错误契约（16 项断言）
cd examples/07-api-service && python smoke_test.py

# 3) 最小可行 Harness：十二大模块的核心七件事（19 项断言）
cd examples/09-mini-harness && python smoke_test.py
```

三个脚本都只依赖**标准库**（`07-api-service` 的离线自检不要求装 fastapi），跑完会打印逐项 ✅/❌。

## 三、怎么用这些示例

| 阶段 | 做法 | 目的 |
|:-----|:-----|:-----|
| **① 先跑** | 不改任何代码，直接运行，看输出长什么样 | 建立"它应该是什么样"的预期 |
| **② 再改** | 改提示词、换工具、调参数，看行为怎么变 | 找到"哪一行决定哪个行为" |
| **③ 再拆** | 把 `main.py` 按职责拆成 `tools.py` / `agent.py` | 理解工程结构（章节里反复强调的做法） |
| **④ 再断** | 删掉某一段，看它报什么错 | 确认自己真的理解这段为什么存在 |

## 四、环境准备

```bash
# 仓库根目录
uv sync                     # 安装依赖（自动创建 .venv）
cp .env.example .env        # 填入 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL_NAME
```

> 环境细节与排错见 [1.2 开发环境搭建](../docs/01-入门基础/02-开发环境搭建.md)，
> 报错对照见 [附录 C：故障排查手册](../docs/附录/03-故障排查手册.md)。
