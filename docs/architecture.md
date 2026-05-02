# 架构说明

OpenTeacher 被设计为一个模块化 AI 教师系统。

## 当前技术选型

- Python 后端
- React Web 前端
- PostgreSQL 关系型数据库
- 记忆存储稍后决定
- RAG 存储稍后决定

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

## 第一版运行流程

1. 学生从 React 应用发送消息。
2. 后端通过 `/api/v1/teacher/chat` 接收消息。
3. 智能体框架加载学生上下文、技能上下文、记忆摘要和教学边界。
4. LLM provider 或 mock provider 生成教师式引导回复。
5. 记忆服务记录轻量学习事件。
6. 前端展示教师回复、当前技能和记忆事件。

## 存储边界

PostgreSQL 是关系型产品数据的事实来源：

- 学生
- 班级
- 教师和志愿者
- 对话
- 消息
- 技能元数据
- 学习事件

记忆和 RAG 未来可能使用：

- PostgreSQL 表
- pgvector
- 向量数据库
- 对象存储加搜索索引
- 混合存储

第一版实现应优先暴露服务接口，不要过早绑定最终存储方案。
