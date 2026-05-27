# 6.1 多 Agent 协作 —— 从单打独斗到团队作战

## 📖 导读

> **一个 Agent 是聪明的，一群分工明确的 Agent 可以是智能的。**

前面我们构建的都是单个 Agent。但现实中的复杂任务往往需要**多个专业角色协作**——一个搜索资料、一个分析数据、一个撰写报告、一个审查质量。多 Agent 系统正是将这种"团队协作"模式引入 AI 系统，让每个 Agent 专注自己最擅长的领域。

---

## 一、前置知识

| 概念 | 章节 | 说明 |
|------|------|------|
| Agent 架构 | 2.3 | Agent 的思考-行动循环 |
| LangGraph | 4.1-4.5 | 图工作流编排 |
| 工具调用 | 3.2 | Agent 使用外部工具 |

---

## 二、为什么需要多 Agent？

### 2.1 单 Agent 的局限

```text
单 Agent 的问题：

🧠 一个大脑做所有事：
1. 知识广度有限（一个 LLM 不可能精通所有领域）
2. 容易产生偏见（没有交叉验证）
3. 上下文窗口限制（一个 Agent 无法处理超长上下文）
4. 故障单点（一个 Agent 出错，整个任务失败）

多 Agent 的优势：

👥 专业分工：
🧑‍💻 研究 Agent → 搜索和分析资料
✍️ 写作 Agent → 撰写内容
🔍 审查 Agent → 质量检查
🎯 协调 Agent → 统筹和决策
```

### 2.2 核心价值

| 优势 | 说明 |
|------|------|
| **分工协作** | 每个 Agent 专注自己擅长的领域 |
| **互相验证** | 一个 Agent 的输出由另一个 Agent 检查 |
| **专业化** | 每个 Agent 可以有专属的 system prompt 和工具集 |
| **可扩展** | 可以随时加入新的 Agent 角色 |

---

## 三、多 Agent 协作模式

### 3.1 层级式（Manager-Worker）

```text
┌──────────────────────────────────┐
│         Manager Agent            │
│   (理解任务，分配工作，合并结果)    │
└──────┬──────┬──────┬────────────┘
       │      │      │
       ▼      ▼      ▼
   ┌─────┐┌─────┐┌─────┐
   │Worker││Worker││Worker│
   │  A   ││  B   ││  C   │
   └─────┘└─────┘└─────┘
```

**适用场景**：CEO 带团队的模式，Manager 分配任务，Worker 执行，Manager 汇总。

### 3.2 流水线式（Pipeline）

```text
输入 → [搜索 Agent] → [分析 Agent] → [写作 Agent] → [审查 Agent] → 输出
```

**适用场景**：每个环节的输出是下一个环节的输入，像生产线一样。

### 3.3 辩论式（Debate）

```text
Agent A: "我认为这个方案是 A"
Agent B: "我不同意，方案 B 更好，因为..."
Agent C: "从实际经验看，方案 A 更可行，因为..."

最终：汇总各方观点 → 综合决策
```

**适用场景**：需要多方讨论、交叉验证的决策场景。

### 3.4 市场式（Marketplace）

```text
任务发布到"任务市场" → 多个 Agent 竞标 → 
协调 Agent 选择最佳提案 → 执行和奖励
```

**适用场景**：开放性任务，多个 Agent 提供不同方案。

---

## 四、实战：多 Agent 内容创作系统

### 4.1 架构设计

```text
用户输入：写一篇关于"AI Agent 趋势"的文章

┌──────────────────────────────────────────────────────────┐
│                     Supervisor Agent                       │
│  (接收用户需求 → 制定计划 → 协调工作 → 汇总输出)          │
└────────┬──────────┬──────────┬──────────┬────────────────┘
         │          │          │          │
         ▼          ▼          ▼          ▼
   ┌─────────┐┌─────────┐┌─────────┐┌─────────┐
   │ Research ││ Writing ││ Review  ││ Format  │
   │ Agent    ││ Agent   ││ Agent   ││ Agent   │
   │ 搜索资料  ││ 撰写内容  ││ 质量检查  ││ 格式化   │
   └─────────┘└─────────┘└─────────┘└─────────┘
```

### 4.2 完整实现

```python
"""
多 Agent 内容创作系统
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from typing import Dict, List


class Agent:
    """基础 Agent 类"""
    
    def __init__(self, name: str, system_prompt: str, model: str = "gpt-4o"):
        self.name = name
        self.system_prompt = system_prompt
        self.llm = ChatOpenAI(model=model, temperature=0.7)
    
    def run(self, task: str, context: str = "") -> str:
        """执行任务"""
        messages = [
            SystemMessage(content=self.system_prompt),
        ]
        if context:
            messages.append(HumanMessage(content=f"当前上下文：\n{context}"))
        messages.append(HumanMessage(content=f"任务：{task}"))
        
        response = self.llm.invoke(messages)
        return response.content


class ResearchAgent(Agent):
    """研究 Agent：搜索和分析"""
    
    def __init__(self):
        super().__init__(
            name="研究员",
            system_prompt="""你是一个专业的研究员。你的任务是：
1. 对给定的主题进行深入研究
2. 从多个角度分析
3. 提供结构化的研究结果

输出格式：
## 研究摘要
[核心发现]

## 关键数据
- 数据点1
- 数据点2

## 主要观点
1. ...
2. ...
"""
        )


class WritingAgent(Agent):
    """写作 Agent：撰写内容"""
    
    def __init__(self):
        super().__init__(
            name="写手",
            system_prompt="""你是一个专业的写作者。你的任务是：
1. 基于研究资料撰写高质量内容
2. 结构清晰，逻辑连贯
3. 语言通俗易懂，适当使用例子

输出时用 Markdown 格式。
"""
        )


class ReviewAgent(Agent):
    """审查 Agent：质量检查"""
    
    def __init__(self):
        super().__init__(
            name="审查员",
            system_prompt="""你是一个严格的内容审查员。你的任务是：
1. 检查内容准确性和逻辑性
2. 指出需要改进的地方
3. 给出 1-10 的质量评分
4. 提供具体的修改建议

输出格式：
## 质量评分：[X]/10

## 优点
...

## 需要改进
...

## 修改建议
...
""",
            model="gpt-4o",
        )


class SupervisorAgent:
    """主管 Agent：协调整个工作流"""
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
        self.research_agent = ResearchAgent()
        self.writing_agent = WritingAgent()
        self.review_agent = ReviewAgent()
    
    def run(self, topic: str) -> Dict:
        """执行完整的多 Agent 创作流程"""
        print(f"\n🚀 开始多 Agent 协作创作")
        print(f"📝 主题: {topic}")
        print("=" * 50)
        
        # 步骤 1: 研究
        print(f"\n🔍 [研究员] 正在研究...")
        research_result = self.research_agent.run(
            f"全面研究以下主题：{topic}\n\n"
            f"请从以下角度进行分析：\n"
            f"1. 核心概念\n2. 现状和趋势\n3. 主要参与者\n4. 挑战和机遇"
        )
        print(f"   ✅ 研究完成")
        
        # 步骤 2: 写作
        print(f"\n✍️  [写手] 正在创作...")
        draft = self.writing_agent.run(
            f"基于以下研究成果，撰写一篇关于'{topic}'的完整文章：",
            context=research_result,
        )
        print(f"   ✅ 初稿完成 ({len(draft)} 字)")
        
        # 步骤 3: 审查
        print(f"\n📋 [审查员] 正在检查...")
        review_result = self.review_agent.run(
            f"请严格审查以下文章：\n\n{draft}",
        )
        print(f"   ✅ 审查完成")
        
        # 步骤 4: 主管总结
        print(f"\n🎯 [主管] 正在汇总...")
        summary = self.llm.invoke([
            SystemMessage(content="你是一个项目主管，请总结整个创作流程的完成情况。"),
            HumanMessage(content=f"""
项目主题：{topic}

研究结果摘要：
{research_result[:500]}...

文章预览：
{draft[:500]}...

审查意见：
{review_result[:500]}...

请给出最终的项目总结报告。
"""),
        ])
        
        return {
            "topic": topic,
            "research": research_result,
            "draft": draft,
            "review": review_result,
            "summary": summary.content,
        }


# 使用
if __name__ == "__main__":
    supervisor = SupervisorAgent()
    result = supervisor.run("2024-2025 AI Agent 发展趋势")
    
    print("\n" + "=" * 60)
    print("🎉 多 Agent 协作完成")
    print("=" * 60)
    print(result["draft"])
```

---

## 五、Agent 间通信机制

### 5.1 三种通信方式

| 方式 | 说明 | 适用场景 |
|------|------|----------|
| **消息传递** | Agent 互相发送消息 | 流水线式协作 |
| **共享黑板** | 所有 Agent 读写共享状态 | 团队协作讨论 |
| **主管调度** | 主管 Agent 分派任务、收集结果 | 层级式协作 |

### 5.2 共享黑板模式实现

```python
class Blackboard:
    """共享黑板：多 Agent 共享状态"""
    
    def __init__(self):
        self.data = {}
        self.history = []
    
    def write(self, agent_name: str, key: str, value: any):
        """写入黑板"""
        self.data[key] = value
        self.history.append({
            "agent": agent_name,
            "action": "write",
            "key": key,
            "timestamp": "..." 
        })
    
    def read(self, key: str) -> any:
        """读取黑板"""
        return self.data.get(key)
    
    def get_all(self) -> dict:
        return self.data
```

---

## 六、适用场景

| 场景 | 协作模式 | 说明 |
|------|----------|------|
| **内容创作** | 研究→写作→审查 | 每个阶段专用 Agent |
| **数据分析** | 数据收集→清洗→分析→报告 | 流水线模式 |
| **客服系统** | 意图识别→FAQ→复杂问题升级 | 层级式 |
| **代码开发** | 需求分析→编码→测试→审查 | 流水线 |
| **决策支持** | 多方观点收集→辩论→综合 | 辩论式 |

---

## 七、本章总结

| 知识点 | 一句话说明 |
|--------|------------|
| **多 Agent** | 多个 Agent 分工协作完成复杂任务 |
| **层级式** | Manager 分配任务，Worker 执行 |
| **流水线** | 前一个 Agent 的输出是后一个的输入 |
| **辩论式** | 多个 Agent 提供不同观点后综合决策 |
| **主管模式** | 最实用，用 Supervisor 协调各个 Specialist |

---

## 📝 课后练习

1. **✅ 基础**：运行上面多 Agent 创作系统，输入不同主题观察输出质量
2. **💡 改进**：给研究 Agent 添加 `search_web` 工具，让它能搜索真实信息
3. **🚀 挑战**：实现一个"辩论模式"，让 3 个 Agent 从不同角度讨论同一问题
4. **🔍 探索**：使用 LangGraph 实现基于子图的多 Agent 工作流，参考第 4 章的内容
