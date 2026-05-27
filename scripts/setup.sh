#!/bin/bash
# AgentLearn 环境设置脚本

set -e

echo "🤖 AgentLearn - 环境设置"
echo "=========================="

# 检查 Python
if ! command -v python &> /dev/null; then
    echo "❌ 未找到 Python，请先安装 Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$(python --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✅ Python 版本: $PYTHON_VERSION"

# 检查 uv
if ! command -v uv &> /dev/null; then
    echo "⚠️  未找到 uv，正在安装..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "✅ uv 版本: $(uv --version)"

# 创建虚拟环境
echo ""
echo "📦 创建虚拟环境..."
uv sync

# 复制环境变量
if [ ! -f .env ]; then
    echo ""
    echo "⚠️  未找到 .env 文件，请复制 .env.example 并配置"
    echo "   cp .env.example .env"
    echo "   # 然后编辑 .env 填入 API Key"
else
    echo "✅ 已找到 .env 文件"
fi

echo ""
echo "🎉 环境设置完成！"
echo ""
echo "下一步："
echo "  1. 配置 .env 文件中的 API Key"
echo "  2. 运行示例: python examples/01-hello-agent/main.py"
