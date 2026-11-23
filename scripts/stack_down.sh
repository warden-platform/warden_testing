#!/usr/bin/env bash
# 只停止由本仓库 stack_up.sh 启动的控制面；不会影响用户已有的 warden 进程。
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PID_FILE="$REPO_ROOT/.warden_test.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "本仓库未启动 warden 控制面，无需停止。"
  exit 0
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" >/dev/null 2>&1; then
  kill "$PID"
  echo "已停止 warden-control (PID ${PID})"
else
  echo "PID ${PID} 已不存在"
fi
rm -f "$PID_FILE"