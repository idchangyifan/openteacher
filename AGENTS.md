# AGENTS.md

本文件是 OpenTeacher 项目的长期交接记忆。任何 agent 在开始工作前都必须先读取本文件；每次工作结束前，都必须把本次重要改动、验证结果、环境变化和下一步建议更新到本文件。

## Agent 工作约定

- 每次运行前必须先阅读 `AGENTS.md`，再开始分析或改代码。
- 每次运行结束前必须更新 `AGENTS.md`，记录值得后续 agent 知道的事实。
- 更新内容应包括：重要技术决策、环境变化、验证命令和结果、未完成事项、下一步建议。
- 不要把密钥、token、密码、代理订阅、`.env` 内容等敏感信息写入本文档。
- 如果用户口头说 `agent.md`、`agnet.md` 或“记忆文件”，默认指本文件 `AGENTS.md`。

## 项目使命

OpenTeacher 是一个面向教育资源不足地区学生的开源 AI 教师项目，尤其关注中国农村和经济困难地区的孩子。

项目目标是教育公平：把高质量、严格、接近一线城市水平的教学带给原本难以获得这些资源的学生。

OpenTeacher 应该是一位老师，而不只是学习陪伴工具。它应该温暖、耐心、严格、有原则，并专注于帮助学生真正学会。

## 产品哲学

- 智能体是老师，不是朋友、家长、心理咨询师或答案机器。
- 它应该温暖但有要求，耐心但不纵容，严格但绝不羞辱。
- 它应该教推理和方法，而不只是输出答案。
- 它应该拒绝纯抄答案行为，并要求学生思考。
- 它应该谨慎记住学生：学业进展、常见错误、学习行为和具体进步。
- 它必须避免收集不必要的未成年人敏感数据。

## 技能生态

长期方向是开放教学技能生态。

核心想法：

- 优秀老师应该能够贡献结构化 Teaching Skills，用来编码他们的教学方法和风格。
- 技能不应该只是 prompt。它们应该包含知识范围、诊断问题、常见错误模式、纠错策略、练习策略和安全边界。
- 项目应支持官方技能、认证教师技能、社区实验技能和私有本地技能。

当前示例技能：

- `skills/junior-math-linear-equation.yaml`

当前 schema 草案：

- `specs/teaching-skill.schema.yaml`

## 技术栈

当前选定技术栈：

- 后端：Python、FastAPI、SQLAlchemy、Alembic
- 前端：React、TypeScript、Vite
- 关系型数据库：PostgreSQL
- 记忆模块存储：暂未最终决定，放在服务接口后面
- RAG 存储：暂未最终决定，放在服务接口后面

当前重要服务边界：

- `backend/app/services/agent_harness.py`
- `backend/app/services/llm_provider.py`
- `backend/app/services/memory.py`
- `backend/app/services/rag.py`
- `backend/app/services/skill_registry.py`

## 当前 Docker 环境

Ubuntu 是当前主要 Docker 开发环境。

默认 Compose 服务：

- `postgres`：PostgreSQL 16，持久化 volume 为 `postgres-data`
- `backend`：FastAPI 应用，启动 Uvicorn 前会运行 `alembic upgrade head`
- `frontend`：Vite 开发服务器，把 `/api` 代理到后端服务

可选 Compose profiles：

- `tools`：`adminer`，用于查看 PostgreSQL
- `cache`：`redis`，预留给未来缓存、队列或轻量会话
- `rag`：`qdrant`，预留给未来向量检索或 RAG 实验

重要 Docker 约定：

- 宿主机端口默认绑定到 `127.0.0.1`。继续使用 SSH 隧道访问，不要直接暴露开发端口到公网。
- 默认配置写在 `.env.example`；真实密钥只放 `.env`，并且 `.env` 已被忽略。
- LLM 默认是 `LLM_PROVIDER=mock`。要使用 OpenAI，在 `.env` 中设置 `LLM_PROVIDER=openai`、`OPENAI_API_KEY` 和 `OPENAI_MODEL`。
- OpenAI provider 通过 `OPENAI_BASE_URL` 使用 Responses API，不需要 OpenAI Python SDK。
- 在服务接口和教学行为更清晰之前，不要把记忆或 RAG 直接绑定到 Redis/Qdrant。
- 后端数据库就绪检查是 `GET /api/v1/ready`；不检查数据库的健康检查是 `GET /api/v1/health`。

常用 Docker 命令：

```bash
cp .env.example .env
docker compose up --build
docker compose logs -f backend frontend
docker compose exec backend pytest
docker compose exec backend ruff check app tests alembic
docker compose exec frontend pnpm build
docker compose --profile tools up -d adminer
docker compose --profile cache up -d redis
docker compose --profile rag up -d qdrant
```

## 仓库信息

GitHub 仓库：

- https://github.com/idchangyifan/openteacher

默认分支：

- `main`

初始脚手架已推送。

## 环境现实

最早的 Windows Server 工作区可以运行 Codex Desktop 并编辑代码，但不能运行 Docker Linux 容器，因为 Windows Server 本身是虚拟化环境，并且没有暴露嵌套虚拟化能力。

除非宿主机启用嵌套虚拟化，否则不要花时间让 Docker Desktop 在那台 Windows Server 上工作。已观察到的失败模式：

- Docker CLI 和 Docker Desktop 安装成功。
- Docker engine 返回 HTTP 500。
- WSL2 distro 创建失败，错误为 `HCS_E_HYPERV_NOT_INSTALLED`。
- Hyper-V 角色安装失败，因为处理器没有暴露所需虚拟化能力。

当前推荐开发方式：

- Mac 或本地工作站用于 SSH、编辑器和浏览器。
- 远程 Ubuntu 服务器作为真实开发机。
- Ubuntu 上运行 Codex CLI。
- Ubuntu 上运行 Docker 和全部中间件。

## 远程 Ubuntu 状态

搭建时使用的远程 Ubuntu 主机：

- Ubuntu 24.04 amd64
- SSH 用户是 `root`
- mihomo 已安装并以 `mihomo.service` 运行
- Codex CLI 已通过 npm 全局安装
- 曾观察到 Codex CLI 版本：`codex-cli 0.128.0`
- Codex 已使用 ChatGPT 完成登录

mihomo 状态：

- 二进制：`/usr/local/bin/mihomo`
- 配置：`/etc/mihomo/config.yaml`
- 服务：`mihomo.service`
- HTTP 代理：`127.0.0.1:7890`
- SOCKS 代理：`127.0.0.1:7891`
- Controller：`127.0.0.1:9090`

Ubuntu 上已为常用 CLI 工具配置基于环境变量的代理：

- `/etc/profile.d/99-proxy.sh`
- `/etc/environment`
- apt proxy
- git proxy
- npm proxy
- pip proxy
- systemd 管理器默认环境

该代理是环境变量形式，不是透明代理或 TUN 代理。不要假设所有进程都会自动使用代理，除非该进程尊重 `HTTP_PROXY`/`HTTPS_PROXY`。

## 如何在 Ubuntu 上继续

在 Ubuntu 上：

```bash
git clone https://github.com/idchangyifan/openteacher.git
cd openteacher
codex
```

后端原生运行目标：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check app tests
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端原生运行目标：

```bash
cd frontend
npm install
npm run build
npm run dev -- --host 127.0.0.1 --port 5173
```

从 Mac 或本地机器访问远程服务时使用 SSH 隧道，不要公开暴露开发端口：

```bash
ssh -L 5173:127.0.0.1:5173 -L 8000:127.0.0.1:8000 root@<ubuntu-host>
```

然后在本地打开：

- http://127.0.0.1:5173
- http://127.0.0.1:8000/api/v1/health

## 当前下一步

推荐下一步：

1. 在 `.env` 中填写 `OPENAI_API_KEY` 和 `OPENAI_MODEL`，设置 `LLM_PROVIDER=openai`，然后用真实模型验证教师回复。
2. 保持 memory 和 RAG 存储在接口后面，直到存储设计更清晰。
3. 围绕初中数学一元一次方程构建第一条真实教学闭环。
4. 只有在教学闭环需要持久化时，再把 mock memory 替换为基于 PostgreSQL 的 learning events。

## 最新验证状态

2026-05-02，在 Ubuntu 工作区中，默认 Docker 栈已构建并验证：

- `docker compose up --build -d` 成功；Compose 已传递构建阶段代理参数。
- `docker compose exec -T backend pytest` 通过。
- `docker compose exec -T backend ruff check app tests alembic` 通过。
- `docker compose exec -T frontend pnpm build` 通过。
- `GET /api/v1/health`、`GET /api/v1/ready` 和 `POST /api/v1/teacher/chat` 返回预期响应。
- `backend/app/services/llm_provider.py` 已包含 mock provider 和 OpenAI Responses API provider。token 位置是 `.env` 中的 `OPENAI_API_KEY`；配置真实 token 和模型前保持 `LLM_PROVIDER=mock`。

2026-05-02，仓库内 Markdown 文档已统一改写为中文版本：

- 已改写 `README.md`、`AGENTS.md` 和 `docs/*.md`。
- `AGENTS.md` 已增加强制约定：每次运行前必须先读本文件，每次运行结束前必须更新本文件。
- Markdown 中保留必要的技术名词、文件路径、命令、URL 和错误码。

2026-05-02，准备提交并推送当前 Docker、LLM provider、前端优化和中文文档改动：

- 当前仓库本地 git author 已设置为 `idchangyifan <idchangyifan@users.noreply.github.com>`，只作用于本仓库。
- 提交前已运行 `git diff --check`，无格式空白问题。
- 推送完成后应确认 remote URL 不包含明文凭据。

## 开发风格

- 保持项目使命和教师身份。
- 避免把智能体变成通用聊天机器人。
- 抽象应小而清晰，并与当前脚手架一致。
- 第一条教学闭环跑通前，不要添加过多中间件。
- Ubuntu 上的中间件优先使用 Docker Compose。
- 不要把密钥提交到仓库。
