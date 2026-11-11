<p align="center">
  <a href="./README.md">中文</a> · <a href="./README.en.md">English</a>
</p>

<p align="center">
  <img src="./assets/readme/hero.svg" width="100%" alt="Azmark 行迹 — 自托管、AI 原生的个人旅行 OS">
</p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-C66B4E" alt="License: Apache-2.0"></a>
  &nbsp;
  <img src="https://img.shields.io/badge/self--hosted-252822" alt="Self-hosted">
  &nbsp;
  <img src="https://img.shields.io/badge/FastAPI%20%C2%B7%20Next.js%20%C2%B7%20TypeScript-6B6557" alt="技术栈：FastAPI · Next.js · TypeScript">
  &nbsp;
  <img src="https://img.shields.io/badge/PostgreSQL-PostGIS-78816A" alt="PostgreSQL + PostGIS">
  &nbsp;
  <a href="https://github.com/Euzohn/Azmark/actions/workflows/ci.yml"><img src="https://github.com/Euzohn/Azmark/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

**Azmark（行迹）** 是一个开源、自托管、AI 原生的个人旅行记录与数据管理系统。它把你每一段航班、火车与旅程，记录成一份只属于你自己的旅行手账——数据在你自己的服务器上，不依赖任何第三方云账号。

> A self-hosted, AI-native personal travel OS — every flight, train and journey in a logbook that belongs only to you.

<p align="center">
  <img src="./assets/readme/showcase.svg" width="100%" alt="界面结构示意：大圆航线地图、时间线、按行程归组的记录列表（线框示意，非截图）">
</p>

仓库开发约定见 [`AGENTS.md`](./AGENTS.md)，更新日志见 [`CHANGELOG.md`](./CHANGELOG.md)，备份 / 恢复运维见 [`docs/backup.md`](./docs/backup.md)，MCP 接入见 [`docs/mcp.md`](./docs/mcp.md)，反向代理与审计 IP 见 [`docs/reverse-proxy.md`](./docs/reverse-proxy.md)。

## 目录

- [已实现](#已实现)
- [为什么不同](#为什么不同)
- [架构](#架构)
- [Agent / API 访问](#agent--api-访问)
- [快速部署（服务器）](#快速部署服务器)
- [本地开发](#本地开发)
- [运维](#运维)
- [安全](#安全)
- [路线图](#路线图)
- [参与贡献](#参与贡献)
- [许可](#许可)

## 已实现

| 模块 | 能力 |
| --- | --- |
| 账号 | 注册、登录（JWT Bearer）、当前用户、改用户名/密码（不依赖邮件） |
| 航班 | 详情、编辑、删除、AI/表单录入 |
| 火车 | 详情、编辑、删除、AI/表单录入 |
| 其他交通 | 详情、编辑、删除、AI/表单录入 |
| 酒店 | 住宿记录（入住/退房、房型、确认号加密、地址、价格）；按行程归组、去重、状态推断 |
| 地点 | 收藏机场 / 车站 / 城市 / 餐厅等地点，含经纬度与时区；通过活动关联行程 |
| 活动 | 活动记录（类型、时间、地点、价格、备注）；作为行程成员进入时间线 |
| 开销 | 多币种开销、分类、汇率换算；可关联交通 / 酒店 / 活动或行程，并计入支出统计 |
| 笔记 | 自由文本笔记，可关联行程 |
| 记录 | 统一 Records 列表（航班/火车/其他）：搜索、类型/状态/行程/日期筛选、排序与分页 |
| 行程 | Trip 归组航班、火车、酒店与活动记录，并聚合行程内的开销与笔记；行程内排序 |
| 附件 | 按记录上传/下载/删除登机牌与票据（交通、酒店、活动；S3 兼容存储 · MinIO） |
| 地图 | 航班大圆航线 + 火车 / 其他交通示意线路 + 地点与酒店图钉，按图层切换；站点标签随缩放分级（城市聚合 ↔ 车站明细，自动避让重叠）（MapLibre GL · OpenFreeMap；车站坐标库可选，缺省按城市级解析） |
| 时间线 | 按时间排列全部交通记录 |
| 总览 | 关键指标、即将出发、跨类型最近记录 |
| 统计 | 航班/火车明细分组、年份/月份/日期分布、支出构成（不重复总览指标） |
| 年度报告 | Travel Wrapped：按年份的旅行总结（里程 / 足迹 / 最常飞航司·机场·车站 / 最长旅程 / 支出），从统计页进入，全屏章节式 |
| 审计日志 | 账号、记录、行程、附件、AI、导入导出等操作；记录客户端 IP 及其加盐哈希 |
| Agent 接入 | 个人访问令牌（read/write 权限、可吊销、按令牌限流）；脚本与 AI agent 可直接调用 REST API |
| MCP | MCP Server（Streamable HTTP）：只读工具 + `write` scope 令牌的写提案；Claude / Cursor 用访问令牌直连 `/api/v1/mcp` |
| 待确认操作 | agent 通过 MCP 提交的写入不会立即生效，需用户在网页「待确认」批准；确认接口拒绝令牌，杜绝 agent 自证 |
| AI 助手 | 对话、自然语言录入 / 搜索、工具调用、截图识图（航班 / 火车 / 酒店确认单）、待确认写入、AI 旅行日志（回忆 / 总结 / 时间线 / 城市故事 / 年度报告）；用户级模型配置 |
| 国际化 | zh-CN / en-US，浅色/深色/跟随系统，移动端底部导航 |

## 为什么不同

- **数据自主** — 自托管，PostgreSQL + PostGIS 在你的服务器上，不经过任何第三方账号。
- **旅行手账** — 编辑式（editorial）界面：大圆航线地图、时间线、行程归组，而非冰冷的表格。
- **AI 原生但受控** — AI 只能通过绑定当前用户的 tool 层操作，禁止直接访问数据库；破坏性操作必须经用户显式确认；网页/邮件/文件内容一律视为不可信，防御 prompt injection。
- **同源代理** — 浏览器只访问 web，后端不对外暴露，降低攻击面。

## 架构

<p align="center">
  <img src="./assets/readme/architecture.svg" width="100%" alt="部署架构：同源代理，仅 web 对外，内部网络隔离">
</p>

浏览器只访问 `web`（对外端口 `WEB_PORT`，默认 3000）。`web` 通过 compose 内部网络把 `/api/*` 转发到 `api`（FastAPI），`api` 再连接 `postgres`、`redis` 与 `minio`。`api` / `postgres` / `redis` / `minio` 均不发布宿主机端口。

附件二进制存于 MinIO（S3 兼容），数据库只保存 `storage_key` 与元数据；下载统一经 API 鉴权后流式返回，不暴露 bucket。

```
backend/   FastAPI + SQLAlchemy 2 + Alembic（PostgreSQL + PostGIS）
web/       Next.js (App Router) + TypeScript + Tailwind + MapLibre GL
docker-compose.yml   postgres / redis / minio / api / web
```

## Agent / API 访问

「设置 → 访问令牌」可创建个人访问令牌（`azm_…`），供脚本、CLI 或 AI agent 调用 REST API。令牌只在创建时显示一次，数据库里只保存它的哈希。

```bash
curl http://<服务器IP>:3000/api/v1/auth/me \
  -H "Authorization: Bearer azm_xxx"
```

- `read` 令牌只能 `GET`；`write` 令牌才能增改删（破坏性操作仍走确认流程）。
- 令牌可随时吊销或删除，吊销/过期后立即失效。
- 每个令牌默认每分钟 120 次请求（`PAT_RATE_LIMIT_PER_MINUTE` 可调，0 关闭）。
- OpenAPI 描述：`/api/v1/openapi.json`。

### MCP（只读 + 写提案）

同一套工具层也通过 MCP Server 暴露给 Claude、Cursor 等客户端，传输为 Streamable HTTP，凭证仍是个人访问令牌：

```json
{
  "mcpServers": {
    "azmark": {
      "type": "http",
      "url": "http://<服务器IP>:3000/api/v1/mcp",
      "headers": { "Authorization": "Bearer azm_xxx" }
    }
  }
}
```

只读工具：`search_records` / `get_record` / `search_hotels` / `get_hotel` / `list_trips` / `get_trip` / `get_statistics` / `search_expenses` / `search_notes` / `search_places` / `search_activities`。`write` scope 令牌还能用 `create_record` / `update_record` 提议新建或修改**任意类型**的记录（航班 / 火车 / 其他交通 / 住宿 / 行程 / 开销 / 笔记 / 地点 / 活动），但**它们不会直接写库**——而是生成一个「待确认操作」，由用户在网页「待确认」页面批准后才生效（spec #69）；agent 无法自己确认，删除也不通过 MCP 暴露。完整配置、curl 验证与排错见 [`docs/mcp.md`](./docs/mcp.md)。

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

`deploy.sh` 会拉取代码 → 备份数据库 → 重建容器 → 执行迁移 → 健康检查 → 清理；若 `git pull` 没有新提交且服务健康，则跳过备份/构建/迁移直接退出（强制重建用 `FORCE_DEPLOY=1 ./deploy.sh`）。完成后浏览器打开 `http://<服务器IP>:3000` → 注册 → 添加航班 → 在「地图」看到大圆航线。

> 审计日志的客户端 IP 在 `.env` 设置 `TRUSTED_PROXIES`（填 compose 网络网段）后即可正确记录，直连 3000 也生效——审计由 api 写入，而它的直连 peer 是 web 容器。详见 [`docs/reverse-proxy.md`](./docs/reverse-proxy.md)；想进一步收紧端口、杜绝 XFF 伪造，可再加一层宿主机 nginx。

首个管理员（二选一）：

```bash
# A. 在 .env 设置 ADMIN_EMAIL / ADMIN_PASSWORD（可选 ADMIN_USERNAME），首次启动自动创建
# B. 服务器上手动创建（密码交互输入，或追加 --password）
docker compose exec api python -m app create-admin --username admin --email you@example.com
```

管理员登录后侧边栏会出现「管理」，可查看用户、全局操作日志与系统统计。

附件使用 compose 内置的 MinIO。请修改 `.env` 中的 `S3_SECRET_KEY`（至少 8 位）。bucket 由 API 在首次上传时自动创建。`deploy.sh` 只备份 PostgreSQL 数据库；附件存放在 `minio_data` 数据卷，请另行备份该卷（例如定期对卷做快照/导出）。使用外部 S3 / R2 / OSS 时，设置 `S3_ENDPOINT`、`S3_REGION`、`S3_USE_SSL`、`S3_ADDRESSING_STYLE`，并提前创建 bucket。

> MinIO 开源版已归档。compose 默认从 `docker.1panel.live` 拉取最后一个开源版本并固定 digest；如服务器可直连 Docker Hub，可在 `.env` 设置 `MINIO_IMAGE=minio/minio:RELEASE.2025-09-07T16-13-09Z`。

> 后端镜像构建默认使用清华 PyPI 镜像，避免服务器从官方源下载依赖过慢。可在 `.env` 用 `PIP_INDEX_URL` 覆盖。

> `POSTGRES_PASSWORD` 必须只用 URL 安全字符（推荐 hex），否则会破坏内部 `DATABASE_URL`。云服务器需在安全组放通入方向 TCP 3000；不要放通 8000/5432/6379/9000/9001。

## 本地开发

> 本机只写代码，**不要本地部署或拉起常驻服务**（不要 `docker compose up`）。本地验证仅限：后端 SQLite 单测 + ruff；前端 lint + typecheck + build。需要 PostgreSQL/Redis 的验证在服务器进行。

<details>
<summary>后端</summary>

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt

# 测试（SQLite 内存库 + 内存 StorageProvider，无需常驻服务）
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

数据在命名卷 `azmark_postgres_data`。`deploy.sh` 在有更新时先备份再迁移，自动存到 `backups/`，默认保留最近 7 份（`KEEP_BACKUPS=14` 可调）。
</details>

<details>
<summary>升级</summary>

```bash
./deploy.sh          # git pull；有更新才 备份+重建+迁移+健康检查，无更新直接跳过
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
- **配了 nginx 后想禁止绕过**：web 默认对外直连 3000；在 `.env` 设 `WEB_BIND_IP=127.0.0.1` 后只留本机入口，外部必须经反代。
- **审计日志客户端显示 `172.21.0.x`**：`TRUSTED_PROXIES` 未设置或没填 compose 网段，api 因此不采信 web 容器转发的 XFF；按 [`docs/reverse-proxy.md`](./docs/reverse-proxy.md) 配置后 `docker compose up -d api`。若显示的是 `172.21.0.1`（网关），检查 iptables 是否有非标准 MASQUERADE 规则。
- **数据库密码特殊字符**：`POSTGRES_PASSWORD` 会被拼进 `DATABASE_URL`，必须 URL 安全（用 `openssl rand -hex 24`）。
- **改了密码仍认证失败**：Postgres 密码仅在数据卷首次初始化时写入。改 `.env` 后需 `docker compose down -v` 重建（会清库），或 `docker compose exec postgres psql -U azmark -c "ALTER USER azmark WITH PASSWORD '<新密码>';"`。
- **改了环境变量不生效**：`API_INTERNAL_URL` 是 Next **构建期**注入，改后要 `docker compose build web` 再 `up -d`。
- **后端不对外**：`api` 仅通过内部网络 `http://api:8000` 被 web 访问；外部健康检查走 `http://localhost:3000/api/v1/health`。
</details>

## 安全

- 所有用户数据按 `user_id` 服务端隔离，跨用户访问一律 404/403。
- PNR、票号、证件号等敏感字段加密存储；日志与审计永不输出明文，客户端 IP 记录原值与其加盐哈希（用于溯源与稳定关联）。
- AI 只能通过绑定当前用户的 tool 层操作，禁止直接访问数据库；破坏性操作必须经用户显式确认；网页 / 邮件 / 文件内容一律视为不可信输入，防御 prompt injection。
- 附件一律经 API 鉴权后流式下载，不暴露存储 bucket。
- 个人访问令牌默认只读、可随时吊销、按令牌限流。
- 部署面收敛：仅 `web` 对外发布端口，`api` / `postgres` / `redis` / `minio` 都在内部网络；请务必设置强 `SECRET_KEY`、`S3_SECRET_KEY` 与 `POSTGRES_PASSWORD`。
- 所有表结构变更经 Alembic migration，禁止直接改库。

## 路线图

- **MVP（已完成）** — 账号、航班 / 火车 / 其他交通记录、行程、附件、地图 / 时间线 / 总览 / 统计、审计日志；AI 对话与自然语言录入（含确认流）；CSV / JSON 导入导出；zh-CN / en-US 与移动端适配；个人访问令牌。
- **P1（已完成）** — 酒店 / 住宿、地点、活动、开销、笔记。照片 / OCR / 登机牌解析不单独实现：识图由网页 AI 助手完成（图片不持久化，需留存时作为附件上传）。
- **P2** — Travel Wrapped（年度报告）与 AI 旅行日志（已完成）；剩余：邮件导入、自动化规则、高级 OCR、AI 照片整理。
- **P3** — 行程协作、家庭账户、多用户共享行程、公开行程页、移动原生 App、插件生态。

## 参与贡献

欢迎 issue 与 PR。开发约定详见 [`AGENTS.md`](./AGENTS.md)，要点：

- 本地只写代码和跑测试 / 静态检查，**不要在本地启动服务**（数据库等联调在服务器进行）。
- 后端 schema 变更必须附 Alembic migration 与测试（SQLite 内存库，不依赖常驻服务）。
- 前端文案一律走 i18n key（zh-CN / en-US），禁止硬编码字符串。
- 提交信息遵循 Conventional Commits（`feat` / `fix` / `perf` / `docs` / `chore` …）。

提交前请确保通过：后端 `pytest -q`、`ruff check .`；前端 `npm run lint`、`npm run typecheck`、`npm test`、`npm run build`。部署由维护者通过 `./deploy.sh` 在服务器执行。

## 许可

Apache-2.0 · Copyright 2026 Euzohn contributors，见 [`LICENSE`](./LICENSE)。
