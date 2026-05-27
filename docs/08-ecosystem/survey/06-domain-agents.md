# 8.6 专业领域 Agent

## 📖 本章目标

- 了解各垂直领域的 Agent 应用
- 掌握领域 Agent 的核心能力模式
- 学会将通用 Agent 知识迁移到专业领域

---

## 领域 Agent 概览

> 本教程前 7 章教你的是通用 Agent 能力，本章展示如何将这些能力应用到具体领域。

```
通用 Agent 技能 ← 本教程 7 章所学
    │
    ├── Prompt 工程 ──────────▶ 各领域提示词优化
    ├── 工具调用 ─────────────▶ 领域专用工具
    ├── RAG 系统 ─────────────▶ 领域知识库
    ├── 多 Agent 协作 ────────▶ 领域角色分工
    └── 工作流编排 ───────────▶ 领域业务流程
            │
            ▼
    领域 Agent 应用
```

---

## 六大领域 Agent 解析

### 1. 编程 Agent — OpenClaw

**核心能力：**
- IDE 深度集成（VS Code、JetBrains）
- 代码生成、补全、审查
- 安全沙箱执行代码
- 多文件上下文理解

```python
# 用 LangChain 构建编程助手的核心逻辑
from langchain_core.tools import tool
import subprocess

@tool
def run_python_code(code: str) -> str:
    """在安全沙箱中执行 Python 代码"""
    # 实际项目中应使用 Docker 沙箱
    result = subprocess.run(
        ["python", "-c", code],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout if result.returncode == 0 else result.stderr

@tool
def search_codebase(query: str) -> str:
    """在代码库中搜索"""
    import subprocess
    result = subprocess.run(
        ["grep", "-r", query, "."],
        capture_output=True, text=True
    )
    return result.stdout[:2000]  # 限制返回长度
```

**技术栈：** Tree-sitter（AST 分析）、LSP（语言服务）、Docker（沙箱）

### 2. 数据科学 Agent — AutoGen Data Scientist

**核心能力：**
- 数据清洗与预处理
- 探索性数据分析
- 模型训练与调参
- 可视化报告生成

```python
# 数据科学 Agent 的工具集
data_science_tools = [
    tool("load_csv", "加载数据文件"),
    tool("clean_data", "数据清洗（缺失值、异常值）"),
    tool("visualize", "生成图表"),
    tool("train_model", "训练 ML 模型"),
    tool("evaluate", "模型评估"),
]

# 多 Agent 协作流程
# 1. 数据分析师 Agent → 加载+清洗数据
# 2. 建模师 Agent → 训练+调参
# 3. 报告撰写 Agent → 生成分析报告
```

**技术栈：** Pandas、Scikit-learn、Matplotlib、Jupyter

### 3. 科研 Agent — SciAgent

**核心能力：**
- 文献自动检索与总结
- 实验方案设计
- 数据分析与图表生成
- 论文写作辅助

```python
# 科研 Agent 工作流示例
from langgraph.graph import StateGraph

class ResearchState(TypedDict):
    question: str              # 研究问题
    literature: list           # 检索到的文献
    experiment_design: str     # 实验设计
    results: dict              # 实验结果
    paper_draft: str           # 论文草稿

workflow = StateGraph(ResearchState)
workflow.add_node("search_literature", search_papers)     # 文献检索
workflow.add_node("design_experiment", design_experiment)  # 实验设计
workflow.add_node("analyze_results", analyze_results)      # 结果分析
workflow.add_node("write_paper", write_paper)             # 论文撰写
```

**技术栈：** Semantic Scholar API、LaTeX、Jupyter Notebook

### 4. DevOps Agent — DevOps Agent

**核心能力：**
- 自动化部署流水线
- 监控告警与自愈
- 故障排查与根因分析
- 容量规划与成本优化

```python
# DevOps Agent 工具集
@tool
def check_service_health(service: str) -> str:
    """检查服务健康状态"""
    import requests
    try:
        r = requests.get(f"http://{service}/health", timeout=5)
        return f"状态: {r.status_code}, 响应: {r.json()}"
    except Exception as e:
        return f"服务异常: {e}"

@tool
def query_logs(service: str, keywords: str, minutes: int = 60) -> str:
    """查询服务日志"""
    # 实际对接 ELK/Loki
    pass

@tool  
def rollback_deployment(service: str, version: str) -> str:
    """回滚部署"""
    # 实际调用 K8s API
    pass
```

**技术栈：** Kubernetes API、Prometheus、Grafana、Terraform

### 5. 金融 Agent — FinAgent

**核心能力：**
- 市场数据分析与预测
- 投资建议生成
- 风险评估
- 合规检查

```python
# 金融 Agent 的安全要求
FINANCIAL_SAFETY_PROMPT = """
你是金融 AI 助手 Finch。你必须：
1. 明确声明"I am an AI assistant, not a licensed financial advisor"
2. 提供信息而非建议
3. 标注所有信息来源和日期
4. 提示投资风险
5. 如果用户询问具体投资建议，建议咨询专业人士
"""

@tool
def get_stock_price(symbol: str) -> str:
    """获取实时股价"""
    # 调用金融 API
    pass

@tool
def calculate_risk_profile(portfolio: dict) -> str:
    """计算投资组合风险"""
    # 风险计算逻辑
    pass
```

**技术栈：** Yahoo Finance API、Pandas、NumPy、监管合规库

### 6. 医疗 Agent — MedAgent

**核心能力：**
- 病历分析
- 辅助诊断建议
- 医学文献检索
- 用药提醒

```python
# 医疗 Agent 的严格安全约束
MEDICAL_SAFETY_PROMPT = """
你是医疗 AI 助手 MedBot。严格遵守：
1. 免责声明：AI 辅助，不能替代医生诊断
2. 紧急情况：立即建议就医
3. 隐私保护：不存储患者个人信息
4. 引用来源：所有医学建议必须有文献支持
5. 不确定性：明确表达置信度
"""

@tool
def search_medical_literature(symptom: str) -> str:
    """检索医学文献"""
    # 对接 PubMed API
    pass
```

**技术栈：** PubMed API、HL7/FHIR 标准、HIPAA 合规

---

## 领域 Agent 通用模式

无论哪个领域，构建专业 Agent 都遵循同样的模式：

```
1. 安全边界
   └── 领域特定的安全限制（金融合规、医疗隐私、代码沙箱）
   
2. 知识注入
   └── RAG + 领域知识库（金融法规、医学文献、代码文档）
   
3. 专用工具
   └── 领域 API 封装（股价查询、文献检索、K8s 操作）
   
4. 角色设计
   └── 多 Agent 分工（分析师+建模师+审查员）
   
5. 评估体系
   └── 领域特定指标（诊断准确率、投资收益、部署成功率）
```

---

## 构建你的领域 Agent

```python
# 领域 Agent 的通用骨架
class DomainAgent(DialogAgent):
    """领域 Agent 基类"""
    
    def __init__(self, domain: str, **kwargs):
        super().__init__(**kwargs)
        self.domain = domain
        self.safety_prompt = self._load_safety_prompt(domain)
        self.knowledge_base = self._init_knowledge_base(domain)
        self.tools = self._load_domain_tools(domain)
    
    def _load_safety_prompt(self, domain: str) -> str:
        """加载领域安全提示词"""
        prompts = {
            "finance": FINANCIAL_SAFETY_PROMPT,
            "medical": MEDICAL_SAFETY_PROMPT,
            "devops": DEVOPS_SAFETY_PROMPT,
        }
        return prompts.get(domain, DEFAULT_SAFETY_PROMPT)
    
    def _init_knowledge_base(self, domain: str):
        """初始化领域知识库（RAG）"""
        # 加载领域文档 → 分块 → 向量化 → 存储
        pass
    
    def _load_domain_tools(self, domain: str) -> list:
        """加载领域专用工具"""
        # 根据领域注册工具
        pass
```

---

## 本章小结

| 要点 | 说明 |
|------|------|
| 🎯 | 领域 Agent = 通用技能 + 领域知识 + 安全约束 |
| 🔧 | 每个领域都有专用工具和 API |
| 🔒 | 安全合规是领域 Agent 的首要考量 |
| 📚 | RAG 是领域知识注入的核心手段 |
| 🔄 | 多 Agent 分工适合复杂领域场景 |

---

## 📝 课后练习

1. **设计题**：选择一个你熟悉的领域，列出 5 个该领域 Agent 必须具备的工具
2. **构建题**：基于 DialogAgent 构建一个简易的领域 Agent，至少包含 RAG 知识库和 2 个专用工具
3. **思考题**：医疗和金融领域的 Agent 在安全约束上有什么异同？

