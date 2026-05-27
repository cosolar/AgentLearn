#!/bin/bash
# AgentLearn 部署脚本

set -e

echo "🚀 AgentLearn - 部署"
echo "===================="

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 未找到 Docker，请先安装 Docker"
    exit 1
fi

# 构建镜像
echo ""
echo "📦 构建 Docker 镜像..."
docker build -t agentlearn:latest .

# 运行容器
echo ""
echo "🏃 启动容器..."
docker run -d \
    --name agentlearn \
    -p 8000:8000 \
    -e OPENAI_API_KEY=${OPENAI_API_KEY} \
    agentlearn:latest

echo ""
echo "🎉 部署完成！"
echo "访问: http://localhost:8000/docs"
