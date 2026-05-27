"""
聊天 Agent 示例 - Chat Agent

带对话记忆的聊天 Agent (LangChain 1.x)
"""

import os
from typing import List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage

load_dotenv()


class ChatAgent:
    """带记忆的聊天 Agent"""
    
    def __init__(self, model: str = "gpt-4o"):
        self.llm = ChatOpenAI(model=model, temperature=0.7)
        self.history: List[BaseMessage] = []
    
    def chat(self, message: str) -> str:
        """聊天"""
        # 构建消息
        messages: List[BaseMessage] = [
            SystemMessage(content="你是一个友好、有帮助的 AI 助手。"),
        ] + self.history + [HumanMessage(content=message)]
        
        # 获取响应
        response = self.llm.invoke(messages)
        
        # 保存历史
        self.history.append(HumanMessage(content=message))
        self.history.append(AIMessage(content=response.content))
        
        # 限制历史长度
        if len(self.history) > 20:
            self.history = self.history[-20:]
        
        return response.content
    
    def clear_history(self):
        """清除历史"""
        self.history = []
    
    def get_history(self) -> List[BaseMessage]:
        """获取历史"""
        return self.history.copy()


def main():
    """主函数"""
    print("🤖 AgentLearn - 聊天 Agent")
    print("=" * 50)
    print("输入 'clear' 清除历史，'exit' 退出\n")
    
    agent = ChatAgent()
    
    while True:
        try:
            user_input = input("你: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["exit", "quit", "退出", "再见"]:
                print("👋 再见！")
                break
            
            if user_input.lower() == "clear":
                agent.clear_history()
                print("✅ 历史已清除\n")
                continue
            
            print("Agent: ", end="", flush=True)
            response = agent.chat(user_input)
            print(response)
            print()
        
        except KeyboardInterrupt:
            print("\n👋 再见！")
            break


if __name__ == "__main__":
    main()
