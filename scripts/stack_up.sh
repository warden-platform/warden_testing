#!/usr/bin/env bash
# 启动本地 warden 控制面（若已在运行则直接返回）。
# 依赖：curl、PostgreSQL 客户端；Docker 仅在需要拉起 compose 数据库时使用。
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO_ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source ./.env
  set +a
fi

BASE_URL="${WARDEN_BASE_URL:-http://127.0.0.1:8080}"
HEALTH="${BASE_URL}/api/v1/health"

if curl -fsS -m 2 "$HEALTH" >/dev/null 2>&1; then
  echo "warden 控制面已就绪: ${BASE_URL}"
  exit 0
fi

WARDEN_HOME="${WARDEN_HOME:-../warden}"
if [[ ! -d "$WARDEN_HOME" ]]; then
  echo "未找到 warden 源码目录: ${WARDEN_HOME}" >&2
  echo "请设置 WARDEN_HOME 指向 warden 仓库根目录。" >&2
  exit 1
fi
WARDEN_HOME=$(cd "$WARDEN_HOME" && pwd)
WARDEN_ENV_FILE="${WARDEN_HOME}/.env"

if [[ ! -f "$WARDEN_ENV_FILE" ]]; then
  echo "缺少 ${WARDEN_ENV_FILE}；请先按 warden docs/quickstart.md 初始化。" >&2
  exit 1
fi

env_value() {
  # 只读取指定 key，避免把 warden .env 里的其他凭据导入当前 shell。
  grep -E "^$1=" "$WARDEN_ENV_FILE" | tail -1 | cut -d= -f2- || true
}

PG_HOST="${PG_HOST:-127.0.0.1}"
PG_PORT="${PG_PORT:-5432}"
PG_USER="${PG_USER:-warden}"
PG_DB="${PG_DB:-warden}"
PG_PASSWORD="${PGPASSWORD:-$(env_value WARDEN_DATABASE_PASSWORD)}"

if ! command -v pg_isready >/dev/null 2>&1 || ! pg_isready -h "$PG_HOST" -p "$PG_PORT" >/dev/null 2>&1; then
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo "==> 启动 compose PostgreSQL"
    (cd "$WARDEN_HOME" && docker compose --env-file .env -f deploy/docker-compose.yaml up -d postgresql)
    for _ in $(seq 1 30); do
      pg_isready -h "$PG_HOST" -p "$PG_PORT" >/dev/null 2>&1 && break
      sleep 1
    done
  else
    echo "PostgreSQL ${PG_HOST}:${PG_PORT} 未就绪，且 Docker 不可用。" >&2
    echo "请先启动 PostgreSQL，或设置 PG_HOST/PG_PORT 指向可用实例。" >&2
    exit 1
  fi
fi

# 全新空库才自动执行全部迁移；已有库请使用 warden 的 make migrate-release。
if command -v psql >/dev/null 2>&1; then
  export PGPASSWORD="$PG_PASSWORD"
  migrated=$(psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" -tAc \
    "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='tenants'" 2>/dev/null || true)
  if [[ "$migrated" != "1" ]]; then
    echo "==> 空库：执行 warden 迁移"
    for migration in "$WARDEN_HOME"/server/migrations/*.sql; do
      psql -v ON_ERROR_STOP=1 -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
        -f "$migration" >/dev/null
    done
  fi
  unset PGPASSWORD
else
  echo "警告：未找到 psql，跳过迁移检查。" >&2
fi

BINARY="${WARDEN_HOME}/server/bin/warden-control"
if [[ ! -x "$BINARY" ]] || [[ "${WARDEN_REBUILD:-0}" == "1" ]]; then
  echo "==> 构建 warden-control"
  (cd "$WARDEN_HOME" && make server-build)
fi

mkdir -p "$REPO_ROOT/logs"
LOG_FILE="$REPO_ROOT/logs/warden-control.log"
PID_FILE="$REPO_ROOT/.warden_test.pid"

echo "==> 启动 warden-control（日志: ${LOG_FILE}）"
(
  cd "$WARDEN_HOME"
  nohup "$BINARY" >"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
)

for _ in $(seq 1 60); do
  if curl -fsS -m 2 "$HEALTH" >/dev/null 2>&1; then
    echo "warden 控制面已就绪: ${BASE_URL}"
    exit 0
  fi
  sleep 1
done

echo "warden 控制面启动超时，最近日志：" >&2
tail -n 40 "$LOG_FILE" >&2 || true
exit 1