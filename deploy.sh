#!/usr/bin/env bash
#
# Azmark 服务器部署脚本：拉取最新代码 -> 备份数据库 -> 重建/重启容器 -> 迁移 -> 健康检查 -> 清理。
# 代码与远端一致时自动跳过重建（见下方“1/6”）。
#
# 在服务器上运行（不要在本地跑）：
#   ./deploy.sh                    # 默认应用目录 /opt/Azmark
#   ./deploy.sh /path/to/azmark    # 指定目录
#   KEEP_BACKUPS=14 ./deploy.sh    # 备份保留份数（默认 7）
#   FORCE_DEPLOY=1 ./deploy.sh     # 代码没变也强制重建（改了 .env 等未跟踪文件时用）
#
# 若 git pull 没有带来新提交、且 api/web 容器健康，则跳过备份/构建/迁移直接退出。
# 注意：.env 不在 git 里，改过它需要用 FORCE_DEPLOY=1（或 docker compose up -d --build）。
#
# 远端历史被改写（force push）时无法快进：只要工作区没有未提交改动，脚本会
# 自动 reset --hard 对齐远端上游；有未提交改动则中止，绝不静默丢弃。
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

# 强制使用 BuildKit：层缓存跨构建复用（依赖重装+Next.js 增量编译的关键）。
# 旧构建器的中间层会被 `docker image prune` 当 dangling 镜像清掉，导致每次全量重装。
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

log() { printf '\033[1;34m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[deploy]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[deploy]\033[0m %s\n' "$*" >&2; }

cd "$APP_DIR"

command -v docker >/dev/null 2>&1 || { err "docker 未安装"; exit 1; }
docker compose version >/dev/null 2>&1 || { err "docker compose 插件不可用"; exit 1; }
[ -f .env ] || { err "缺少 .env（首次部署请参照 README 配置后再运行）"; exit 1; }

# 把工作副本推进到远端最新：优先快进，快进不了（远端历史被改写）且工作区
# 干净时对齐上游。有未提交改动一律中止——服务器上的部署副本不该有本地改动，
# 真有就必须让维护者自己决定保留还是丢弃，脚本不替它做主。
sync_with_remote() {
  if git pull --ff-only --no-rebase; then
    return 0
  fi

  warn "  git pull 无法快进：远端历史可能被改写（force push）。"
  if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    err "服务器上有未提交的改动，不会自动覆盖："
    git status --short --untracked-files=no >&2
    err "保留改动：git stash && $0"
    err "确认丢弃：git reset --hard origin/$(git symbolic-ref --short HEAD 2>/dev/null || echo main) && $0"
    return 1
  fi

  # 变量一律用 ${} 包裹：消息里有全角标点，某些 locale 下 bash 会把它
  # 算进变量名，配 set -u 就成了 unbound variable。
  local branch upstream remote
  branch="$(git symbolic-ref --short HEAD 2>/dev/null || true)"
  [ -n "${branch}" ] || { err "当前不在分支上（detached HEAD），无法自动对齐远端。"; return 1; }
  upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)"
  [ -n "${upstream}" ] || { err "分支 ${branch} 没有设置上游，无法自动对齐远端。"; return 1; }
  remote="${upstream%%/*}"

  git fetch "${remote}"
  git reset --hard "${upstream}"
  log "  已对齐 ${upstream}: $(git rev-parse --short HEAD)"
}

log "1/6 拉取最新代码 ($APP_DIR)"
before_rev="$(git rev-parse HEAD 2>/dev/null || true)"
sync_with_remote || exit 1
after_rev="$(git rev-parse HEAD)"

# 没有新提交 + 服务已在跑 + 健康检查通过：不必再备份/构建/迁移，直接收工。
# BuildKit 会复用层缓存，但“无变更重建”同样会重新生成镜像 ID 并重启容器（白白中断服务）。
if [ -z "${FORCE_DEPLOY:-}" ] && [ "$before_rev" = "$after_rev" ] \
  && [ -n "$(docker compose ps -q api 2>/dev/null)" ] \
  && [ -n "$(docker compose ps -q web 2>/dev/null)" ]; then
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    log "  代码无更新（${after_rev:0:7}），服务健康：跳过备份 / 构建 / 迁移。"
    log "  需要强制重建（例如改过 .env）：FORCE_DEPLOY=1 $0"
    exit 0
  fi
  warn "  代码无更新，但健康检查失败：继续完整部署流程。"
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
warn "  已清理旧镜像/停止容器；备份保留最近 ${KEEP_BACKUPS} 份于 ${BACKUP_DIR}。"

log "完成。服务状态："
docker compose ps
