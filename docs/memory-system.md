# 学生记忆系统

记忆系统的目标是在尊重隐私、保护未成年人的前提下，让 OpenTeacher 随着时间推移教得更好。

工程架构详见：

- `docs/memory-architecture.md`

当前结论：

- 长期记忆不绑定 PostgreSQL。
- 第一阶段使用 MongoDB 统一承载完整课堂记录、结构化记忆、抽取任务和向量检索。
- MongoDB 可以同时作为历史会话恢复的 source of truth 和 Atlas Vector Search 的向量检索载体。
- 物理存储可以统一，逻辑上仍必须区分课堂事实、结构化记忆和检索视图。

## 记忆目标

记忆应该回答：

- 这个学生正在学什么？
- 这个学生经常误解什么？
- 老师应该怎样向这个学生解释？
- 哪些学习行为应该被强化或纠正？
- 哪些进步值得记住并反馈给学生？

记忆不应该变成泛化的私人日记。

## 记忆类型

### 1. 画像记忆

稳定、最小化的学生上下文。

字段：

- `student_id`
- `preferred_name`
- `school_stage`：`primary`、`junior`、`senior`
- `grade`
- `region_level`：可选，只保留粗粒度
- `active_subjects`
- `textbook_version`：可选

### 2. 学业记忆

按学科和知识点记录学习状态。

字段：

- `subject`
- `grade`
- `knowledge_point_id`
- `mastery_level`：0-5
- `evidence`
- `last_practiced_at`
- `common_errors`
- `recommended_next_steps`

### 3. 教学偏好记忆

记录这个学生怎样更容易学会。

字段：

- `explanation_preference`：`concrete_examples`、`step_by_step`、`visual`、`exam_strategy`
- `response_length_preference`
- `strictness_tolerance`：`low`、`medium`、`high`
- `needs_more_checkpoints`
- `avoids_direct_answer`：`true`

### 4. 学习行为记忆

记录学习行为中反复出现的模式。

字段：

- `often_skips_steps`
- `often_requests_direct_answer`
- `checks_work_carefully`
- `persists_after_error`
- `recent_attention_pattern`

### 5. 鼓励记忆

记录值得被再次提起的具体进步。

字段：

- `progress_event`
- `subject`
- `evidence`
- `date`
- `reusable_encouragement`

## 隐私规则

不要存储：

- 精确家庭地址
- 家庭收入
- 家长电话号码
- 健康状况，除非为无障碍支持所必需且学生明确提供
- 政治或宗教信仰
- 敏感家庭情况
- 心理标签或诊断

## 记忆更新策略

只有在以下情况下才应更新记忆：

- 学生表现出重复的学业模式
- 学生完成了有意义的学习步骤
- 学生多次犯同一个错误
- 学生明确设置了学习偏好
- 教师或志愿者确认了某个观察

不要因为一次很弱的信号就更新长期记忆。
