# OpenTeacher

OpenTeacher 是一个开源 AI 教师项目，面向教育资源不足地区的学生。项目目标是通过可扩展的智能体框架、开放教学技能和长期学生记忆，让每个孩子都能获得高质量、严格而温暖的教学。

项目从一个简单的网页原型开始，逐步发展为完整的 AI 教师基础设施：

- 像老师一样工作的智能体，而不是普通学习陪伴工具
- 由教育工作者编写的学科和年级技能
- 面向学生学习进展的结构化记忆
- 教师和志愿者管理面板
- 面向社区贡献的开放技能标准

## 产品原则

1. 做老师。
   智能体应该温暖、耐心、严格、有原则。它不应该讨好学生，也不应该只是给答案。

2. 教方法，而不只是给结果。
   智能体应该诊断学生卡在哪里，分步骤引导，并要求学生解释自己的思路。

3. 谨慎记忆。
   记忆应该提升教学质量，但不能收集不必要的个人信息。

4. 让好教学可以复用。
   优秀老师应该能够把自己的教学风格和方法编码成可复用的技能。

5. 为公共利益而构建。
   项目应该开源、可审计、可自部署，并对学校、志愿者和公益组织友好。

## 当前 MVP

当前仓库包含：

- `backend/`：Python 后端脚手架
- `frontend/`：React 前端脚手架
- `docker-compose.yml`：本地 PostgreSQL、后端、前端和可选中间件服务
- `web/`：静态网页原型
- `specs/teaching-skill.schema.yaml`：第一版教学技能 schema
- `skills/junior-math-linear-equation.yaml`：初中数学一元一次方程示例技能
- `docs/teacher-persona.md`：教师人格和行为边界
- `docs/memory-system.md`：学生记忆系统设计
- `docs/skill-authoring.md`：教师编写技能的贡献模型

可以直接在浏览器中打开 `web/index.html` 体验最早的静态原型。

## 技术栈

- 后端：Python、FastAPI、SQLAlchemy、Alembic
- 前端：React、TypeScript、Vite
- 关系型数据库：PostgreSQL
- 记忆模块存储：暂未最终决定，先放在服务接口后面
- RAG 存储：暂未最终决定，先放在服务接口后面

## 项目结构

```text
backend/        Python API、智能体框架、服务接口
frontend/       React Web 应用
docs/           产品和架构说明
skills/         教学技能示例
specs/          技能 schema 草案
web/            用于快速预览的静态原型
```

## Docker 开发方式

当前推荐在 Ubuntu 上使用 Docker Compose 开发：

```bash
cp .env.example .env
docker compose up --build
```

启动后访问：

- 前端：`http://127.0.0.1:5173`
- 后端健康检查：`http://127.0.0.1:8000/api/v1/health`
- 后端就绪检查：`http://127.0.0.1:8000/api/v1/ready`

默认栈会启动 PostgreSQL、FastAPI 后端和 Vite 前端。未来可能用到的支持服务放在可选 Compose profile 中：

```bash
docker compose --profile tools up -d adminer
docker compose --profile cache up -d redis
docker compose --profile rag up -d qdrant
```

原生后端和前端命令、运维注意事项见 `docs/dev-setup.md`。

## LLM 接入

后端默认使用 mock 教师 provider，不需要任何密钥。要接入 OpenAI Responses API，在 `.env` 中设置：

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=你的 token
OPENAI_MODEL=你的模型名
```

不要把 `.env` 或任何真实密钥提交到仓库。

## 建议路线图

### 阶段 0：基础

- 定义教师人格
- 定义教学技能格式
- 定义学生记忆模型
- 构建本地网页原型

### 阶段 1：第一条真实教学闭环

- 接入真实 LLM 后端
- 增加学生登录或稳定学生标识
- 保存学生学习记忆
- 深入支持一个强示例技能：初中数学一元一次方程

### 阶段 2：教师技能生态

- 构建教师技能编辑器
- 增加技能校验和预览
- 增加审核等级：官方、认证教师、社区实验

### 阶段 3：学校和志愿者部署

- 增加教师管理面板
- 增加班级和学生进展视图
- 增加自部署指南
- 增加面向未成年人的隐私和安全控制

## 许可证

许可证尚未选择。接受外部贡献前，应选择适合公共利益开源项目的许可证。
