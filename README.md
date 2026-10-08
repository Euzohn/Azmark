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

前端默认走**同源代理**：浏览器只访问 web（`/api/v1/...`），由 Next.js 服务端把 `/api/*` 转发到后端。本地开发时转发目标是 `http://localhost:8000`，Docker 部署时是内部地址 `http://api:8000`（见 `web/next.config.ts` 的 `API_INTERNAL_URL`，由 compose 构建参数注入）。后端无需对外暴露端口。

## 部署（Docker Compose，服务器）

前置：服务器已装 Docker Engine + Compose 插件。默认只对外暴露 **web** 端口，api/postgres/redis 仅在内部网络可达。

1) 拉取代码并配置 `.env`

```bash
git clone <仓库地址> azmark && cd azmark
cp .env.example .env
openssl rand -hex 24   # 填入 POSTGRES_PASSWORD
openssl rand -hex 32   # 填入 SECRET_KEY
```

`.env` 关键项：

```dotenv
COMPOSE_PROJECT_NAME=azmark
POSTGRES_PASSWORD=<上面的 hex>
SECRET_KEY=<上面的 hex>
WEB_PORT=3000
CORS_ORIGINS=http://<服务器IP>:3000
```

> `POSTGRES_PASSWORD` 必须只用 URL 安全字符（推荐 hex），否则会破坏内部 `DATABASE_URL`。

2) 构建、启动、迁移

```bash
docker compose up -d --build
docker compose exec api alembic upgrade head
```

3) 验证

```bash
docker compose ps                                  # api/postgres/redis 无对外端口，仅 web 暴露
curl -fsS http://localhost:3000/api/v1/health      # {"status":"ok"}（经 Next 同源代理）
```

4) 放行端口（仅 web）

```bash
sudo ufw allow 3000/tcp
```

云服务器还需在**安全组**放通入方向 TCP 3000；不要放通 8000/5432/6379。

5) 浏览器打开 `http://<服务器IP>:3000` → 注册 → 添加航班 → “操作日志”。

### 备份 / 恢复

```bash
# 备份
docker compose exec -T postgres pg_dump -U azmark azmark | gzip > azmark-$(date +%F).sql.gz
# 恢复
gunzip -c azmark-YYYY-MM-DD.sql.gz | docker compose exec -T postgres psql -U azmark -d azmark
```

数据在命名卷 `azmark_postgres_data`。

### 升级

```bash
git pull
docker compose up -d --build
docker compose exec api alembic upgrade head
```

### 忘记密码（无邮件找回）

已登录可在「设置 → 账号安全」改密码；登不进去时用一次性命令（替换用户名/新密码）：

```bash
docker compose exec api python -c "from app.core.db import SessionLocal; from app.models import User; from app.core.security import hash_password; db=SessionLocal(); u=db.query(User).filter_by(username='alice').first(); u.password_hash=hash_password('newpass123'); db.commit(); print('ok')"
```

### 常见坑

- **端口冲突**：只有 web 对外发布端口（`WEB_PORT`）。宿主机 3000 被占用时改 `WEB_PORT`，并同步 `CORS_ORIGINS`。
- **数据库密码特殊字符**：`POSTGRES_PASSWORD` 会被拼进 `DATABASE_URL`，必须 URL 安全（用 `openssl rand -hex 24`）。
- **改了密码仍认证失败**：Postgres 密码仅在数据卷首次初始化时写入。改 `.env` 后需 `docker compose down -v` 重建（会清库），或 `docker compose exec postgres psql -U azmark -c "ALTER USER azmark WITH PASSWORD '<新密码>';"`。
- **改了环境变量不生效**：`API_INTERNAL_URL` 是 Next **构建期**注入，改后要 `docker compose build web` 再 `up -d`。
- **后端不对外**：`api` 仅通过内部网络 `http://api:8000` 被 web 访问；外部健康检查走 `http://localhost:3000/api/v1/health`。

## 本地验证边界（重要）

本机只写代码，**不要本地部署或拉起常驻服务**（不要 `docker compose up`）。
本地验证仅限：后端 SQLite 单测 + ruff；前端 lint + typecheck + build。部署与联调在服务器进行。

## 许可

Apache-2.0，见 `LICENSE`。
