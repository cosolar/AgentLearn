"""
研究助手 Agent - Research Agent

使用 LangChain 1.x 最新 API 构建研究助手
"""

import os
from typing import List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_tool_calling_agent, AgentExecutor

load_dotenv()


# 定义工具
@tool
def search_information(query: str) -> str:
    """搜索互联网信息"""
    return f"搜索结果（模拟）：关于 '{query}' 的相关信息..."


@tool
def summarize_text(text: str) -> str:
    """总结文本内容"""
    llm = ChatOpenAI(model="gpt-4o")
    prompt = f"请总结以下内容（不超过 200 字）：\n\n{text}"
    response = llm.invoke(prompt)
    return response.content


def create_research_agent():
    """创建研究助手 Agent"""
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    tools = [search_information, summarize_text]
    
    # 使用最新 Prompt 格式 (LangChain 1.x)
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一位专业的研究助手。
你的任务是：
1. 搜索相关信息
2. 整理和分析信息
3. 生成结构化的研究报告

请确保信息准确、全面、有条理。"""),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)


def main():
    """主函数"""
    print("🤖 AgentLearn - 研究助手")
    print("=" * 50)
    print("输入研究主题，我将为您生成报告（输入 q 退出）\n")
    
    agent = create_research_agent()
    
    while True:
        try:
            topic = input("研究主题：").strip()
            
            if topic.lower() in ["q", "quit", "exit", "退出"]:
                print("👋 再见！")
                break
            
            if not topic:
                continue
            
            print("\n🔍 正在研究...\n")
            result = agent.invoke({"input": topic, "chat_history": []})
            print("=" * 50)
            print(result["output"])
            print("=" * 50)
            print()
        
        except KeyboardInterrupt:
            print("\n👋 再见！")
            break


if __name__ == "__main__":
    main()
