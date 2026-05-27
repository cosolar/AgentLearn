# 7.4 CI/CD 流水线 —— 自动化构建、测试和部署

## 📖 导读

> **手动部署是风险的温床。CI/CD 让"一键部署"变成"一次提交，自动上线"。**

CI/CD（持续集成/持续部署）是现代软件开发的核心实践。对 Agent 应用来说，CI/CD 意味着：**每次代码变更都自动经过构建→测试→部署的完整流程**，确保发布的质量和速度。

---

## 一、前置知识

| 概念 | 说明 |
|------|------|
| CI（持续集成） | 代码变更后自动构建和测试 |
| CD（持续部署） | 测试通过后自动部署到目标环境 |
| GitHub Actions | GitHub 提供的 CI/CD 平台 |
| Pipeline | 定义自动化流程的配置文件 |

---

## 二、CI/CD 流程设计

```text
开发者提交代码
     │
     ▼
┌─────────────────────┐
│   触发 CI/CD         │
│    (push / PR)       │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   代码检查 (Lint)    │
│   - 语法检查         │
│   - 格式化检查       │
│   - 安全扫描         │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   单元测试           │
│   - Python 测试      │
│   - Agent 功能测试   │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   构建 Docker 镜像   │
│   - 构建             │
│   - 扫描漏洞         │
│   - 推送到仓库       │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   部署               │
│   - 开发环境 (自动)   │
│   - 预发布环境 (自动) │
│   - 生产环境 (手动)  │
└─────────────────────┘
```

---

## 三、代码质量和测试

### 3.1 测试用例编写

```python
# tests/test_agent.py
import pytest
from agent import SupportAgent


@pytest.fixture
def agent():
    """创建测试用的 Agent 实例"""
    return SupportAgent()


class TestSupportAgent:
    """测试 SupportAgent 的核心功能"""
    
    def test_initialization(self, agent):
        """测试初始化"""
        assert agent is not None
        assert agent.llm is not None
    
    def test_answer_basic(self, agent):
        """测试基本回答功能"""
        result = agent.answer("你好")
        assert "answer" in result
        assert len(result["answer"]) > 0
    
    def test_answer_with_context(self, agent):
        """测试基于知识库的回答"""
        result = agent.answer("什么是 RAG？")
        assert len(result["answer"]) > 10
    
    def test_sources_format(self, agent):
        """测试来源信息格式"""
        result = agent.answer("AI Agent")
        if result.get("sources"):
            for source in result["sources"]:
                assert "title" in source
                assert "content" in source
    
    @pytest.mark.parametrize("question", [
        "",                           # 空字符串
        "a" * 5000,                   # 超长输入
        "<script>alert(1)</script>",  # XSS 尝试
    ])
    def test_edge_cases(self, agent, question):
        """测试边界情况"""
        with pytest.raises(Exception):
            agent.answer(question)


# tests/test_api.py
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class TestAPI:
    """测试 API 端点"""
    
    def test_health_check(self):
        """测试健康检查"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    def test_chat_endpoint(self):
        """测试聊天接口"""
        response = client.post("/chat", json={
            "message": "你好",
        })
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "session_id" in data
    
    def test_chat_with_session(self):
        """测试带会话的聊天"""
        # 第一次对话
        r1 = client.post("/chat", json={"message": "你好"})
        session_id = r1.json()["session_id"]
        
        # 第二次对话（同一会话）
        r2 = client.post("/chat", json={
            "session_id": session_id,
            "message": "刚才说到哪里了？",
        })
        assert r2.status_code == 200
        assert r2.json()["session_id"] == session_id
```

### 3.2 Agent 特定测试

```python
# tests/test_agent_eval.py
class TestAgentQuality:
    """Agent 质量测试"""
    
    def test_no_hallucination(self, agent):
        """测试是否会产生幻觉"""
        # 对于知识库中没有的信息，Agent 不应编造
        result = agent.answer("地球是平的吗？")
        assert "无法确定" in result["answer"] or \
               "未找到" in result["answer"] or \
               "抱歉" in result["answer"]
    
    def test_consistency(self, agent):
        """测试回答一致性"""
        # 同样的问题应该得到一致的答案
        answers = []
        for _ in range(3):
            result = agent.answer("什么是 CI/CD？")
            answers.append(result["answer"])
        
        # 至少应该包含核心概念
        for answer in answers:
            assert "持续集成" in answer or \
                   "持续部署" in answer or \
                   "automated" in answer
    
    def test_response_time(self, agent):
        """测试响应时间"""
        import time
        start = time.time()
        agent.answer("Python 列表怎么用？")
        elapsed = time.time() - start
        assert elapsed < 10.0  # 应在 10 秒内
```

---

## 四、GitHub Actions 配置

### 4.1 基础流水线

```yaml
# .github/workflows/ci.yml
name: CI Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  # ===== 代码质量检查 =====
  lint:
    name: Code Quality
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install ruff black mypy
          pip install -r requirements.txt

      - name: Lint with Ruff
        run: ruff check .

      - name: Check formatting with Black
        run: black --check .

      - name: Type check with mypy
        run: mypy . --ignore-missing-imports

  # ===== 测试 =====
  test:
    name: Run Tests
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run tests with coverage
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          pytest tests/ --cov=. --cov-report=xml --cov-report=term -v

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

  # ===== 构建 Docker 镜像 =====
  build:
    name: Build Docker Image
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: ${{ github.event_name != 'pull_request' }}
          tags: |
            ${{ secrets.DOCKER_USERNAME }}/agent-api:latest
            ${{ secrets.DOCKER_USERNAME }}/agent-api:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### 4.2 部署流水线

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  workflow_run:
    workflows: ["CI Pipeline"]
    branches: [main]
    types:
      - completed

jobs:
  deploy-staging:
    name: Deploy to Staging
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Deploy to staging server
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.STAGING_HOST }}
          username: ${{ secrets.STAGING_USER }}
          key: ${{ secrets.STAGING_SSH_KEY }}
          script: |
            cd /opt/agent-service
            docker-compose pull
            docker-compose up -d --force-recreate
            echo "✅ 部署到预发布环境完成"

  deploy-production:
    name: Deploy to Production
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production
    # 生产部署需要手动审批
    steps:
      - name: Manual approval gate
        run: echo "等待人工审批..."

      - name: Deploy to production
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.PROD_HOST }}
          username: ${{ secrets.PROD_USER }}
          key: ${{ secrets.PROD_SSH_KEY }}
          script: |
            cd /opt/agent-service
            docker-compose pull
            docker-compose up -d --force-recreate
            echo "✅ 部署到生产环境完成"
```

### 4.3 自动发布版本

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - "v*"  # 推送 v1.0.0 这样的 tag 时触发

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Generate changelog
        id: changelog
        uses: ./.github/actions/changelog

      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          body: ${{ steps.changelog.outputs.changelog }}
          files: |
            Dockerfile
            docker-compose.yml
```

---

## 五、本地 Git Hook（可选）

在提交代码前自动检查，避免不合规的代码进入仓库：

```bash
# .githooks/pre-commit
#!/bin/bash
echo "🔍 运行 pre-commit 检查..."

# 运行代码检查
ruff check .
if [ $? -ne 0 ]; then
    echo "❌ 代码检查未通过"
    exit 1
fi

# 运行快速测试
pytest tests/ -x --timeout=30 -q
if [ $? -ne 0 ]; then
    echo "❌ 测试未通过"
    exit 1
fi

echo "✅ 所有检查通过"
```

---

## 六、环境管理

```yaml
# .github/environments.yaml
name: Agent Service Environments

environments:
  - name: development
    protection_rules: []
    deployment_branch: develop
    variables:
      LLM_MODEL_NAME: gpt-4o-mini
      LOG_LEVEL: debug

  - name: staging
    protection_rules: []
    deployment_branch: main
    variables:
      LLM_MODEL_NAME: gpt-4o-mini
      LOG_LEVEL: info

  - name: production
    protection_rules:
      - required_reviewers: 1  # 需要审批
      - wait_timer: 5          # 5 分钟等待期
    deployment_branch: main
    variables:
      LLM_MODEL_NAME: gpt-4o
      LOG_LEVEL: warning
      ENABLE_MONITORING: true
```

---

## 七、CI/CD 注意事项

| 注意点 | 说明 | 最佳实践 |
|--------|------|----------|
| **API Key** | 不硬编码在代码中 | 使用 GitHub Secrets |
| **测试环境** | 使用 Mock 而不是真实 API | 控制测试成本 |
| **构建缓存** | 避免每次都重新下载依赖 | Docker layer caching |
| **回滚方案** | 部署失败能快速回退 | 保留上一个版本 |
| **测试数据** | 测试用的小型知识库 | 避免加载完整知识库 |

---

## 八、本章总结

| 环节 | 工具/方法 | 说明 |
|------|-----------|------|
| **代码检查** | Ruff + Black | 自动检查代码风格 |
| **测试** | pytest | 单元测试 + API 测试 |
| **构建** | Docker Buildx | 多架构镜像构建 |
| **CI 流水线** | GitHub Actions | 自动触发构建和测试 |
| **CD 部署** | SSH + Docker | 自动部署到服务器 |

---

## 📝 课后练习

1. **✅ 基础**：在 GitHub 仓库中配置 `.github/workflows/ci.yml`，运行基本的 lint + test
2. **💡 改进**：添加 Docker 构建和推送步骤到 CI 流水线
3. **🚀 挑战**：配置完整的 CI/CD，实现"推送 main 分支 → 自动测试 → 构建镜像 → 部署到预发布环境"
4. **🔍 探索**：了解 GitHub Actions 的 matrix 策略，配置 Python 3.11 / 3.12 的多版本测试
