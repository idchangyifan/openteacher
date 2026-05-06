# 架构说明

OpenTeacher 被设计为一个模块化 AI 教师系统。

核心智能体架构详见：

- `docs/harness-agent-architecture.md`

长期记忆架构详见：

- `docs/memory-architecture.md`

## 当前技术选型

- Python 后端
- React Web 前端
- PostgreSQL 关系型产品数据库，只用于用户、账号、权限、班级、教师/志愿者和运营关系等结构化业务数据
- MongoDB 统一承载课堂历史、课程状态、短期记忆、长期记忆、LangGraph checkpoint、记忆抽取任务和后续向量检索
- MongoDB Atlas Vector Search 作为第一阶段记忆与教材向量检索方向
- LangChain DeepAgents / LangGraph 作为 harness agent 主 runtime

记忆、课程状态、checkpoint、RAG 和后续向量索引的物理存储统一放在 MongoDB，减少早期依赖和运维复杂度；服务边界仍需清晰，避免业务代码直接依赖 MongoDB 文档细节。

## 后端模块

```text
app/
  api/          HTTP 路由
  core/         配置和共享基础设施
  db/           关系型数据库设置
  models/       SQLAlchemy 模型
  schemas/      API 请求和响应 schema
  services/     智能体、LLM、记忆、技能和 RAG 接口
```

## 当前运行流程

1. 学生从 React 应用发送消息。
2. 后端通过 `/api/v1/teacher/chat` 接收消息。
3. `AgentHarness` 应调用 LangGraph/DeepAgents harness graph，并以 `session_id` 作为 `thread_id`。
4. Graph 通过 MongoDB checkpointer 恢复短期课堂状态和 messages。
5. Planner 节点读取 lesson state、学生消息、selected skill、教材 chunks 和 memory cards，判断当前教学动作。
6. Executor 节点调用受控 tools：skill selection、lesson state、textbook RAG、memory retrieval、answer evaluation、message persistence。
7. Verifier 节点检查教师身份、教学质量、当前知识点一致性、安全隐私和是否需要修正输出。
8. Graph 更新 MongoDB 中的 checkpoint、lesson session、lesson messages、memory extraction jobs 和必要的 state snapshots。
9. 前端展示教师回复、当前技能、课堂状态、课堂历史和记忆事件。

## 存储边界

PostgreSQL 当前是关系型产品数据的候选来源和基础脚手架，适合后续承载：

- 学生
- 班级
- 教师和志愿者
- 技能元数据
- 账号、权限和运营关系数据

长短期记忆、课程状态、checkpoint、课堂历史和检索视图统一使用 MongoDB：

- `lesson_sessions`
- `lesson_messages`
- `lesson_state_snapshots`
- `langgraph_checkpoints`
- `langgraph_checkpoint_writes`
- `memory_cards`
- `memory_conflicts`
- `memory_extraction_jobs`
- `textbook_chunks`
- `vector_index_views`

不要把长期记忆、短期 checkpoint、课程状态、RAG 或向量检索写入 PostgreSQL。即使物理存储后续调整，也应保持 `LessonService`、`MemoryService`、`MemoryExtractionService`、`TeachingGraphRuntime` 等服务边界。
