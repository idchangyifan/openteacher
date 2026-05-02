# 开发环境设置

当前主要开发目标是 Ubuntu + Docker Compose。旧的 Windows PowerShell 脚本保留为历史辅助工具，但 Linux 容器应在 Ubuntu 机器上运行。

## Docker 开发

复制示例环境文件并启动默认服务：

```bash
cp .env.example .env
docker compose up --build
```

默认服务：

- 前端：`http://127.0.0.1:5173`
- 后端健康检查：`http://127.0.0.1:8000/api/v1/health`
- 后端就绪检查，包含数据库检查：`http://127.0.0.1:8000/api/v1/ready`
- PostgreSQL：`127.0.0.1:5432`

后端容器会在启动 Uvicorn 前运行 `alembic upgrade head`。宿主机端口默认绑定到 `127.0.0.1`；远程开发时使用 SSH 隧道，不要把开发端口直接暴露到公网。

LLM provider 默认保持 mock。只有填写下面这些 `.env` 值后，才会接入真实模型：

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=<your token>
OPENAI_MODEL=<model name>
```

`OPENAI_BASE_URL` 默认是 `https://api.openai.com/v1`。只有在使用支持 Responses API 的 OpenAI 兼容网关时才修改它。

常用命令：

```bash
docker compose up --build
docker compose up -d postgres
docker compose logs -f backend frontend
docker compose exec backend pytest
docker compose exec backend ruff check app tests alembic
docker compose exec backend alembic revision --autogenerate -m "描述改动"
docker compose exec frontend pnpm build
docker compose down
```

## 可选服务

可选中间件通过 Compose profiles 管理，避免在第一条教学闭环完成前引入过多基础设施：

```bash
docker compose --profile tools up -d adminer
docker compose --profile cache up -d redis
docker compose --profile rag up -d qdrant
```

- Adminer：在 `http://127.0.0.1:8080` 查看 PostgreSQL
- Redis：预留给未来缓存、队列或轻量会话
- Qdrant：预留给未来 RAG 或向量检索实验

在服务接口和产品行为更清晰之前，不要把记忆或 RAG 直接绑定到 Redis/Qdrant。

## 原生后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://openteacher:openteacher@localhost:5432/openteacher
export LLM_PROVIDER=mock
pytest
ruff check app tests
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## 原生前端

```bash
cd frontend
corepack enable
pnpm install --frozen-lockfile
pnpm build
pnpm dev --host 127.0.0.1 --port 5173
```

Vite 开发服务器会把 `/api` 代理到后端。Docker 中代理目标是 `http://backend:8000`；原生运行时默认回退到 `http://localhost:8000`。

## Windows 说明

早期 Windows Server 工作区无法运行 Docker Linux 容器，因为没有嵌套虚拟化能力。除非宿主机暴露虚拟化支持，否则不要继续尝试修 Docker Desktop。Docker 和中间件开发请使用 Ubuntu。
