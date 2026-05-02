# 上下文交接

本文档记录初始规划、环境搭建和当前实现状态中的重要上下文，方便未来 Codex 会话不依赖聊天记录也能继续工作。

## 项目摘要

OpenTeacher 是一个面向教育公平的开源 AI 教师系统，目标是帮助教育资源不足地区的学生获得高质量教学。

用户希望系统表现为老师，而不仅是学习陪伴工具：

- 温暖但严格
- 严谨但绝不羞辱
- 专注推理，而不是倾倒答案
- 能谨慎记住学生
- 能通过教师编写的技能扩展

项目的首要目标不是商业变现。开源生态和公共声誉价值比短期商业化更重要。

## 核心产品决策

1. 架构上支持完整 K-12 方向，但先做深一个样板。
2. 用技能表达学科、教学任务和教师风格。
3. Teaching Skill 必须是结构化、可审核、可测试的 artifact，而不是一段 prompt。
4. 先做 Web 应用，因为用户更熟悉 Web 开发。
5. 后续加入教师和志愿者管理面板。
6. 长期学生记忆是核心差异化能力。

## 当前脚手架

仓库包含：

- Python FastAPI 后端
- React/Vite 前端
- PostgreSQL、后端、前端和可选中间件的 Docker Compose 配置
- 教师人格文档
- 记忆系统文档
- 技能编写文档
- 教学技能 schema 草案
- 初中数学一元一次方程示例技能
- `web/` 中的静态原型

## 环境历史

最早的本地工作区是 Windows Server 虚拟机。

Windows 上已经成功的事项：

- 后端依赖曾安装在 `backend/.venv`
- 前端依赖曾通过项目本地 pnpm 安装
- 后端测试和 lint 曾通过
- 前端 build 曾通过
- Git 和 GitHub CLI 曾安装
- GitHub 仓库已经创建并推送

Windows 上不可行的事项：

- Docker Desktop 可以安装
- Docker CLI 和 Compose 可以安装
- 但由于虚拟机没有嵌套虚拟化，Linux 容器无法运行
- WSL2 无法创建 VM

重要失败特征：

```text
Docker engine HTTP 500
HCS_E_HYPERV_NOT_INSTALLED
Hyper-V cannot be installed: The processor does not have required virtualization capabilities.
```

结论：

不要把 Windows Server 当作主要中间件主机。Docker 和中间件应运行在 Ubuntu 上。

## Ubuntu 设置历史

远程 Ubuntu 服务器已被准备为主要开发环境：

- 已确认 Ubuntu 24.04 amd64
- mihomo 安装在 `/usr/local/bin/mihomo`
- `/etc/mihomo/config.yaml` 来自用户提供的订阅
- 已创建并启用 `mihomo.service`
- 代理端口为安全起见只绑定本机：
  - HTTP：`127.0.0.1:7890`
  - SOCKS：`127.0.0.1:7891`
  - API：`127.0.0.1:9090`
- 到 Google 和 OpenAI 的代理测试曾成功
- 常用工具的全局代理环境变量已配置
- Node.js/npm 已通过 Ubuntu apt 安装
- Codex CLI 已通过 `npm install -g @openai/codex` 安装
- Codex CLI 已使用 ChatGPT 完成登录

## 安全说明

搭建过程中曾在聊天中提供过敏感值，包括 GitHub token、SSH 密码和代理订阅 URL。它们没有提交到仓库，但用户应当轮换这些值。

不要提交：

- OpenAI API key
- GitHub token
- SSH 密码
- 代理订阅
- mihomo 配置文件
- `.env` 文件

## 推荐开发流程

使用远程 Ubuntu 服务器作为真实开发环境：

```bash
git clone https://github.com/idchangyifan/openteacher.git
cd openteacher
codex
```

Mac 或其他本地机器只作为：

- 浏览器
- 终端
- 通过 SSH / Remote SSH 连接的编辑器

中间件通过 Ubuntu 上的 Docker Compose 运行。

开发端口使用 SSH 隧道访问：

```bash
ssh -L 5173:127.0.0.1:5173 -L 8000:127.0.0.1:8000 root@<ubuntu-host>
```

## 当前实现状态

当前 Ubuntu 工作区已经完成：

1. 默认 Docker 栈：PostgreSQL、后端、前端。
2. 可选 Compose profiles：Adminer、Redis、Qdrant。
3. 初始 Alembic migration。
4. 后端 `/api/v1/health` 和 `/api/v1/ready`。
5. 前端 API 状态、Skill ID、memory events 展示。
6. LLM provider 边界：默认 mock，预留 OpenAI Responses API。

后续具体工程任务：

1. 在 `.env` 中填写 `OPENAI_API_KEY` 和 `OPENAI_MODEL`，设置 `LLM_PROVIDER=openai`。
2. 用真实模型验证一元一次方程教学闭环。
3. 让 `skills/junior-math-linear-equation.yaml` 真正参与教学提示和诊断。
4. 在第一条教学闭环稳定后，再把 learning events 和长期记忆落到 PostgreSQL。
