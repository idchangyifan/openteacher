# AGENTS.md

本文件是 OpenTeacher 项目的压缩交接记忆。任何 agent 开始工作前都先读这里；每次结束前更新“当前进度 / 推荐下一步 / 最近工作日志”。旧流水日志已迁出到 `docs/agent-log-archive-2026-05.md`，只有追溯历史决策时才需要读。

## 工作约定

- 每次运行前先阅读 `AGENTS.md`。
- 每次结束前更新本文，尤其是 `## 推荐下一步`，不要只追加日志。
- 不要把密钥、token、密码、代理订阅、`.env` 全量内容写入文档。
- 用户说 `agent.md`、`agnet.md` 或“记忆文件”时，默认指本文件。
- 做教材 chunk 切分、RAG 录入、Teaching Skill 草稿生成等离线工作时，不调用豆包；默认由当前 Codex/agent 自身能力配合确定性脚本完成。

## 项目使命

OpenTeacher 是面向教育资源不足地区学生的开源 AI 教师项目，尤其关注中国农村和经济困难地区的孩子。它应该是一位老师，而不只是陪聊工具：温暖、耐心、严格、有原则，专注于帮助学生真正学会。

核心产品原则：

- 老师身份优先，不做朋友、家长、心理咨询师或答案机器。
- 温暖但有要求，耐心但不纵容，严格但不羞辱。
- 教推理和方法，不直接给可抄答案。
- 谨慎记住学生的学业进展、常见错误、学习行为和具体进步。
- 避免收集不必要的未成年人敏感数据。

## 当前架构

后端：Python、FastAPI、SQLAlchemy、Alembic。
前端：React、TypeScript、Vite。
关系型产品数据：PostgreSQL，仅用于用户、账号、权限、班级、教师/志愿者、运营关系等。
AI 运行态：MongoDB，统一承载课堂历史、课程状态、短期记忆、长期记忆、LangGraph/DeepAgents checkpoint、记忆抽取任务、教材 RAG chunks 和后续向量检索。
向量检索方向：优先 MongoDB Atlas Vector Search 或 MongoDB 兼容能力；第一阶段不把独立向量库作为必需依赖。

重要服务边界：

- `backend/app/services/agent_harness.py`：教师回合主编排。
- `backend/app/services/deepagents_runtime.py`：DeepAgents/LangGraph 运行态、tools、middleware。
- `backend/app/services/deepagents_memory.py`：DeepAgents MemoryMiddleware 后端适配。
- `backend/app/services/memory.py`：学生长期记忆边界与 MongoDB `memory_cards`。
- `backend/app/services/rag.py`：教材 RAG、多路召回和 rerank。
- `backend/app/services/skill_registry.py`：Teaching Skill 选择与保留。
- `backend/app/services/teaching_turn_context.py`：当前问题、学生回答归因、答案归一化。
- `backend/app/services/textbook_to_skill_pipeline.py`：TextbookToTeachingSkill 离线加工。

## Docker 环境

当前主开发环境是远程 Ubuntu + Docker Compose。宿主机端口默认绑定 `127.0.0.1`，本地访问用 SSH 隧道，不要公开开发端口。

默认 Compose 服务：

- `postgres`：PostgreSQL 16。
- `mongo`：MongoDB Atlas Local 8.0；AI 运行态主路径。
- `backend`：FastAPI，启动前运行 `alembic upgrade head`。
- `frontend`：Vite dev server，`/api` 代理到 backend。

可选 profiles：

- `tools`：`adminer`。
- `cache`：`redis`，预留。
- `rag`：`qdrant`，历史实验预留；当前主路线不依赖。

常用命令：

```bash
cp .env.example .env
docker compose up --build
docker compose logs -f backend frontend
docker compose exec -T backend pytest
docker compose exec -T backend ruff check app tests alembic
docker compose exec -T frontend pnpm build
docker compose --profile tools up -d adminer
docker compose --profile cache up -d redis
docker compose --profile rag up -d qdrant
```

本地访问远程服务：

```bash
ssh -L 5173:127.0.0.1:5173 -L 8000:127.0.0.1:8000 root@<ubuntu-host>
```

然后打开：

- http://127.0.0.1:5173
- http://127.0.0.1:8000/api/v1/health

## 当前进度

截至 2026-05-07，当前工作区已完成长期记忆 v2 与课堂历史删除管理，准备提交。

已完成的主线能力：

- 基础 Docker 栈已跑通，PostgreSQL、MongoDB、backend、frontend 默认可启动。
- LLM provider 已支持 mock、OpenAI Responses API、Doubao Chat Completions；自动化测试默认强制 mock，避免 `.env` 影响测试。
- Teaching Skill 已从一元一次方程单技能，扩展到 `TextbookToTeachingSkill` 生成的人教版七上数学第一章正负数相关技能。
- 七上第一章教材切片已进入 MongoDB `textbook_chunks`，当前样例约 112 条 chunks，包含学习目标、导入、诊断题、误区、纠错策略、例题、步骤、变式、易错对照、小结等类型。
- RAG 已从简单文件读取升级为 MongoDB 多路召回 + 确定性 rerank；召回考虑 knowledge point、section、chapter、teaching_phase、content_type、retrieval_tags、student_error_pattern、lexical text。
- DeepAgents 已接入主教学运行态，使用 MongoDB checkpointer，并暴露 `load_lesson_state`、`retrieve_student_memory`、`retrieve_textbook_chunks`、`plan_next_teaching_move` 等工具。
- 短期记忆不再只拼最近 6 条消息；DeepAgents `dynamic_prompt` middleware 注入完整当前 session transcript、当前问题、学生回答状态、当前 skill / knowledge point。
- 长期记忆已接入 DeepAgents 原生 `MemoryMiddleware`，由 `StaticMemoryBackend` 提供只读 `/openteacher/student-memory.md`。
- 长期记忆从硬编码 lesson-history snapshot 升级到 MongoDB `memory_cards`：`MemoryService.record_learning_event()` 会把明确学习信号写成结构化卡片；普通 conversation 不进入长期记忆。
- `memory_cards` 已加厚来源与审计字段：`source_session_id`、`source_message_ids`、`evidence_snippets`、`last_seen_at`、`review_status`、`expires_at`、`supersedes`、`conflict_group` 和来源课堂删除标记。
- 已新增 MongoDB `memory_extraction_jobs`，每次受控抽取都会记录来源 session/message、抽取事件、生成的 card ids 和抽取版本。
- 历史课堂支持软删除：`DELETE /api/v1/lessons/{session_id}` 会把课堂标为 `deleted`，列表和详情不再返回，但保留原始消息和已抽取记忆；对应记忆只标记 `source_session_deleted=True`，不级联删除。
- 当前课堂 transcript、lesson state、`current_skill_id` 永远高于最近课堂和长期记忆卡片；长期记忆只作为背景假设。
- 修复了“刚学正负数，问上堂课却回到一元一次方程”的问题：连续性输入会挂回最近同学科课堂，skill registry 会保留当前 skill。
- 前端已优化：Enter 发送、Shift+Enter 换行；等待文案更自然；默认记忆摘要不再展示一元一次方程假数据。

## 当前已知问题

- `memory_cards` 已有抽取任务和来源审计，但仍缺人工审核界面、冲突解决、过期/撤销策略和更细粒度 rerank。
- DeepAgents summarization/checkpoint/store 还没有完整合流：长课堂会话超过阈值后的自动压缩策略尚未实现。
- RAG 还缺可审核 trace：需要记录候选 routes、rerank 分数、最终 chunks 和使用的 lesson state / student_answer_status。
- TextbookToTeachingSkill 的 schema 还需要把 `teaching_phase`、`retrieval_tags`、`source_section_id`、`difficulty`、`student_error_pattern_ids` 等字段正式固化。
- 老师回复自然度已有改善，但仍需要用真实课堂脚本继续做小样本人工评估，避免过度流程化。

## 推荐下一步

1. 给长期记忆补人工审核/撤销管理：查看 `memory_cards`、改 `review_status`、停用错误记忆、处理 `conflict_group`。
2. 接入 DeepAgents summarization/checkpoint/store：超过阈值后压缩完整课堂历史，但保留当前未完成问题、学生最新回答状态和下一步教学动作。
3. 为 MongoDB RAG 增加可审核召回 trace：记录 routes、rerank 分数、最终 chunks、lesson state、student_answer_status，方便回放“为什么用了这些 chunk”。
4. 继续完善 TextbookToTeachingSkill：把 chunk 元数据写入正式 schema，准备 MongoDB Atlas Vector Search index / embedding 字段。
5. 继续补教材切片质量：章节复习、跨知识点衔接、分层练习、学生回答评价依据；仍按知识点/教学动作组织，不做机械 token 切块。
6. 继续改善老师自然度：DeepAgents/LangGraph 只负责准备上下文、RAG 和记忆 trace，不把教学过程做成有限状态机；回复生成保留 LLM 的临场判断。

## 最新验证

2026-05-07 最后一次完整验证：

- `docker compose exec -T backend pytest`：66 passed。
- `docker compose exec -T backend pytest tests/test_memory.py tests/test_lesson_sessions.py tests/test_teacher_chat.py`：18 passed。
- `docker compose exec -T backend ruff check app tests alembic`：通过。
- `docker compose exec -T frontend pnpm build`：通过。
- `git diff --check`：通过。
- MongoDB smoke：删除来源课堂后，课堂详情不再可见；已抽取 `memory_cards` 保留且 `source_session_deleted=True`。

## 最近工作日志

2026-05-07，长期记忆 v2 与课堂历史删除管理：

- `MemoryCard` 增加来源 session/message、证据片段、审核状态、过期/替代/冲突组和来源课堂删除标记。
- 新增 `MemoryExtractionJob` 和 MongoDB `memory_extraction_jobs` collection；每次受控抽取都记录来源、事件、生成卡片和抽取版本。
- `AgentHarness` 现在把学生/老师消息 id 与 session id 传入长期记忆抽取，记忆卡片能追溯到课堂来源。
- 新增 `DELETE /api/v1/lessons/{session_id}`，课堂采用软删除；列表、详情、追加消息和状态更新都会忽略 deleted session。
- 删除课堂不级联删除已抽取记忆；只给相关 `memory_cards` / extraction jobs 标记 `source_session_deleted=True`，保留学习画像和审计信息。
- 前端课堂历史增加删除按钮；删除当前课堂后清空当前会话并回到初始状态，确认文案说明长期记忆会保留。
- 验证：后端全量 66 passed，ruff 通过，frontend build 通过，MongoDB 删除来源 smoke 通过。

2026-05-07，压缩 `AGENTS.md`：

- 将原 `AGENTS.md` 中 2026-05-02 至 2026-05-07 的详细流水迁移到 `docs/agent-log-archive-2026-05.md`。
- 本文件改为压缩交接版，保留当前架构、当前进度、已知问题、推荐下一步、最新验证和必要运行命令。
- 后续每次更新仍要同步维护 `## 推荐下一步`，不要让顶部路线落后于底部日志。

2026-05-07，`cee1d09 feat: persist controlled memory cards`：

- 新增 `MemoryCard` 和 `MongoMemoryService`，长期记忆卡片写入 MongoDB `memory_cards`。
- `MemoryService.record_learning_event()` 做第一版受控抽取，不调用豆包或其他运行时 LLM。
- DeepAgents `MemoryMiddleware` 的 memory snapshot 会读取 `memory_cards`，并明确长期记忆只作背景。
- `.env.example` 默认 `MEMORY_BACKEND=mongodb`；`mongo` 已是默认 Compose 服务。

2026-05-07，`da31f65 feat: inject student memory via deepagents middleware`：

- 接入 DeepAgents 原生 `MemoryMiddleware`。
- `StaticMemoryBackend` 将 OpenTeacher 学生记忆暴露为只读 memory file。
- 当前课堂 transcript 与 lesson state 仍通过短期 middleware 注入，优先级高于长期记忆。

2026-05-07，`f9be213 fix lesson memory continuity`：

- 修复“上堂课讲到哪儿”错误回到一元一次方程。
- 连续性输入会挂回最近同学科课堂，并保留当前正负数 skill。

## 历史归档

- 详细流水日志：`docs/agent-log-archive-2026-05.md`
- 只有需要追溯旧决策、旧验证或提交历史时才读归档；常规接手优先读本文件。
