"""
工具调用示例 - Tool Use

使用 LangChain 1.x 最新 Tool Calling API
"""

import os
from typing import List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_core.tools import BaseTool

# 加载环境变量
load_dotenv()


# 定义工具
@tool
def search_web(query: str) -> str:
    """搜索互联网信息"""
    return f"搜索结果（模拟）：关于 '{query}' 的相关信息..."


@tool
def calculate(expression: str) -> str:
    """执行数学计算"""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return f"计算结果: {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"


@tool
def get_weather(city: str) -> str:
    """获取城市天气"""
    weather_data = {
        "北京": "晴，25°C",
        "上海": "多云，22°C",
        "广州": "小雨，28°C",
    }
    return f"{city}的天气：{weather_data.get(city, '未知')}"


def create_agent_with_tools():
    """创建带工具的 Agent"""
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    # 获取所有工具
    tools: List[BaseTool] = [search_web, calculate, get_weather]
    
    # 绑定工具到 LLM (LangChain 1.x API)
    llm_with_tools = llm.bind_tools(tools)
    
    return llm_with_tools, tools


def run_agent(llm, tools: List[BaseTool], user_message: str):
    """运行 Agent"""
    messages = [
        SystemMessage(content="你是一个有用的 AI 助手，可以使用工具来回答问题。"),
        HumanMessage(content=user_message),
    ]
    
    response = llm.invoke(messages)
    
    # 检查是否有工具调用 (LangChain 1.x API)
    if hasattr(response, 'tool_calls') and response.tool_calls:
        print("🔧 调用工具:")
        for tc in response.tool_calls:
            print(f"   工具: {tc['name']}")
            print(f"   参数: {tc['args']}")
    
    return response


def main():
    """主函数"""
    print("🤖 AgentLearn - 工具调用示例")
    print("=" * 50)
    
    llm, tools = create_agent_with_tools()
    
    # 测试工具调用
    test_messages = [
        "1234 * 5678 等于多少？",
        "北京今天天气怎么样？",
        "帮我搜索一下人工智能的发展历史",
    ]
    
    for msg in test_messages:
        print(f"\n你: {msg}")
        response = run_agent(llm, tools, msg)
        print(f"Agent: {response.content}")


if __name__ == "__main__":
    main()
