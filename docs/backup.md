# 备份与恢复（spec #97）

覆盖 MVP 的运维层备份：**PostgreSQL 全库 dump** + **S3/MinIO 对象**。
方案里的 “One-click Backup / Restore” 属于未来项，不在此实现。

## 产物结构

`scripts/backup.sh` 每次在 `BACKUP_DIR` 下生成一个时间戳目录：

```text
backups/
└── 20261025T030000Z/
    ├── MANIFEST            # 时间、库名、bucket 名（不含任何密钥）
    ├── db/
    │   └── azmark.sql.gz   # pg_dump 的纯 SQL，gzip 压缩
    └── objects/
        └── azmark/         # 附件对象的镜像（bucket 名目录）
```

## 前置条件

- 宿主机有 `docker compose`（v2）。
- 正常栈已启动（至少 `postgres`、`minio`）：`docker compose up -d`。
- 项目根目录有 `.env`（备份脚本与 compose 读同一份）。

## 一次性备份

```bash
./scripts/backup.sh
```

- PostgreSQL：在 `postgres` 容器内经 unix socket 执行 `pg_dump`，无需密码。
- 对象：用一次性 `mc` 容器（compose 的 `backup` profile）镜像 bucket。
- bucket 尚不存在（从未上传附件）时自动跳过对象，不报错。

可用环境变量覆盖：

| 变量 | 默认 | 说明 |
|---|---|---|
| `BACKUP_DIR` | `<repo>/backups` | 落盘目录（会挂载进 mc 容器） |
| `BACKUP_RETENTION_DAYS` | `30` | 超过天数的旧备份目录会被删除；`0` 关闭 |
| `PG_USER` / `PG_DB` | `azmark` / `azmark` | 数据库连接 |
| `MINIO_MC_IMAGE` | `minio/mc:RELEASE.2025-04-16T18-13-26Z` | mc 客户端镜像 |

## 定时执行

用宿主机 crontab（每天 03:00 UTC）：

```cron
0 3 * * * cd /path/to/azmark && ./scripts/backup.sh >> backups/backup.log 2>&1
```

> 脚本自带保留清理，不需要额外的 `find` 任务。

## 恢复

恢复是**破坏性**操作：会 DROP 并重建数据库、清空并重传 bucket。

```bash
# 1) 先停掉写入端，避免恢复期间产生新数据
docker compose stop api web

# 2) 恢复（会要求输入库名确认；-y 可跳过）
./scripts/restore.sh backups/20261025T030000Z

# 3) 重新启动
docker compose start api web
```

- 需要 `PG_USER` 具备 `CREATEDB` / `DROP` 权限（compose 默认的 `POSTGRES_USER` 是超级用户，满足）。
- 对象恢复使用只读挂载的备份目录，不会改动备份本身。
- 恢复后建议跑一次迁移确认：`docker compose exec api alembic upgrade head`。

## 外部 S3 / R2 / OSS

若把附件放在外部对象存储（`S3_ENDPOINT` 指向外部），备份脚本会直接用 `mc` 连外部端点，行为不变；
`docker-compose.yml` 里的 `minio` 服务可保留不动（不参与备份）。请确保：

- `.env` 中 `S3_ENDPOINT` 带协议（如 `https://s3.example.com`）或把 `S3_USE_SSL=true`。
- 访问密钥具备读 bucket（备份）/ 写 bucket（恢复）的权限。

## 安全

- 脚本不会把 `S3_SECRET_KEY`、`POSTGRES_PASSWORD` 打到日志或 `MANIFEST`。
- `mc alias set` 的密钥只在一次性容器内部通过环境变量读取，不出现在宿主机命令行 / `ps` 中。
- 备份目录含全量用户数据，务必放在受控位置并按需做异地副本（`rsync` / 对象存储）。
