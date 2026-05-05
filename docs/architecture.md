# 架构说明

OpenTeacher 被设计为一个模块化 AI 教师系统。

核心智能体架构详见：

- `docs/harness-agent-architecture.md`

长期记忆架构详见：

- `docs/memory-architecture.md`

## 当前技术选型

- Python 后端
- React Web 前端
- PostgreSQL 关系型数据库
- MongoDB 长期记忆和课堂历史存储
- MongoDB Atlas Vector Search 作为第一阶段记忆向量检索方向
- LangChain DeepAgents / LangGraph 作为 harness agent runtime 方向

记忆和 RAG 的具体存储方案应当始终放在接口后面，这样项目可以在不重写智能体框架的情况下逐步演进。

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
3. `AgentHarness` 加载学生上下文、技能上下文、记忆摘要和教学边界。
4. Planner v1 输出教学模式、学生状态、下一步教师目标、记忆检索计划、技能选择计划和工具计划。
5. 默认 runtime 使用 provider 生成教师回复；`AGENT_RUNTIME=deepagents` 时可选尝试 DeepAgents runtime，并在失败时回退 provider。
6. Executor 当前由 provider 或 DeepAgents adapter 承担，生成回复时会收到 Planner 决策。
7. Verifier 仍待实现；当前只靠 prompt 和测试约束基础行为。
8. 如果绑定 lesson session，课堂消息会写入 lesson store；`LESSON_STORE_BACKEND=mongodb` 时持久化到 MongoDB。
9. 记忆服务记录轻量学习事件。
10. 前端展示教师回复、当前技能、课堂历史和记忆事件。

## 存储边界

PostgreSQL 当前是关系型产品数据的候选来源和基础脚手架，适合后续承载：

- 学生
- 班级
- 教师和志愿者
- 技能元数据
- 账号、权限和运营关系数据

长期记忆和课堂历史第一阶段使用 MongoDB：

- `lesson_sessions`
- `lesson_messages`
- `lesson_state_snapshots`
- `memory_cards`
- `memory_conflicts`
- `memory_extraction_jobs`

不要把长期记忆绑定到 PostgreSQL。即使物理存储后续调整，也应保持 `LessonService`、`MemoryService`、`MemoryExtractionService` 等服务边界。
