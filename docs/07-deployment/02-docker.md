# 7.2 Docker 容器化 —— 一次构建，到处运行

## 📖 导读

> **"在我机器上能跑"是一个开发者的噩梦。"在任何机器上都能跑"才是一个合格的交付。**

Docker 容器化解决了"环境不一致"这个最让人头疼的问题。通过将 Agent 应用及其依赖打包到一个轻量级的容器中，你可以确保：**在本地能运行的程序，在服务器上、在同事机器上、在云上也一样能运行**。

---

## 一、前置知识

| 概念 | 说明 |
|------|------|
| Docker | 容器化平台，将应用和依赖打包 |
| 镜像（Image） | 应用的打包快照，只读 |
| 容器（Container） | 镜像的运行实例 |
| Dockerfile | 定义如何构建镜像的脚本 |
| docker-compose | 多容器编排工具 |

---

## 二、为什么需要容器化？

```text
❌ 没有容器化的痛点：

开发者 A: "我用 Python 3.12，装好包就能跑"
开发者 B: "我用 Python 3.10，报错了..."
运维: "我们服务器是 CentOS，没有 Python 3.12"

每个环境都要手动配置 → 耗时、易错、不兼容

✅ 容器化后的好处：

开发者: 编写 Dockerfile → 构建镜像 → 推送
运维: 拉取镜像 → 运行容器

2 步搞定，环境完全一致！
```

---

## 三、为 Agent 创建 Dockerfile

### 3.1 基础 Dockerfile

```dockerfile
# ===== 多阶段构建 =====

# 阶段一：依赖安装
FROM python:3.12-slim AS builder

WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 先复制依赖文件，利用 Docker 缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# 阶段二：运行
FROM python:3.12-slim

WORKDIR /app

# 从 builder 阶段复制已安装的包
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY . .

# 创建非 root 用户（安全最佳实践）
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3.2 优化版 Dockerfile（生产推荐）

```dockerfile
# 使用更小的基础镜像
FROM python:3.12-alpine AS builder

WORKDIR /app

# 安装编译依赖
RUN apk add --no-cache gcc musl-dev linux-headers

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


FROM python:3.12-alpine

WORKDIR /app

# 只复制需要的运行时库
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用
COPY . .

# 非 root 用户
RUN adduser -D appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 3.3 .dockerignore

```text
# .dockerignore - 排除不需要的文件，减小镜像体积
__pycache__/
*.pyc
*.pyo
.env
.git/
.gitignore
.vscode/
.idea/
*.md
tests/
notebooks/
chroma_db/  # 向量数据库数据（太大了）
kb_data/
*.db
*.sqlite3
Dockerfile
.dockerignore
```

---

## 四、构建和运行

### 4.1 构建镜像

```bash
# 构建镜像
docker build -t agent-api:latest .

# 查看镜像
docker images

# 构建并指定平台（重要：M1/M2 Mac 构建给 Linux 服务器）
docker build --platform linux/amd64 -t agent-api:latest .
```

### 4.2 运行容器

```bash
# 基本运行
docker run -p 8000:8000 agent-api:latest

# 后台运行
docker run -d --name agent-service -p 8000:8000 agent-api:latest

# 挂载配置（传递 API Key）
docker run -d --name agent-service \
  -p 8000:8000 \
  -e OPENAI_API_KEY="sk-xxx" \
  -e LLM_MODEL_NAME="gpt-4o-mini" \
  -v /data/kb_data:/app/kb_data \  # 持久化知识库数据
  agent-api:latest
```

### 4.3 常用 Docker 命令

```bash
# 查看运行中的容器
docker ps

# 查看日志
docker logs agent-service
docker logs -f agent-service  # 实时查看

# 进入容器内部
docker exec -it agent-service /bin/sh

# 停止和删除
docker stop agent-service
docker rm agent-service

# 查看资源占用
docker stats agent-service
```

---

## 五、Docker Compose 多服务编排

当你的 Agent 系统依赖多个服务（如 Redis、PostgreSQL、向量数据库）时，使用 `docker-compose.yml` 统一管理：

```yaml
# docker-compose.yml
version: "3.8"

services:
  # Agent API 服务
  agent-api:
    build:
      context: .
      dockerfile: Dockerfile
    image: agent-api:latest
    container_name: agent-api
    restart: always
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - LLM_MODEL_NAME=gpt-4o-mini
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_URL=postgresql://user:pass@postgres:5432/agent
    volumes:
      - ./kb_data:/app/kb_data
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    networks:
      - agent-network
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Redis（会话存储）
  redis:
    image: redis:7-alpine
    container_name: agent-redis
    restart: always
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - agent-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  # PostgreSQL（持久化存储）
  postgres:
    image: postgres:16-alpine
    container_name: agent-postgres
    restart: always
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: agent
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - agent-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d agent"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Qdrant（向量数据库，替代 Chroma）
  qdrant:
    image: qdrant/qdrant:latest
    container_name: agent-qdrant
    restart: always
    ports:
      - "6333:6333"
    volumes:
      - qdrant-data:/qdrant/storage
    networks:
      - agent-network

  # Nginx（反向代理）
  nginx:
    image: nginx:alpine
    container_name: agent-nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - agent-api
    networks:
      - agent-network

volumes:
  redis-data:
  postgres-data:
  qdrant-data:

networks:
  agent-network:
    driver: bridge
```

### 启动多服务

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f agent-api

# 停止所有服务
docker-compose down

# 停止并删除数据卷
docker-compose down -v
```

---

## 六、镜像体积优化

| 优化技巧 | 优化前 | 优化后 | 效果 |
|----------|--------|--------|------|
| 使用 slim/alpine 基础镜像 | 1.2GB | 400MB | -67% |
| 多阶段构建 | 800MB | 400MB | -50% |
| .dockerignore | 800MB | 650MB | -19% |
| 只装必要依赖 | 800MB | 500MB | -37% |
| **综合优化** | **1.2GB** | **~350MB** | **-71%** |

```bash
# 查看镜像分层
docker history agent-api:latest

# 查看镜像大小
docker images agent-api:latest
```

---

## 七、CI/CD 集成

```yaml
# .github/workflows/docker-build.yml
name: Build and Push Docker Image

on:
  push:
    branches: [main]
    tags: ["v*"]

jobs:
  build:
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
          push: true
          tags: |
            yourusername/agent-api:latest
            yourusername/agent-api:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

---

## 八、本章总结

| 步骤 | 命令/操作 | 说明 |
|------|-----------|------|
| **编写 Dockerfile** | 多阶段构建 | 减小镜像体积 |
| **构建镜像** | `docker build -t agent-api .` | 打包应用 |
| **本地测试** | `docker run -p 8000:8000 agent-api` | 验证运行 |
| **多服务编排** | `docker-compose up -d` | 启动整套环境 |
| **部署** | 推送到镜像仓库 → 服务器拉取运行 | 生产交付 |

---

## 📝 课后练习

1. **✅ 基础**：为你的 Agent 项目编写 Dockerfile 并成功构建镜像
2. **💡 改进**：添加 docker-compose.yml，包含 Agent + Redis 两服务
3. **🚀 挑战**：使用 GitHub Actions 自动构建 Docker 镜像并推送到 Docker Hub
4. **🔍 探索**：对比 alpine 和 slim 基础镜像的体积差异，以及各自的问题
