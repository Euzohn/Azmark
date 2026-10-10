<p align="center">
  <img src="./assets/readme/hero.svg" width="100%" alt="Azmark 行迹 — 自托管、AI 原生的个人旅行 OS">
</p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-9a4b1a" alt="License: Apache-2.0"></a>
  &nbsp;
  <img src="https://img.shields.io/badge/self--hosted-211A12" alt="Self-hosted">
  &nbsp;
  <img src="https://img.shields.io/badge/PostgreSQL-PostGIS-7a6f60" alt="PostgreSQL + PostGIS">
</p>

**Azmark（行迹）** 是一个开源、自托管、AI 原生的个人旅行记录与数据管理系统。它把你每一段航班、火车与旅程，记录成一份只属于你自己的旅行手账——数据在你自己的服务器上，不依赖任何第三方云账号。

> 完整产品方案见仓库内设计文档（不纳入版本控制，见 `.gitignore`）。产品与架构的唯一事实来源是该文档；实现遵循 `AGENTS.md`。

## 已实现

| 模块 | 能力 |
| --- | --- |
| 账号 | 注册、登录（JWT Bearer）、当前用户、改用户名/密码（不依赖邮件） |
| 航班 | 列表（搜索/分页/高级筛选：状态、舱位、行程、日期范围）、增删改查 |
| 火车 | 列表（搜索/筛选）、增删改查 |
| 行程 | Trip 归组航班与火车记录 |
| 地图 | 大圆航线可视化（MapLibre GL · OpenFreeMap） |
| 时间线 | 按时间排列全部交通记录 |
| 统计 | 仪表盘 + 统计页 |
| 审计日志 | 登录/失败/注册/改密/改用户名/增改删航班火车；IP 仅存加盐哈希 |
| 国际化 | zh-CN / en-US，浅色/深色/跟随系统，移动端底部导航 |

安全：所有用户数据按 `user_id` 服务端隔离（跨用户访问返回 404/403）；PNR、票号等敏感字段加密存储；所有表结构变更经 Alembic migration。

## 为什么不同

- **数据自主** — 自托管，PostgreSQL + PostGIS 在你的服务器上，不经过任何第三方账号。
- **旅行手账** — 编辑式（editorial）界面：大圆航线地图、时间线、行程归组，而非冰冷的表格。
- **AI 原生但受控** — AI 只能通过绑定当前用户的 tool 层操作，禁止直接访问数据库；破坏性操作必须经用户显式确认；网页/邮件/文件内容一律视为不可信，防御 prompt injection。
- **同源代理** — 浏览器只访问 web，后端不对外暴露，降低攻击面。

## 架构

<p align="center">
  <img src="./assets/readme/architecture.svg" width="100%" alt="部署架构：同源代理，仅 web 对外，内部网络隔离">
</p>

浏览器只访问 `web`（对外端口 `WEB_PORT`，默认 3000）。`web` 通过 compose 内部网络把 `/api/*` 转发到 `api`（FastAPI），`api` 再连接 `postgres` 与 `redis`。`api` / `postgres` / `redis` 均不发布宿主机端口。

```
backend/   FastAPI + SQLAlchemy 2 + Alembic（PostgreSQL + PostGIS）
web/       Next.js (App Router) + TypeScript + Tailwind + MapLibre GL
docker-compose.yml   postgres / redis / api / web
```

## 快速部署（服务器）

前置：服务器已装 Docker Engine + Compose 插件。

```bash
git clone https://github.com/Euzohn/Azmark.git azmark && cd azmark
cp .env.example .env
openssl rand -hex 24    # POSTGRES_PASSWORD
openssl rand -hex 32    # SECRET_KEY
# 编辑 .env：填入上面两个值，设 CORS_ORIGINS=http://<服务器IP>:3000
./deploy.sh
```

`deploy.sh` 会拉取代码 → 备份数据库 → 重建容器 → 执行迁移 → 健康检查 → 清理。完成后浏览器打开 `http://<服务器IP>:3000` → 注册 → 添加航班 → 在「地图」看到大圆航线。

> `POSTGRES_PASSWORD` 必须只用 URL 安全字符（推荐 hex），否则会破坏内部 `DATABASE_URL`。云服务器需在安全组放通入方向 TCP 3000；不要放通 8000/5432/6379。

## 本地开发

> 本机只写代码，**不要本地部署或拉起常驻服务**（不要 `docker compose up`）。本地验证仅限：后端 SQLite 单测 + ruff；前端 lint + typecheck + build。需要 PostgreSQL/Redis 的验证在服务器进行。

<details>
<summary>后端</summary>

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt

# 测试（SQLite 内存库，无需常驻服务）
./.venv/bin/pytest -q
./.venv/bin/ruff check .
./.venv/bin/ruff format --check .
```

需要 PostgreSQL 时（在服务器上）：

```bash
DATABASE_URL=postgresql+psycopg://azmark:azmark@localhost:5432/azmark ./.venv/bin/alembic upgrade head
DATABASE_URL=... ./.venv/bin/uvicorn app.main:app --reload
```
</details>

<details>
<summary>前端</summary>

```bash
cd web
npm install
npm run dev        # http://localhost:3000
npm run lint
npm run typecheck
npm run build
```

前端默认走**同源代理**：浏览器只访问 web（`/api/v1/...`），由 Next.js 服务端转发到后端。本地开发目标是 `http://localhost:8000`，Docker 部署时是 `http://api:8000`（见 `web/next.config.ts` 的 `API_INTERNAL_URL`，构建期注入）。后端无需对外暴露端口。
</details>

## 运维

<details>
<summary>备份 / 恢复</summary>

```bash
# 备份
docker compose exec -T postgres pg_dump -U azmark azmark | gzip > azmark-$(date +%F).sql.gz
# 恢复
gunzip -c azmark-YYYY-MM-DD.sql.gz | docker compose exec -T postgres psql -U azmark -d azmark
```

数据在命名卷 `azmark_postgres_data`。`deploy.sh` 每次部署自动备份到 `backups/`，默认保留最近 7 份（`KEEP_BACKUPS=14` 可调）。
</details>

<details>
<summary>升级</summary>

```bash
./deploy.sh          # git pull + 备份 + 重建 + 迁移 + 健康检查，一步完成
```
</details>

<details>
<summary>忘记密码（无邮件找回）</summary>

已登录可在「设置 → 账号安全」改密码；登不进去时用一次性命令（替换用户名/新密码）：

```bash
docker compose exec api python -c "from app.core.db import SessionLocal; from app.models import User; from app.core.security import hash_password; db=SessionLocal(); u=db.query(User).filter_by(username='alice').first(); u.password_hash=hash_password('newpass123'); db.commit(); print('ok')"
```
</details>

<details>
<summary>常见坑</summary>

- **端口冲突**：只有 web 对外发布端口（`WEB_PORT`）。宿主机 3000 被占用时改 `WEB_PORT`，并同步 `CORS_ORIGINS`。
- **数据库密码特殊字符**：`POSTGRES_PASSWORD` 会被拼进 `DATABASE_URL`，必须 URL 安全（用 `openssl rand -hex 24`）。
- **改了密码仍认证失败**：Postgres 密码仅在数据卷首次初始化时写入。改 `.env` 后需 `docker compose down -v` 重建（会清库），或 `docker compose exec postgres psql -U azmark -c "ALTER USER azmark WITH PASSWORD '<新密码>';"`。
- **改了环境变量不生效**：`API_INTERNAL_URL` 是 Next **构建期**注入，改后要 `docker compose build web` 再 `up -d`。
- **后端不对外**：`api` 仅通过内部网络 `http://api:8000` 被 web 访问；外部健康检查走 `http://localhost:3000/api/v1/health`。
</details>

## 许可

Apache-2.0，见 `LICENSE`。
