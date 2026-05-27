# Docsify 文档服务
FROM node:20-alpine

WORKDIR /app

# 安装 docsify-cli
RUN npm install -g docsify-cli

# 复制文档目录
COPY ../docs ./docs/

# 暴露端口
EXPOSE 3000

# 启动 docsify 服务
CMD ["npx", "docsify", "serve", "docs"]
