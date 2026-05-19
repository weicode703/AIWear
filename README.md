# AIWear 智能穿搭平台

AIWear 是一个面向服装穿搭场景的 AI Web 应用。项目重点放在 FastAPI 后端、数据库、Redis、对象存储、大模型接口、图片向量检索和 RAG 问答链路，前端页面主要用于功能演示和接口联调。

这个项目适合用于展示：如何把大模型能力接入真实业务系统，而不是只写一个简单的模型调用脚本。

## 在线演示

```text
演示地址：http://8.130.189.100
```

说明：项目已部署到云服务器，可直接访问在线演示环境，体验用户登录、图片处理、检索和 RAG 问答等核心功能。

## 项目亮点

- **完整业务链路**：包含用户登录、邮箱验证码、JWT 鉴权、图片上传、我的图片、历史记录等基础 Web 应用能力。
- **多模态 AI 能力**：接入 DashScope / 通义千问 / 通义万相，实现图片描述、图片编辑、图片合并等功能。
- **图片向量检索**：使用 CLIP 生成图片向量，支持文搜图和图搜图。
- **RAG 穿搭问答**：内置穿搭知识库，结合用户问题生成更贴近服装搭配场景的回答。
- **SSE 流式输出**：RAG 问答支持服务端流式返回，页面可以逐段展示模型输出。
- **部署实践**：使用 Docker Compose 组织后端、数据库、缓存、前端页面和 Nginx，方便项目在线演示。

## 技术栈

| 分类 | 技术 |
|---|---|
| 前端 | Vue 3、Vite、Element Plus、Pinia、Axios |
| 后端 | FastAPI、Pydantic、SQLAlchemy、PyJWT |
| 数据库 | PostgreSQL |
| 缓存 | Redis |
| 文件存储 | 本地存储 / 阿里云 OSS |
| AI 能力 | DashScope、Qwen-VL、通义万相、LangChain |
| 向量检索 | CLIP-ViT-Base-Patch16、Redis |
| 部署 | Docker、Docker Compose、Nginx |

说明：本项目的学习和实现重点是 **FastAPI 后端业务、AI 能力接入、RAG、SSE、数据库、Redis、OSS 和部署流程**。前端和 Nginx 主要作为演示页面和部署辅助组件使用。

## 功能说明

### 用户模块

- 发送邮箱验证码
- 邮箱验证码登录 / 注册
- JWT 登录状态维护
- 查询当前用户信息
- 退出登录并将 token 加入 Redis 黑名单

### 图片模块

- 上传图片到本地或 OSS
- 自动生成图片描述
- 自动生成 CLIP 图片向量
- 我的图片列表
- AI 单图编辑
- AI 双图合并
- 图片编辑与合并历史记录

### 检索模块

- 文搜图：用户输入文字，系统生成文本向量后检索相似图片。
- 图搜图：用户上传图片或传入图片 URL，系统生成图片向量后检索相似图片。

### RAG 问答模块

- 内置服装穿搭知识库
- 支持穿搭建议问答
- 支持多会话管理
- 支持上下文记忆
- 支持删除会话
- 支持 SSE 流式输出

## 系统架构

```mermaid
flowchart LR
    U["用户浏览器"] --> F["演示页面\nVue"]
    F --> N["Nginx\n静态资源/接口转发"]
    N --> B["FastAPI 后端\n项目重点"]
    B --> P["PostgreSQL\n用户、图片、历史、RAG 会话"]
    B --> R["Redis\n验证码、Token 黑名单、图片向量"]
    B --> O["阿里云 OSS\n图片文件"]
    B --> D["DashScope / Qwen\n图片理解、图片编辑、RAG 生成"]
    B --> C["CLIP\n图片/文本向量"]
    B --> K["本地穿搭知识库"]
```

## 项目结构

```text
aiwear/
  app/
    api/routes/          FastAPI 接口路由
    core/                配置、数据库、鉴权等基础能力
    models/              SQLAlchemy 数据库模型
    schemas/             Pydantic 请求和响应模型
    services/            业务逻辑
    main.py              后端启动入口
  data/rag/              RAG 穿搭知识库
  fronted/               前端演示页面
  tests/                 后端测试用例
  docker-compose.yml     Docker Compose 部署编排
  Dockerfile.backend     后端镜像构建文件
  requirements.txt       Python 依赖
  .env.example           本地环境变量模板
  .env.docker.example    Docker 部署环境变量模板
```

## 快速启动

### 1. 准备环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

然后按自己的环境填写数据库、Redis、DashScope、OSS 等配置。

注意：`.env` 包含密钥和数据库密码，不能提交到 GitHub。

### 2. Docker Compose 启动

```bash
docker compose up -d --build
```

启动后访问：

```text
本地前端页面：http://localhost
本地后端接口：http://localhost:8000
本地接口文档：http://localhost:8000/docs
本地健康检查：http://localhost:8000/health
```

### 3. 本地开发启动后端

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 4. 本地开发启动前端

```bash
cd fronted
npm install
npm run dev
```

前端默认访问：

```text
http://127.0.0.1:5173
```

## 环境变量示例

本仓库只提交 `.env.example` 和 `.env.docker.example`，不提交真实 `.env`。

常见配置项：

```env
DATABASE_URL=postgresql+psycopg2://aiwear:your-password@127.0.0.1:5432/aiwear
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=please-change-this-to-a-random-secret

DASHSCOPE_API_KEY=sk-your-dashscope-api-key

STORAGE_BACKEND=oss
OSS_ENDPOINT=https://oss-cn-beijing.aliyuncs.com
OSS_BUCKET=your-bucket-name
OSS_ACCESS_KEY_ID=your-access-key-id
OSS_ACCESS_KEY_SECRET=your-access-key-secret
OSS_BASE_URL=https://your-bucket-name.oss-cn-beijing.aliyuncs.com
```

## 核心接口

| 模块 | 方法 | 路径 | 说明 |
|---|---|---|---|
| 用户 | POST | `/api/user/send-code` | 发送邮箱验证码 |
| 用户 | POST | `/api/user/auth` | 登录 / 注册 |
| 用户 | GET | `/api/user/me` | 查询当前用户 |
| 用户 | POST | `/api/user/logout` | 退出登录 |
| 图片 | POST | `/api/file/upload/image` | 上传图片 |
| 图片 | GET | `/api/file/my-images` | 查询我的图片 |
| 图片 | POST | `/api/file/edit` | AI 图片编辑 |
| 图片 | POST | `/api/file/merge` | AI 图片合并 |
| 检索 | POST | `/api/file/search/text` | 文搜图 |
| 检索 | POST | `/api/file/search/image` | 图搜图 |
| 历史 | GET | `/api/record/my` | 查询图片操作历史 |
| RAG | POST | `/api/rag/chat` | 普通 RAG 问答 |
| RAG | POST | `/api/rag/chat/stream` | SSE 流式 RAG 问答 |
| RAG | GET | `/api/rag/conversations` | 查询 RAG 会话列表 |
| RAG | DELETE | `/api/rag/conversations/{conversation_id}` | 删除 RAG 会话 |

## 演示建议

可以按这个顺序体验和介绍项目：

1. 打开 README，先说明项目重点是后端业务链路和 AI 能力接入。
2. 展示登录和用户鉴权流程，说明邮箱验证码、JWT 和 Redis token 黑名单。
3. 上传一张服装或人物图片，说明图片会进入 OSS，并由后端生成描述和向量。
4. 演示 AI 图片编辑，例如“给人物加一副黑色眼镜”。
5. 演示图片合并，例如将人物图和服装图进行合并。
6. 演示文搜图或图搜图，说明 CLIP 向量检索的作用。
7. 演示 RAG 穿搭问答，说明知识库召回、上下文记忆和 SSE 流式输出。
8. 最后简单说明 Docker Compose 如何把后端、数据库、Redis、前端演示页面和 Nginx 组织起来。

## 截图建议

建议后续在仓库中加入以下截图，放到 `assets/screenshots/` 目录：

```text
assets/screenshots/login.png
assets/screenshots/images.png
assets/screenshots/edit.png
assets/screenshots/merge.png
assets/screenshots/rag.png
```

加入截图后，可以在 README 中补充：

```md
![登录页面](assets/screenshots/login.png)
![图片编辑](assets/screenshots/edit.png)
![RAG 问答](assets/screenshots/rag.png)
```

截图中不要出现真实邮箱、验证码、API Key、OSS 后台、服务器密码等敏感信息。

## 安全说明

以下内容不会提交到 GitHub：

```text
.env
aiwear.db
uploads/
fronted/node_modules/
fronted/dist/
docs/
*.zip
__pycache__/
```

真实密钥只放在本地或服务器的 `.env` 文件中。上传 GitHub 前需要确认 Git 历史中没有提交过真实密钥。

## 后续优化方向

- 使用 Alembic 管理数据库迁移。
- 将 Redis 中的图片向量迁移到 PostgreSQL + pgvector 或专业向量数据库。
- 将图片向量化和 AI 图片处理改成异步任务。
- 给 RAG 问答增加更完整的召回评估和回答质量评估。
- 配置域名、HTTPS 和线上监控。
