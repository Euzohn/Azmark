#!/usr/bin/env bash
# Azmark 运维备份（spec #97）：PostgreSQL dump + S3/MinIO 对象。
#
# 在 Docker 宿主机上运行，依赖 `docker compose`（v2）与项目根目录的 .env。
# 不启动任何常驻服务：只 `exec` 已在运行的 postgres，并用一次性 mc 容器镜像对象。
#
# 用法：
#   scripts/backup.sh
# 环境变量（可写在 .env，也可在命令行临时覆盖）：
#   BACKUP_DIR             备份落盘目录（默认 <repo>/backups）
#   BACKUP_RETENTION_DAYS  保留天数，0 表示不清理（默认 30）
#   PG_USER / PG_DB        postgres 用户/库（默认 azmark/azmark）
#   S3_*                   与 api 相同，见 .env.example
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_DIR"

# 与 compose 使用同一份 .env；已存在的环境变量优先，便于 crontab 覆盖。
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

: "${PG_USER:=azmark}"
: "${PG_DB:=azmark}"
: "${S3_BUCKET:=azmark}"
: "${BACKUP_DIR:=$PROJECT_DIR/backups}"
: "${BACKUP_RETENTION_DAYS:=30}"

mkdir -p "$BACKUP_DIR"
# compose 的卷挂载需要绝对路径。
BACKUP_DIR=$(cd "$BACKUP_DIR" && pwd)
export BACKUP_DIR

ts=$(date -u +%Y%m%dT%H%M%SZ)
dest="$BACKUP_DIR/$ts"

# 中途失败时删除半成品，避免被误认为有效备份。
cleanup() {
  status=$?
  if [ "$status" -ne 0 ] && [ -d "$dest" ]; then
    echo "[backup] failed (exit $status); removing incomplete $dest" >&2
    rm -rf "$dest"
  fi
}
trap cleanup EXIT

mkdir -p "$dest/db" "$dest/objects"

echo "[backup] $(date -u +%FT%TZ) -> $dest"

# 1) PostgreSQL：在 postgres 容器内经 unix socket 执行 pg_dump（无需密码），
#    gzip 后直接落盘。pipefail 保证 pg_dump 失败时整条管道失败。
echo "[backup] pg_dump $PG_DB"
docker compose exec -T postgres \
  pg_dump -U "$PG_USER" -d "$PG_DB" --no-owner --no-privileges \
  | gzip > "$dest/db/azmark.sql.gz"

# 2) S3 / MinIO 对象：一次性 mc 容器镜像到备份目录。
#    bucket 不存在（从未上传过附件）时跳过，避免整次备份失败。
echo "[backup] mc mirror s3://$S3_BUCKET"
docker compose --profile backup run --rm --no-deps --entrypoint sh \
  -e TS="$ts" \
  mc -c '
    set -e
    mc alias set azmarksrc "$S3_ENDPOINT" "$S3_ACCESS_KEY" "$S3_SECRET_KEY" --api S3v4 >/dev/null
    if mc ls "azmarksrc/$S3_BUCKET" >/dev/null 2>&1; then
      mc mirror --overwrite "azmarksrc/$S3_BUCKET" "/backups/$TS/objects/$S3_BUCKET"
    else
      echo "[backup] bucket $S3_BUCKET not found; skipping objects"
      mkdir -p "/backups/$TS/objects/$S3_BUCKET"
    fi
  '

# 3) manifest（只记录结构信息，绝不写密钥）。
cat > "$dest/MANIFEST" <<EOF
azmark backup
created_at: $(date -u +%FT%TZ)
pg_db: $PG_DB
s3_bucket: $S3_BUCKET
db_dump: db/azmark.sql.gz
objects: objects/$S3_BUCKET
EOF

# 4) 保留策略：删除超过 N 天的备份目录（目录名是时间戳，避免误删其它目录）。
if [ "$BACKUP_RETENTION_DAYS" -gt 0 ]; then
  find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d \
    -name '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z' \
    -mtime +"$BACKUP_RETENTION_DAYS" -exec rm -rf {} +
fi

echo "[backup] done: $(du -sh "$dest" | cut -f1) ($dest)"
