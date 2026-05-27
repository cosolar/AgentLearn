# 3.5 实战：研究助手 Agent —— 从需求到实现的完整项目

## 📖 导读

前面我们学习了 LangChain 的各种组件——Chain、工具、向量存储、Agent。现在是时候**综合运用所有知识，构建一个真正实用的 Agent 应用**。

本节将带领你完成一个**研究助手 Agent**：它能接收一个研究主题，自动搜索资料、整理分析、生成结构化报告。这个项目涵盖了 Agent 开发的完整流程，是后续构建复杂应用的基础。

---

## 一、项目需求

### 1.1 核心功能

创建一个研究助手，能够：
1. **搜索**互联网信息（获取原始资料）
2. **整理**和分析信息（提取关键点）
3. **生成**结构化研究报告（Markdown 格式）

### 1.2 用户视角

```text
用户输入：帮我研究一下 AI Agent 的发展趋势

Agent 输出：
# AI Agent 发展趋势研究报告

## 1. 核心发现
...

## 2. 关键数据
...

## 3. 技术分析
...

## 4. 结论与展望
...
```

---

## 二、项目结构

```
examples/04-research-agent/
├── main.py              # 入口文件
├── agents.py            # Agent 定义
├── tools.py             # 自定义工具
├── utils.py             # 工具函数
├── config.py            # 配置管理
└── README.md            # 说明文档
```

---

## 三、逐步实现

### 3.1 配置管理（config.py）

```python
"""项目配置"""
import os
from dotenv import load_dotenv

load_dotenv()

# LLM 配置
LLM_CONFIG = {
    "model": os.getenv("LLM_MODEL_NAME", "gpt-4o"),
    "temperature": 0.3,  # 研究需要准确性，所以温度较低
    "api_key": os.getenv("LLM_API_KEY"),
    "base_url": os.getenv("LLM_BASE_URL"),
}

# 搜索配置
SEARCH_CONFIG = {
    "max_results": 5,
    "cache_enabled": True,
}

# 报告配置
REPORT_CONFIG = {
    "max_sections": 5,
    "language": "zh-CN",
    "include_sources": True,
}
```

### 3.2 工具定义（tools.py）

```python
"""研究助手使用的工具"""
import json
from typing import Optional
from datetime import datetime

from langchain_core.tools import tool


@tool
def search_web(query: str) -> str:
    """
    搜索互联网获取最新信息。
    当需要查找特定主题的最新资料、新闻、论文或技术文档时使用此工具。
    
    Args:
        query: 搜索关键词，应该简洁明确
        
    Returns:
        搜索结果的摘要文本
    """
    # 提示：实际项目中应接入真实搜索 API（如 SerpAPI、Bing Search）
    # 这里用模拟数据展示结构
    
    mock_results = {
        "AI Agent": """
        1. AI Agent 市场预计到 2028 年将达到 420 亿美元（来源：MarketsAndMarkets）
        2. 多 Agent 协作系统成为企业应用新趋势
        3. 从单工具到工具集成的演进加速
        4. 记忆系统和持续学习成为研究热点
        """,
        "LangGraph": """
        1. LangGraph 提供基于图的工作流编排
        2. 支持条件路由和循环，适合复杂业务流程
        3. 与 LangChain 生态深度集成
        4. 2024 年 1 月发布稳定版本
        """,
        "RAG 最佳实践": """
        1. 文档分块大小 500-1000 tokens 效果最佳
        2. 混合检索（关键词+向量）比纯向量搜索提升 15-20%
        3. 重排序（Re-ranking）是提升准确率的关键步骤
        4. HyDE 技术可显著改善检索相关性
        """,
    }
    
    for key, result in mock_results.items():
        if any(kw in query for kw in key.split()):
            return result
    
    return f"关于'{query}'的搜索结果：\n1. 相关工作已找到\n2. 正在进行综合分析"


@tool
def save_report(content: str, filename: Optional[str] = None) -> str:
    """
    将研究报告保存到文件。
    在生成最终报告后调用此工具保存结果。
    
    Args:
        content: 报告内容（Markdown 格式）
        filename: 文件名（可选，默认自动生成）
        
    Returns:
        保存结果信息
    """
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"research_report_{timestamp}.md"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    
    return f"✅ 报告已保存到 {filename}"
```

### 3.3 Agent 定义（agents.py）

```python
"""研究助手 Agent 定义"""
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

from config import LLM_CONFIG, REPORT_CONFIG
from tools import search_web, save_report


class ResearchAgent:
    """研究助手 Agent"""
    
    def __init__(self, verbose: bool = True):
        self.llm = ChatOpenAI(
            model=LLM_CONFIG["model"],
            temperature=LLM_CONFIG["temperature"],
        )
        self.tools = [search_web, save_report]
        self.verbose = verbose
        self.agent = self._create_agent()
    
    def _create_agent(self) -> AgentExecutor:
        """创建研究 Agent"""
        
        system_prompt = f"""你是一个专业的研究助手 AI。你的任务是：

## 能力
1. 搜索互联网获取最新信息
2. 综合分析多个来源
3. 生成结构化研究报告

## 研究流程
1. 理解用户的研究主题
2. 分解为子问题，逐个搜索
3. 综合分析所有信息
4. 生成结构化报告

## 报告格式（{REPORT_CONFIG['language']}）
- 使用 Markdown 格式
- 包含：摘要、背景、发现、分析、结论
- 引用信息来源
- 标注不确定的推断

## 输出规范
- 用中文撰写报告
- 结构清晰，使用 ### 次级标题
- 数据点用列表呈现"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=self.verbose,
            max_iterations=8,       # 研究需要多步搜索
            handle_parsing_errors=True,
            return_intermediate_steps=True,
        )
    
    def research(self, topic: str) -> dict:
        """
        执行研究任务
        
        Args:
            topic: 研究主题
            
        Returns:
            {"output": "报告内容", "steps": ["中间步骤"]}
        """
        print(f"\n🔬 开始研究：{topic}")
        print("=" * 50)
        
        result = self.agent.invoke({"input": f"请研究以下主题并生成报告：\n\n{topic}"})
        
        return {
            "output": result["output"],
            "steps": result.get("intermediate_steps", []),
        }
```

### 3.4 工具函数（utils.py）

```python
"""工具函数"""

def print_report(report: str):
    """美化打印报告"""
    print("\n" + "=" * 60)
    print("📊 研究报告")
    print("=" * 60)
    print(report)
    print("=" * 60)


def estimate_research_cost(steps: list) -> dict:
    """估算研究的 token 消耗和成本"""
    total_llm_calls = len([s for s in steps if "llm" in str(s).lower()])
    total_tool_calls = len([s for s in steps if "tool" in str(s).lower()])
    
    return {
        "llm_calls": total_llm_calls,
        "tool_calls": total_tool_calls,
        "estimated_tokens": total_llm_calls * 500 + total_tool_calls * 200,
        "estimated_cost_usd": (total_llm_calls * 500 + total_tool_calls * 200) * 0.00001,
    }
```

### 3.5 主入口（main.py）

```python
"""研究助手 - 主入口"""

from agents import ResearchAgent
from utils import print_report, estimate_research_cost


def main():
    """主函数"""
    print("🤖 AI 研究助手")
    print("=" * 50)
    print("输入研究主题，我将为你生成结构化报告")
    print("输入 'exit' 退出\n")
    
    agent = ResearchAgent(verbose=True)
    
    while True:
        topic = input("📝 研究主题: ").strip()
        
        if topic.lower() == "exit":
            print("👋 再见！")
            break
        
        if not topic:
            continue
        
        # 执行研究
        result = agent.research(topic)
        
        # 打印报告
        print_report(result["output"])
        
        # 成本估算
        cost = estimate_research_cost(result["steps"])
        print(f"\n📊 本次研究统计：")
        print(f"   - LLM 调用: {cost['llm_calls']} 次")
        print(f"   - 工具调用: {cost['tool_calls']} 次")
        print(f"   - 预估 Token: {cost['estimated_tokens']}")
        print()


if __name__ == "__main__":
    main()
```

---

## 四、运行与测试

```bash
# 确保在项目根目录且虚拟环境已激活
cd AgentLearn
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 运行研究助手
python examples/04-research-agent/main.py
```

**运行示例**：

```text
🤖 AI 研究助手
==================================================
输入研究主题，我将为你生成结构化报告
输入 'exit' 退出

📝 研究主题: 2024年AI Agent发展趋势

🔬 开始研究：2024年AI Agent发展趋势
==================================================


> Entering new AgentExecutor chain...

Invoking: `search_web` with `{'query': '2024 AI Agent trends'}`
...

Invoking: `search_web` with `{'query': '多Agent协作 2024'}`
...

📊 研究报告
==================================================
# 2024 年 AI Agent 发展趋势研究报告

## 摘要
...

==================================================

📊 本次研究统计：
   - LLM 调用: 3 次
   - 工具调用: 2 次
```

---

## 五、进阶优化

### 5.1 添加向量记忆

让 Agent 能从之前的研究中"学习"：

```python
from langchain.memory import VectorStoreRetrieverMemory
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

class ResearchAgentWithMemory(ResearchAgent):
    """带记忆的研究助手"""
    
    def __init__(self, verbose=True):
        super().__init__(verbose)
        self.memory = self._setup_memory()
    
    def _setup_memory(self):
        embeddings = OpenAIEmbeddings()
        vectorstore = Chroma(
            embedding_function=embeddings,
            persist_directory="./research_memory",
        )
        return VectorStoreRetrieverMemory(
            retriever=vectorstore.as_retriever(),
            memory_key="research_history",
        )
    
    def research(self, topic: str) -> dict:
        # 先查询历史研究中是否已有相关信息
        relevant_history = self.memory.load_memory_variables({})
        
        # 结合历史信息进行研究
        result = super().research(topic)
        
        # 保存本次研究结果
        self.memory.save_context(
            {"input": topic},
            {"output": result["output"]},
        )
        
        return result
```

### 5.2 添加报告质量检查

```python
class ResearchQualityChecker:
    """报告质量检查器"""
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    def check_report(self, report: str, topic: str) -> dict:
        """检查报告质量"""
        prompt = f"""
        检查以下关于"{topic}"的研究报告的质量：
        
        报告内容：
        {report}
        
        请在以下维度打分（1-10）并给出改进建议：
        1. 完整性：是否覆盖了主题的主要方面
        2. 准确性：信息是否准确可信
        3. 结构性：报告结构是否清晰
        4. 可读性：语言是否流畅易懂
        5. 实用性：是否包含可操作的建议
        """
        
        result = self.llm.invoke([HumanMessage(content=prompt)])
        return result.content
```

---

## 六、扩展思路

| 扩展方向 | 实现方式 | 效果 |
|----------|----------|------|
| **接入真实搜索** | 集成 SerpAPI、Bing Search 等 | 获取真实互联网数据 |
| **多语言支持** | 增加语言参数控制 | 支持全球用户 |
| **图文报告** | 添加图片搜索和排版 | 更丰富的报告格式 |
| **协作研究** | 多 Agent 分工（搜索→分析→写作） | 更深入、更专业的报告 |
| **定期调研** | 添加定时任务自动跟踪主题 | 持续性研究 |

---

## 七、本章总结

| 要点 | 说明 |
|------|------|
| **模块化设计** | config / tools / agents / utils 分离 |
| **工具设计** | search_web 获取信息，save_report 持久化结果 |
| **Agent 思维** | 研究→分析→生成 的多步骤流程 |
| **记忆扩展** | VectorStoreRetrieverMemory 实现跨研究记忆 |
| **质量保障** | 报告检查器确保输出质量 |

---

## 📝 课后练习

1. **✅ 基础**：运行研究助手，输入一个你感兴趣的技术主题，观察 Agent 的思考过程
2. **💡 改进**：将 search_web 工具替换为真实的搜索 API（如 DuckDuckGo 或 Bing Search）
3. **🚀 扩展**：添加一个 "专家评审" 步骤——用第二个 LLM 审查报告质量
4. **🔍 探索**：用 VectorStoreRetrieverMemory 实现跨会话记忆，让 Agent 在多次研究中积累知识
