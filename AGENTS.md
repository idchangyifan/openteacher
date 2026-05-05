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

1. 优先围绕初中数学一元一次方程构建第一条真实教学闭环，让系统能诊断学生卡点、拒绝直接抄答案、要求学生写下一步、识别常见错误并给出针对性小练习。
2. 豆包是当前真实模型方向。在 `.env` 中填写 `DOUBAO_API_KEY` 和 `DOUBAO_MODEL`，设置 `LLM_PROVIDER=doubao`，然后用真实模型验证教师回复是否符合“温暖但严格”的教师身份。
3. 保持 memory 和 RAG 存储在接口后面，直到教学闭环需要持久化证据时，再把 mock memory 替换为基于 PostgreSQL 的 learning events。
4. 暂时不要引入更多中间件；优先把 `skills/junior-math-linear-equation.yaml` 的教学策略真正接入 `backend/app/services/agent_harness.py` 和测试。

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

2026-05-02，提交和推送已完成：

- 已提交 `2001d7a chore: add docker stack and Chinese docs` 并推送到 `origin/main`。
- 推送后已将本地 `origin` 改为不含明文凭据的 GitHub URL。

2026-05-03，本次只做下一步研判，未改业务代码：

- 已按约定先读取 `AGENTS.md`。
- 已查看 `backend/app/services/agent_harness.py`、`skills/junior-math-linear-equation.yaml` 和 `backend/tests/test_teacher_chat.py`。
- 当前工作区 `git status --short` 起始为空。
- 判断下一步应从“真实教学闭环”开始，而不是继续扩展基础设施：把技能 YAML 中的诊断问题、错误模式、纠错策略和回答策略接入后端回复构造，并用测试固定“不能直接给答案、必须要求学生写步骤、能识别移项变号/负号括号错误”等行为。

2026-05-03，已实现第一条一元一次方程教学闭环雏形，并接入豆包 provider：

- `backend/app/services/skill_registry.py` 现在读取 `skills/junior-math-linear-equation.yaml`，并把教学原则、诊断问题、错误模式、回答策略、安全边界整理成 `TeachingSkill.guidance`。
- `backend/app/services/agent_harness.py` 会把 `skill_guidance` 传入 LLM prompt。
- `backend/app/services/llm_provider.py` 新增 `DoubaoChatCompletionsProvider`，走火山方舟 OpenAI 风格 Chat Completions：默认 `DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3`，请求路径 `/chat/completions`，使用 Bearer API Key。未配置 `DOUBAO_API_KEY` 或 `DOUBAO_MODEL` 时仍回退 mock provider。
- `.env.example` 和 `docker-compose.yml` 已新增 `DOUBAO_*` 配置；backend 容器已将 `./skills` 只读挂载到 `/app/skills`，并设置 `SKILLS_DIR=/app/skills`。
- `backend/pyproject.toml` 新增 `pyyaml` 依赖，用于读取技能 YAML。
- 新增测试覆盖：豆包响应解析、豆包 system prompt 包含技能规则、拒绝直接给答案、识别移项变号错误、识别负号括号错误、要求代入检验。
- 验证结果：`docker compose build backend` 成功；`docker compose up -d backend` 成功；`docker compose exec -T backend pytest` 通过 12 项；`docker compose exec -T backend ruff check app tests alembic` 通过；`curl http://127.0.0.1:8000/api/v1/health` 返回 `{"status":"ok"}`；`POST /api/v1/teacher/chat` 对“直接告诉我答案吧，我要抄。”返回拒绝抄答案并要求学生写下一步。
- 未完成事项：尚未填入真实豆包 API Key 和模型 Endpoint/模型名，未用真实豆包模型做人类评估。下一步应配置 `.env` 后，用 5-10 条典型学生消息人工检查回复是否足够严格、短、可教学。

2026-05-03，断线恢复后检查未提交改动：

- 已按约定重新读取 `AGENTS.md`，并检查 `git status --short`、`git diff --stat`、关键文件 diff、`git log --oneline -5` 和 `git diff --check`。
- 当前未提交改动集中在一元一次方程教学闭环、豆包 provider、技能 YAML 接入、Docker/env 配置和测试；未发现密钥或 `.env` 内容进入 diff。
- 本次只做现场确认和本记录更新，未额外修改业务逻辑；`git diff --check` 无输出。

2026-05-03，已把本机 Docker 开发环境切到真实豆包模型：

- 已按约定先读取 `AGENTS.md`。
- 本机 `.env` 已设置 `LLM_PROVIDER=doubao`、`DOUBAO_MODEL=doubao-seed-1-8-251228` 和豆包方舟默认 base URL；真实 API key 只保存在 `.env`，不得写入 git diff、文档或日志。
- 已执行 `docker compose up -d --force-recreate backend`，backend 容器环境确认 `LLM_PROVIDER=doubao`、`DOUBAO_MODEL` 已设置、`DOUBAO_API_KEY` 已设置。
- 真实模型冒烟：`POST /api/v1/teacher/chat` 对 `2(x - 3) = 10，我不会下一步` 返回要求学生先写去括号式子的引导；backend 日志无 `LLM provider failed` fallback 异常。
- 真实模型抽查了直接抄答案、移项不变号、负号括号、代入验算 4 类消息；总体符合“温暖但严格、不直接给可抄答案、要求学生写步骤”的方向，移项解释略长，后续可继续收紧 prompt。
- 新增 `backend/tests/conftest.py`，让自动化测试固定使用 mock provider，避免本机 `.env` 切到真实模型后 `pytest` 变成网络测试。
- 验证结果：`docker compose exec -T backend pytest` 通过 12 项；`docker compose exec -T backend ruff check app tests alembic` 通过；`docker compose exec -T frontend pnpm build` 通过；`git diff --check` 无输出。
- 下一步建议：人工评估 5-10 条真实学生消息，优先调短豆包回复并增强“只推进一步”的稳定性；确认满意后提交当前未提交改动。

2026-05-03，产品路线重新聚焦到普适教师能力：

- 用户明确判断：一元一次方程知识点太小，不应继续把下一步重点放在单一知识点闭环上。
- 下一步应优先抽象普适性教师技能：诊断学生卡点、拒绝抄答案、分步引导、追问学生思路、纠错、鼓励但保持要求、根据知识点选择教学策略。
- 模型 prompt 不应只做通用压缩；回复质量应与具体知识点、题型和学生当前步骤结合，知识点技能负责提供内容层教学方法，教师核心技能负责控制教学行为。
- 教学质量评测也应从单点题目升级为跨知识点评测：覆盖数学、语文、英语等多个学科/知识类型下的普适教学行为。
- 记忆边界需要重新定义：不收集身份证号、精确住址、联系方式等身份定位信息；但可在必要、克制、可解释的前提下记住影响教学和支持方式的重要学生背景，例如家庭结构、照护状况、重大压力源等。
- 对家庭困难、留守、离异、受欺负或被不公平对待等信息，OpenTeacher 应能记住并在后续对话中给予温暖、稳定的支持；同时仍需明确边界：它是老师，不是心理咨询师或监护人。遇到现实伤害、虐待、自伤风险等高风险情况，应鼓励学生寻求可信成年人、学校老师或当地紧急帮助。
- 下一步建议：先设计 `UniversalTeachingSkill` / 教师核心行为规范、跨知识点评测集和 memory schema 的信息分类，而不是继续加深一元一次方程专项逻辑。

2026-05-03，对教学 skill 生态方向做进一步澄清：

- 不要把“聚焦普适教师技能”误解为“不负责教具体知识点”。OpenTeacher 最终仍然要负责具体知识点教学。
- 长期设想是：每个具体知识点都可能对应一个 Teaching Skill，例如一元一次方程、古诗鉴赏、英语一般过去时、浮力、化学方程式配平等。
- 知识点 skill 的来源可以多样化：项目团队生成；真正的一线老师设计和撰写；名师教案、课堂方法或教学经验经过结构化抽取后转化为 skill。
- 当前尚未完全确定知识点 skill 的生产、审核、认证、版本管理和质量评估机制，需要慢慢谋划。
- 现阶段优先做普适教师能力底座，是因为具体知识点体系极其庞大；先把“老师如何教学、如何追问、如何纠错、如何拒绝抄答案、如何结合学生状态”的底层行为稳定下来，再扩展知识点 skill 更稳。
- 推荐架构方向：教师核心 skill 负责通用教学行为和边界；知识点 skill 负责具体内容、常见误区、诊断题、讲解路径、练习策略；两者在 agent harness 中组合成最终教师行为。

2026-05-03，下一步执行建议：

- 优先产出一份“教师核心能力规格”，而不是继续写单点知识点逻辑或调模型短回复。
- 规格应先覆盖：教学状态机、学生意图/卡点分类、允许/禁止的教师行为、不同学生情绪状态下的回应原则、与知识点 skill 的组合接口。
- 同步更新 Teaching Skill schema 草案，让它能区分“通用教师行为”和“知识点内容策略”，为未来老师撰写、名师教案抽取和官方/认证/社区 skill 打基础。
- 在规格之后再做一组跨知识点黄金样例，用来评估普适教师能力是否稳定。

2026-05-03，已开始落地普适教师核心能力底座：

- 新增 `docs/universal-teaching-core.md`，定义 OpenTeacher 的通用教学状态、教师行为规则、禁止行为、高风险安全边界，以及与知识点 Skill 的组合方式。
- 新增 `skills/universal-teacher-core.yaml`，作为第一版可被后端读取的通用教师核心 Skill；其 `skill_type` 为 `core`，覆盖学生状态模型、诊断问题、掌握信号、回答策略、隐私边界和组合优先级。
- 更新 `specs/teaching-skill.schema.yaml`，正式加入 `core` skill 类型，并增加 `learner_state_model`、`composition_policy`、`uncertainty_policy`、`emotional_support_policy` 等字段。
- 更新 `docs/skill-authoring.md`，明确推荐组合为“教师核心技能 + 知识技能 + 可选教师风格技能 + 可选任务技能”，并规定教师核心技能在安全、边界和教学纪律上优先。
- 更新 `backend/app/services/skill_registry.py`：新增 `SkillSelection`，默认组合 `universal-teacher-core.yaml` 与当前知识点 Skill；保留 `pick_skill` 兼容旧调用；返回给 API 的 `skill_id` 仍为知识点 Skill id。
- 更新 `backend/app/services/agent_harness.py` 和 `backend/app/services/llm_provider.py`：传给模型的 prompt 现在区分教师核心 Skill 与知识点 Skill，两层规则会同时进入 OpenAI/Doubao system prompt。
- 新增 `backend/tests/test_skill_registry.py`，验证 registry 会组合通用教师核心 Skill 与知识点 Skill；更新 LLM provider 测试，验证豆包 system prompt 同时包含核心教师规则和知识点规则。
- 验证结果：`docker compose exec -T backend pytest` 通过 14 项；`docker compose exec -T backend ruff check app tests alembic` 通过；`docker compose exec -T frontend pnpm build` 通过；`git diff --check` 无输出。
- 真实模型冒烟：`POST /api/v1/teacher/chat` 对“老师，我这题不会，直接给我答案行吗？”返回拒绝直接给答案并要求学生提供题目或已有步骤；backend 日志无 fallback 异常。
- 下一步建议：基于 `docs/universal-teaching-core.md` 设计跨知识点黄金评测集，覆盖数学、语文、英语、物理等不同知识类型下的普适教学行为。

2026-05-03，已新增跨知识点普适教师能力黄金评测集：

- 新增 `backend/tests/fixtures/teacher-core-golden.yaml`，作为第一版可执行黄金样例集；当前放在 backend tests fixture 下，便于现有 Docker 测试直接读取，后续可升级为仓库级 `evals/` 资产和独立评测 runner。
- 黄金集覆盖数学、语文、英语、物理和 general 安全场景；覆盖 `insufficient_information`、`answer_seeking`、`genuinely_stuck`、`concept_error`、`step_error`、`emotional_distress`、`safety_risk` 等学生状态。
- 每条样例包含 `student_message`、学科/年级/知识点、`expected_behaviors`、`forbidden_behaviors`、`ideal_teacher_move` 和 `scoring_notes`。`ideal_teacher_move` 是参考教师动作，不要求模型逐字复现。
- 样例中特别加入家庭支持背景和安全风险边界：可以温暖回应影响学习支持的背景，但不得索要精确地址、身份信息等可定位信息；遇到自伤/虐待/即时危险时，OpenTeacher 应引导学生联系可信成年人、学校老师或当地紧急帮助，不能继续普通教学或假装替代专业支持。
- 新增 `backend/tests/test_teacher_eval_cases.py`，验证黄金集结构完整、跨学科覆盖、状态覆盖，以及是否包含核心边界要求。
- 新增 `docs/teacher-evaluation.md`，说明黄金样例的评测目标、单条结构、0-2 分人工评分建议和扩展原则。
- 验证结果：`docker compose exec -T backend pytest` 通过 17 项；`docker compose exec -T backend ruff check app tests alembic` 通过；`docker compose exec -T frontend pnpm build` 通过；`git diff --check` 无输出。
- 下一步建议：做一个真实模型评测 runner，读取黄金集，调用当前 `/api/v1/teacher/chat` 或 provider，保存模型回复与人工评分结果；先不要自动判分过度复杂化。

2026-05-03，已新增真实模型教师评测 runner：

- 新增 `scripts/run-teacher-eval.py`，默认读取 `backend/tests/fixtures/teacher-core-golden.yaml`，调用 `http://127.0.0.1:8000/api/v1/teacher/chat`，输出 JSONL 明细和 summary JSON。
- runner 支持 `--dry-run`、`--limit`、`--case-id`、`--base-url`、`--output`、`--timeout` 和 `--teacher-style`；也可通过 `OPENTEACHER_API_BASE_URL` 指定 API base URL。
- 每条报告记录包含学生输入、期望行为、禁止行为、参考教师动作、实际请求、模型响应、错误信息、耗时、`manual_score` 和 `reviewer_notes`，便于人工评分。
- 新增 `.gitignore` 的 `reports/`，默认评测报告不提交到仓库。
- 更新 `docs/teacher-evaluation.md`，加入 runner 使用命令、dry-run、指定 case 和报告说明。
- 已运行 dry-run：`python3 scripts/run-teacher-eval.py --dry-run --limit 2 --output /tmp/openteacher-teacher-eval-dry-run.jsonl` 成功。
- 已运行真实模型 smoke：`python3 scripts/run-teacher-eval.py --limit 2 --output /tmp/openteacher-teacher-eval-smoke.jsonl` 成功，2 条样例均返回 200 响应并写入报告；这次 smoke 消耗了 2 次豆包调用。
- 验证结果：`python3 -m py_compile scripts/run-teacher-eval.py` 通过；`docker compose exec -T backend pytest` 通过 17 项；`docker compose exec -T backend ruff check app tests alembic` 通过；`docker compose exec -T frontend pnpm build` 通过；`git diff --check` 无输出；未发现 API key 进入仓库文件。
- 下一步建议：运行完整黄金集真实评测，把 `reports/*.jsonl` 中的 `manual_score` 和 `reviewer_notes` 人工填完；之后再考虑做一个汇总脚本统计平均分、0 分样例和常见失败类型。

2026-05-03，本次按用户要求重新读取记忆文件并研判下一步：

- 已按约定先读取 `AGENTS.md`，并查看 `git status --short`、`git log --oneline -5`、`git diff --stat`、`docs/teacher-evaluation.md`、`scripts/run-teacher-eval.py` 和 `backend/tests/fixtures/teacher-core-golden.yaml`。
- 当前工作区仍有一批未提交改动，集中在豆包 provider、通用教师核心 Skill、跨知识点评测集和评测 runner；最近提交仍是 `9887924 docs: update handoff after push`。
- `git diff --check` 无输出；本次未改业务代码，只补充本记录。
- 判断下一步应优先做完整黄金集真实模型评测和人工评分，而不是继续扩展新功能：运行 `python3 scripts/run-teacher-eval.py` 生成完整报告，逐条填写 `manual_score` 和 `reviewer_notes`，总结 0 分/1 分样例及常见失败类型。
- 完成人工评测后，再根据失败类型决定是收紧 `skills/universal-teacher-core.yaml`、调整知识点 Skill 组合 prompt，还是补充黄金样例；稳定后再提交当前未提交改动。

2026-05-03，已完成第一轮完整黄金集真实模型评测并据此修正教师核心规则：

- 运行前确认 `GET /api/v1/health` 正常，backend 容器中 `LLM_PROVIDER=doubao`，`DOUBAO_MODEL` 和 `DOUBAO_API_KEY` 均已设置；未输出真实 key。
- 首轮完整评测命令：`python3 scripts/run-teacher-eval.py`，报告为 `reports/teacher-core-eval-20260503T045234Z.jsonl`；10 条均返回 200，人工评分 16/20，无 0 分。
- 首轮 1 分样例为：`english-concept-error-tense`、`english-emotional-distress`、`physics-answer-seeking-homework`、`chinese-family-support-context`。
- 主要失败类型：概念错误场景没有先明确修正错误规则；情绪支持后没有给立即可执行的小任务；通用学科场景容易退回“告诉我条件/说说哪里不会”的泛化追问。
- 已更新 `skills/universal-teacher-core.yaml`：概念错误必须先点名错误规则和正确边界；情绪受挫后必须给一个具体学术小任务；新增 `concrete_next_action_policy` 和 `concept_error_policy`；新增英语时态、浮力选择题、背词困难等示例。
- 已更新 `backend/app/services/skill_registry.py`：通用 fallback knowledge skill 现在包含语文阅读、语文作文、英语概念错误、英语背词、物理状态/受力线索、数学重写步骤等学科相关下一步；`_build_guidance` 现在会把 YAML `examples` 纳入模型 prompt。
- 已更新 `docs/universal-teaching-core.md`，补充概念纠错和情绪受挫后的具体动作要求。
- 已更新 `backend/tests/test_skill_registry.py`，覆盖通用 skill 的具体下一步规则和核心 skill 示例进入 guidance。
- 验证结果：`docker compose exec -T backend pytest` 通过 18 项；`docker compose exec -T backend ruff check app tests alembic` 通过；`docker compose up -d --force-recreate backend` 成功；重启后 `GET /api/v1/health` 返回 `{"status":"ok"}`；`git diff --check` 无输出。
- 针对 4 个首轮 1 分样例复测：`python3 scripts/run-teacher-eval.py --case-id english-concept-error-tense --case-id english-emotional-distress --case-id physics-answer-seeking-homework --case-id chinese-family-support-context`，报告为 `reports/teacher-core-eval-20260503T045701Z.jsonl`；人工评分 8/8。
- 最终完整回归：再次运行 `python3 scripts/run-teacher-eval.py`，报告为 `reports/teacher-core-eval-20260503T045754Z.jsonl`；10 条均返回 200，人工评分 20/20。评测报告在 `reports/` 下，已被 `.gitignore` 忽略，不提交。
- 本轮真实模型评测共消耗 24 次豆包调用：首轮完整 10 次、针对复测 4 次、最终完整回归 10 次。
- 下一步建议：当前未提交改动已经形成一组可提交的功能批次；提交前可再运行一次 `docker compose exec -T frontend pnpm build` 做全栈确认，然后检查 diff 中无敏感信息，提交并推送。

2026-05-03，提交前最终检查：

- 已按约定重新读取 `AGENTS.md`，确认当前任务是提交普适教师核心、豆包 provider、跨知识点评测集和评测 runner 这一批改动。
- 额外验证：`docker compose exec -T frontend pnpm build` 通过。
- 提交前检查：`git diff --check` 无输出；`git remote -v` 显示 remote URL 不含明文凭据；对 diff 中 `api_key`、`token`、`password`、`secret`、`DOUBAO_API_KEY`、`OPENAI_API_KEY` 等字样做快速扫描，只发现配置名、空占位符和测试 token，没有真实密钥。
- 后续建议：提交后如需同步远端，再执行 `git push origin main`；推送前可按需确认代理可用。

2026-05-03，尝试推送但远端凭据不可用：

- 当前本地已有提交 `98c93a1 feat: add universal teacher core evaluation`，推送前 `main...origin/main [ahead 2]`。
- 执行 `git push origin main` 失败，原因是全局 gitconfig 将 `https://github.com/` 重写为 `https://ghproxy.net/https://github.com/`，该代理 URL 在非交互环境要求用户名，错误为 `fatal: could not read Username for 'https://ghproxy.net': No such device or address`。
- 临时忽略全局 rewrite 并显式使用代理推送标准 GitHub URL：`GIT_CONFIG_GLOBAL=/dev/null git -c http.proxy=http://127.0.0.1:7890 -c https.proxy=http://127.0.0.1:7890 push https://github.com/idchangyifan/openteacher.git main`，仍失败，原因是没有可用 HTTPS GitHub 凭据：`fatal: could not read Username for 'https://github.com': No such device or address`。
- 检查 `gh`、git credential helper、`~/.git-credentials`、`~/.config/git/credentials`，均不可用或不存在。
- 检查 SSH：存在 `~/.ssh/id_ed25519`，但 `ssh -T -o BatchMode=yes git@github.com` 返回 `Permission denied (publickey)`，说明该公钥未授权到 GitHub。
- 下一步建议：配置一种非交互推送凭据后再推送，例如安装并登录 `gh`、配置 GitHub token 到 credential helper，或把当前 `~/.ssh/id_ed25519.pub` 加到 GitHub 账号/仓库 deploy key；也可临时移除/覆盖全局 `url.https://ghproxy.net/https://github.com/.insteadof` rewrite 后使用标准 GitHub 凭据。

2026-05-03，用户提供新的 GitHub token 后已完成第一段推送：

- 使用临时 HTTPS token 认证推送本地 3 个提交到 `main`，未把 token 写入代码、`AGENTS.md`、git remote 或仓库配置。
- 推送输出显示 `9887924..41dc97f  main -> main`，包括 `98c93a1 feat: add universal teacher core evaluation` 和 `41dc97f docs: record push credential blocker`。
- 推送后检查 `git remote -v`，remote 仍显示 `https://ghproxy.net/https://github.com/idchangyifan/openteacher.git`，未包含明文凭据。
- 注意：由于本次使用显式 URL 推送，`origin/main` 本地跟踪引用尚未自动更新；可在凭据和代理配置理顺后 fetch，或使用显式 URL fetch 更新远端跟踪引用。

2026-05-03，本机已配置 GitHub HTTPS 推送凭据：

- 用户允许把新的 GitHub token 记录在本地，但不要提交或推送；token 只写入本机 Git credential store，未写入仓库文件、`AGENTS.md`、remote URL 或 git 历史。
- 已设置 `git config --global credential.helper store`，凭据文件为 `~/.git-credentials`，权限已设为 `600`。
- 已移除全局 `url.https://ghproxy.net/https://github.com/.insteadof` rewrite；当前仍保留 `http.proxy` 和 `https.proxy` 指向 `127.0.0.1:7890`。
- `git remote -v` 现在显示标准 `https://github.com/idchangyifan/openteacher.git`，不含凭据。
- 已验证普通 `git push origin main` 可用，输出为 `Everything up-to-date`。
- 本记录不含 token；除本记录外，不应把 `~/.git-credentials` 内容写入任何仓库文件或日志。

2026-05-03，下一步产品方向研判：

- 用户建议开始丰富应用功能和页面；已重新读取 `AGENTS.md`，查看 `frontend/src/App.tsx`、`frontend/src/styles.css`、`backend/app/schemas/teacher.py` 和 `backend/app/api/v1/router.py`。
- 当前前端仍是单页聊天 demo：左侧学生画像和记忆摘要，右侧对话框，调用 `/api/v1/teacher/chat`，后端 API 也主要围绕 teacher chat、health/ready。
- 判断下一步应做“学习工作台 v1”，而不是营销页或纯 UI 装饰：把聊天 demo 升级为学生真实学习界面，包含学科/年级/教师风格选择、当前学习任务、对话、下一步行动、学习记录/记忆事件、技能状态和服务状态。
- 第一阶段建议仍尽量前端优先，不急着扩数据库或引入新中间件；必要时只补很薄的后端 read-only 接口，例如可用 skill/学科列表或 demo 学习任务。
- 设计原则：教育工具应安静、清晰、任务导向，避免过度营销化；第一屏直接是可用学习工作台。

2026-05-03，用户再次明确长期记忆和产品定位边界：

- 长期记忆不要直接使用 PostgreSQL 实现，用户担心后续改起来麻烦。后续 memory 应继续保持在服务接口后面，具体存储要可替换；不要把长期记忆 schema、检索方式或写入策略过早绑定到 PG 表结构。
- OpenTeacher 绝不能被做成“解题老师”“作业辅助老师”或“辅助写题工具”。它应该是可以主动授课的老师。
- 产品功能和页面设计应从“主动教学”出发：课程目标、教学计划、授课节奏、诊断提问、讲解、课堂练习、纠错、复盘、课后任务，而不是只围绕学生发题、老师答题。
- 下一步页面方向应从“学习工作台”进一步调整为“课堂/课程工作台”：学生进入后能看到今天要学什么、为什么学、老师正在讲哪一步、需要完成什么练习、掌握情况如何；聊天只是授课交互的一部分，不是整个产品。

2026-05-03，纠偏后重新评估现有黄金评测：

- 已查看 `backend/tests/fixtures/teacher-core-golden.yaml` 和 `docs/teacher-evaluation.md`。
- 结论：现有黄金评测仍然可用，但定位应改成“被动答疑/学生发起互动场景下的教师底线评测”，不能代表 OpenTeacher 的完整教师能力。
- 现有 10 条样例覆盖拒绝抄答案、信息不足、真实卡住、概念错误、步骤错误、情绪受挫、安全边界等通用教师行为，这些能力对主动授课同样必要，所以不应删除。
- 现有评测缺口：没有评估老师是否能主动设定学习目标、规划课程、导入新课、讲授概念、设计诊断题、根据学生回答调整节奏、安排课堂练习、总结复盘、布置课后任务。
- 下一步应新增一套主动授课黄金评测，例如 `teacher-lesson-golden.yaml`，覆盖 lesson_start、concept_instruction、guided_practice、diagnostic_check、adaptive_remediation、lesson_summary、homework_assignment 等课堂阶段。
- 文档命名也应调整：当前 `teacher-core-golden.yaml` 保留为 interaction-safety/core-behavior 类评测；新增 lesson/teaching-flow 类评测，避免团队误以为 20/20 就代表“会主动授课”。

2026-05-03，功能层架构进一步讨论：

- 用户明确：评测先放一放，只留 TODO；当前重点转向功能层设计。
- 用户提出整体 agent 框架可以考虑 DeepAgent；结论是可以调研/试点，但不要把业务直接耦合到某个 agent 框架。建议先定义 `TeachingAgentRuntime` 这类适配接口，把主动授课、被动答疑、工具调用、记忆读写都放在领域服务边界后面。
- 用户强调长期记忆一定需要，核心功能包括历史会话查看和恢复，这对学生复习很重要。这里“长期记忆”至少要拆成两类：完整会话/课堂记录的 source of truth，以及从会话中抽取出的结构化学习记忆。
- 历史会话查看和恢复更适合文档型存储，例如 MongoDB；不要用向量库做 source of truth。向量库适合语义检索，不适合承载完整会话恢复、分页、审计、可解释删除等主数据职责。
- 记忆抽取需要独立 pipeline：从课堂/对话事件中抽取知识掌握、常见错误、学习行为、情绪/支持背景、复习建议等 memory cards；这些结构化 memory cards 可同时写入文档存储，并为摘要/片段生成 embedding 写入向量库。
- 推荐方向：MongoDB 存 lesson sessions、messages、lesson state、memory cards、extraction jobs；Qdrant 或同类向量库存 message summaries、memory cards、知识片段的 embedding。PostgreSQL 继续只做当前基础关系数据或后续可替换，不承载长期记忆主路径。
- 下一步功能实现建议：先设计课堂/课程 session 数据模型、历史会话恢复接口、memory card schema、记忆抽取 job 流程，再决定是否引入 MongoDB 和是否把现有 Qdrant profile 从预留变成实际依赖。

2026-05-03，用户反驳并进一步收敛 agent 与记忆架构：

- 用户明确希望整个项目主框架直接使用 LangChain 的 deepagents，不只是作为可替换候选。后续实现应围绕 deepagents/ LangGraph runtime 设计主动授课 agent，但仍应在业务层保留清晰服务边界，避免页面和数据库直接依赖 deepagents 内部细节。
- 用户赞同记忆分层，但强调完整会话保存、记忆抽取、记忆冲突、何时调用/检索记忆是一套庞大工程，需要从一开始作为核心功能设计。
- 为了简化中间件依赖，用户提出是否可以都用 MongoDB 搞定，因为 MongoDB 也支持向量检索。经官方资料确认，MongoDB Atlas Vector Search 支持向量检索、过滤和混合检索，可用任意 MongoDB driver 执行 `$vectorSearch` 聚合；因此现阶段可以采用“MongoDB 统一承载长期记忆和向量检索”的方案，暂不引入 Qdrant。
- 修正推荐方向：MongoDB 作为长期记忆主存储，保存 lesson sessions、messages、lesson state snapshots、memory cards、memory conflicts、extraction jobs，以及 memory card / summary embeddings；使用 Atlas Vector Search 或本地 Atlas 部署能力做语义检索。
- 仍需保持逻辑分层：完整会话是历史恢复 source of truth；memory cards 是抽取后的结构化教学记忆；embedding/vector index 是检索视图。即使物理上都在 MongoDB，也不要在领域模型里把三者混成一种数据。
- 下一步应优先设计 MongoDB collection schema、索引、memory extraction pipeline、conflict resolution 策略和 lesson memory retrieval policy，再把 PostgreSQL 从长期记忆路径中排除。

2026-05-03，已产出长期记忆架构定义：

- 新增 `docs/memory-architecture.md`，定义 MongoDB 统一承载长期记忆和向量检索的第一阶段架构。
- 文档明确三层逻辑：课堂事实层（`lesson_sessions`、`lesson_messages`、`lesson_state_snapshots`）、结构化记忆层（`memory_cards`、`memory_conflicts`）、检索视图层（embedding 和 MongoDB Atlas Vector Search）。
- 文档定义了 MongoDB collection 示例 schema、建议索引、记忆抽取触发时机、抽取步骤、抽取原则、冲突类型、冲突解决策略、主动授课/课堂进行中/被动答疑/复习恢复四类记忆检索策略。
- 文档定义 DeepAgents 接入边界：项目主 agent runtime 使用 LangChain deepagents，但数据库读写必须通过 `LessonService`、`MemoryService`、`MemoryExtractionService`、`TeachingAgentRuntime` 等领域服务和受控工具。
- 更新 `docs/memory-system.md`，把它定位为产品原则摘要，并链接到 `docs/memory-architecture.md`；明确长期记忆不绑定 PostgreSQL，第一阶段使用 MongoDB 承载课堂记录、结构化记忆、抽取任务和向量检索。
- 更新 `backend/app/services/memory.py` 注释，移除未来指向 PostgreSQL/pgvector 的表述，改为长期记忆应迁移到 MongoDB-backed lesson history、memory cards、extraction jobs 和 vector search。
- 验证结果：`git diff --check` 无输出。本次主要是文档和注释变更，未运行后端/前端构建。
- 下一步建议：基于 `docs/memory-architecture.md` 做第一阶段实现计划，优先加 MongoDB compose profile、配置项、repository 接口和 lesson session/message API；暂不实现复杂冲突解决和完整 DeepAgents 接入。

2026-05-03，已实现长期记忆/课堂历史第一阶段骨架并充分验证：

- 新增课堂历史后端 API：`POST /api/v1/lessons` 创建课堂，`GET /api/v1/lessons?student_id=...` 列出历史课堂，`GET /api/v1/lessons/{session_id}` 恢复课堂详情。
- 新增 `backend/app/schemas/lesson.py`，定义 `LessonSession`、`LessonMessage`、`LessonSessionSummary`、`LessonSessionDetail` 和课堂阶段枚举。
- 新增 `backend/app/services/lesson_store.py`，当前使用 `InMemoryLessonRepository` 作为 MongoDB 接入前的服务边界；后续 Mongo repository 应实现同等接口。
- `TeacherChatRequest.context` 新增可选 `session_id`。`AgentHarness` 在收到带 `session_id` 的聊天请求时，会把学生消息和老师回复追加到对应课堂，支持历史恢复。
- 新增 `backend/tests/test_lesson_sessions.py`，覆盖创建课堂、列出课堂、恢复课堂、chat 自动写入课堂消息和未知课堂 404。
- 前端 `frontend/src/App.tsx` 已接入课堂历史：左侧可新建课堂、查看最近课堂、点击恢复历史消息；发送消息时会确保存在课堂并把 `session_id` 传给后端；顶部显示课堂标题、阶段和下一步动作。
- 前端 `frontend/src/styles.css` 增加课堂历史列表、课堂状态和新建课堂按钮样式，保持工具型学习界面而非营销页。
- `docker-compose.yml` 新增可选 `memory` profile：`mongo` 服务使用 `mongodb/mongodb-atlas-local:8.0`，默认不启动；`.env.example` 新增 `LESSON_STORE_BACKEND`、`MONGODB_URI`、`MONGODB_DATABASE`。
- `docs/dev-setup.md` 新增 `docker compose --profile memory up -d mongo`，并明确长期记忆第一阶段通过 MongoDB 接入，不绑定 PostgreSQL。
- 运行时冒烟：通过 `POST /api/v1/lessons` 创建课堂，再带 `session_id` 调用 `POST /api/v1/teacher/chat`，最后 `GET /api/v1/lessons/{session_id}` 成功恢复 3 条消息（teacher/student/teacher），summary 为“已进行 2 轮教师引导和 1 轮学生回应。”。
- 验证结果：`docker compose exec -T backend pytest` 通过 21 项；`docker compose exec -T backend ruff check app tests alembic` 通过；`docker compose exec -T frontend pnpm build` 通过；`docker compose config --quiet` 通过；`docker compose --profile memory config --services` 输出包含 `mongo`；`git diff --check` 无输出。
- 未完成事项：MongoDB repository 尚未实现，当前课堂历史仍是内存实现，backend 重启会丢失；记忆抽取、冲突解决、MongoDB Vector Search 和 LangChain deepagents 接入仍待后续实现。
- 下一步建议：实现 MongoDB-backed `LessonRepository`，将 `lesson_sessions` 和 `lesson_messages` 持久化；随后再做 `memory_cards` schema 和 lesson end 后的第一版记忆抽取。

2026-05-03，用户测试发现一个关键教学行为问题：

- 用户反馈：学生明明已经写出正确答案，老师仍执着要求解题步骤，像是没有看到学生已经写出正确结果。
- 判断：这是当前应优先处理的教学行为缺陷，不只是 UI 或功能问题。现有教师核心规则过度强调“不要直接给答案、要求写步骤”，但缺少“识别正确答案/掌握信号/完成当前任务后推进下一阶段”的策略。
- 修正方向：老师看到正确结果时应先明确确认“结果对了”，再根据教学目标要求学生补一句关键理由、做代入检验或进入下一题/复盘，而不是重复要求学生从头写步骤。
- 后续应补充测试和黄金样例：学生给出正确答案但步骤不完整、学生给出正确答案且有理由、学生给出正确答案但理由错误三类场景，分别要求不同教师动作。

2026-05-03，已修复“学生答对仍机械要求步骤”的教师行为问题：

- 更新 `skills/universal-teacher-core.yaml`：新增 `correct_or_mastery_signal` 学生状态，要求老师先确认学生完成/答对，不要要求从头重写；如果理由缺失，只补一个短理由/验算；如果理由足够，则进入总结、下一题或下一教学阶段。
- 更新 `skills/junior-math-linear-equation.yaml`：新增答对后的策略，学生已给出正确 `x` 时不重启完整解题；缺验证则要求代入，验证已完成则进入类似练习或总结。
- 更新 `backend/app/services/llm_provider.py`：OpenAI/Doubao system prompt 增加“学生已给出正确结果时先明确确认正确，不机械从头重写”的规则；mock provider 对 `2(x-3)=10` 且 `x=8` 的场景会先确认正确，再根据是否已有验算决定要求代入或进入下一题。
- 新增测试：`test_teacher_chat_acknowledges_correct_answer_before_requesting_reason` 和 `test_teacher_chat_advances_after_correct_answer_with_check`，固定正确答案无验算/有验算两种动作。
- 验证结果：`docker compose exec -T backend pytest` 通过 23 项；`docker compose exec -T backend ruff check app tests alembic` 通过；`git diff --check` 无输出。
- 真实模型冒烟：重启 backend 后，对 `2(x-3)=10，我算出来 x=8` 返回先确认 `x=8` 正确并要求代入验算；对 `2(x-3)=10，我算出来 x=8，代入左边右边都是10` 返回确认正确和验证到位，并要求一句关键理由，没有要求从头重写步骤。
- 产品判断：OpenTeacher 是完整老师，不应执着于“拒绝答案/写步骤”；防抄答案只是底线，老师还必须识别掌握信号并推进课堂。

2026-05-03，已提交并推送课堂历史基础与答对识别修复：

- 提交 `c968625 feat: add lesson history foundation` 已推送到 `origin/main`。
- 该提交包含长期记忆架构文档、课堂历史 API、前端课堂历史入口、MongoDB memory profile、答对后先确认的教师行为修复，以及相关测试。

2026-05-03，已实现 MongoDB-backed 课堂历史落库：

- `backend/pyproject.toml` 新增 `pymongo>=4.10.0`。
- `backend/app/services/lesson_store.py` 新增 `LessonRepository` 协议和 `MongoLessonRepository`；当 `LESSON_STORE_BACKEND=mongodb` 时，`get_lesson_repository()` 会使用 MongoDB，否则继续使用内存实现。
- MongoDB collections：`lesson_sessions` 和 `lesson_messages`；已创建索引 `student_updated`、`student_subject_updated`、`status_updated`、`session_created`、`student_created`。
- `backend/app/api/v1/routes/lessons.py` 和 `backend/app/services/agent_harness.py` 已改为依赖 `LessonRepository` 协议，而不是具体内存实现。
- `backend/tests/conftest.py` 固定测试使用内存 lesson store，并清理内存状态，避免测试依赖或污染 MongoDB。
- 已执行 `docker compose build backend`，成功安装 `pymongo`。
- 运行时 Mongo 落库验证：使用 `LESSON_STORE_BACKEND=mongodb docker compose --profile memory up -d mongo backend` 启动 MongoDB Atlas Local 和 backend；创建课堂、带 `session_id` 调用 `teacher/chat` 后，重启 backend 仍可通过 `GET /api/v1/lessons/{session_id}` 恢复 3 条消息，证明课堂历史已落入 MongoDB 而非内存。
- 直接查 MongoDB：`lesson_sessions` 为 1 条，`lesson_messages` 为 3 条，索引列表包含上述自定义索引。
- 验证结果：`docker compose exec -T backend pytest` 通过 23 项；`docker compose exec -T backend ruff check app tests alembic` 通过；`docker compose exec -T frontend pnpm build` 通过；`docker compose config --quiet` 通过；`docker compose --profile memory config --services` 输出包含 `mongo`；`git diff --check` 无输出。
- 关于 PostgreSQL 当前用途：PG 目前主要是脚手架级基础数据库，Compose 默认启动并供 `GET /api/v1/ready` 和 Alembic 使用；已有 `students`、`conversations`、`messages`、`learning_events` 初始表和 SQLAlchemy models，但当前 teacher chat、lesson history 和长期记忆主流程没有真正把业务数据写入 PG。长期记忆和课堂历史已转向 MongoDB；PG 后续可只保留给账号、权限、运营关系数据，或在产品边界更清楚后裁剪。
- 下一步建议：提交并推送 MongoDB-backed lesson repository；之后做 `memory_cards` collection 和 lesson end 后的第一版记忆抽取，不要再把长期记忆写回 PG。

2026-05-03，用户再次指出智能层仍是 demo 级并要求接入 DeepAgents：

- 用户反馈：当前智能仍然像只会用很蠢方式教一元一次方程，怀疑只是简单 demo。判断成立：当前 `AgentHarness` 主要靠单点 skill 和 prompt 规则，不具备真正的课程规划、模式判断、记忆调用和主动授课能力。
- 用户明确：需要把 LangChain `deepagents` 作为 harness agent 框架用起来，包括如何调用记忆点。
- 已查官方资料：LangChain Deep Agents 官方定位是 agent harness，基于 LangChain/LangGraph，内置 planning、filesystem、subagents、长期记忆等能力；`create_deep_agent` 是主入口并返回 compiled LangGraph graph。
- 下一步实现方向：新增 `TeachingAgentRuntime` / DeepAgents adapter，定义工具边界（读取课堂状态、检索 memory cards、保存课堂消息、生成练习、创建记忆抽取任务），逐步替换当前简单 `AgentHarness` 的“单轮 prompt 调 provider”模式。
- 近期不要继续堆页面或存储外围功能；优先重构智能层，让 OpenTeacher 能判断主动授课/被动答疑/诊断/练习/复盘，并基于长期记忆选择教学动作。

2026-05-03，已完成 DeepAgents harness 第一版可选接入：

- `backend/pyproject.toml` 新增 `deepagents>=0.3.0` 和 `langchain-openai>=1.0.0`；实际构建安装到 `deepagents 0.5.6`。
- 新增 `backend/app/services/deepagents_runtime.py`，定义 `DeepAgentsTeachingRuntime`。该 runtime 使用 `create_deep_agent` 构建 LangChain DeepAgents graph，并提供四个教学工具：`retrieve_student_memory`、`load_lesson_state`、`plan_next_teaching_move`、`create_memory_extraction_hint`。
- 新增配置：`AGENT_RUNTIME`，默认 `provider`；`DEEPAGENTS_MODEL` 可选。`AGENT_RUNTIME=deepagents` 时 `AgentHarness` 先尝试 DeepAgents runtime；失败时回退当前 LLM provider，再失败回退 mock teacher。
- DeepAgents system prompt 明确：OpenTeacher 是完整老师，主动授课是主轴，被动答疑只是能力之一；每轮应判断 active_lesson、qa、diagnostic_check、guided_practice、review、lesson_summary 等模式；不要把所有输入都当成一元一次方程解题。
- 为了减少“一元一次方程 demo 感”，`AgentHarness` 增加轻量 subject inference：消息中出现“浮力/受力/重力/斜面/物理”时使用物理；出现英语/单词/语法/yesterday 等使用英语；出现语文/作文/阅读/比喻/修辞等使用语文。这样前端默认 subject 是数学时，学生说“学浮力”不会再走一元一次方程 skill。
- 新增 `backend/tests/test_deepagents_runtime.py`，覆盖 DeepAgents system prompt 的主动授课约束，以及工具读取学生记忆和课堂状态。
- 更新 `backend/tests/test_teacher_chat.py`，覆盖“浮力”输入不会被强制塞到数学一元一次方程 skill。
- 验证结果：`docker compose build backend` 成功，确认 `deepagents` 和 `langchain_openai` 可导入；`docker compose exec -T backend pytest` 通过 26 项；`docker compose exec -T backend ruff check app tests alembic` 通过；`docker compose exec -T frontend pnpm build` 通过；`docker compose config --quiet` 通过；`git diff --check` 无输出。
- 运行时冒烟：用 `AGENT_RUNTIME=deepagents` 重启 backend 后，请求“我想开始学浮力，不是做题”（context 仍传数学）返回 `skill_id=opent-teacher-general`，回复进入浮力概念主动授课并要求学生举生活例子；之后已把 backend 恢复为默认 `AGENT_RUNTIME=provider`。
- 未完成事项：DeepAgents 已作为可选 harness 接入，但还没有成为默认 runtime；记忆工具目前读取的是 mock summary，还没有接 `memory_cards`；`create_memory_extraction_hint` 还只是候选提示，未落 extraction job。
- 下一步建议：实现 `memory_cards` Mongo collection 和 `retrieve_student_memory` 的真实检索；随后把 DeepAgents runtime 接入 lesson start/continue API，让主动授课不再依赖单轮 chat。

2026-05-03，用户澄清 harness agent 的真正含义：

- 用户说的 harness agent 不是简单 deepagents runtime adapter，而是 OpenTeacher 主控智能体架构。
- 基本架构应包含 planner、executor、verifier 三层：planner 负责课程/本轮教学计划和工具选择；executor 负责执行授课、答疑、练习、记忆调用和工具动作；verifier 负责检查教学质量、是否越界、是否识别学生状态、是否需要修正输出。
- harness agent 还必须包含：记忆层（记住每个学生情况）、guardrails（规范教师行为、安全边界、隐私边界、反作弊但不机械）、skill 广场/生态（可开放给老师自己编写技能，二期也要预留接口）、LangSmith 可视化 agent 调试和追踪。
- 之前 `077894a feat: add deepagents teaching runtime` 只是第一版可选 runtime 接入，不等同于完整 harness agent。后续应补正式架构规格，定义 planner/executor/verifier/memory/guardrails/skills/observability 的边界和数据流。
- 下一步建议：先产出 `docs/harness-agent-architecture.md`，再按架构逐步重构，而不是继续随手往 `AgentHarness` 加 prompt 或工具。

2026-05-03，已补充正式 harness agent 架构规格：

- 新增 `docs/harness-agent-architecture.md`，明确 OpenTeacher harness agent 是主控教师智能体，而不是简单 LLM provider 包装或单个 deepagents adapter。
- 文档定义 planner、executor、verifier 三层核心：planner 负责教学模式/学习状态/工具计划/记忆检索计划/技能选择计划；executor 负责执行授课、答疑、练习、保存课堂、创建记忆抽取任务；verifier 负责检查教师身份、教学质量、安全隐私、是否机械要求步骤、是否识别掌握信号等。
- 文档定义记忆层、guardrails、skill 广场、LangSmith observability、API/service 边界和分阶段实现路线。
- 更新 `docs/architecture.md`，链接 `docs/harness-agent-architecture.md` 和 `docs/memory-architecture.md`，并把当前技术方向更新为 MongoDB 长期记忆、MongoDB Atlas Vector Search、LangChain DeepAgents / LangGraph runtime。
- 更新 `docs/memory-architecture.md`，反向链接主控 harness 架构。
- 重要判断：`backend/app/services/deepagents_runtime.py` 是接入点，不是完整 harness agent。下一步应优先实现 planner 数据结构、真实 `memory_cards` 检索工具和 verifier 第一版规则，而不是继续堆单 prompt。

2026-05-03，已开始把 harness agent 三层架构落到代码：

- 新增 `backend/app/services/planner.py`，实现 Planner v1 规则骨架，显式产出 `teaching_mode`、`learner_state`、`next_teacher_goal`、`memory_retrieval_plan`、`skill_selection_plan`、`tool_plan` 和 guardrail notes。
- `AgentHarness` 现在会先调用 Planner，再把 planner 决策注入 `TeacherPrompt`；OpenAI、Doubao 和 DeepAgents runtime 都会收到结构化 Planner 决策。
- `DeepAgentsTeachingRuntime` 的角色文案已调整为 OpenTeacher harness 的 Executor，由 DeepAgents runtime 执行；文档中进一步明确 DeepAgents / LangGraph 是 runtime，OpenTeacher harness 才是产品主控层。
- 新增 `backend/tests/test_planner.py`，覆盖掌握信号、主动授课请求、直接要答案和结构化 prompt context；更新 LLM provider 与 DeepAgents runtime 测试，确认 planner 决策进入 prompt。
- 更新 `docs/harness-agent-architecture.md`：新增关键边界，明确 harness agent 不是第三方库薄封装；planner/executor/verifier 是最小三层，LangSmith 是调试追踪层，Skill 广场可二期但接口要预留。
- 更新 `docs/architecture.md` 当前运行流程，加入 Planner v1、Executor 当前边界和 Verifier 待实现状态。
- 验证结果：`docker compose exec -T backend pytest` 通过 30 项；`docker compose exec -T backend ruff check app tests alembic` 通过。
- 未完成事项：Verifier 仍未实现；memory tools 仍未接真实 `memory_cards`；LangSmith tracing 尚未配置；Skill 广场还只是架构预留。
- 下一步建议：优先做 Verifier v1 规则检查，固定“答对先确认、不机械要求步骤、不能给可抄答案、主动授课不能退化成答疑、隐私/安全边界”等质量门；随后做 MongoDB `memory_cards` 和真实记忆检索。

2026-05-04，本次按用户要求查看 `agent.md`/记忆文件并确认项目进度：

- 已按约定先读取 `AGENTS.md`，并查看最新尾部记录、`git status --short --branch` 和 `git log --oneline -8`。
- 当前 `main...origin/main` 无 ahead/behind 提示，但工作区存在未提交改动：`AGENTS.md`、`backend/app/services/agent_harness.py`、`backend/app/services/deepagents_runtime.py`、`backend/app/services/llm_provider.py`、`backend/tests/test_deepagents_runtime.py`、`backend/tests/test_llm_provider.py`、`docs/architecture.md`、`docs/harness-agent-architecture.md`，以及新增 `backend/app/services/planner.py`、`backend/tests/test_planner.py`。
- 最近已提交到 git 的进度包括：harness agent 架构文档、DeepAgents runtime 可选接入、MongoDB 课堂历史落库、课堂历史基础和答对识别修复。
- 当前最新未提交方向是 Planner v1：把 OpenTeacher harness agent 从简单 provider 调用推进到 planner/executor/verifier 三层架构的第一步；Verifier、真实 `memory_cards` 检索、LangSmith tracing 和 Skill 广场仍待实现。
- 本次未改业务代码、未运行测试；只补充本记录。

2026-05-04，用户指出当前教师对话仍然“迷、没重点”，并提出是否应提供教材、按教材章节做 skill 和 RAG：

- 重要产品判断：问题不只是 prompt 不够好，而是老师缺少教材章节、课程目标、本节课边界、知识先后顺序和评价标准，因此对话容易像泛泛答疑，缺少严谨教师的授课主线。
- 用户倾向：如果提供教材，应围绕教材章节构建教学能力；教材内容可拆成章节/小节/知识点/例题/练习/课后题，分别进入 Teaching Skill 和 RAG。
- 建议架构方向：教材章节结构用于课程地图和 lesson plan；Teaching Skill 负责“怎么教”某章节/知识点，包括目标、重难点、前置知识、常见误区、诊断题、讲解路径、练习设计和掌握标准；RAG 负责“教什么”的可引用教材内容、例题、定义、课文片段、题目和解析证据。
- 下一步建议：先选择一本教材的一章作为试点，建立 `course -> chapter -> lesson -> knowledge_point` 的内容结构，抽取一个章节 skill，并接入 RAG 检索；再让 Planner 根据学生当前位置选择本节课目标和下一步教学动作。

2026-05-04，已查看用户提供的教材仓库 `https://github.com/TapXWorld/ChinaTextbook`：

- 仓库 README 说明其目标是集中小初高、大学 PDF 教材资源；GitHub 页面显示约 70k stars、15k forks，顶层目录包含 `小学`、`初中`、`高中`、`大学`、五四学制目录和练习题目录。
- 未发现 GitHub license API 返回明确开源许可证；因此该仓库可作为本地研发试点/目录发现来源，但公开发布、再分发、商用或把教材原文提交入本仓库前必须处理版权授权问题。
- 目录结构适合课程地图抽取：例如 `初中/数学/人教版-人民教育出版社/七年级/义务教育教科书·数学七年级上册.pdf`，同级还有七下；`初中/物理/人教版-人民教育出版社/八年级/义务教育教科书·物理八年级上册.pdf`、八下；`初中/英语/人教版-人民教育出版社/七年级/义务教育教科书·英语七年级上册.pdf`、七下。
- 通过 GitHub API 查看目录即可，不建议整仓 clone；README 提到部分超过 GitHub 文件大小限制的 PDF 会拆成 `.pdf.1`、`.pdf.2` 等片段，需要合并。本次查看的人教版初中数学七上/七下、物理八上/八下、英语七上/七下均显示为单个 PDF，大小约 9-18MB。
- 尝试临时下载数学七上 PDF 到 `/tmp` 查看内容，raw 下载较慢并中止；未把教材内容加入仓库。
- 下一步建议：先围绕 `初中/数学/人教版-人民教育出版社/七年级/义务教育教科书·数学七年级上册.pdf` 做一章试点，优先抽目录、章节结构和一章内容，生成 `course_map`、章节 Teaching Skill 和 RAG chunks；不要全量下载或提交 PDF。

2026-05-04，已接收并整理用户上传的人教版初中数学教材：

- 用户明确只需要 `初中/数学/人教版-人民教育出版社`，不需要其他版本教材。
- 用户上传的文件为 `/root/openteacher-data/textbooks/ChinaTextbook/初中/数学/middle_school_math.zip`，大小约 53MB。
- zip 内包含 6 个 PDF 和 6 个 `__MACOSX/._*` 元数据文件；zip 内中文文件名显示为乱码，但 PDF 文件大小与仓库中人教版初中数学六册一致。
- 已用 Python 标准库解压并按规范路径重命名到：
  - `/root/openteacher-data/textbooks/ChinaTextbook/初中/数学/人教版-人民教育出版社/七年级/义务教育教科书·数学七年级上册.pdf`，9975261 bytes
  - `/root/openteacher-data/textbooks/ChinaTextbook/初中/数学/人教版-人民教育出版社/七年级/义务教育教科书·数学七年级下册.pdf`，15097728 bytes
  - `/root/openteacher-data/textbooks/ChinaTextbook/初中/数学/人教版-人民教育出版社/八年级/义务教育教科书·数学八年级上册.pdf`，9055875 bytes
  - `/root/openteacher-data/textbooks/ChinaTextbook/初中/数学/人教版-人民教育出版社/八年级/义务教育教科书·数学八年级下册.pdf`，13183195 bytes
  - `/root/openteacher-data/textbooks/ChinaTextbook/初中/数学/人教版-人民教育出版社/九年级/义务教育教科书·数学九年级上册.pdf`，8925172 bytes
  - `/root/openteacher-data/textbooks/ChinaTextbook/初中/数学/人教版-人民教育出版社/九年级/义务教育教科书·数学九年级下册.pdf`，9688920 bytes
- 已确认六个 PDF 文件头分别为 `%PDF-1.6` 或 `%PDF-1.7`。
- 环境观察：服务器没有 `unzip`、`pdfinfo`、`pdftotext`、`pypdf/PyPDF2/pdfplumber/fitz`；尝试 `apt-get install subversion` 因系统代理链路返回 502 失败；尝试安装 `pypdf` 到独立 target 也被全局 pip 代理拖慢并中止。后续 PDF 解析建议通过 Docker 容器、项目 dev 依赖，或先补一个稳定的本地教材处理环境。
- 下一步建议：先做教材利用方案和最小 pipeline：为人教版初中数学生成 `textbook_manifest`，抽取目录和章节页码，再选七年级上册一章做 `course_map`、章节 Teaching Skill、RAG chunks 和主动授课评测样例。

2026-05-04，用户提出教材抽取与教学设计本身也应成为一个 Skill：

- 已按约定先读取 `AGENTS.md`；本次主要做可行性研判，不开始动业务代码。
- 重要产品判断：从教材抽取知识点并确定如何教学是可行的，而且应该被设计成一种专门的 Skill，暂命名方向可为 `TextbookToTeachingSkill` / `教材到教学技能生成 Skill`。
- 该 Skill 不应只做 PDF 摘要，而应产出可教学资产：教材 manifest、目录/章节结构、知识点图谱、课程目标、前置知识、重难点、常见误区、诊断问题、讲解路径、课堂练习、掌握标准、课后任务，以及可进入 RAG 的教材 chunks。
- 该 Skill 应作为“技能生产流水线”运行：上传教材 -> 解析版面和目录 -> 抽取章节和知识点 -> 生成章节/知识点 Teaching Skill 草稿 -> 建立 RAG 索引 -> 生成评测样例 -> 人工审核/修订 -> 发布为官方/认证/本地 Skill。
- 需要明确版权边界：教材 PDF 和原文 chunks 不应提交进本仓库；公开发布或再分发教材内容前必须处理授权。研发阶段可把用户上传教材放在 `/root/openteacher-data` 等本地数据目录。
- 需要明确质量边界：自动抽取结果不能直接等同于可靠教学方案，必须支持来源引用、人工审核、版本管理、评测回归和失败样例修正。
- 下一步建议：先写一份 `docs/textbook-to-skill-pipeline.md` 规格，定义输入/输出、数据结构、审核流程、与 Teaching Skill schema/RAG/Planner 的关系；再用人教版初中数学七年级上册一章做最小闭环试点。

2026-05-04，开始共同设计 `TextbookToTeachingSkill`：

- 已重新读取 `AGENTS.md`、`specs/teaching-skill.schema.yaml` 和 `docs/skill-authoring.md`，确认当前 schema 只有 `core`、`knowledge`、`teacher_style`、`task` 四种 skill 类型。
- 设计判断：`TextbookToTeachingSkill` 不应被当作普通 `knowledge` skill，而应作为“元技能/生产型技能”，负责把教材和教师输入转化为可审核、可评测、可发布的知识点 Teaching Skill、课程地图和 RAG 资产。
- 初步分层建议：教材解析层负责 PDF/图片/OCR/公式/版面；课程结构层负责 book/chapter/section/lesson/knowledge_point；教学设计层负责目标、前置知识、重难点、误区、诊断、讲解路径、练习、掌握标准；审核发布层负责人审、版本、来源引用、版权边界和评测。
- 关键原则：生成物必须保留教材来源和页码证据；教材原文和 PDF 不提交仓库；自动生成的 skill 默认是 draft，必须经过人工审核或评测门槛后才能进入官方/认证技能。
- 后续 schema 可能需要新增 `generator` / `pipeline` 类 skill，或单独建立 `skill_generation_pipeline` schema，而不是把生成流程硬塞进现有 Teaching Skill schema。

2026-05-04，用户补充教师教案输入口：

- `TextbookToTeachingSkill` 不能只从教材抽取，也必须保留“老师提供教案/教学设计/课堂经验”的输入口。
- 教材主要提供知识结构、原文证据、例题和练习；教师教案主要补充“某个知识点应该如何教学”，包括导入方式、讲解顺序、提问设计、常见学生反应、纠错方法、练习安排、板书/类比/活动设计等。
- 教案应更新 Teaching Skill 的教学方法层，而不是无审查地覆盖教材事实层；如果教案与教材知识点、定义或例题解释冲突，应标记为 `needs_review` 交给人工审核。
- 后续设计中应支持多来源合并：教材抽取草稿 + 教师教案增强 + 名师经验/校本策略增强；每条教学策略应保留来源、作者/审核状态、适用范围和版本。

2026-05-04，`TextbookToTeachingSkill` 第一版设计共识：

- 该能力是 OpenTeacher 的核心“技能工厂”，定位为 generator/pipeline skill：把教材、LLM 教学设计和未来教师教案转成课程地图、知识点 Teaching Skill、RAG 证据库和评测样例。
- 第一版输入源可以先只有教材 PDF 与 LLM 推断；教师教案、课堂实录、老师笔记、校本策略作为可选增强输入预留。
- 核心数据流：`textbook_manifest` -> `course_map` -> `knowledge_point_graph` -> `skill_draft` -> `rag_chunks` -> `eval_cases` -> `review_record` -> `published_skill`。
- 事实层与方法层必须分离：教材事实、定义、例题和练习必须带页码/来源；教学目标、讲解路径、常见误区和练习策略可以由 LLM 推断，但默认标记为 `llm_inferred`、`draft` 和可审核。
- 生成的 Teaching Skill 草稿建议包含：适用范围、学习目标、前置知识、核心概念、讲解顺序、诊断问题、常见误区、纠错策略、例题路径、分层练习、掌握标准、复习安排、评测样例和来源证据。
- 审核状态建议至少包括：`draft`、`needs_review`、`approved_local`、`certified`、`rejected`、`deprecated`。公开/官方技能必须经过审核与评测，不应由模型直接发布。
- 最小试点建议：人教版初中数学七年级上册第一章，先做离线 pipeline 规格与样例产物，不急着做上传页面；成功标准是能生成一章 course map、1-3 个知识点 skill 草稿、RAG chunks 和主动授课评测样例。

2026-05-05，关于 `TextbookToTeachingSkill` 是否要先建 RAG：

- 已按约定重新读取 `AGENTS.md`，并查看 `backend/app/services/rag.py`、RAG 相关文档和当前 `git status --short`。
- 当前 `RagService` 仍是 mock 边界，只返回固定“一元一次方程”样板上下文；`settings.rag_backend` 存在但未接真实后端。Qdrant 只是 Compose profile 预留，不应立刻变成硬依赖。
- 判断：不需要先建完整线上 RAG 系统或向量库；但必须先定义“RAG 资产格式”和离线 `rag_chunks` 产物。`TextbookToTeachingSkill` 的第一版输出应包含可检索 chunk、来源页码、内容类型、知识点关联和版权/审核状态。
- 推荐顺序：先写 `docs/textbook-to-skill-pipeline.md`，明确 `rag_chunks` schema；再用七年级上册第一章生成本地 JSON/YAML 样例；随后实现一个文件型/内存型 `TextbookRagService` 用于本地检索 smoke；最后再决定是否接 MongoDB Atlas Vector Search、Qdrant 或其他向量存储。
- 重要原则：先把“教什么”和“怎么教”的资产边界做好，不要为了一开始能向量检索而把教材原文、版权内容或存储选择过早绑定进仓库和业务逻辑。

2026-05-05，本次提交 Planner v1 并开始构建 `TextbookToTeachingSkill`：

- 已检查此前未提交改动，确认其主要内容是 Planner v1 接入 harness：新增 `backend/app/services/planner.py` 和 `backend/tests/test_planner.py`，`AgentHarness` 会把 planner 决策注入 OpenAI、Doubao 和 DeepAgents prompt；相关架构文档也已更新。
- 提交前验证：`docker compose exec -T backend pytest` 通过 30 项；`docker compose exec -T backend ruff check app tests alembic` 通过；`git diff --check` 无输出；敏感信息扫描只发现配置名、空占位符和测试 token，没有真实密钥。
- 已提交 `8d49d7d feat: add planner to teaching harness`；当前本地 `main` 相对 `origin/main` ahead。
- 已新增 `docs/textbook-to-skill-pipeline.md`，定义 `TextbookToTeachingSkill` 的输入、输出、教材/教案/LLM 推断合并规则、RAG chunks 边界、Planner 关系和七上第一章试点范围。
- 已新增 `specs/textbook-to-skill-pipeline.schema.yaml`，作为生成型流水线产物 schema 草案；同时在 `specs/teaching-skill.schema.yaml` 和 `docs/skill-authoring.md` 中加入 `generator` / 生成型技能说明。
- 已新增 `backend/tests/fixtures/textbook-to-skill-sample.yaml`，用人教版七年级上册第一章做不含教材原文的样例产物，覆盖 `input_sources`、`textbook_manifest`、`course_map`、`knowledge_point_graph`、`skill_drafts`、`rag_chunks`、`eval_cases` 和 `review_record`。
- 已新增 `backend/tests/test_textbook_to_skill_pipeline.py`，验证样例产物有核心输出、区分教材与 LLM 来源、生成资产默认 draft、RAG chunks 可追溯。
- 验证结果：`docker compose exec -T backend pytest` 通过 34 项；`docker compose exec -T backend ruff check app tests alembic` 通过；`git diff --check` 无输出。
- 下一步建议：实现离线生成脚本或服务骨架，先读取本地教材 manifest/人工章节草稿，输出上述 pipeline YAML/JSON；随后再补 PDF 解析依赖和文件型 `TextbookRagService` smoke。

2026-05-05，已实现 `TextbookToTeachingSkill` 离线生成骨架：

- 新增 `backend/app/services/textbook_to_skill_pipeline.py`，提供 `build_textbook_to_skill_artifact()` 和 `PipelineInputError`。第一版输入是人工/工具整理的结构化草稿，不直接解析 PDF；后续 PDF/OCR 解析模块应产出同样输入结构。
- 新增 `scripts/generate-textbook-skill.py`，支持 `--input`、`--output` 和 `--format yaml|json`，从结构化 YAML/JSON 草稿生成完整 pipeline artifact。
- 新增 `backend/tests/fixtures/textbook-to-skill-input.yaml`，作为七年级上册第一章的结构化输入草稿；继续避免提交教材 PDF 或大段教材原文。
- 更新 `backend/tests/test_textbook_to_skill_pipeline.py`，覆盖 builder 输出结构和错误引用检测；更新 `docs/textbook-to-skill-pipeline.md`，加入离线脚本用法。
- 已运行脚本 smoke：`python3 scripts/generate-textbook-skill.py --input backend/tests/fixtures/textbook-to-skill-input.yaml --output /tmp/openteacher-textbook-to-skill-artifact.yaml`，成功生成 1 个 skill draft 和 2 个 rag chunks。
- 验证结果：`docker compose exec -T backend pytest` 通过 36 项；`docker compose exec -T backend ruff check app tests alembic` 通过；`git diff --check` 无输出。
- 下一步建议：把这批离线生成骨架提交；随后做文件型 `TextbookRagService`，读取生成 artifact 的 `rag_chunks` 做本地检索 smoke，并让 `RagService` 在 `RAG_BACKEND=textbook_file` 时使用它。

## 开发风格

- 保持项目使命和教师身份。
- 避免把智能体变成通用聊天机器人。
- 抽象应小而清晰，并与当前脚手架一致。
- 第一条教学闭环跑通前，不要添加过多中间件。
- Ubuntu 上的中间件优先使用 Docker Compose。
- 不要把密钥提交到仓库。
