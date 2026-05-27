"""
多 Agent 协作示例 - Multi-Agent Team

使用 LangChain 1.x 最新 API 实现多 Agent 协作
"""

import os
from typing import List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()


class TeamMember:
    """团队成员 Agent"""
    
    def __init__(self, role: str, expertise: str):
        self.role = role
        self.expertise = expertise
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.5)
    
    def work(self, task: str, context: str = "") -> str:
        """执行任务"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""你是一位{self.role}，专长是{self.expertise}。
你的任务是完成分配的工作。

上下文：{context}"""),
            ("human", "{task}"),
        ])
        
        chain = prompt | self.llm
        response = chain.invoke({"task": task})
        return response.content


class TeamManager:
    """团队管理者"""
    
    def __init__(self):
        self.members = [
            TeamMember("研究员", "信息收集和分析"),
            TeamMember("作家", "内容创作和编辑"),
            TeamMember("审查员", "质量检查和改进"),
        ]
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
    
    def run(self, task: str):
        """运行团队"""
        print(f"\n📋 任务：{task}\n")
        
        # 第一步：研究
        print("🔍 研究员正在收集信息...")
        research_result = self.members[0].work(
            f"研究以下主题：{task}",
            "为后续写作提供素材"
        )
        print(f"   ✅ 完成：收集了相关信息\n")
        
        # 第二步：写作
        print("✍️ 作家正在撰写内容...")
        draft = self.members[1].work(
            f"基于以下研究结果撰写内容：\n{research_result}",
            "创建一篇结构完整的内容"
        )
        print(f"   ✅ 完成：草稿已生成\n")
        
        # 第三步：审查
        print("🔍 审查员正在检查质量...")
        final = self.members[2].work(
            f"审查以下内容并提出改进建议：\n{draft}",
            "确保内容准确、清晰、完整"
        )
        print(f"   ✅ 完成：审查完毕\n")
        
        return final


def main():
    """主函数"""
    print("🤖 AgentLearn - 多 Agent 协作")
    print("=" * 50)
    print("输入任务，团队成员将协作完成（输入 q 退出）\n")
    
    team = TeamManager()
    
    while True:
        try:
            task = input("任务：").strip()
            
            if task.lower() in ["q", "quit", "exit", "退出"]:
                print("👋 再见！")
                break
            
            if not task:
                continue
            
            result = team.run(task)
            print("\n" + "=" * 50)
            print("📄 最终成果：")
            print("=" * 50)
            print(result)
            print("=" * 50 + "\n")
        
        except KeyboardInterrupt:
            print("\n👋 再见！")
            break


if __name__ == "__main__":
    main()
