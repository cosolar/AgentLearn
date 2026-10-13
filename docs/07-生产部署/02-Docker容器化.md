# 7.2 Docker 容器化 —— 一次构建，到处运行

> 📅 更新至 2026-10 · 技术栈基线见 [知识库大纲](../知识库大纲.md)

## 📖 导读

> **"在我机器上能跑"是开发者的噩梦，"在任何机器上都能跑"才是合格交付。**

Docker 把 Agent 应用及其依赖打包进一个轻量容器，彻底解决"环境不一致"。本章用**多阶段构建 + `uv`** 打造一个小巧、安全的镜像，用 **Compose**（无 `version:` 字段的现代写法）编排多服务，并讲清**镜像瘦身**与**密钥管理**。

---

## 一、前置知识

| 概念 | 说明 |
|------|------|
| 镜像（Image） | 应用的只读打包快照 |
| 容器（Container） | 镜像的运行实例 |
| Dockerfile | 定义镜像构建步骤 |
| Docker Compose | 多容器编排 |
| `uv` | 极快的 Python 包 / 环境管理器 |

---

## 二、为什么需要容器化

```text
❌ 没有容器化：
开发者 A：我用 Python 3.12，装好包就能跑
开发者 B：我用 3.10，报错了……
运维：我们服务器没有 Python 3.12
每个环境手动配置 → 耗时、易错、不一致

✅ 容器化后：
构建镜像 → 推送 → 任意机器拉取运行
环境完全一致，2 步搞定
```

---

## 三、Dockerfile：多阶段构建

```dockerfile
# syntax=docker/dockerfile:1.7

# ---------- Stage 1: builder ----------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt ./
RUN uv venv /opt/venv && \
    VIRTUAL_ENV=/opt/venv uv pip install --no-cache -r requirements.txt

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy the virtualenv from builder (no compiler toolchain in final image)
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY . .

# Run as a non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> 💡 **多阶段构建的收益**：编译期工具（gcc、头文件）只存在于 `builder` 阶段，最终镜像只保留 `venv` 与应用代码，体积和攻击面都显著减小。

---

## 四、`.dockerignore`

```text
__pycache__/
*.py[cod]
.venv/
venv/
.env
.env.*
!.env.example
.git/
.gitignore
.idea/
.vscode/
tests/
*.md
Dockerfile
docker-compose.yml
.dockerignore
chroma_db/
kb_data/
*.sqlite3
```

> ⚠️ **务必排除 `.env`**：否则密钥会被"烧"进镜像层，即使后续删除也能被还原。

---

## 五、构建与运行

```bash
# Build the image
docker build -t agent-api:1.0.0 .

# Build for linux/amd64 (e.g. from Apple Silicon)
docker build --platform linux/amd64 -t agent-api:1.0.0 .

# Run with an env file (never pass secrets on the command line in production)
docker run -d --name agent-api --env-file .env -p 8000:8000 agent-api:1.0.0

# Inspect
docker ps
docker logs -f agent-api
docker stats agent-api

# Stop and remove
docker stop agent-api && docker rm agent-api
```

---

## 六、Docker Compose 多服务编排

> 📌 现代 Compose 规范**不再需要 `version:` 字段**，直接以 `services:` 开头。

```yaml
# docker-compose.yml
services:
  agent-api:
    build:
      context: .
      dockerfile: Dockerfile
    image: agent-api:1.0.0
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      REDIS_URL: redis://redis:6379/0
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 1g
    networks:
      - agent-net

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - agent-net

volumes:
  redis-data:

networks:
  agent-net:
    driver: bridge
```

```bash
# Start all services
docker compose up -d

# Status and logs
docker compose ps
docker compose logs -f agent-api

# Stop (keep volumes) / stop and wipe data
docker compose down
docker compose down -v
```

---

## 七、镜像瘦身

| 手段 | 说明 | 典型收益 |
|------|------|----------|
| **`slim` 基础镜像** | 比完整镜像小很多 | −60%+ |
| **多阶段构建** | 编译工具不进最终镜像 | −40%+ |
| **`.dockerignore`** | 不把无关文件打进去 | −10%~−20% |
| **依赖最小化** | 只装运行时必需 | −30%+ |
| **合并 RUN 层** | 减少镜像层数与缓存 | 少量 |

```bash
# Inspect layer sizes
docker history agent-api:1.0.0

# Show final image size
docker images agent-api:1.0.0
```

> 💡 **优先 `slim` 而非 `alpine`**：`alpine` 更小，但使用 musl libc，部分含 C 扩展的包（如某些科学计算库）需重新编译甚至不兼容。Agent 项目依赖较杂，`slim` 更稳妥。

---

## 八、密钥管理

| 场景 | 做法 |
|------|------|
| **本地开发** | `.env` 文件（加入 `.gitignore`），用 `--env-file` 注入 |
| **CI/CD** | GitHub Secrets / 平台密钥库，构建时通过环境变量注入 |
| **生产（单机）** | Docker secrets / 挂载只读密钥文件 |
| **生产（编排）** | Kubernetes Secret / 云厂商 Secret Manager |

```yaml
# Production example: inject secrets via Docker secrets
services:
  agent-api:
    secrets:
      - llm_api_key
    environment:
      LLM_API_KEY_FILE: /run/secrets/llm_api_key

secrets:
  llm_api_key:
    external: true
```

```python
# 应用侧：优先读取 *_FILE 指向的密钥文件
import os
from pathlib import Path


def read_secret(env_name: str) -> str:
    """从 <NAME>_FILE 指定的文件读取，回退到 <NAME> 环境变量"""
    file_path = os.getenv(f"{env_name}_FILE")
    if file_path and Path(file_path).exists():
        return Path(file_path).read_text(encoding="utf-8").strip()
    return os.getenv(env_name, "")
```

> ⚠️ **三条铁律**：① 密钥绝不写进镜像或代码；② 绝不通过命令行参数传递密钥（会留在 shell 历史与 `ps` 中）；③ 镜像仓库设为私有。

---

## 九、在 CI 中构建镜像

```yaml
# .github/workflows/docker.yml (snippet; full pipeline in 7.4)
jobs:
  build:
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

> 📌 完整的测试门禁、评测回归与灰度发布见 [7.4 CI/CD 流水线](./04-CICD流水线.md)。

---

## 十、本章小结

| 环节 | 命令 / 做法 | 说明 |
|------|-------------|------|
| **编写 Dockerfile** | 多阶段 + `uv` | 体积小、构建快 |
| **构建镜像** | `docker build -t agent-api:1.0.0 .` | 打包应用 |
| **本地验证** | `docker run --env-file .env -p 8000:8000` | 不硬编码密钥 |
| **多服务编排** | `docker compose up -d` | 无 `version:` 字段 |
| **密钥管理** | `.env` / secrets / `*_FILE` | 密钥永不进镜像 |
| **瘦身** | slim + 多阶段 + `.dockerignore` | 降体积、降攻击面 |

---

## 📝 课后练习

1. **✅ 基础**：为你的 Agent 项目写 Dockerfile 并成功构建镜像。
2. **💡 改进**：添加 `docker-compose.yml`（Agent + Redis），验证健康检查与依赖顺序。
3. **🚀 挑战**：用 Docker secrets 注入 `LLM_API_KEY`，并在应用侧用 `read_secret` 读取。
4. **🔍 探索**：对比 `python:3.12-slim` 与 `python:3.12-alpine` 的体积与依赖兼容性差异。
