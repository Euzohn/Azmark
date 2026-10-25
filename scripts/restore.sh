#!/usr/bin/env bash
# Azmark 运维恢复（spec #97）：从 scripts/backup.sh 产出的目录恢复 PG + S3/MinIO 对象。
#
# 破坏性操作：会 DROP 并重建数据库、清空并重传 bucket。
# 默认要求手动输入库名确认；加 -y/--yes 跳过。
#
# 建议先停掉写入端，恢复完再启动：
#   docker compose stop api web
#   scripts/restore.sh backups/20261025T030000Z
#   docker compose start api web
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

: "${PG_USER:=azmark}"
: "${PG_DB:=azmark}"
: "${S3_BUCKET:=azmark}"

usage() {
  echo "usage: $0 <backup-dir> [--yes]" >&2
  echo "  e.g. $0 backups/20261025T030000Z --yes" >&2
}

src="${1:-}"
[ -n "$src" ] || { usage; exit 1; }
shift || true

assume_yes=0
for arg in "$@"; do
  case "$arg" in
    -y | --yes) assume_yes=1 ;;
    *)
      echo "unknown option: $arg" >&2
      usage
      exit 1
      ;;
  esac
done

src=$(cd "$src" 2>/dev/null && pwd) || {
  echo "backup dir not found: $src" >&2
  exit 1
}

sql="$src/db/azmark.sql.gz"
objects="$src/objects/$S3_BUCKET"
[ -f "$sql" ] || {
  echo "missing dump: $sql" >&2
  exit 1
}

echo "WARNING: this will DESTROY the current data:"
echo "  - DROP and recreate database '$PG_DB'"
echo "  - replace all objects in bucket '$S3_BUCKET'"
echo "  source: $src"
if [ "$assume_yes" -ne 1 ]; then
  printf 'type the database name (%s) to continue: ' "$PG_DB"
  read -r answer
  [ "$answer" = "$PG_DB" ] || {
    echo "aborted"
    exit 1
  }
fi

echo "[restore] dropping and recreating database $PG_DB"
docker compose exec -T postgres psql -U "$PG_USER" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '$PG_DB' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS "$PG_DB";
CREATE DATABASE "$PG_DB";
SQL

echo "[restore] loading $sql"
gunzip -c "$sql" | docker compose exec -T postgres \
  psql -U "$PG_USER" -d "$PG_DB" -v ON_ERROR_STOP=1

if [ -d "$objects" ]; then
  echo "[restore] restoring objects to s3://$S3_BUCKET"
  docker compose --profile backup run --rm --no-deps --entrypoint sh \
    -v "$objects:/restore/objects:ro" \
    mc -c '
      set -e
      mc alias set azmarkdst "$S3_ENDPOINT" "$S3_ACCESS_KEY" "$S3_SECRET_KEY" --api S3v4 >/dev/null
      mc rb --force "azmarkdst/$S3_BUCKET" >/dev/null 2>&1 || true
      mc mb --ignore-existing "azmarkdst/$S3_BUCKET" >/dev/null
      mc mirror --overwrite "/restore/objects/$S3_BUCKET" "azmarkdst/$S3_BUCKET"
    '
else
  echo "[restore] no objects in backup; skipping object restore"
fi

echo "[restore] done from $src"
