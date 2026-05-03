# 长期记忆架构

OpenTeacher 的长期记忆不是聊天记录的简单堆积，也不是一个向量库。它是一套面向教学的系统：保存课堂事实，抽取学习记忆，处理冲突，在合适的教学时机召回，并允许学生回看和恢复学习。

本设计采用 MongoDB 作为第一阶段统一记忆存储。MongoDB 同时承载完整课堂记录、结构化记忆、抽取任务和向量检索索引，减少早期中间件复杂度。后续如果规模或检索质量需要，可以再把向量索引迁移到专用向量库，但领域模型不应依赖具体存储。

## 设计原则

- OpenTeacher 是主动授课的老师，不是解题工具。记忆首先服务于课程连续性、复习安排和个性化教学节奏。
- 完整课堂记录是 source of truth。向量检索只是一种召回视图，不能替代历史会话恢复。
- 记忆必须可解释。每条长期记忆都要有证据、来源课堂、置信度和更新时间。
- 记忆必须可修正。学生后续表现可能推翻旧记忆，系统需要冲突检测、合并、降权和过期。
- 未成年人隐私优先。只记对教学支持必要的信息，不收集可定位身份信息。
- 物理存储可以统一在 MongoDB，逻辑模型必须分层。

## 逻辑分层

### 1. 课堂事实层

保存实际发生过的课堂和会话，用于历史查看、恢复课堂、审计和重新抽取记忆。

主要对象：

- `lesson_sessions`
- `lesson_messages`
- `lesson_state_snapshots`

这一层不做主观推断，只记录课堂事实和必要元数据。

### 2. 结构化记忆层

保存从课堂事实中抽取出的教学记忆。它不是原文，而是可被老师使用的学习判断。

主要对象：

- `memory_cards`
- `memory_conflicts`

这一层回答：

- 学生掌握了什么？
- 常犯什么错？
- 适合怎样讲？
- 哪些背景会影响教学支持？
- 下次复习应该从哪里开始？

### 3. 检索视图层

保存用于语义检索的 embedding 和检索字段。第一阶段 embedding 可以直接放在 `memory_cards` 和课堂摘要文档里，通过 MongoDB Atlas Vector Search 检索。

这一层只负责“找相关记忆”，不负责定义记忆事实。

## MongoDB Collections

### `lesson_sessions`

一节课或一次连续学习活动。

```json
{
  "_id": "lesson_...",
  "student_id": "student_...",
  "course_id": "junior_math_core",
  "subject": "math",
  "grade": "junior",
  "knowledge_points": ["linear_equation"],
  "mode": "active_lesson",
  "status": "in_progress",
  "title": "一元一次方程：去括号与移项",
  "lesson_goal": "能解释去括号和移项每一步的理由",
  "current_phase": "guided_practice",
  "teacher_style": "严格但温暖",
  "skill_ids": ["opent-teacher-universal-core", "opent-teacher-junior-math-linear-equation"],
  "started_at": "2026-05-03T12:00:00Z",
  "updated_at": "2026-05-03T12:20:00Z",
  "ended_at": null,
  "summary": "学生能完成去括号，但移项变号仍不稳定。"
}
```

建议索引：

- `{ student_id: 1, updated_at: -1 }`
- `{ student_id: 1, subject: 1, updated_at: -1 }`
- `{ status: 1, updated_at: -1 }`

### `lesson_messages`

课堂中的每一轮消息和工具结果。

```json
{
  "_id": "msg_...",
  "session_id": "lesson_...",
  "student_id": "student_...",
  "role": "teacher",
  "content": "先不急着求答案。你先写出去括号后的式子。",
  "message_type": "instruction",
  "phase": "guided_practice",
  "created_at": "2026-05-03T12:05:00Z",
  "skill_ids": ["opent-teacher-universal-core"],
  "tool_calls": [],
  "metadata": {
    "model": "doubao-seed-1-8-251228",
    "agent_runtime": "langchain_deepagents"
  }
}
```

建议索引：

- `{ session_id: 1, created_at: 1 }`
- `{ student_id: 1, created_at: -1 }`
- `{ session_id: 1, phase: 1 }`

### `lesson_state_snapshots`

课堂可恢复状态。它比消息摘要更接近 agent runtime 的 checkpoint，但仍应保持领域可读。

```json
{
  "_id": "state_...",
  "session_id": "lesson_...",
  "student_id": "student_...",
  "phase": "guided_practice",
  "lesson_plan_position": 3,
  "current_teacher_goal": "确认学生能正确去括号",
  "pending_student_action": "写出 2(x - 3) = 10 去括号后的式子",
  "recent_diagnosis": {
    "learner_state": "step_error",
    "confidence": 0.78
  },
  "working_context": {
    "current_problem": "2(x - 3) = 10",
    "latest_student_step": "2x - 3 = 10"
  },
  "created_at": "2026-05-03T12:07:00Z"
}
```

建议索引：

- `{ session_id: 1, created_at: -1 }`

### `memory_cards`

长期记忆的核心对象。每张卡片代表一个可被教学使用的判断。

```json
{
  "_id": "mem_...",
  "student_id": "student_...",
  "memory_type": "academic_error",
  "subject": "math",
  "knowledge_point": "linear_equation.move_terms",
  "summary": "移项时经常忘记变号。",
  "details": "在两次一元一次方程练习中，把 +3 移到等号另一边后仍写成 +3。",
  "teaching_implication": "下次遇到移项，先要求学生说出等式两边同时做了什么操作。",
  "evidence": [
    {
      "session_id": "lesson_...",
      "message_ids": ["msg_1", "msg_2"],
      "quote": "我把 +3 移过去还是 +3。"
    }
  ],
  "confidence": 0.82,
  "stability": "medium",
  "status": "active",
  "privacy_level": "learning",
  "created_at": "2026-05-03T12:25:00Z",
  "updated_at": "2026-05-03T12:25:00Z",
  "expires_at": null,
  "embedding_text": "数学 一元一次方程 移项变号错误 下次先解释等式操作",
  "embedding": [0.0123, -0.0456]
}
```

`memory_type` 建议枚举：

- `academic_mastery`
- `academic_error`
- `learning_behavior`
- `teaching_preference`
- `support_context`
- `progress_event`
- `review_plan`

`privacy_level` 建议枚举：

- `learning`：普通学习信息
- `support_low_resolution`：低分辨率支持背景，例如缺少稳定家庭学习支持
- `sensitive_guarded`：需要谨慎处理的高敏信息，只能在安全或支持场景下有限使用

建议索引：

- `{ student_id: 1, status: 1, updated_at: -1 }`
- `{ student_id: 1, subject: 1, knowledge_point: 1 }`
- `{ student_id: 1, memory_type: 1, status: 1 }`
- vector search index on `embedding`

### `memory_conflicts`

记录两条或多条记忆之间的冲突，不急于删除旧记忆。

```json
{
  "_id": "conflict_...",
  "student_id": "student_...",
  "conflict_type": "mastery_vs_error",
  "memory_ids": ["mem_mastery_...", "mem_error_..."],
  "description": "旧记忆显示学生已掌握通分，但最近三次练习仍出现通分错误。",
  "resolution_status": "needs_more_evidence",
  "resolution": null,
  "created_at": "2026-05-03T13:00:00Z",
  "updated_at": "2026-05-03T13:00:00Z"
}
```

`resolution_status` 建议枚举：

- `needs_more_evidence`
- `resolved_keep_new`
- `resolved_keep_old`
- `resolved_merge`
- `resolved_decay_old`

### `memory_extraction_jobs`

异步或准异步记忆抽取任务。第一阶段可以由请求结束后同步触发，后续迁移到队列。

```json
{
  "_id": "job_...",
  "student_id": "student_...",
  "session_id": "lesson_...",
  "trigger": "lesson_ended",
  "status": "pending",
  "input_message_range": {
    "from": "msg_...",
    "to": "msg_..."
  },
  "created_memory_ids": [],
  "conflict_ids": [],
  "error": null,
  "created_at": "2026-05-03T12:30:00Z",
  "updated_at": "2026-05-03T12:30:00Z"
}
```

建议索引：

- `{ status: 1, updated_at: 1 }`
- `{ student_id: 1, session_id: 1 }`

## 记忆抽取流程

### 触发时机

第一阶段建议使用三类触发：

- `lesson_ended`：一节课结束后抽取完整记忆。
- `important_event`：出现明显错误、明显进步、安全/支持信号时抽取小片段。
- `periodic_compaction`：定期把多条旧记忆合并或降权。

不要每条消息都生成长期记忆。每条消息都写入历史记录，但长期记忆需要门槛。

### 抽取步骤

1. 读取本节课消息、课堂状态、已有相关 memory cards。
2. 判断是否有值得长期保存的信号。
3. 生成候选 memory cards，带证据、置信度、隐私级别和教学含义。
4. 对候选记忆做安全过滤，删除可定位身份信息和不必要敏感细节。
5. 与现有 memory cards 做冲突检测。
6. 合并、更新、降权或创建 `memory_conflicts`。
7. 为可检索文本生成 embedding。
8. 写入 MongoDB。

### 抽取原则

应该抽取：

- 反复出现的学业错误
- 明确的掌握信号
- 具体进步
- 学习行为模式
- 影响教学支持方式的低分辨率背景
- 下次复习的起点

不应该抽取：

- 一次性弱信号
- 精确地址、电话、证件号、账号信息
- 无教学意义的家庭细节
- 心理诊断标签
- 老师无法解释来源的主观判断

## 冲突解决策略

记忆冲突是正常现象，不应简单覆盖。

常见冲突：

- `mastery_vs_error`：曾经掌握，但最近又频繁犯错。
- `preference_changed`：学生过去喜欢详细讲解，现在更适合短提示。
- `support_context_changed`：支持背景发生变化。
- `stale_memory`：旧记忆长期未被证实。

处理方式：

- 新证据强且多次出现：降权旧记忆，保留新记忆。
- 新证据弱：创建 conflict，标记 `needs_more_evidence`。
- 两条记忆都成立但适用范围不同：合并或加适用条件。
- 旧记忆长期未命中：降低 confidence 或设置过期。

在 prompt 中调用记忆时，不应把冲突中的结论当作确定事实。可以转化为更谨慎的教师动作，例如“先检查一下你现在还会不会这一步”。

## 记忆检索策略

记忆不是每轮都全量塞进上下文。检索应服务于当前教学动作。

### 主动授课开始前

召回：

- 当前课程知识点相关的 mastery/error cards
- 最近课程 summary
- 复习计划
- 重要教学偏好

用途：

- 决定导入方式
- 决定诊断题难度
- 决定是否先复习前置知识

### 课堂进行中

召回：

- 当前知识点相关错误
- 学生近期类似回答
- 与当前 learner state 相关的教学偏好

用途：

- 调整讲解粒度
- 选择追问或练习
- 判断是否进入补救教学

### 被动答疑时

召回：

- 当前题目/概念相关 memory cards
- 学生是否有抄答案、跳步骤等学习行为模式
- 相关历史课堂片段摘要

用途：

- 不直接给答案
- 找到学生可能卡点
- 让学生回到自己的下一步

### 复习页和历史恢复

不依赖向量检索恢复完整课堂。历史恢复应按 `lesson_sessions` 和 `lesson_messages` 精确读取。

向量检索只用于：

- 找相似错误
- 找相关复习点
- 找过去讲过的相似概念

## DeepAgents 接入

项目主 agent 框架采用 LangChain deepagents。OpenTeacher 应把 deepagents 作为课堂执行 runtime，而不是把数据库细节暴露给 agent prompt。

建议工具边界：

- `start_lesson_tool`
- `load_lesson_state_tool`
- `save_lesson_message_tool`
- `save_lesson_state_tool`
- `retrieve_student_memory_tool`
- `create_memory_extraction_job_tool`
- `generate_practice_tool`
- `record_practice_result_tool`

业务服务边界：

- `LessonService`：课堂创建、恢复、状态保存。
- `MemoryService`：结构化记忆读写、检索、冲突处理。
- `MemoryExtractionService`：从课堂事实生成 memory cards。
- `TeachingAgentRuntime`：deepagents 适配层，负责主动授课和被动答疑流程。

deepagents 的规划能力适合主动授课流程，但安全、隐私和记忆写入必须由工具和服务层约束。

## 第一阶段实现顺序

1. 增加 MongoDB Compose profile 和配置项，但保持可选。
2. 定义 MongoDB repository 接口，不立刻删除 mock memory。
3. 实现 `lesson_sessions` 和 `lesson_messages`，支持历史课堂列表、查看和恢复。
4. 实现 `memory_cards` 基础 CRUD，不先做复杂冲突解决。
5. 实现 lesson end 后的第一版记忆抽取。
6. 实现 memory retrieval policy，把少量相关 memory cards 注入授课/答疑 prompt。
7. 接入 MongoDB Atlas Vector Search 或本地 Atlas Vector Search；如果本地能力受限，先用文本/metadata 检索兜底。
8. 再接 LangChain deepagents，替换当前简单 `AgentHarness` 的授课 runtime。

## 暂不做

- 不把长期记忆绑定到 PostgreSQL。
- 不引入 Qdrant 作为第一阶段必需依赖。
- 不把每轮聊天都直接写成长期记忆。
- 不让模型自由写数据库；所有写入必须通过受控工具和 schema 校验。
- 不把敏感家庭信息作为普通画像字段。

