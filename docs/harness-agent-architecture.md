# Harness Agent 架构

OpenTeacher 的 harness agent 是主控教师智能体，不是简单的 LLM provider 包装，也不是只把 LangChain DeepAgents 接进来。它负责把课程目标、学生记忆、教学技能、课堂状态、工具调用、安全边界和质量检查组织成一套可运行、可调试、可扩展的教师系统。

本架构采用 LangChain DeepAgents / LangGraph 作为主 agent runtime 基础。OpenTeacher 的教师职责、记忆策略、guardrails、skill 生态和评测观测仍定义在项目自己的领域层，但 `/teacher/chat` 的主控路径应进入 DeepAgents / LangGraph graph，而不是继续依赖 provider-style 单轮 prompt。

## 关键边界

这里的 harness agent 指 OpenTeacher 自己的主控教师架构，而不是某个第三方库的薄封装。

- DeepAgents / LangGraph 是主 runtime：负责执行 agent 图、工具调用、checkpoint、短期记忆、上下文压缩和后续 subagent 编排。
- OpenTeacher harness 是产品主控层：负责 planner、executor、verifier、记忆策略、guardrails、skill 选择、课堂状态和可观测性。
- planner / executor / verifier 是最小三层结构。即使第一阶段规则很轻，也必须显式存在，不能把所有判断塞进一个 system prompt。
- LangSmith 是调试和追踪层，不是教学决策来源；trace 应服务于复盘“为什么这样教”。
- Skill 广场可以二期建设，但 runtime selection、schema validation、来源和版本字段必须提前预留。
- MongoDB 是长短期记忆、课程状态、checkpoint、RAG 和后续向量检索的统一存储；PostgreSQL 只承载用户、账号、权限、班级、教师/志愿者和运营关系等关系型数据。

## 目标

harness agent 应该让 OpenTeacher 能够：

- 主动授课，而不是等待学生发题。
- 在被动答疑时仍保持老师身份，而不是变成答案机器。
- 根据学生记忆和课堂历史调整教学节奏。
- 规划一节课、一轮互动和下一道练习。
- 调用工具读取课堂状态、检索记忆、选择技能、保存消息、生成练习和创建记忆抽取任务。
- 检查自己的输出是否符合教师行为、安全边界和当前教学目标。
- 被 LangSmith 等工具可视化追踪和调试。
- 未来支持 teacher-authored skills 和 skill 广场。

## 总体结构

```text
Student / UI
  -> Lesson API / Teacher API
  -> Harness Agent
      -> LangGraph / DeepAgents Thread (thread_id = session_id)
      -> MongoDB Checkpointer / Store
      -> Planner Node
      -> Executor Node
      -> Verifier Node
      -> Memory Layer
      -> Guardrails
      -> Skill Registry / Skill Marketplace
      -> Observability
  -> Response + State Updates + Memory Jobs
```

## 三层核心

### Planner

Planner 决定“现在应该怎么教”。

输入：

- 学生消息
- 当前 lesson session
- 当前课堂阶段
- 学生长期记忆摘要
- 当前学科、年级、知识点
- 可用 Teaching Skills
- guardrails 和教师核心规范

输出：

- `teaching_mode`：`active_lesson`、`qa`、`diagnostic_check`、`concept_instruction`、`guided_practice`、`adaptive_remediation`、`review`、`lesson_summary`
- `learner_state`：信息不足、想抄答案、真实卡住、概念错误、步骤错误、已答对、情绪受挫、安全风险等
- `next_teacher_goal`
- `tool_plan`
- `memory_retrieval_plan`
- `skill_selection_plan`

Planner 不直接生成最终回答。它生成教学计划和执行约束。

Planner 的输入必须来自 graph state，而不是只来自当前一句学生消息。最低 state 字段应包括：

- `messages`
- `lesson_state.current_phase`
- `lesson_state.current_chapter_id`
- `lesson_state.current_knowledge_point_id`
- `lesson_state.current_skill_id`
- `current_question`
- `student_answer_status`
- `retrieved_memory`
- `retrieved_chunks`

### Executor

Executor 执行 Planner 的计划。

职责：

- 调用 memory retrieval 工具
- 调用 skill registry
- 调用 lesson state 工具
- 生成讲解、追问、练习、复盘或答疑回复
- 保存课堂消息和状态
- 创建记忆抽取任务

Executor 可以由 LangChain DeepAgents 执行。它可以使用 subagents，例如：

- `lesson_planning_agent`
- `memory_retrieval_agent`
- `practice_generation_agent`
- `skill_selection_agent`
- `safety_review_agent`

第一阶段不一定真的拆 subagents，但接口上应允许后续拆分。

Provider 模型只应作为 Executor 内部 LLM 调用，不应继续作为 `AgentHarness` 的主控决策路径。

### Verifier

Verifier 检查 Executor 的输出能不能发给学生。

检查维度：

- 是否符合 OpenTeacher 是老师的身份
- 是否误把主动授课变成作业答疑
- 是否机械要求步骤，忽略学生已经答对
- 是否给了可抄完整答案
- 是否根据学生状态选择了合适动作
- 是否尊重隐私和未成年人安全边界
- 是否过长、太泛、没有具体下一步
- 是否和当前知识点/课堂阶段一致
- 是否需要改写、追问或升级安全处理

Verifier 输出：

- `approved`
- `needs_revision`
- `blocked`
- `revision_instructions`
- `safety_escalation`

第一阶段可以用规则 + LLM verifier 混合；高风险安全和隐私边界必须优先规则化。

## 记忆层

记忆层不是单个向量库。它包含：

- 课堂事实：完整 lesson sessions、messages、state snapshots
- 短期 checkpoint：LangGraph thread state 和 checkpoint writes
- 课程状态：当前 chapter、section、knowledge point、skill、current question、student answer status
- 结构化记忆：memory cards
- 冲突处理：memory conflicts
- 抽取任务：memory extraction jobs
- 检索视图：MongoDB Atlas Vector Search embedding index

物理存储统一使用 MongoDB：

- source of truth：`lesson_sessions`、`lesson_messages`
- 短期 checkpoint：`langgraph_checkpoints`、`langgraph_checkpoint_writes`
- 课程状态：`lesson_sessions` 当前字段和可选 `lesson_state_snapshots`
- 长期记忆：`memory_cards`、`memory_conflicts`
- 教材/RAG/向量视图：`textbook_chunks`、MongoDB Atlas Vector Search index

harness agent 调用记忆必须经过工具和策略：

- `retrieve_student_memory`
- `load_lesson_history`
- `load_recent_lesson_state`
- `create_memory_extraction_job`
- `record_memory_conflict`

记忆调用原则：

- 当前学生回答优先于旧记忆。
- 旧记忆只能作为教学假设，不能当作确定标签。
- 有冲突的记忆应转化为诊断动作，而不是直接下结论。
- 支持背景只在教学支持相关场景低分辨率使用。

## Guardrails

Guardrails 分两类。

### 教师行为 guardrails

- 不做答案机器。
- 不羞辱学生。
- 不机械要求步骤。
- 学生答对时先确认，再推进。
- 主动授课应有目标、讲解、诊断、练习、复盘。
- 被动答疑也要引导学生学会，而不是只解决当前题。

### 安全与隐私 guardrails

- 不索要身份证号、精确地址、联系方式、账号密码。
- 不记录无教学必要的敏感家庭细节。
- 遇到自伤、虐待、现实危险，优先现实帮助，不继续普通教学。
- 不假装心理咨询师、家长、医生或执法者。

Guardrails 应作用在三个阶段：

- Planner 阶段：限制可选教学目标。
- Executor 阶段：限制工具和输出。
- Verifier 阶段：检查最终回复。

## Skill 广场

Skill 广场是长期生态目标，但架构必须提前预留。

Skill 类型：

- Core teacher skills
- Knowledge skills
- Pedagogy/style skills
- Task skills
- Private local skills
- Certified teacher skills
- Community experimental skills

Skill 生命周期：

- authoring
- schema validation
- safety review
- versioning
- certification
- runtime selection
- evaluation
- deprecation

harness agent 不应硬编码“初中数学 = 一元一次方程”。它应通过 skill selection plan 选择合适技能。没有合适知识点 skill 时，应进入通用主动授课/诊断策略，而不是装作有该知识点能力。

## Observability / LangSmith

OpenTeacher 需要可视化调试 agent，而不只是看最终回复。

每轮应记录：

- planner 输入和输出
- memory retrieval query 和命中结果
- selected skills
- tool calls
- executor draft
- verifier 结果
- final response
- lesson state update
- memory extraction job

LangSmith 用途：

- 查看为什么选了某个教学模式
- 查看是否误召回记忆
- 查看 verifier 为什么改写或阻断
- 对比不同 prompt/skill/runtime 版本
- 复盘失败课堂样例

注意：LangSmith traces 不能包含密钥，也应避免记录不必要的未成年人敏感信息。必要时应对学生标识和敏感字段脱敏。

## API 与服务边界

建议服务：

- `TeachingAgentRuntime`
- `PlannerService`
- `ExecutorService`
- `VerifierService`
- `LessonService`
- `MemoryService`
- `MemoryExtractionService`
- `SkillRegistry`
- `GuardrailService`
- `ObservabilityService`

第一阶段可以不拆成这么多文件，但逻辑边界要清楚。

## 与当前代码关系

当前状态：

- `backend/app/services/agent_harness.py` 仍是单轮 orchestration，但已开始接入结构化 planner 决策。
- `backend/app/services/planner.py` 是第一版规则 Planner，负责输出教学模式、学生状态、下一步教学目标、记忆检索计划、技能选择计划和工具计划。
- `backend/app/services/deepagents_runtime.py` 是第一版 DeepAgents adapter。
- `backend/app/services/lesson_store.py` 已有 Mongo-backed lesson history。
- `MemoryService` 仍是 mock summary。
- Verifier 尚未实现。

这意味着当前系统仍不是完整 harness agent。`deepagents_runtime.py` 只是 runtime 接入点，`planner.py` 只是第一块骨架；后续还必须补真实记忆、verifier、guardrails 服务和 observability。

## 分阶段实现

### Phase 1：骨架

- 定义 planner/executor/verifier 数据结构。
- 在 `AgentHarness` 中显式产出 teaching mode 和 learner state。（已完成 Planner v1）
- DeepAgents runtime 使用 planner 输出，而不是直接吃 raw prompt。（已完成 Planner v1 注入）
- Memory tools 接真实 `memory_cards`。

### Phase 2：记忆闭环

- 实现 `memory_cards` collection。
- lesson end 后生成 memory extraction job。
- 实现冲突检测和 memory retrieval policy。
- 在 planner 阶段使用记忆，而不是只在 prompt 中塞摘要。

### Phase 3：Verifier

- 实现规则 verifier。
- 实现 LLM verifier。
- 高风险 safety guardrails 规则优先。
- Verifier 失败时要求 executor 改写。

### Phase 4：Skill 生态

- 扩展 Teaching Skill schema。
- 支持 teacher-authored skills。
- 支持 skill package metadata、版本、来源、认证状态。
- 支持 skill selection trace。

### Phase 5：LangSmith

- 配置 LangSmith tracing。
- 为 planner/executor/verifier/tool calls 加 tags 和 metadata。
- 建立失败课堂样例复盘流程。

## 当前优先级

下一步应优先实现：

1. Planner 数据结构和基础规则。
2. `memory_cards` collection 和真实检索工具。
3. Verifier 的第一版规则检查。

不要继续把智能提升寄托在单个 prompt 或单个知识点 skill 上。
