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

## 开发风格

- 保持项目使命和教师身份。
- 避免把智能体变成通用聊天机器人。
- 抽象应小而清晰，并与当前脚手架一致。
- 第一条教学闭环跑通前，不要添加过多中间件。
- Ubuntu 上的中间件优先使用 Docker Compose。
- 不要把密钥提交到仓库。
