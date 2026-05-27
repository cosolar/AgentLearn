# 5.2 文档处理与分块 —— 构建高质量知识库的基础

## 📖 导读

> **RAG 的质量上限，取决于文档处理的质量。垃圾进，垃圾出。**

文档处理是 RAG 系统的第一步，也是最容易被忽视的关键环节。如果你的文档分块不合理、加载不完整、清洗不到位，后续的检索和生成都会受到影响。**好的文档处理能让 RAG 系统的准确率提升 20-30%。**

---

## 一、前置知识

| 概念 | 章节 | 说明 |
|------|------|------|
| Document | 3.3 | LangChain 中的文档对象（page_content + metadata） |
| Embedding | 3.3 | 文本转为向量的过程 |
| Token | 1.1 | LLM 的处理单元 |

---

## 二、文档加载

### 2.1 支持的文件类型

LangChain 提供了丰富的文档加载器，覆盖几乎所有常见格式：

| 格式 | 加载器 | 安装命令 |
|------|--------|----------|
| **纯文本** (.txt) | `TextLoader` | 内置 |
| **PDF** (.pdf) | `PyPDFLoader` | `pip install pypdf` |
| **Word** (.docx) | `Docx2txtLoader` | `pip install docx2txt` |
| **Markdown** (.md) | `UnstructuredMarkdownLoader` | `pip install unstructured` |
| **HTML** (.html) | `UnstructuredHTMLLoader` | `pip install unstructured` |
| **CSV** (.csv) | `CSVLoader` | 内置 |
| **JSON** (.json) | `JSONLoader` | 内置 |
| **Excel** (.xlsx) | `UnstructuredExcelLoader` | `pip install openpyxl` |
| **图片中的文字** | `AzureAIDocumentIntelligenceLoader` | 需额外配置 |

### 2.2 加载单个文件

```python
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredMarkdownLoader,
)

# 加载文本文件
text_loader = TextLoader("manual.txt", encoding="utf-8")
text_docs = text_loader.load()

# 加载 PDF 文件
pdf_loader = PyPDFLoader("manual.pdf")
pdf_docs = pdf_loader.load()
print(f"PDF 共 {len(pdf_docs)} 页")
for page in pdf_docs:
    print(f"  第 {page.metadata['page'] + 1} 页: {len(page.page_content)} 字")

# 加载 Word 文件
word_loader = Docx2txtLoader("manual.docx")
word_docs = word_loader.load()

# 加载 Markdown
md_loader = UnstructuredMarkdownLoader("README.md")
md_docs = md_loader.load()
```

### 2.3 批量加载目录

```python
from langchain_community.document_loaders import DirectoryLoader

# 加载目录下所有文件
loader = DirectoryLoader(
    "./documents/",
    glob="**/*.md",          # 只加载 Markdown 文件
    loader_cls=TextLoader,    # 使用文本加载器
    loader_kwargs={"encoding": "utf-8"},
    show_progress=True,       # 显示进度条
    use_multithreading=True,  # 多线程加速
)

docs = loader.load()
print(f"加载了 {len(docs)} 个文件")

# 按文件分组
from collections import defaultdict
by_source = defaultdict(list)
for doc in docs:
    source = doc.metadata.get("source", "unknown")
    by_source[source].append(doc)

for source, source_docs in by_source.items():
    print(f"  {source}: {len(source_docs)} 段")
```

### 2.4 文档清洗

加载后的文档通常需要清洗：

```python
def clean_document(doc) -> str:
    """清洗文档内容"""
    text = doc.page_content
    
    # 1. 去除多余空白
    text = " ".join(text.split())
    
    # 2. 去除特殊字符（保留中文和常用标点）
    import re
    text = re.sub(r'[^\w\s\u4e00-\u9fff。，、；：？！""''（）【】《》\-\.\,\!\?\(\)]', '', text)
    
    # 3. 去除过短的行
    lines = text.split('\n')
    lines = [l for l in lines if len(l.strip()) > 5]
    text = '\n'.join(lines)
    
    # 4. 更新元数据
    doc.metadata["cleaned"] = True
    doc.metadata["original_length"] = len(doc.page_content)
    doc.metadata["cleaned_length"] = len(text)
    
    doc.page_content = text
    return doc
```

---

## 三、文本分块（Chunking）

### 3.1 为什么需要分块？

```text
❌ 不分块的痛点：
1. 整篇文档太大，超过 LLM 的 context window
2. 太长 → Embedding 向量"平均化" → 检索精度下降
3. 一篇文档包含多个主题 → 检索时命中率低

✅ 分块的好处：
1. 每块聚焦一个子主题 → 检索精度高
2. 长度可控 → 适合 Embedding 和 LLM 处理
3. 可识别具体引用来源（第几章第几节）
```

### 3.2 分块策略详解

LangChain 提供了多种文本分割器：

```python
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,  # 递归字符分割（推荐）
    TokenTextSplitter,               # Token 级别分割
    MarkdownHeaderTextSplitter,      # Markdown 标题分割
    PythonCodeTextSplitter,          # Python 代码分割
    CharacterTextSplitter,           # 简单字符分割
)
```

#### 策略一：RecursiveCharacterTextSplitter（首选）

**原理**：递归地尝试不同的分隔符（\n\n → \n → 。 → 空格），尽量在自然边界处分割。

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,         # 每块最大字符数
    chunk_overlap=50,       # 块间重叠字符数
    length_function=len,     # 长度计算函数
    separators=["\n\n", "\n", "。", ".", " ", ""],  # 分隔符优先级
)

# 分割文档
chunks = splitter.split_documents(docs)
print(f"分割为 {len(chunks)} 个块")

# 查看第一个块
print(f"第 1 块: {len(chunks[0].page_content)} 字")
print(f"内容预览: {chunks[0].page_content[:100]}...")
```

#### 策略二：TokenTextSplitter

按 Token 数量分割，更适合 Embedding 的 token 限制。

```python
from langchain_text_splitters import TokenTextSplitter

# TokenTextSplitter 更精确地控制 token 数
token_splitter = TokenTextSplitter(
    chunk_size=500,          # 每块 500 tokens
    chunk_overlap=50,        # 50 tokens 重叠
    encoding_name="cl100k_base",  # OpenAI 使用的编码
)

token_chunks = token_splitter.split_documents(docs)
```

#### 策略三：MarkdownHeaderTextSplitter

按 Markdown 标题分割，保留文档的层次结构。

```python
from langchain_text_splitters import MarkdownHeaderTextSplitter

markdown_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[
        ("#", "header1"),
        ("##", "header2"),
        ("###", "header3"),
    ]
)

md_text = """
# 第一章：Python 基础
## 1.1 变量
Python 是一种动态类型语言...
## 1.2 数据类型
常见类型包括整型、浮点型、字符串...
### 1.2.1 字符串操作
字符串支持切片、拼接等操作...
"""

chunks = markdown_splitter.split_text(md_text)
for chunk in chunks:
    print(f"标题: {chunk.metadata}")
    print(f"内容预览: {chunk.page_content[:50]}...")
    print()
```

### 3.3 chunk_size 和 chunk_overlap 的选择

| chunk_size | 适用场景 | 优点 | 缺点 |
|-----------|----------|------|------|
| 128-256 | 代码、短文本 | 检索精度高 | 上下文不完整 |
| **500-1000** | **通用文档** | **平衡检索和生成** | **推荐** |
| 1000-2000 | 长段落、论文 | 上下文完整 | 检索精度下降 |

```python
def compare_chunk_sizes(docs, sizes=[250, 500, 1000, 2000]):
    """对比不同 chunk_size 的效果"""
    for size in sizes:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=size,
            chunk_overlap=size // 10,
        )
        chunks = splitter.split_documents(docs)
        
        avg_len = sum(len(c.page_content) for c in chunks) / len(chunks)
        print(f"chunk_size={size:5d} → {len(chunks):4d} 块, 平均 {avg_len:.0f} 字符")
```

**chunk_overlap 的作用**：

```text
没有重叠：
[...句子结尾...] [下一句开头...]
                ↑ 断开处可能丢失关键信息

有重叠：
[...句子结尾...重叠部分...]
                [重叠部分...下一句开头...]
                ↑ 上下文连贯性更好
```

**推荐配置**：`chunk_overlap = chunk_size * 10% ~ 20%`

---

## 四、实战：完整的文档处理流水线

```python
import os
from typing import List
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


class DocumentProcessor:
    """文档处理流水线"""
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def load_documents(self, directory: str) -> List[Document]:
        """加载目录下所有支持的文档"""
        print(f"📂 从 {directory} 加载文档...")
        
        loaders = {
            ".txt": TextLoader,
            ".md": TextLoader,
            ".py": TextLoader,
        }
        
        all_docs = []
        for ext, loader_cls in loaders.items():
            pattern = f"**/*{ext}"
            loader = DirectoryLoader(
                directory,
                glob=pattern,
                loader_cls=loader_cls,
                loader_kwargs={"encoding": "utf-8"},
                show_progress=True,
            )
            try:
                docs = loader.load()
                all_docs.extend(docs)
                print(f"  ✅ {ext}: {len(docs)} 个文件")
            except Exception as e:
                print(f"  ❌ {ext}: {e}")
        
        print(f"  共加载 {len(all_docs)} 个文档")
        return all_docs
    
    def clean_documents(self, docs: List[Document]) -> List[Document]:
        """清洗文档"""
        import re
        
        for doc in docs:
            text = doc.page_content
            # 去除多余空白
            text = re.sub(r'\s+', ' ', text)
            # 更新
            doc.page_content = text.strip()
        
        print(f"  ✅ 清洗完成: {len(docs)} 个文档")
        return docs
    
    def split_documents(self, docs: List[Document]) -> List[Document]:
        """分割文档"""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", "。", ".", " "],
        )
        
        chunks = splitter.split_documents(docs)
        print(f"  ✂️ 分割为 {len(chunks)} 个块")
        print(f"  平均块大小: {sum(len(c.page_content) for c in chunks) / len(chunks):.0f} 字符")
        
        return chunks
    
    def process(self, directory: str) -> List[Document]:
        """完整处理流程"""
        print("🔄 文档处理流水线")
        print("=" * 40)
        
        docs = self.load_documents(directory)
        docs = self.clean_documents(docs)
        chunks = self.split_documents(docs)
        
        print(f"\n✅ 处理完成: {len(chunks)} 个文档块")
        return chunks


# 使用
if __name__ == "__main__":
    processor = DocumentProcessor(chunk_size=500, chunk_overlap=50)
    chunks = processor.process("./documents/")
    
    # 查看结果统计
    lengths = [len(c.page_content) for c in chunks]
    print(f"最短: {min(lengths)} 字符")
    print(f"最长: {max(lengths)} 字符")
    print(f"平均: {sum(lengths) / len(lengths):.0f} 字符")
```

---

## 五、分块策略选择指南

| 文档类型 | 推荐策略 | chunk_size | 原因 |
|----------|----------|-----------|------|
| **技术文档** | MarkdownHeader | 500-1000 | 保留章节结构 |
| **小说/文章** | Recursive | 500-1000 | 自然段落边界 |
| **代码** | PythonCode | 200-500 | 函数级别分割 |
| **法律合同** | Recursive + 小 overlap | 300-500 | 精确度高要求 |
| **论文/报告** | Recursive + 大 overlap | 1000-2000 | 完整上下文 |
| **FAQ/问答** | 不分割（保持单条） | 按原样 | Q&A 对不宜拆分 |

---

## 六、常见问题

### ❌ 分块破坏了关键信息

```python
# 问题：一句话被切成两段，检索时找不到
# 解决：使用适当的 overlap + 在分块时考虑语义边界

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,  # 增大重叠
    separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " "],
)
```

### ❌ 元数据丢失

```python
# 问题：分块后不知道文档来源
# 解决：确保 metadata 被正确继承

for chunk in chunks:
    # 添加文档级元数据
    chunk.metadata["source_file"] = source_doc.metadata["source"]
    chunk.metadata["chunk_index"] = i
    chunk.metadata["total_chunks"] = total
```

### ❌ 加载大文件超时

```python
# 问题：几百页的 PDF 加载太慢
# 解决：使用流式加载或限制页数

loader = PyPDFLoader("large.pdf")
# 只加载前 50 页
docs = loader.load()  # 或 loader.load_and_split()
pages = docs[:50]
```

---

## 七、本章总结

| 要点 | 说明 |
|------|------|
| **文档加载** | DirectoryLoader 批量加载多格式文件 |
| **文档清洗** | 去除噪声、标准化格式 |
| **文本分块** | RecursiveCharacterTextSplitter（首选） |
| **chunk_size** | 通用推荐 500-1000 |
| **chunk_overlap** | 推荐 size 的 10-20% |
| **元数据** | 保留来源信息，便于追溯 |

---

## 📝 课后练习

1. **✅ 基础**：用 RecursiveCharacterTextSplitter 将一篇长文章分割为 500 字符的块
2. **💡 对比**：分别用 chunk_size=200 和 chunk_size=1000 分割同一文档，对比分割结果的质量
3. **🚀 挑战**：实现一个"智能分块"函数，能根据 Markdown 标题结构化地分割文档
4. **🔍 探索**：加载一个真实的 PDF 文档，查看 PyPDFLoader 返回的 metadata 包含哪些信息
