# TextbookToTeachingSkill 流水线

`TextbookToTeachingSkill` 是 OpenTeacher 的技能工厂。它不是普通知识技能，而是把教材、教师教案和教学经验转化为可审核、可评测、可发布教学资产的生成型流水线。

第一版目标不是把 PDF 全量塞进向量库，而是先得到清晰、可追溯的资产边界：

```text
textbook_manifest
-> course_map
-> knowledge_point_graph
-> skill_drafts
-> rag_chunks
-> eval_cases
-> review_record
-> published_skills
```

## 输入

### 教材输入

教材提供事实层和课程结构。

典型字段：

- 教材版本、学段、年级、学科、册次
- 本地文件路径或外部来源引用
- 章节、小节、页码范围
- 定义、例题、练习、课后题、图表、栏目等内容类型
- OCR/解析质量和需要人工复核的位置

教材 PDF 和教材原文不提交进仓库。研发阶段可放在 `/root/openteacher-data`，生成的公开样例也应避免包含大段教材原文。

### 教案输入

教案提供方法层，不能无审查地覆盖教材事实层。

典型来源：

- 教师上传的教学设计
- 课堂笔记
- 名师讲法或校本策略
- 志愿者团队整理的教学经验

教案可增强：

- 导入方式
- 讲解顺序
- 提问设计
- 常见学生反应
- 纠错方法
- 练习安排
- 板书、类比或活动设计

如果教案与教材定义、例题结论或知识范围冲突，应标记为 `needs_review`。

### LLM 推断

LLM 可以补全教学目标、常见误区、诊断题、讲解路径和练习策略，但所有推断内容默认：

- `source_type: llm_inferred`
- `review_status: draft`
- 必须保留推断依据和关联教材位置

## 输出

### textbook_manifest

记录一本教材或一组教材的基本事实。

必须包含：

- `textbook_id`
- `title`
- `publisher`
- `edition`
- `subject`
- `grade`
- `volume`
- `source`
- `copyright`
- `books`

### course_map

课程地图用于 Planner 选择授课位置。

建议层级：

```text
course -> chapter -> section -> lesson -> knowledge_point
```

每个节点应包含标题、顺序、页码范围、学习目标和关联知识点。

### knowledge_point_graph

知识点图谱用于说明先后关系和依赖。

每个知识点应包含：

- `id`
- `name`
- `chapter_id`
- `prerequisites`
- `unlocks`
- `difficulty`
- `mastery_criteria`

### skill_drafts

知识点 Teaching Skill 草稿用于回答“怎么教”。

每个草稿应包含：

- 适用范围
- 学习目标
- 前置知识
- 核心概念
- 讲解顺序
- 诊断问题
- 常见误区
- 纠错策略
- 例题路径
- 分层练习
- 掌握标准
- 复习安排
- 评测样例
- 来源证据

草稿默认不能直接发布，必须经过审核或评测门槛。

### rag_chunks

`rag_chunks` 是第一版 RAG 资产。它们不绑定具体向量库，先保证结构可检索、可引用、可审核。

必须包含：

- `id`
- `source_ref`
- `content_type`
- `chapter_id`
- `knowledge_point_ids`
- `page_range`
- `text`
- `text_role`
- `review_status`
- `copyright_policy`

`text` 第一版可以是教材内容摘要、人工改写描述或短片段。公开仓库中不应放入大段教材原文。

### eval_cases

评测样例用于验证生成的 skill 是否真的会教。

每条样例应包含：

- 学生输入
- 适用知识点
- 期望教师行为
- 禁止教师行为
- 参考教师动作
- 评分说明

### review_record

审核记录用于控制质量和发布。

建议状态：

- `draft`
- `needs_review`
- `approved_local`
- `certified`
- `rejected`
- `deprecated`

## 合并规则

1. 教材事实层优先于教案和 LLM 推断。
2. 教案增强教学方法层，但不能静默修改教材事实。
3. LLM 推断只生成 draft，不直接进入官方或认证技能。
4. 每条教学策略必须保留来源、作者/生成者、审核状态和适用范围。
5. 冲突内容不自动合并，进入 `needs_review`。

## 与 RAG 的关系

第一阶段不先建完整向量库。先生成本地 `rag_chunks`，再用文件型或内存型检索做 smoke test。

推荐演进：

1. 结构化 `rag_chunks` JSON/YAML。
2. 文件型 `TextbookRagService` 做本地检索。
3. 结合真实课堂和评测检查 chunk 是否足够支持授课。
4. 再选择 MongoDB Atlas Vector Search、Qdrant 或其他向量存储。

当前可用的本地 smoke 后端是 `RAG_BACKEND=textbook_file`。它读取 `TEXTBOOK_RAG_ARTIFACT_PATH` 指向的 pipeline artifact，并对其中 `rag_chunks` 做轻量关键词检索。

示例：

```bash
RAG_BACKEND=textbook_file \
TEXTBOOK_RAG_ARTIFACT_PATH=/tmp/textbook-to-skill-artifact.yaml \
docker compose up -d --force-recreate backend
```

然后调用 `/api/v1/teacher/chat`，学生问题中包含“正数”“负数”“支出”“相反意义”等词时，后端会把命中的教材 RAG chunk 注入教师 prompt。

## 与 Planner 的关系

Planner 不直接读 PDF。Planner 应使用：

- `course_map` 判断当前课程位置
- `knowledge_point_graph` 判断前置知识和下一步
- `skill_drafts` 选择教学方法
- `rag_chunks` 检索教材证据
- `eval_cases` 回归教师质量

## 第一版试点

试点范围：

- 学段：初中
- 学科：数学
- 教材：人教版七年级上册
- 章节：第一章

第一版成功标准：

- 产出一章 `course_map`
- 产出 1-3 个知识点 `skill_drafts`
- 产出可本地检索的 `rag_chunks`
- 产出主动授课评测样例
- 不提交教材 PDF 或大段教材原文

## 离线生成脚本

第一版离线脚本接收结构化草稿，而不是直接解析 PDF：

```bash
python3 scripts/generate-textbook-skill.py \
  --input backend/tests/fixtures/textbook-to-skill-input.yaml \
  --output /tmp/textbook-to-skill-artifact.yaml
```

输入草稿应包含教材 manifest、章节结构、知识点、教学设计草稿、RAG chunk 草稿和评测样例。脚本会补齐统一的 pipeline artifact 结构，并检查 skill draft 与 RAG chunk 是否引用了已声明的来源和知识点。

后续 PDF/OCR 解析模块应产出同样的输入草稿结构，再交给该 builder，而不是让解析逻辑直接写最终 skill。

如果已经有 PDF 目录/页码 inspection 结果，可以用 `--outline` 覆盖输入草稿中的章节和小节页码：

```bash
python3 scripts/generate-textbook-skill.py \
  --input backend/tests/fixtures/textbook-to-skill-input.yaml \
  --outline backend/tests/fixtures/textbook-outline-sample.yaml \
  --output /tmp/textbook-to-skill-artifact.yaml
```
