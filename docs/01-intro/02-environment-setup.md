# 1.2 开发环境搭建 —— 从零配置完整的 Agent 开发环境

## 📖 导读

工欲善其事，必先利其器。一个干净、高效的开发环境是学习 Agent 开发的基础。本文将从 **Python 安装 → 包管理 → 项目克隆 → 依赖安装 → API Key 配置 → IDE 设置** 全流程手把手教你搭建环境。**无论你用的是 macOS、Windows 还是 Linux，都能找到对应的详细步骤。**

---

## 一、开发环境概览

### 1.1 我们需要什么？

| 组件 | 版本要求 | 用途 |
|------|----------|------|
| Python | 3.10+（推荐 3.11/3.12） | Agent 开发语言 |
| uv | 0.2+ | 超快速 Python 包管理器 |
| Git | 2.0+ | 代码版本管理 |
| VS Code | 最新版 | 代码编辑器（推荐） |
| API Key | 有效 | 调用 LLM 服务 |

### 1.2 为什么使用 uv 而不是 pip？

| 对比项 | pip | uv |
|--------|-----|-----|
| **速度** | 较慢（串行下载） | **快 10–100 倍**（并行下载+缓存） |
| **依赖解析** | 标准 | **更快更准** |
| **虚拟环境** | venv 单独管理 | **内置虚拟环境管理** |
| **锁文件** | 需要 pip-tools | **原生支持 uv.lock** |
| **安装方式** | pip install | 可执行文件，**无需 Python 即可安装** |

---

## 二、前置检查

在开始安装前，先检查你系统上已有的工具：

```bash
# 检查是否已有 Python（Windows 用 cmd，macOS/Linux 用 terminal）
python --version
# 或
python3 --version

# 检查是否已有 Git
git --version

# 检查是否已有 VS Code
code --version
```

> ⚠️ **注意**：macOS 自带 Python 2.x（已废弃），需额外安装 Python 3.x。

---

## 三、各系统详细安装步骤

### 3.1 安装 Python

#### macOS

**方法一：Homebrew（推荐）**

```bash
# 安装 Homebrew（如果没有）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装 Python 3.11
brew install python@3.11

# 验证
python3 --version
# 输出: Python 3.11.x

# 找到安装路径（后续 uv 可能需要）
which python3
# 输出: /opt/homebrew/bin/python3  （Apple Silicon）
# 或:   /usr/local/bin/python3     （Intel）
```

**方法二：pyenv（多版本管理，推荐进阶用户）**

```bash
# 安装 pyenv
curl https://pyenv.run | bash

# 在 ~/.zshrc 中添加（如果自动配置未生效）
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"

# 安装 Python 3.11
pyenv install 3.11.8
pyenv global 3.11.8

# 验证
python --version
```

#### Windows

**方法一：官网安装（推荐初学者）**

1. 访问 [Python 官网下载页](https://www.python.org/downloads/)
2. 点击 **Download Python 3.11.x**（不要下载 3.13，部分库兼容性可能有问题）
3. 运行安装程序
4. **⚠️ 关键步骤**：务必勾选底部的 **"Add Python to PATH"**（见下图）
5. 点击 **"Install Now"**

6. 安装完成后验证：
```cmd
# 打开新命令提示符
python --version
# 输出: Python 3.11.x

pip --version
# 输出: pip 23.x from ...
```

**方法二：Microsoft Store（替代方案）**

1. 打开 Microsoft Store
2. 搜索 "Python 3.11"
3. 选择由 Python Software Foundation 发布的版本
4. 点击安装
5. 验证同上

> 💡 **推荐用官网安装**，Store 版的路径比较特殊，后续配置 uv 可能遇到权限问题。

#### Linux（Ubuntu/Debian）

```bash
# 更新包索引
sudo apt update

# 安装依赖
sudo apt install -y build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev curl \
    libncursesw5-dev xz-utils tk-dev libxml2-dev \
    libxmlsec1-dev libffi-dev liblzma-dev

# 方法一：apt 直接安装（版本可能较旧）
sudo apt install -y python3.11 python3.11-venv python3-pip

# 方法二：pyenv（推荐，可指定精确版本）
curl https://pyenv.run | bash
pyenv install 3.11.8
pyenv global 3.11.8

# 验证
python3 --version
```

---

### 3.2 安装 uv

#### macOS / Linux

```bash
# 官方安装命令
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装完成后，重启终端或执行：
source ~/.bashrc   # 如果使用 bash
# 或
source ~/.zshrc    # 如果使用 zsh（macOS 默认）

# 验证
uv --version
# 输出: uv 0.2.x (xxxxxxx 2024-xx-xx)
```

#### Windows

**方法一：PowerShell（推荐）**

```powershell
# 以管理员身份打开 PowerShell，执行：
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**方法二：pip 安装（备选）**

```cmd
pip install uv
```

**方法三：手动下载**

1. 访问 [uv 的 GitHub Releases 页面](https://github.com/astral-sh/uv/releases)
2. 下载 `uv-x86_64-pc-windows-msvc.zip`
3. 解压到 `C:\uv`
4. 将 `C:\uv` 添加到系统 PATH 环境变量

验证安装：

```cmd
uv --version
```

---

### 3.3 安装和配置 Git

#### macOS

```bash
# 方法一：Homebrew
brew install git

# 方法二：Xcode Command Line Tools（自带 git）
xcode-select --install
```

#### Windows

1. 访问 [Git 官网](https://git-scm.com/download/win)
2. 下载安装程序
3. 安装时保持默认选项，**注意"调整 PATH 环境变量"处选择"从命令行使用 Git"**
4. 安装完成后验证：

```cmd
git --version
```

#### Linux

```bash
sudo apt install -y git
```

#### 配置 Git（所有系统通用）

```bash
# 设置用户名和邮箱（替换成你的信息）
git config --global user.name "你的名字"
git config --global user.email "your@email.com"

# 推荐：设置默认分支名为 main
git config --global init.defaultBranch main

# 验证配置
git config --list
```

---

### 3.4 克隆项目并安装依赖

#### 克隆 AgentLearn 仓库

```bash
# 使用 HTTPS（推荐初学者）
git clone https://gitcode.com/mininote/AgentLearn.git
cd AgentLearn

# 或者使用 SSH（需要先配置 SSH Key）
git clone git@gitcode.com:mininote/AgentLearn.git
cd AgentLearn
```

#### 查看项目结构

```
AgentLearn/
├── docs/                    # 教程文档
│   ├── 01-intro/           # 第一章
│   ├── 02-fundamentals/    # 第二章
│   └── ...
├── examples/               # 配套示例代码
│   ├── 01-hello-agent/     # 第一个 Agent
│   ├── 02-chat-agent/      # 聊天 Agent
│   └── ...
├── pyproject.toml          # 项目依赖配置（uv 使用）
├── uv.lock                 # 依赖锁定文件
└── .env.example            # 环境变量模板
```

#### 使用 uv 安装依赖

```bash
# 创建虚拟环境并安装所有依赖（一条命令）
uv sync

# 如果速度慢，可以使用国内镜像
# 设置环境变量 UV_INDEX_URL
# macOS/Linux:
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
uv sync

# Windows (cmd):
set UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
uv sync
```

`uv sync` 会做以下事情：

1. 读取 `pyproject.toml` 和 `uv.lock`
2. 创建一个名为 `.venv` 的虚拟环境
3. 并行下载所有依赖包
4. 激活虚拟环境

#### 激活虚拟环境

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (cmd)
.venv\Scripts\activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

激活后，终端提示符会变成 `(.venv)` 前缀：

```
(.venv) ➜  AgentLearn $
```

---

### 3.5 配置 API Key

本教程默认使用 OpenAI 兼容的 API。你需要准备一个 API Key。

#### 第一步：获取 API Key

| 服务商 | 获取地址 | 说明 |
|--------|----------|------|
| **OpenAI** | https://platform.openai.com/api-keys | 官方，需海外支付方式 |
| **国内代理** | 各种国内 API 代理服务 | 无需海外支付，价格实惠 |

> ⚠️ **建议**：国内开发者优先使用国内代理服务，网络延迟更低，支付更方便。

#### 第二步：配置环境变量

项目根目录下有一个 `.env.example` 文件，复制为 `.env`：

```bash
# macOS / Linux
cp .env.example .env

# Windows (cmd)
copy .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

然后编辑 `.env` 文件：

```env
# LLM API 配置
LLM_API_KEY=sk-your-api-key-here
LLM_BASE_URL=https://api.example.com/v1
LLM_MODEL_NAME=gpt-4o

# 可选配置
LANGCHAIN_TRACING_V2=false
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your-langsmith-key
LANGCHAIN_PROJECT=agent-guide
```

> 🔐 **安全提醒**：`.env` 文件包含敏感信息，已自动被 `.gitignore` 排除，**不会提交到 Git**。

#### 第三方步骤：验证配置是否生效

```bash
# 确保虚拟环境已激活
python examples/01-hello-agent/check_env.py
# 预期输出：
# ✅ Python 版本: 3.11.x
# ✅ 环境变量已加载
# ✅ API Key 存在 (sk-...xxxx)
# ✅ 基础 URL: https://api.example.com/v1
```

---

## 四、VS Code 配置推荐

### 4.1 安装 VS Code

| 系统 | 下载地址 |
|------|----------|
| **macOS** | https://code.visualstudio.com/ (下载 macOS 版) |
| **Windows** | https://code.visualstudio.com/ (下载 Windows 版) |
| **Linux** | `sudo snap install code --classic` 或官网下载 `.deb` |

### 4.2 推荐扩展

```json
{
  "必装扩展": [
    "Python (ms-python.python)",
    "Pylance (ms-python.vscode-pylance)",
    "GitLens (eamodio.gitlens)",
    "Markdown Preview Enhanced (shd101wyy.markdown-preview-enhanced)"
  ],
  "强烈推荐": [
    "Git Graph (mhutchie.git-graph)",
    "Error Lens (usernamehw.errorlens)",
    "Code Spell Checker (streetsidesoftware.code-spell-checker)",
    "Jupyter (ms-toolsai.jupyter)"
  ]
}
```

### 4.3 设置 Python 解释器

1. 按 `Cmd+Shift+P` (macOS) 或 `Ctrl+Shift+P` (Windows/Linux)
2. 输入 `Python: Select Interpreter`
3. 选择 `.venv` 下的解释器（路径类似 `./.venv/bin/python`）

---

## 五、常见问题排查

### ❌ Python 安装问题

**问题：`python` 命令找不到**

```bash
# macOS — 使用 python3 替代
python3 --version

# Windows — 重新安装，勾选 "Add Python to PATH"
# 或手动添加：
# 1. 找到 Python 安装目录（如 C:\Users\xxx\AppData\Local\Programs\Python\Python311）
# 2. 添加到系统 PATH 环境变量
```

**问题：多个 Python 版本冲突**

```bash
# 查看所有 Python
which python3
/usr/bin/python3        # 系统自带
/opt/homebrew/bin/python3.11  # Homebrew 安装
~/.pyenv/shims/python   # pyenv 安装

# 建议只保留一个，或使用 pyenv 统一管理
```

### ❌ uv 安装问题

**问题：`uv: command not found`**

```bash
# macOS/Linux — 重启终端，或手动添加 PATH
export PATH="$HOME/.local/bin:$PATH"

# Windows — 重新运行安装脚本，确保以管理员身份运行

# 或使用 pip 安装（备选）
pip install uv
```

**问题：uv 安装依赖很慢**

```bash
# 使用国内镜像
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 或设置环境变量（推荐，一劳永逸）
# macOS/Linux
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# Windows (cmd)
set UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

### ❌ API Key 问题

**问题：`AuthenticationError` 或 `401`**

```
openai.AuthenticationError: 
The api key is invalid or missing. 
Please check your API key.
```

排查步骤：
1. 检查 `.env` 文件是否存在，文件名是否正确（不是 `.env.txt`）
2. 检查 Key 是否完整复制，**不要有引号包裹**
3. 确认 API Key 仍有余额（登录服务商后台查看）
4. 确认 `LLM_BASE_URL` 是否正确（结尾是否为 `/v1`）

**问题：`ConnectionError` 或网络超时**

```
httpx.ConnectError: 
Connection refused by the server
```

解决方案：
- 国内网络访问 OpenAI 官方 API 需要科学上网
- 或切换为国内代理服务

### ❌ Git 问题

**问题：`Permission denied (publickey)`**

使用 SSH 方式时出现的常见错误。解决方案：

```bash
# 改用 HTTPS 方式克隆
git clone https://gitcode.com/mininote/AgentLearn.git

# 或配置 SSH Key（长期方案）
ssh-keygen -t ed25519 -C "your@email.com"
# 然后将 ~/.ssh/id_ed25519.pub 内容添加到 GitCode 后台
```

---

## 六、环境验证清单

完成所有步骤后，运行以下命令全面验证：

```bash
# 1. 检查 Python
python3 --version
# ✅ Python 3.11.x

# 2. 检查 uv
uv --version
# ✅ uv 0.2.x

# 3. 检查 Git
git --version
# ✅ git 2.x

# 4. 检查虚拟环境
which python
# ✅ 路径应是项目下的 .venv/bin/python

# 5. 检查依赖是否安装完成
uv pip list | grep langchain
# ✅ langchain, langchain-openai, langchain-community 等

# 6. 验证 API Key
python -c "from dotenv import load_dotenv; import os; load_dotenv(); key=os.getenv('LLM_API_KEY'); print('✅' if key else '❌'); print(f'Key preview: {key[:8]}...' if key else 'Key not found')"
```

如果以上 6 步全部通过，恭喜！你的 Agent 开发环境已完全就绪 🎉

---

## 七、本章总结

| 步骤 | 要做什么 | 验证命令 |
|------|----------|----------|
| 1️⃣ | 安装 Python 3.11+ | `python --version` |
| 2️⃣ | 安装 uv 包管理器 | `uv --version` |
| 3️⃣ | 安装 Git 并配置 | `git --version` && `git config --list` |
| 4️⃣ | 克隆项目 | `git clone ...` |
| 5️⃣ | 安装依赖 | `uv sync` |
| 6️⃣ | 配置 API Key | 编辑 `.env` |
| 7️⃣ | VS Code 配置 | 安装扩展 + 选择解释器 |

---

## 📝 课后练习

1. **✅ 必做**：成功运行 `python examples/01-hello-agent/check_env.py`（如果存在）或自己写一个小脚本来验证所有环境变量
2. **📋 记录**：把你的安装过程中遇到的报错和解决方式记录下来，这是最宝贵的学习资料
3. **🔍 探索**：了解 uv 的其他常用命令（`uv add`, `uv remove`, `uv build`, `uv tool run`）
4. **💡 拓展**：配置 VS Code 的 `settings.json`，让它在打开项目时自动激活虚拟环境
