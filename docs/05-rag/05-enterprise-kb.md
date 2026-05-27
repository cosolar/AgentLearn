# 5.5 实战：企业知识库 —— 构建生产级 RAG 系统

## 📖 导读

> **从"能答对几个问题"到"稳定可靠地解决实际问题"，是 RAG 系统走向生产的必经之路。**

前几节我们学习了 RAG 的各个组件。现在我们要**综合运用所有知识，构建一个真正的企业级知识库问答系统**。这个项目将涵盖：多格式文档处理、向量存储、智能检索、会话管理、权限控制等生产环境必须的能力。

---

## 一、项目需求

### 1.1 核心功能

| 功能 | 说明 |
|------|------|
| **多格式文档支持** | PDF / Word / Markdown / 代码文件 |
| **智能检索** | 混合检索 + 重排序 |
| **会话管理** | 多用户隔离，保存对话历史 |
| **来源追溯** | 每条回答附上引用来源 |
| **权限管理** | 不同用户可访问不同文档 |
| **增量更新** | 支持随时添加新文档 |

### 1.2 用户视角

```text
👤 用户：公司的远程办公政策是什么？
🤖 AI：根据《员工手册》第 5 章第 2 节（员工手册.pdf），公司远程办公政策如下：
1. 每周可申请最多 2 天远程办公
2. 需提前一天在 OA 系统提交申请
3. 远程办公期间需保持即时通讯在线
4. ...

📚 参考来源：
- 员工手册.pdf (第 5 章，第 2 节)
- 远程办公补充规定.md (2024 年更新)
```

---

## 二、完整项目结构

```
examples/05-enterprise-kb/
├── main.py                    # 主入口
├── config.py                  # 配置管理
├── document_processor.py      # 文档处理
├── knowledge_base.py          # 知识库管理
├── retriever.py               # 检索优化
├── qa_chain.py                # QA 问答链
├── session_manager.py         # 会话管理
├── documents/                 # 文档存放目录
├── kb_data/                   # 知识库持久化数据
└── README.md
```

---

## 三、逐步实现

### 3.1 配置管理（config.py）

```python
"""配置文件"""
import os
from dotenv import load_dotenv

load_dotenv()

# LLM 配置
LLM_CONFIG = {
    "model": os.getenv("LLM_MODEL_NAME", "gpt-4o"),
    "temperature": 0.1,  # 知识问答需要低温度，保持准确
}

# Embedding 配置
EMBEDDING_CONFIG = {"model": "text-embedding-3-small"}

# 知识库配置
KB_CONFIG = {
    "persist_directory": "./kb_data",
    "chunk_size": 500,
    "chunk_overlap": 50,
    "retriever_k": 4,
    "score_threshold": 0.5,
}

# 会话配置
SESSION_CONFIG = {"max_history": 10}
```

### 3.2 文档处理器（document_processor.py）

```python
"""文档处理模块：加载、清洗、分块"""
from typing import List
from pathlib import Path
from langchain_community.document_loaders import (
    DirectoryLoader, TextLoader, PyPDFLoader, Docx2txtLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from config import KB_CONFIG


class DocumentProcessor:
    """文档处理器"""
    
    def __init__(self):
        self.loaders = {
            ".txt": TextLoader, ".md": TextLoader, ".pdf": self._create_pdf_loader,
            ".docx": Docx2txtLoader, ".csv": TextLoader,
        }
    
    def _create_pdf_loader(self, file_path: str):
        return PyPDFLoader(file_path)
    
    def load_single(self, file_path: str) -> List[Document]:
        path = Path(file_path)
        ext = path.suffix.lower()
        if ext not in self.loaders:
            raise ValueError(f"不支持的文件格式: {ext}")
        loader_cls = self.loaders[ext]
        loader = loader_cls(file_path) if callable(loader_cls) else loader_cls(file_path, encoding="utf-8")
        docs = loader.load()
        for doc in docs:
            doc.metadata["source_file"] = path.name
            doc.metadata["source_path"] = str(path)
        print(f"  ✅ 加载: {path.name} ({len(docs)} 页/段)")
        return docs
    
    def load_directory(self, directory: str) -> List[Document]:
        print(f"📂 从 {directory} 加载文档...")
        all_docs = []
        for ext in self.loaders:
            loader = DirectoryLoader(
                directory, glob=f"**/*{ext}", loader_cls=TextLoader,
                loader_kwargs={"encoding": "utf-8"}, show_progress=True, use_multithreading=True,
            )
            try:
                docs = loader.load()
                all_docs.extend(docs)
                print(f"  {ext}: {len(docs)} 个文件")
            except Exception:
                pass
        return all_docs
    
    def split_documents(self, docs: List[Document]) -> List[Document]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=KB_CONFIG["chunk_size"],
            chunk_overlap=KB_CONFIG["chunk_overlap"],
            separators=["\n\n", "\n", "。", ".", " ", ""],
        )
        chunks = splitter.split_documents(docs)
        print(f"  ✂️ 分割为 {len(chunks)} 个块")
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_id"] = i
            chunk.metadata["total_chunks"] = len(chunks)
        return chunks
    
    def process(self, input_path: str) -> List[Document]:
        path = Path(input_path)
        docs = self.load_single(input_path) if path.is_file() else self.load_directory(input_path)
        return self.split_documents(docs)
```

### 3.3 知识库管理（knowledge_base.py）

```python
"""知识库管理：向量存储的增删查"""
from typing import List, Optional
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from config import KB_CONFIG, EMBEDDING_CONFIG


class KnowledgeBase:
    """企业知识库"""
    
    def __init__(self, persist_directory: Optional[str] = None):
        self.embeddings = OpenAIEmbeddings(model=EMBEDDING_CONFIG["model"])
        self.persist_directory = persist_directory or KB_CONFIG["persist_directory"]
        self.vectorstore = self._load_or_create()
    
    def _load_or_create(self) -> Chroma:
        import os
        if os.path.exists(self.persist_directory):
            print(f"📦 加载已有知识库: {self.persist_directory}")
            return Chroma(embedding_function=self.embeddings, persist_directory=self.persist_directory)
        print(f"🆕 创建新知识库: {self.persist_directory}")
        return Chroma(embedding_function=self.embeddings, persist_directory=self.persist_directory)
    
    def add_documents(self, documents: List[Document]):
        self.vectorstore.add_documents(documents)
        self.vectorstore.persist()
        print(f"✅ 已添加 {len(documents)} 个文档块到知识库")
    
    def search(self, query: str, k: int = None, filter: dict = None) -> List[Document]:
        k = k or KB_CONFIG["retriever_k"]
        if filter:
            return self.vectorstore.similarity_search(query, k=k, filter=filter)
        return self.vectorstore.similarity_search(query, k=k)
    
    def search_with_scores(self, query: str, k: int = None) -> List[tuple]:
        k = k or KB_CONFIG["retriever_k"]
        return self.vectorstore.similarity_search_with_relevance_scores(query, k=k)
    
    def get_stats(self) -> dict:
        count = self.vectorstore._collection.count()
        return {"total_documents": count, "persist_directory": self.persist_directory}
    
    def refresh(self):
        self.vectorstore.persist()
        print("🔄 知识库已刷新")
```

### 3.4 检索优化（retriever.py）

```python
"""检索优化：查询扩展 + 重排序"""
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from config import LLM_CONFIG


class OptimizedRetriever:
    """优化检索器"""
    
    def __init__(self, knowledge_base):
        self.kb = knowledge_base
        self.llm = ChatOpenAI(model=LLM_CONFIG["model"], temperature=0)
    
    def retrieve(self, query: str, k: int = 4) -> List[Document]:
        expanded = self._expand_query(query)
        all_docs = self._multi_query_retrieval(expanded, k * 2)
        return self._rerank(query, all_docs, top_k=k)
    
    def _expand_query(self, query: str) -> list:
        return [query, f"什么是{query}", f"关于{query}的说明"]
    
    def _multi_query_retrieval(self, queries: list, k: int) -> List[Document]:
        all_docs, seen = [], set()
        for q in queries:
            docs = self.kb.search(q, k=k // len(queries) + 1)
            for doc in docs:
                key = doc.page_content[:80]
                if key not in seen:
                    seen.add(key)
                    all_docs.append(doc)
        return all_docs
    
    def _rerank(self, query: str, docs: List[Document], top_k: int) -> List[Document]:
        scored_docs = []
        for doc in docs:
            prompt = f"评估以下文档与问题的相关性，输出0-10的数字。\n问题：{query}\n文档：{doc.page_content[:200]}\n分数："
            score_text = self.llm.invoke(prompt)
            try:
                score = float(score_text.content.strip())
            except:
                score = 5.0
            scored_docs.append((score, doc))
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored_docs[:top_k]]
```

### 3.5 QA 问答链（qa_chain.py）

```python
"""QA 问答链"""
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from config import LLM_CONFIG


class QAChain:
    """问答链：检索 → 增强 → 生成"""
    
    def __init__(self, retriever):
        self.retriever = retriever
        self.llm = ChatOpenAI(model=LLM_CONFIG["model"], temperature=LLM_CONFIG["temperature"])
        self.prompt = self._build_prompt()
        self.chain = self._build_chain()
    
    def _build_prompt(self):
        return ChatPromptTemplate.from_messages([
            ("system", "你是一个企业知识库问答助手。基于参考信息回答问题。"),
            ("human", "参考信息：\n{context}\n\n问题：{question}"),
        ])
    
    def _build_chain(self):
        return self.prompt | self.llm | StrOutputParser()
    
    def answer(self, question: str) -> dict:
        docs = self.retriever.retrieve(question)
        context = "\n\n".join([
            f"[来源 {i+1}: {d.metadata.get('source_file', '未知')}]\n{d.page_content}"
            for i, d in enumerate(docs)
        ])
        answer = self.chain.invoke({"context": context, "question": question})
        return {
            "question": question,
            "answer": answer,
            "sources": [
                {"file": d.metadata.get("source_file", "未知"), "content": d.page_content[:100]}
                for d in docs
            ],
        }
```

### 3.6 会话管理（session_manager.py）

```python
"""会话管理：多用户隔离"""
import uuid
from datetime import datetime
from typing import Dict, List


class Session:
    """单个会话"""
    def __init__(self, session_id: str, user: str = "anonymous"):
        self.session_id = session_id
        self.user = user
        self.history: List[dict] = []
        self.created_at = datetime.now()
    
    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content, "time": datetime.now().isoformat()})
    
    def get_history(self, max_turns: int = 10) -> List[dict]:
        return self.history[-max_turns * 2:] if self.history else []


class SessionManager:
    """会话管理器"""
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
    
    def create_session(self, user: str = "anonymous") -> str:
        session_id = str(uuid.uuid4())[:8]
        self.sessions[session_id] = Session(session_id, user)
        return session_id
    
    def get_session(self, session_id: str) -> Session:
        return self.sessions.get(session_id)
    
    def chat(self, session_id: str, message: str, qa_chain) -> dict:
        session = self.get_session(session_id)
        if not session:
            session_id = self.create_session()
            session = self.get_session(session_id)
        
        session.add_message("user", message)
        result = qa_chain.answer(message)
        session.add_message("assistant", result["answer"])
        
        result["session_id"] = session_id
        return result
```

### 3.7 主入口（main.py）

```python
"""企业知识库主程序"""
from document_processor import DocumentProcessor
from knowledge_base import KnowledgeBase
from retriever import OptimizedRetriever
from qa_chain import QAChain
from session_manager import SessionManager


class EnterpriseKB:
    """企业知识库系统"""
    
    def __init__(self):
        print("🚀 初始化企业知识库系统...")
        self.kb = KnowledgeBase()
        self.retriever = OptimizedRetriever(self.kb)
        self.qa_chain = QAChain(self.retriever)
        self.session_mgr = SessionManager()
        self.doc_processor = DocumentProcessor()
    
    def index_documents(self, path: str):
        """索引文档到知识库"""
        chunks = self.doc_processor.process(path)
        self.kb.add_documents(chunks)
        print(f"✅ 知识库状态: {self.kb.get_stats()}")
    
    def chat(self, session_id: str = None, message: str = ""):
        """对话"""
        if not session_id:
            session_id = self.session_mgr.create_session()
            print(f"🆕 新会话: {session_id}")
        return self.session_mgr.chat(session_id, message, self.qa_chain)
    
    def interactive(self):
        """交互式对话"""
        session_id = self.session_mgr.create_session()
        print(f"\n{'=' * 50}")
        print("💬 企业知识库问答 (输入 'exit' 退出)")
        print(f"会话 ID: {session_id}")
        print(f"{'=' * 50}\n")
        
        while True:
            question = input("👤 你: ").strip()
            if question.lower() == "exit":
                break
            result = self.session_mgr.chat(session_id, question, self.qa_chain)
            print(f"\n🤖 AI: {result['answer']}")
            print(f"\n📚 参考来源:")
            for s in result['sources']:
                print(f"  - {s['file']}")
            print()


def main():
    kb = EnterpriseKB()
    kb.index_documents("./documents/")
    kb.interactive()


if __name__ == "__main__":
    main()
```

---

## 四、运行与使用

```bash
cd examples/05-enterprise-kb
source .venv/bin/activate  # 激活环境

# 1. 把文档放入 documents/ 目录
# 2. 运行
python main.py
```

---

## 五、扩展方案

| 扩展方向 | 实现方式 |
|----------|----------|
| **Web 界面** | 添加 FastAPI + Gradio |
| **权限管理** | 按用户/角色过滤可访问的文档 |
| **多语言** | 检测用户语言，检索对应语言文档 |
| **版本管理** | 文档更新时自动重新索引 |
| **分析面板** | 记录问答数据，统计高频问题和检索质量 |

---

## 六、本章总结

| 模块 | 说明 |
|------|------|
| **文档处理器** | 多格式加载 + 智能分块 |
| **知识库** | Chroma 持久化，支持增量更新 |
| **优化检索器** | 查询扩展 + 重排序 |
| **QA 链** | 检索增强生成 + 来源追溯 |
| **会话管理** | 多用户隔离，历史维护 |

---

## 📝 课后练习

1. **✅ 基础**：在 documents/ 中放入几个文档，运行知识库系统并提问
2. **💡 改进**：添加 FastAPI Web 接口，让知识库可以通过 HTTP 访问
3. **🚀 挑战**：实现权限管理——不同用户只能检索自己有权限的文档
4. **🔍 探索**：添加 RAGAS 评估，量化知识库的检索质量和回答准确率
