#!/usr/bin/env bash
# 在项目虚拟环境中运行 pytest，可透传任意参数。
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3.13}"
if [[ ! -x .venv/bin/python ]]; then
  "$PYTHON_BIN" -m venv .venv
  .venv/bin/pip install --quiet -r requirements.txt
fi

exec .venv/bin/python -m pytest "$@"