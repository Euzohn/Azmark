#!/usr/bin/env bash
#
# Azmark 服务器部署脚本：拉取最新代码 -> 备份数据库 -> 重建/重启容器 -> 迁移 -> 健康检查 -> 清理。
#
# 在服务器上运行（不要在本地跑）：
#   ./deploy.sh                    # 默认应用目录 /opt/Azmark
#   ./deploy.sh /path/to/azmark    # 指定目录
#   KEEP_BACKUPS=14 ./deploy.sh    # 备份保留份数（默认 7）
#
# 前置：docker + compose 插件已安装，当前用户有 docker 权限，目录内已有 .env。
set -euo pipefail

APP_DIR="${1:-/opt/Azmark}"
BACKUP_DIR="${APP_DIR}/backups"
KEEP_BACKUPS="${KEEP_BACKUPS:-7}"
HEALTH_URL="${HEALTH_URL:-http://localhost:3000/api/v1/health}"
HEALTH_RETRIES="${HEALTH_RETRIES:-30}"
DB_USER="${POSTGRES_USER:-azmark}"
DB_NAME="${POSTGRES_DB:-azmark}"

log() { printf '\033[1;34m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[deploy]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[deploy]\033[0m %s\n' "$*" >&2; }

cd "$APP_DIR"

command -v docker >/dev/null 2>&1 || { err "docker 未安装"; exit 1; }
docker compose version >/dev/null 2>&1 || { err "docker compose 插件不可用"; exit 1; }
[ -f .env ] || { err "缺少 .env（首次部署请参照 README 配置后再运行）"; exit 1; }

log "1/6 拉取最新代码 ($APP_DIR)"
if ! git pull --ff-only --no-rebase; then
  err "git pull 失败：服务器上可能有未提交的改动，请先处理再重试。"
  exit 1
fi

log "2/6 备份数据库"
mkdir -p "$BACKUP_DIR"
if [ -n "$(docker compose ps -q postgres 2>/dev/null)" ]; then
  backup_file="$BACKUP_DIR/azmark-$(date +%Y%m%d-%H%M%S).sql.gz"
  docker compose exec -T postgres pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$backup_file"
  log "  已备份 -> $backup_file"
else
  warn "  postgres 未在运行（首次部署？），跳过备份。"
fi

log "3/6 重建并启动容器"
docker compose up -d --build

log "4/6 数据库迁移"
docker compose exec -T api alembic upgrade head

log "5/6 健康检查 ($HEALTH_URL)"
ok=0
for _ in $(seq 1 "$HEALTH_RETRIES"); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 2
done
if [ "$ok" -ne 1 ]; then
  err "健康检查失败：$HEALTH_URL"
  err "请查看日志：docker compose logs --tail=100 api web"
  err "如需回滚：git checkout <上一个commit> && $0（脚本会自动备份后再迁移）"
  exit 1
fi
log "  服务正常。"

log "6/6 清理"
# 只清理无引用的镜像与已停止的容器，绝不动数据卷（postgres_data）。
docker image prune -f
docker container prune -f
# 备份只保留最近 KEEP_BACKUPS 份。
ls -1t "$BACKUP_DIR"/azmark-*.sql.gz 2>/dev/null \
  | tail -n +$((KEEP_BACKUPS + 1)) \
  | xargs -r rm -f
warn "  已清理旧镜像/停止容器；备份保留最近 $KEEP_BACKUPS 份于 $BACKUP_DIR。"

log "完成。服务状态："
docker compose ps
