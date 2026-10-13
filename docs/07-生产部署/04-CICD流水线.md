# 7.4 CI/CD 流水线 —— 自动化构建、测试和部署

> 📅 更新至 2026-10 · 技术栈基线见 [教程大纲](../教程大纲.md)

## 📖 导读

> **手动部署是风险的温床。CI/CD 让"一次提交，自动上线"成为可能——但也让"一次提交，自动翻车"成为可能。**

对 Agent 应用来说，CI/CD 不只是跑单元测试：**还必须把评测回归纳入门禁**——代码能跑不代表效果没退化。本章给出完整流水线：**质量检查 → 测试 → 评测回归阻断 → 构建镜像 → 灰度发布 → 可回滚**。

---

## 一、前置知识

| 概念 | 说明 |
|------|------|
| CI（持续集成） | 变更后自动构建与测试 |
| CD（持续部署） | 测试通过后自动发布 |
| GitHub Actions | 主流 CI/CD 平台 |
| 门禁（Gate） | 不达标就阻断流程的检查点 |
| 灰度（Canary） | 先放量小流量，验证后再全量 |

---

## 二、流程设计

```text
提交代码 / PR
     │
     ▼
① Lint + 类型检查（ruff / mypy）
     │
     ▼
② 单元测试 + 覆盖率（pytest / codecov）
     │
     ▼
③ 评测回归门禁（eval gate）★ Agent 专属
     │  准确率回退或安全用例失败 → 阻断
     ▼
④ 构建并推送镜像（buildx）
     │
     ▼
⑤ 部署预发布 → 冒烟测试
     │
     ▼
⑥ 灰度发布（10% 流量）→ 观察 → 全量 / 回滚
```

---

## 三、测试与代码质量

### 3.1 API 测试

```python
# tests/test_api.py
"""API 端点测试"""
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)
HEADERS = {"X-API-Key": "test-key"}


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_chat_requires_api_key():
    """缺少鉴权应返回 401，且符合错误契约"""
    resp = client.post("/chat", json={"message": "hi"})
    assert resp.status_code == 401
    body = resp.json()
    assert {"error", "code", "request_id"} <= set(body)


def test_chat_validation_error():
    """空消息应被 Pydantic 拦截，返回 422 错误契约"""
    resp = client.post("/chat", json={"message": ""}, headers=HEADERS)
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_error"
```

### 3.2 评测回归门禁（Agent 专属）

把 [6.2 评估与优化](../06-高级主题/02-评估与优化.md) 的评测框架接入 CI：**每次改动都跑一遍评测集，准确率回退或安全用例失败就阻断发布。**

```python
# scripts/eval_gate.py
"""CI 评测回归门禁：当前 vs 基线，回退即失败退出（退出码非 0 阻断流水线）"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASELINE_PATH = Path("eval/baseline.json")
CURRENT_PATH = Path("eval/current.json")
MAX_ACCURACY_DROP = 0.02  # 总体准确率允许的最大回退


def load_report(path: Path) -> dict:
    """加载评测报告（由 pytest 或评测脚本产出）"""
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if not BASELINE_PATH.exists() or not CURRENT_PATH.exists():
        print("missing eval reports; skip gate")
        return 0

    baseline = load_report(BASELINE_PATH)
    current = load_report(CURRENT_PATH)

    base_acc = baseline["accuracy"]
    curr_acc = current["accuracy"]
    base_fail = {item["id"] for item in baseline["failures"]}
    curr_fail = {item["id"] for item in current["failures"]}
    regressions = sorted(curr_fail - base_fail)

    print(f"baseline accuracy : {base_acc:.2%}")
    print(f"current  accuracy : {curr_acc:.2%}")
    print(f"regressions       : {regressions}")

    if curr_acc < base_acc - MAX_ACCURACY_DROP or regressions:
        print("EVAL REGRESSION DETECTED -> blocking release")
        return 1

    print("eval gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

> ⚠️ **为什么必须有这道门禁**：Prompt、工具、模型、检索策略的任何改动都可能让效果回退。**没有评测门禁的 CI，只保证"代码能跑"，不保证"效果没退"。**

---

## 四、GitHub Actions 流水线

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - name: Install dev dependencies
        run: uv pip install --system ruff mypy
      - name: Ruff
        run: ruff check .
      - name: Mypy
        run: mypy . --ignore-missing-imports

  test:
    name: Unit Tests
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest tests/ --cov=. --cov-report=xml --cov-report=term -q
      - name: Upload coverage
        uses: codecov/codecov-action@v5
        with:
          files: ./coverage.xml

  eval-gate:
    name: Eval Regression Gate
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest
      - name: Run evaluation set
        env:
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          LLM_MODEL_NAME: gpt-5.5
        run: pytest tests/test_eval.py -q   # 产出 eval/current.json
      - name: Check regression against baseline
        run: python scripts/eval_gate.py

  build:
    name: Build & Push Image
    needs: eval-gate
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ${{ secrets.DOCKER_USERNAME }}/agent-api:latest
            ${{ secrets.DOCKER_USERNAME }}/agent-api:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

> 💡 用 `needs:` 串起"质量 → 测试 → 评测 → 构建"，任何一环失败都不会进入下一环，避免把回归版本推上线。

---

## 五、部署：灰度发布与回滚

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  workflow_run:
    workflows: ["CI"]
    types: [completed]
    branches: [main]

jobs:
  staging:
    name: Deploy to Staging
    if: github.event.workflow_run.conclusion == 'success'
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Roll out to staging
        uses: appleboy/ssh-action@v1.2.0
        with:
          host: ${{ secrets.STAGING_HOST }}
          username: ${{ secrets.STAGING_USER }}
          key: ${{ secrets.STAGING_SSH_KEY }}
          script: |
            cd /opt/agent-api
            export IMAGE_TAG=${{ github.event.workflow_run.head_sha }}
            docker compose pull
            docker compose up -d
            ./scripts/smoke_test.sh http://localhost:8000

  production:
    name: Canary then Full Release
    needs: staging
    runs-on: ubuntu-latest
    environment: production        # 在仓库 Settings → Environments 配置人工审批
    steps:
      - name: Canary rollout (10%)
        uses: appleboy/ssh-action@v1.2.0
        with:
          host: ${{ secrets.PROD_HOST }}
          username: ${{ secrets.PROD_USER }}
          key: ${{ secrets.PROD_SSH_KEY }}
          script: |
            cd /opt/agent-api
            export IMAGE_TAG=${{ github.event.workflow_run.head_sha }}
            ./scripts/canary.sh 10 300   # 放量 10%，观察 300 秒
      - name: Full rollout
        uses: appleboy/ssh-action@v1.2.0
        with:
          host: ${{ secrets.PROD_HOST }}
          username: ${{ secrets.PROD_USER }}
          key: ${{ secrets.PROD_SSH_KEY }}
          script: |
            cd /opt/agent-api
            ./scripts/canary.sh 100 0
```

```bash
#!/usr/bin/env bash
# scripts/canary.sh: shift traffic weight, watch metrics, auto rollback on failure
set -euo pipefail

WEIGHT="${1:?weight percent required}"
OBSERVE_SECONDS="${2:-0}"
API="http://localhost:8000"

# 1) Shift traffic to the new version
echo "shifting ${WEIGHT}% traffic to new version"
# (illustrative: update nginx upstream weight or a service mesh rule here)

# 2) Observe metrics for the given window
if [ "${OBSERVE_SECONDS}" -gt 0 ]; then
  echo "observing for ${OBSERVE_SECONDS}s ..."
  sleep "${OBSERVE_SECONDS}"
  ERROR_RATE=$(curl -s "${API}/metrics" | grep -c "status=\"error\"" || true)
  if [ "${ERROR_RATE}" -gt 5 ]; then
    echo "error budget exceeded, rolling back"
    ./scripts/rollback.sh
    exit 1
  fi
fi

echo "canary ok at ${WEIGHT}%"
```

```bash
#!/usr/bin/env bash
# scripts/rollback.sh: switch back to the previous known-good image tag
set -euo pipefail

PREV_TAG="$(cat .last_good_tag 2>/dev/null || echo latest)"
echo "rolling back to ${PREV_TAG}"

cd /opt/agent-api
export IMAGE_TAG="${PREV_TAG}"
docker compose pull
docker compose up -d
./scripts/smoke_test.sh http://localhost:8000
echo "rollback complete"
```

> 💡 **回滚三原则**：① 镜像**不可变**（用 git sha 打 tag，别只依赖 `latest`）；② 记录"上一个已知良好版本"（`.last_good_tag`）；③ 回滚后自动跑**冒烟测试**确认恢复。

---

## 六、环境与密钥

GitHub 的**环境（Environments）在仓库 Settings → Environments 中配置**，不是 YAML 文件。建议：

| 环境 | 审批 | 变量 / 密钥 |
|------|------|-------------|
| **development** | 无 | `LLM_MODEL_NAME=gpt-5.5`，`LOG_LEVEL=debug` |
| **staging** | 无 | 独立 `LLM_API_KEY`（限额），`LOG_LEVEL=info` |
| **production** | **需人工审批** | 生产密钥，`LOG_LEVEL=warning` |

| 注意点 | 最佳实践 |
|--------|----------|
| **API Key** | 存 GitHub Secrets，绝不硬编码 |
| **测试成本** | 单元测试用 Mock；评测集用小样本 |
| **构建缓存** | `cache-from/to: type=gha` |
| **回滚** | 保留上一版本镜像 + `.last_good_tag` |
| **最小权限** | Actions 默认 `permissions: read-all`，按需授权 |

---

## 七、本章小结

| 环节 | 工具 / 方法 | 说明 |
|------|-------------|------|
| **代码检查** | Ruff + Mypy | 风格与类型门禁 |
| **测试** | pytest + codecov | 单元测试与覆盖率 |
| **评测门禁** | `eval_gate.py` | 回归即阻断（Agent 专属） |
| **构建** | Docker Buildx | 多架构、带缓存 |
| **CI** | GitHub Actions | `needs:` 串联各阶段 |
| **CD** | 灰度 → 观察 → 全量 / 回滚 | 可回滚的发布 |

---

## 📝 课后练习

1. **✅ 基础**：为你的仓库配置 `.github/workflows/ci.yml`，跑通 lint + test。
2. **💡 改进**：把评测集接入 CI，产出 `eval/current.json` 并运行 `eval_gate.py`。
3. **🚀 挑战**：实现 `canary.sh` 与 `rollback.sh`，模拟一次"灰度失败 → 自动回滚"。
4. **🔍 探索**：用 matrix 策略在 Python 3.12 / 3.13 上并行跑测试。
