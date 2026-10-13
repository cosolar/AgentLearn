"""
研究助手 Agent - Research Agent

使用 LangChain v1 的 create_agent 构建一个能搜索资料并生成研究报告的 Agent。
"""

import os
from datetime import datetime

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.tools import tool

# 加载环境变量
load_dotenv()


# ===== 工具定义 =====

@tool
def search_web(query: str) -> str:
    """搜索互联网，获取与查询相关的最新资料。"""
    # 提示：实际项目应接入真实搜索 API（如 Tavily / Bing / SerpAPI）
    mock_results = {
        "AI Agent": (
            "1. AI Agent 市场规模持续高速增长\n"
            "2. 多 Agent 协作成为企业应用新趋势\n"
            "3. MCP 成为工具调用事实标准"
        ),
        "LangGraph": (
            "1. 基于图的工作流编排运行时\n"
            "2. 支持条件路由、循环、持久化与人机协同\n"
            "3. 与 LangChain v1 深度集成"
        ),
    }
    for key, result in mock_results.items():
        if key.lower() in query.lower():
            return result
    return f"关于'{query}'的搜索结果：\n1. 已找到相关工作\n2. 正在综合分析"


@tool
def save_report(content: str, filename: str = "") -> str:
    """把研究报告保存为 Markdown 文件，返回保存结果。"""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"research_report_{timestamp}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    return f"✅ 报告已保存到 {filename}"


# ===== Agent 构建 =====

SYSTEM_PROMPT = """你是一个专业的研究助手。工作流程：
1. 理解研究主题，必要时拆解为子问题
2. 用 search_web 搜索资料
3. 综合分析后生成结构化 Markdown 报告（摘要/背景/发现/结论）
4. 用 save_report 保存最终报告
用中文撰写，结构清晰，标注信息来源。"""


def create_research_agent():
    """创建研究助手 Agent（LangChain v1）"""
    # 从环境变量读取 LLM 配置，便于跨厂商切换
    model = ChatOpenAI(
        model=os.getenv("LLM_MODEL_NAME", "gpt-5.5"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        temperature=0.3,  # 研究需要准确性，温度调低
    )
    # create_agent 内置"模型 → 工具 → 回传模型"的完整循环
    return create_agent(
        model=model,
        tools=[search_web, save_report],
        system_prompt=SYSTEM_PROMPT,
    )


def main():
    """主函数"""
    print("🤖 AgentLearn - 研究助手")
    print("=" * 50)
    print("输入研究主题，我将为你生成研究报告（输入 exit 退出）\n")

    agent = create_research_agent()

    while True:
        try:
            topic = input("研究主题：").strip()

            if topic.lower() in ["exit", "quit", "q", "退出"]:
                print("👋 再见！")
                break

            if not topic:
                continue

            print("\n🔍 正在研究...\n")
            result = agent.invoke(
                {"messages": [{"role": "user", "content": f"请研究以下主题并生成报告：\n\n{topic}"}]}
            )
            print("=" * 50)
            print(result["messages"][-1].content)
            print("=" * 50)
            print()

        except KeyboardInterrupt:
            print("\n👋 再见！")
            break


if __name__ == "__main__":
    main()
