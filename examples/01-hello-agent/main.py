"""
第一个 Agent - Hello Agent

使用 LangChain 1.x 最新 API 创建简单的对话 Agent
"""

import os
from typing import List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage

# 加载环境变量
load_dotenv()


def create_agent(model: str | None = None):
    """创建 Agent。

    模型名与密钥统一从环境变量读取，便于在 OpenAI / DeepSeek / 通义之间切换：
      LLM_MODEL_NAME（默认 gpt-5.5）
      LLM_API_KEY / LLM_BASE_URL（缺省时回退到 OPENAI_API_KEY / OPENAI_API_BASE）
    """
    model = model or os.getenv("LLM_MODEL_NAME", "gpt-5.5")
    llm = ChatOpenAI(
        model=model,
        temperature=0.7,
        api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_API_BASE"),
    )
    return llm


def chat_with_agent(llm, user_message: str, history: List[BaseMessage] = None):
    """与 Agent 对话"""
    messages: List[BaseMessage] = [
        SystemMessage(content="你是一个有用的 AI 助手。"),
    ]
    
    if history:
        messages.extend(history)
    
    messages.append(HumanMessage(content=user_message))
    
    response = llm.invoke(messages)
    return response


def main():
    """主函数"""
    print("🤖 AgentLearn - 第一个 Agent")
    print("=" * 50)
    
    llm = create_agent()
    history: List[BaseMessage] = []
    
    while True:
        try:
            user_input = input("\n你: ").strip()
            
            if user_input.lower() in ["exit", "quit", "退出", "再见"]:
                print("👋 再见！")
                break
            
            if not user_input:
                continue
            
            response = chat_with_agent(llm, user_input, history)
            print(f"Agent: {response.content}")
            
            # 保存历史
            history.append(HumanMessage(content=user_input))
            history.append(response)
            
            # 限制历史长度
            if len(history) > 20:
                history = history[-20:]
        
        except KeyboardInterrupt:
            print("\n👋 再见！")
            break


if __name__ == "__main__":
    main()
