<p align="center">
  <a href="./README.en.md">English</a> · <a href="./README.md">中文</a>
</p>

<p align="center">
  <img src="./assets/readme/hero-en.svg" width="100%" alt="Azmark — a self-hosted, AI-native personal travel OS">
</p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-C66B4E" alt="License: Apache-2.0"></a>
  &nbsp;
  <img src="https://img.shields.io/badge/self--hosted-252822" alt="Self-hosted">
  &nbsp;
  <img src="https://img.shields.io/badge/FastAPI%20%C2%B7%20Next.js%20%C2%B7%20TypeScript-6B6557" alt="Stack: FastAPI · Next.js · TypeScript">
  &nbsp;
  <img src="https://img.shields.io/badge/PostgreSQL-PostGIS-78816A" alt="PostgreSQL + PostGIS">
</p>

**Azmark (行迹)** is an open-source, self-hosted, AI-native personal travel log and data management system. It turns every flight, train ride and journey into a travel logbook that belongs to you alone — the data lives on your own server, with no third-party cloud account in the loop.

> 自托管、AI 原生的个人旅行 OS——每段航班、火车与旅程，都记在只属于你自己的手账里。

<p align="center">
  <img src="./assets/readme/showcase-en.svg" width="100%" alt="Interface overview: great-circle route map, timeline, and records grouped by trip (schematic wireframe, not screenshots)">
</p>

See [`AGENTS.md`](./AGENTS.md) for repository conventions, [`docs/backup.md`](./docs/backup.md) for backup / restore operations, [`docs/mcp.md`](./docs/mcp.md) for MCP integration, and [`docs/reverse-proxy.md`](./docs/reverse-proxy.md) for reverse proxying and audit client IPs.

## Table of contents

- [Implemented](#implemented)
- [Why it's different](#why-its-different)
- [Architecture](#architecture)
- [Agent / API access](#agent--api-access)
- [Quick deploy (server)](#quick-deploy-server)
- [Local development](#local-development)
- [Operations](#operations)
- [Security](#security)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Implemented

| Module | Capabilities |
| --- | --- |
| Accounts | Register, login (JWT bearer), current user, change username / password (no email required) |
| Flights | Detail, edit, delete, AI / form entry |
| Trains | Detail, edit, delete, AI / form entry |
| Other transport | Detail, edit, delete, AI / form entry |
| Hotels | Stay records (check-in / check-out, room type, encrypted confirmation number, address, price); trip grouping, deduplication, status inference |
| Records | Unified records list (flight / train / other): search, type / status / trip / date filters, sorting and pagination |
| Trips | A trip groups flights, trains and hotel records; ordering within a trip |
| Attachments | Upload / download / delete boarding passes and receipts per record (S3-compatible storage · MinIO) |
| Map | Great-circle route visualization (MapLibre GL · OpenFreeMap) |
| Timeline | Every transport record in chronological order |
| Dashboard | Key metrics, upcoming departures, recent records across types |
| Statistics | Flight / train breakdowns, year / month / day distributions (no overlap with dashboard metrics) |
| Audit log | Login / failure / register / password change / username change / flight & train CRUD; client IP and its salted hash |
| Agent access | Personal access tokens (read / write scopes, revocable, rate-limited per token); scripts and AI agents can call the REST API directly |
| MCP | MCP server (Streamable HTTP): read-only tools plus write proposals for `write`-scope tokens; Claude / Cursor connect to `/api/v1/mcp` with an access token |
| Pending actions | Writes submitted by agents via MCP never apply immediately — a user must approve them on the web "Pending" page; the confirm endpoint rejects tokens, so an agent can never approve its own proposal |
| i18n | zh-CN / en-US, light / dark / system theme, mobile bottom navigation |

## Why it's different

- **Your data, your server** — self-hosted; PostgreSQL + PostGIS on your machine, never routed through a third-party account.
- **A travel logbook, not a spreadsheet** — an editorial interface: great-circle route map, timeline and trip grouping instead of cold tables.
- **AI-native, but controlled** — AI operates only through a tool layer bound to the current user and never touches the database directly; destructive operations require explicit user confirmation; web / email / file content is always treated as untrusted to defend against prompt injection.
- **Same-origin proxy** — the browser only ever talks to `web`; the backend is never exposed, shrinking the attack surface.

## Architecture

<p align="center">
  <img src="./assets/readme/architecture-en.svg" width="100%" alt="Deployment architecture: same-origin proxy, only web exposed, isolated internal network">
</p>

The browser only talks to `web` (public port `WEB_PORT`, default 3000). `web` forwards `/api/*` to `api` (FastAPI) over the compose internal network; `api` then connects to `postgres`, `redis` and `minio`. None of `api` / `postgres` / `redis` / `minio` publish a host port.

Attachment binaries live in MinIO (S3-compatible); the database stores only the `storage_key` and metadata. Downloads stream through the API after authentication and never expose the bucket.

```
backend/   FastAPI + SQLAlchemy 2 + Alembic (PostgreSQL + PostGIS)
web/       Next.js (App Router) + TypeScript + Tailwind + MapLibre GL
docker-compose.yml   postgres / redis / minio / api / web
```

## Agent / API access

"Settings → Access tokens" creates personal access tokens (`azm_…`) for scripts, CLIs or AI agents to call the REST API. A token is shown once at creation; only its hash is stored in the database.

```bash
curl http://<server-ip>:3000/api/v1/auth/me \
  -H "Authorization: Bearer azm_xxx"
```

- `read` tokens can only `GET`; `write` tokens can create / update / delete (destructive operations still go through the confirmation flow).
- Tokens can be revoked or deleted at any time; a revoked or expired token stops working immediately.
- Each token defaults to 120 requests per minute (`PAT_RATE_LIMIT_PER_MINUTE`, 0 disables).
- OpenAPI description: `/api/v1/openapi.json`.

### MCP (read-only + write proposals)

The same tool layer is exposed to Claude, Cursor and other clients through an MCP server over Streamable HTTP; the credential is still a personal access token:

```json
{
  "mcpServers": {
    "azmark": {
      "type": "http",
      "url": "http://<server-ip>:3000/api/v1/mcp",
      "headers": { "Authorization": "Bearer azm_xxx" }
    }
  }
}
```

Read-only tools: `search_records` / `get_record` / `search_hotels` / `get_hotel` / `list_trips` / `get_trip` / `get_statistics` / `search_expenses` / `search_notes` / `search_places` / `search_activities`. A `write`-scope token additionally unlocks `create_record` / `update_record` to propose creating or changing a record of **any type** (flight / train / other transport / hotel / trip / expense / note / place / activity), but **they never write to the database directly** — they produce a "pending action" that only takes effect after a user approves it on the web "Pending" page (spec #69); an agent cannot approve its own proposal, and deletion is not exposed through MCP. Full configuration, curl verification and troubleshooting: [`docs/mcp.md`](./docs/mcp.md).

## Quick deploy (server)

Prerequisite: Docker Engine + the Compose plugin installed on the server.

```bash
git clone https://github.com/Euzohn/Azmark.git azmark && cd azmark
cp .env.example .env
openssl rand -hex 24    # POSTGRES_PASSWORD
openssl rand -hex 32    # SECRET_KEY
# Edit .env: fill in the two values above, set CORS_ORIGINS=http://<server-ip>:3000
./deploy.sh
```

`deploy.sh` pulls the code → backs up the database → rebuilds containers → runs migrations → health-checks → cleans up. If `git pull` finds no new commits and the services are healthy, it skips backup / build / migration and exits (force a rebuild with `FORCE_DEPLOY=1 ./deploy.sh`). When it finishes, open `http://<server-ip>:3000` → register → add a flight → watch the great-circle route appear on the map.

> The audit log records real client IPs once `TRUSTED_PROXIES` is set in `.env` (to the compose network's subnet), including with direct :3000 access — the audit is written by the api, whose direct peer is the web container. See [`docs/reverse-proxy.md`](./docs/reverse-proxy.md). A host-level nginx can additionally lock the port down and prevent X-Forwarded-For spoofing.

First admin (pick one):

```bash
# A. Set ADMIN_EMAIL / ADMIN_PASSWORD in .env (optionally ADMIN_USERNAME); created automatically on first start
# B. Create it manually on the server (password prompted, or append --password)
docker compose exec api python -m app create-admin --username admin --email you@example.com
```

After an admin logs in, an "Admin" entry appears in the sidebar with users, the global action log and system statistics.

Attachments use the MinIO bundled in compose. Change `S3_SECRET_KEY` in `.env` (at least 8 characters). The bucket is created automatically by the API on first upload. `deploy.sh` only backs up the PostgreSQL database; attachments live in the `minio_data` volume — back that volume up separately (e.g. periodic volume snapshots / exports). For external S3 / R2 / OSS, set `S3_ENDPOINT`, `S3_REGION`, `S3_USE_SSL`, `S3_ADDRESSING_STYLE` and create the bucket in advance.

> The open-source edition of MinIO is archived. Compose pulls the last open-source release from `docker.1panel.live` with a pinned digest by default; if your server can reach Docker Hub directly, set `MINIO_IMAGE=minio/minio:RELEASE.2025-09-07T16-13-09Z` in `.env`.

> Backend image builds default to the Tsinghua PyPI mirror so servers don't stall on the official index. Override with `PIP_INDEX_URL` in `.env`.

> `POSTGRES_PASSWORD` must contain only URL-safe characters (hex recommended), otherwise the internal `DATABASE_URL` breaks. Cloud servers need inbound TCP 3000 open in the security group; do not open 8000/5432/6379/9000/9001.

## Local development

> Write code locally only — **do not deploy or start resident services locally** (no `docker compose up`). Local verification is limited to: backend SQLite tests + ruff; frontend lint + typecheck + build. Anything needing PostgreSQL / Redis is verified on the server.

<details>
<summary>Backend</summary>

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt

# Tests (SQLite in-memory + in-memory StorageProvider; no resident services)
./.venv/bin/pytest -q
./.venv/bin/ruff check .
./.venv/bin/ruff format --check .
```

When you need PostgreSQL (on the server):

```bash
DATABASE_URL=postgresql+psycopg://azmark:azmark@localhost:5432/azmark ./.venv/bin/alembic upgrade head
DATABASE_URL=... ./.venv/bin/uvicorn app.main:app --reload
```
</details>

<details>
<summary>Frontend</summary>

```bash
cd web
npm install
npm run dev        # http://localhost:3000
npm run lint
npm run typecheck
npm run build
```

The frontend uses a **same-origin proxy** by default: the browser only talks to web (`/api/v1/...`), and the Next.js server forwards to the backend. The local development target is `http://localhost:8000`; in Docker deployments it is `http://api:8000` (see `API_INTERNAL_URL` in `web/next.config.ts`, injected at build time). The backend never exposes a port externally.
</details>

## Operations

<details>
<summary>Backup / restore</summary>

```bash
# Backup
docker compose exec -T postgres pg_dump -U azmark azmark | gzip > azmark-$(date +%F).sql.gz
# Restore
gunzip -c azmark-YYYY-MM-DD.sql.gz | docker compose exec -T postgres psql -U azmark -d azmark
```

Data lives in the named volume `azmark_postgres_data`. When there are updates, `deploy.sh` backs up before migrating into `backups/`, keeping the latest 7 by default (`KEEP_BACKUPS=14` to change).
</details>

<details>
<summary>Upgrades</summary>

```bash
./deploy.sh          # git pull; only backs up + rebuilds + migrates + health-checks when there are updates, otherwise skips
```
</details>

<details>
<summary>Forgotten password (no email recovery)</summary>

While logged in, change it under "Settings → Account security". If you can't log in, use a one-shot command (replace the username / new password):

```bash
docker compose exec api python -c "from app.core.db import SessionLocal; from app.models import User; from app.core.security import hash_password; db=SessionLocal(); u=db.query(User).filter_by(username='alice').first(); u.password_hash=hash_password('newpass123'); db.commit(); print('ok')"
```
</details>

<details>
<summary>Common pitfalls</summary>

- **Port conflicts**: only web publishes a port (`WEB_PORT`). If host port 3000 is taken, change `WEB_PORT` and update `CORS_ORIGINS` to match.
- **Want to block direct :3000 access after adding nginx**: web publishes 3000 by default; set `WEB_BIND_IP=127.0.0.1` in `.env` so only the local proxy can reach it.
- **Audit log shows a `172.21.0.x` client**: `TRUSTED_PROXIES` is unset or does not match the compose network, so the api ignores the X-Forwarded-For forwarded by the web container; configure it per [`docs/reverse-proxy.md`](./docs/reverse-proxy.md) and run `docker compose up -d api`. If it shows `172.21.0.1` (the bridge gateway), check iptables for a non-standard MASQUERADE rule.
- **Special characters in the database password**: `POSTGRES_PASSWORD` is interpolated into `DATABASE_URL` and must be URL-safe (use `openssl rand -hex 24`).
- **Changed the password but auth still fails**: the Postgres password is only written on first initialization of the data volume. After editing `.env`, either `docker compose down -v` and recreate (wipes the database), or `docker compose exec postgres psql -U azmark -c "ALTER USER azmark WITH PASSWORD '<new-password>';"`.
- **Changed env vars with no effect**: `API_INTERNAL_URL` is injected at Next **build** time — after changing it, run `docker compose build web` then `up -d`.
- **Backend is not public**: `api` is reachable only as `http://api:8000` on the internal network; external health checks go through `http://localhost:3000/api/v1/health`.
</details>

## Security

- All user data is isolated server-side by `user_id`; cross-user access always returns 404/403.
- Sensitive fields such as PNR, ticket numbers and credential numbers are encrypted at rest; logs and audit entries never emit plaintext; client IPs are stored as the raw address plus a salted hash (for traceability and stable correlation).
- AI operates only through a tool layer bound to the current user and never touches the database directly; destructive operations require explicit user confirmation; web / email / file content is always treated as untrusted input, defending against prompt injection.
- Attachments always download through the authenticated API stream; the storage bucket is never exposed.
- Personal access tokens default to read-only, are revocable at any time, and are rate-limited per token.
- Minimal deployment surface: only `web` publishes a port; `api` / `postgres` / `redis` / `minio` stay on the internal network. Set strong `SECRET_KEY`, `S3_SECRET_KEY` and `POSTGRES_PASSWORD`.
- Every schema change goes through an Alembic migration; direct database edits are forbidden.

## Roadmap

- **MVP (done)** — accounts; flight / train / other transport records; trips; attachments; map / timeline / dashboard / statistics; audit log; AI chat with natural-language entry (including the confirmation flow); JSON import / export; zh-CN / en-US and mobile adaptation; personal access tokens.
- **P1 (in progress)** — hotels / stays (done), places, activities, expenses, photos, notes, OCR, boarding-pass parsing.
- **P2** — email import, automation rules, AI travel journal, Travel Wrapped, advanced OCR, AI photo organization.
- **P3** — trip collaboration, family accounts, multi-user shared trips, public trip pages, native mobile apps, plugin ecosystem.

## Contributing

Issues and PRs are welcome. See [`AGENTS.md`](./AGENTS.md) for development conventions; highlights:

- Write code and run tests / static checks locally only — **do not start services locally** (database integration happens on the server).
- Backend schema changes must ship with an Alembic migration and tests (SQLite in-memory, no resident services).
- All frontend copy goes through i18n keys (zh-CN / en-US); hardcoded strings are forbidden.
- Commit messages follow Conventional Commits (`feat` / `fix` / `perf` / `docs` / `chore` …).

Before submitting, make sure these pass: backend `pytest -q`, `ruff check .`; frontend `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`. Deployment is performed by maintainers on the server via `./deploy.sh`.

## License

Apache-2.0 · Copyright 2026 Euzohn contributors, see [`LICENSE`](./LICENSE).
