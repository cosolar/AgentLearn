# 📖 HiClaw 实践教程

> **HiClaw** — 基于 Kubernetes 原生理念的多 Agent 协作编排平台。  
> Manager 统一调度多个 Worker，人类全程可见、随时可介入。

<p align="center">
  <img src="https://img.alicdn.com/imgextra/i4/O1CN01c1VlDE1zYZ46EW3OA_!!6000000006726-49-tps-9895-8231.webp" width="600" alt="HiClaw 架构图" />
</p>

---

## 🧭 学习路径

教程分为 **四个阶段**，建议按顺序学习：

| 阶段 | 包含文档 | 学习目标 |
|:----:|----------|----------|
| 🟢 **上手** | ① 快速开始 → ② Windows 部署 | 5 分钟内跑起来，创建第一个 Worker |
| 🔵 **理解** | ③ 系统架构 → ④ K8s 原生编排 → ⑤ 声明式资源管理 | 理解系统设计理念和资源模型 |
| 🟠 **运维** | ⑥ Manager 指南 → ⑦ Worker 指南 → ⑧ CMS 集成 → ⑨ 钉钉集成 → ⑩ 导入 Worker | 日常配置、监控、集成 |
| 🔴 **进阶** | ⑪ 开发指南 → ⑫ 常见问题 | 本地开发、镜像构建、故障排查 |

---

## 📚 教程目录

### 🟢 第一阶段：上手体验

| # | 文档 | 内容 | 预计时间 |
|:-:|:----|:-----|:---------|
| ① | [快速开始](quickstart.md) | 安装 Manager → 创建 Worker Alice → 分配任务 → 人工介入 → 多 Worker 协作 → MCP GitHub 操作 | 15 分钟 |
| ② | [Windows 部署手册](windows-deploy.md) | Windows 平台详细安装步骤（Docker Desktop → 安装脚本 → 配置选择 → Element Web 登录） | 20 分钟 |

### 🔵 第二阶段：深入理解

| # | 文档 | 内容 | 预计时间 |
|:-:|:----|:-----|:---------|
| ③ | [系统架构](architecture.md) | 多容器架构、组件关系、通信机制（Matrix / MinIO / Higress）、运行时模型、Skills 系统 | 20 分钟 |
| ④ | [K8s 原生多 Agent 编排](k8s-native-agent-orch.md) | 三层组织架构、CRD 设计、Controller 架构、安全模型、与 NemoClaw 对比 | 30 分钟 |
| ⑤ | [声明式资源管理](declarative-resource-management.md) | Worker / Team / Manager / Human 四种 CRD 详解、YAML 批量部署、CLI / HTTP API、服务发布、通信策略 | 30 分钟 |

### 🟠 第三阶段：运维管理

| # | 文档 | 内容 | 预计时间 |
|:-:|:----|:-----|:---------|
| ⑥ | [Manager 指南](manager-guide.md) | 环境变量配置、QwenPaw Manager、多渠道通信（Discord/钉钉/Telegram）、会话管理、监控、备份恢复、YOLO 模式 | 20 分钟 |
| ⑦ | [Worker 指南](worker-guide.md) | 部署方式（直接创建 / Docker Run）、故障排查、生命周期管理、文件同步、配置热重载 | 15 分钟 |
| ⑧ | [接入 CMS 可观测性](cms-integration.md) | OpenTelemetry 接入阿里云 CMS 2.0，追踪 Agent 请求链路和 Token 消耗 | 10 分钟 |
| ⑨ | [钉钉机器人配置](dingtalk-setup-guide.md) | 钉钉开发者平台配置、OpenClaw 插件安装、Channel 配置、AI 互动卡片 | 20 分钟 |
| ⑩ | [导入 Worker 指南](import-worker.md) | 声明式 YAML 管理、Worker 包格式、迁移独立 OpenClaw、导入 Worker 模板 | 15 分钟 |

### 🔴 第四阶段：开发与故障排查

| # | 文档 | 内容 | 预计时间 |
|:-:|:----|:-----|:---------|
| ⑪ | [开发指南](development.md) | 项目结构、本地构建镜像、安装/测试/CI/CD、代理配置、容器运行时集成、调试技巧 | 30 分钟 |
| ⑫ | [常见问题](faq.md) | CLI 管理、模型切换、运行时切换、故障排查、会话管理、对接 IM | — |

---

## 🎯 快速入口

| 目标 | 操作 |
|:----|:-----|
| 🚀 我想直接试用 | → [快速开始](quickstart.md) |
| 🪟 我在 Windows 上 | → [Windows 部署](windows-deploy.md) |
| 🏗️ 我想理解架构 | → [系统架构](architecture.md) |
| 📋 我想用 YAML 管理资源 | → [声明式资源管理](declarative-resource-management.md) |
| 💬 我想接入钉钉 | → [钉钉集成](dingtalk-setup-guide.md) |
| 🔧 我想参与开发 | → [开发指南](development.md) |
| ❓ 遇到问题 | → [常见问题](faq.md) |

---

## 📌 设计文档

以下为内部设计文档，供架构了解：

- [Team Worker 提案](design/team-worker-proposal.md)
- [HiClaw Controller 重构](design/hiclaw-controller-refactor.md)
- [重构进度追踪](design/hiclaw-controller-refactor-progress.md)

---

## 🏘️ 社区

| 渠道 | 链接 |
|:----|:-----|
| 💬 Discord | [Join](https://discord.gg/NVjNA4BAVw) |
| 📱 钉钉群 | [扫描加入](https://qr.dingtalk.com/action/joingroup?code=v1,k1,OPhRSPWeie5/IMWQkyrCI34IqMdl/h/6ObYHKKzZJCI=&_dt_no_comment=1&origin=11) |
| 📢 微信群 | 社区群请扫描官方二维码加入 |

## 📄 许可证

Apache License 2.0
