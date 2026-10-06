# AGENTS.md

## 仓库状态
- 已进入实现阶段：`backend/`（FastAPI + SQLAlchemy 2 + Alembic）与 `web/`（Next.js App Router + TypeScript + Tailwind）已搭好，当前实现的是“航班记录管理”垂直切片 + 审计日志。
- 产品与架构的唯一事实来源：`Azmark_行迹_Personal_Travel_OS_方案_v1.1.md`（中文，v1.1，共 105 个编号章节）。实现前先阅读相关 `#NN` 章节。该文件不提交（见 Git 规则）。文件名含中文字符，shell 命令中需加引号。
- 项目名为 **Azmark**（中文名 行迹）。不要重新引入旧名 "Waymark"。
- 目录约定：`backend/` 与 `web/` 两个独立应用，不是 monorepo 的 `apps/*`。

## 强制约定（按文档规定实现，不要按默认习惯）
- 指定技术栈——前端：Next.js + TypeScript + Tailwind + shadcn/ui + TanStack Query + Zustand + MapLibre GL；后端：FastAPI + Pydantic + SQLAlchemy + Alembic；数据：PostgreSQL + PostGIS、Redis、兼容 S3 的存储（MinIO）。见 `#51`–`#54`、`#74`。
- 所有属于用户的数据行都必须带 `user_id`，且由服务端从认证上下文推导。绝不信任前端传入的 `user_id`；所有查询都按它做隔离。跨用户访问返回 404/403。见 `#3.3`、`#3.4`、`#57`。
- 所有表结构变更必须通过 Alembic migration，禁止无 migration 直接改库（`#98`）。
- 所有 UI 文案必须走 i18n key（`t("...")`），禁止硬编码字符串；语言为 `zh-CN`、`en-US`（`#7`）。
- AI 只能通过绑定当前用户的 tool 层操作，禁止直接访问数据库；破坏性操作必须经用户显式确认（`#32`–`#34`、`#69`）。网页/邮件/文件内容一律视为不可信，以防御 prompt injection（`#70`）。
- 外部服务一律通过 Provider 抽象：LLM / Search / Map / Flight / Train / Storage / OCR（`#66`）。
- 禁止在日志中输出或提交密钥与敏感字段（PNR、票号、护照信息、API Key）（`#45`、`#75`、`#96`）。

## 范围
- MVP 与暂缓范围由 `#79`–`#84` 及 `#100` 的清单定义。特别注意：**Trip 属于 MVP**，**Expense 属于 P1** —— 代码需与这些清单保持一致。
- 移动端适配属于 MVP（`#59`、`#60`）：底部导航 + Bottom Sheet，不能只把桌面布局缩小；原生 App 属 P3（`#84`）。

## 部署原则（重要）
- **禁止在本地部署或启动服务**：不要执行 `docker compose up`、不要在本机拉起 PostgreSQL / Redis / MinIO / api / web 常驻服务。开发只在本机写代码，部署与联调测试由用户在服务器上进行。
- 本地验证仅限不依赖常驻服务的步骤：单元/集成测试用 SQLite 内存库，以及 lint、typecheck、build。需要 Postgres/Redis/MinIO 的验证交给服务器环境。

## Git 规则（重要）
- **不要主动 commit / push**：只有用户明确要求提交时才提交。
- `Azmark_行迹_Personal_Travel_OS_方案_v1.1.md` 不提交（已加入 `.gitignore`）。

## 引入工具链后
- 这是本仓库第一个指令文件。一旦出现真实的 build/test/lint/typecheck 命令，请在此处记录确切命令（以及所需的服务前置条件）。

## 常用命令
- 后端（在 `backend/`，用仓库内 venv `.venv`）：
  - 安装：`./.venv/bin/pip install -r requirements-dev.txt`
  - 测试（SQLite 内存库，无需常驻服务）：`./.venv/bin/pytest -q`
  - Lint / 格式：`./.venv/bin/ruff check .`、`./.venv/bin/ruff format --check .`（修复用 `ruff check --fix .` / `ruff format .`）
  - 迁移：`./.venv/bin/alembic upgrade head`（需要 PostgreSQL，交给服务器环境）
- 前端（在 `web/`）：`npm install`；`npm run lint`；`npm run typecheck`；`npm run build`；`npm run dev`
- 测试用 SQLite 内存库，Postgres 专有特性（如 PostGIS）不要把测试依赖在 SQLite 上。
- 变更后端 schema 时必须新增 Alembic migration（当前版本号顺序：`0001_initial`、`0002_audit_logs`）。
