# Azmark（行迹）

开源、自托管、AI 原生的个人旅行记录与旅行数据管理系统的 **MVP 骨架**。
第一个可用切片是**航班记录管理**：注册/登录、航班的增删改查、以及操作审计日志。

> 完整产品方案见仓库内的设计文档（不纳入版本控制，见 `.gitignore`）。
> 文档是产品与架构的唯一事实来源，实现请遵循 `AGENTS.md`。

## 结构

```
backend/   FastAPI + SQLAlchemy 2 + Alembic（PostgreSQL）
web/       Next.js (App Router) + TypeScript + Tailwind
docker-compose.yml  postgres / redis / api / web
```

## 已实现

- 账号：注册、登录（JWT Bearer）、当前用户、修改用户名/密码（不依赖邮件）。
- 航班：列表（搜索/分页）、新增、详情、编辑、删除；所有查询按 `user_id` 服务端隔离。
- 审计日志：登录/登录失败/注册/改密/改用户名/增改删航班；IP 仅存加盐哈希，敏感字段不入库。
- 前端：登录/注册、航班列表与表单、操作日志页、个人设置；i18n（zh-CN/en-US）、浅色/深色/跟随系统、移动端底部导航。

## 后端开发

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt

# 测试（SQLite 内存库，无需任何常驻服务）
./.venv/bin/pytest -q
./.venv/bin/ruff check .
./.venv/bin/ruff format --check .
```

需要 PostgreSQL 时（在服务器上，勿在本地部署）：

```bash
cd backend
DATABASE_URL=postgresql+psycopg://azmark:azmark@localhost:5432/azmark ./.venv/bin/alembic upgrade head
DATABASE_URL=... ./.venv/bin/uvicorn app.main:app --reload
```

## 前端开发

```bash
cd web
npm install
npm run dev        # http://localhost:3000
npm run lint
npm run typecheck
npm run build
```

API 地址由 `NEXT_PUBLIC_API_BASE_URL` 配置（默认 `http://localhost:8000`）。

## 本地验证边界（重要）

本机只写代码，**不要本地部署或拉起常驻服务**（不要 `docker compose up`）。
本地验证仅限：后端 SQLite 单测 + ruff；前端 lint + typecheck + build。部署与联调在服务器进行。

## 许可

Apache-2.0，见 `LICENSE`。
