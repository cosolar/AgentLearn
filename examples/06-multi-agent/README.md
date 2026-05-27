# 示例 06: 多 Agent 协作

## 📖 说明

展示多个 Agent 如何分工协作完成复杂任务。

## 团队结构

```
TeamManager (管理者)
    │
    ├── Researcher (研究员) - 信息收集
    ├── Writer (作家) - 内容创作
    └── Reviewer (审查员) - 质量检查
```

## 运行

```bash
python examples/06-multi-agent/main.py
```

## 工作流程

1. 📋 管理者分解任务
2. 🔍 研究员收集信息
3. ✍️ 作家撰写内容
4. 🔍 审查员检查质量
5. 📄 输出最终成果
