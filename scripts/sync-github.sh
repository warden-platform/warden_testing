#!/usr/bin/env bash
# 把 gitee 主仓库 warden_testing 的当前树快照同步到 GitHub 镜像
# （warden-platform/warden_testing，main 分支）。
#
# 设计（与 warden 主仓 scripts/sync-github.sh 同构）：
# - GitHub 镜像是快照历史（每个同步点一个 commit），不携带 gitee 完整历史。
# - 用 git plumbing（read-tree/write-tree/commit-tree）构造提交；树一致时跳过。
# - 空仓首次同步：直接构造首个 commit 建立 main 分支。
# - 网络：gitee 侧直连（去死代理变量）；GitHub 侧走系统代理 127.0.0.1:7897。
#
# 依赖：git。gh 需已授权（或 token 已落盘 ~/.config/gh/hosts.yml）。
# 用法：scripts/sync-github.sh
set -euo pipefail

GITHUB_REPO="${GITHUB_REPO:-warden-platform/warden_testing}"
GITHUB_BRANCH="${GITHUB_BRANCH:-main}"
GITHUB_PROXY="${GITHUB_PROXY:-http://127.0.0.1:7897}"

cd "$(git rev-parse --show-toplevel)"

# gitee 侧操作必须去掉死代理变量
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy

COMMIT="$(git rev-parse HEAD)"
SHORT="$(git rev-parse --short HEAD)"

# 导出目标树（仅 tracked 文件，gitignore 的 .env 等不会进入快照）
EXPORT_DIR="$(mktemp -d)"
git archive "$COMMIT" | tar -x -C "$EXPORT_DIR"

# 浅克隆镜像（走代理）；空仓首次克隆会失败，则 init 一个空仓库。
MIRROR="$(mktemp -d)"
if git -c http.proxy="$GITHUB_PROXY" clone --quiet --branch "$GITHUB_BRANCH" --single-branch \
  "https://github.com/$GITHUB_REPO.git" "$MIRROR" 2>/dev/null; then
  PARENT="$(git -C "$MIRROR" rev-parse "origin/$GITHUB_BRANCH")"
else
  echo "镜像为空仓（首次同步），构造初始 commit。"
  git -C "$MIRROR" init --quiet --initial-branch="$GITHUB_BRANCH"
  git -C "$MIRROR" remote add origin "https://github.com/$GITHUB_REPO.git"
  PARENT=""
fi

export GIT_INDEX_FILE="$MIRROR/.git/sync-index"
git -C "$MIRROR" read-tree --empty
git -C "$MIRROR" --work-tree="$EXPORT_DIR" add -A
TREE="$(git -C "$MIRROR" write-tree)"

if [ -n "$PARENT" ] && [ "$TREE" = "$(git -C "$MIRROR" rev-parse "$PARENT^{tree}")" ]; then
  echo "树与镜像 HEAD 一致（gitee@$SHORT），无需新 commit。"
else
  MSG="chore: 同步 gitee master@$SHORT"
  if [ -n "$PARENT" ]; then
    NEW_COMMIT="$(git -C "$MIRROR" commit-tree "$TREE" -p "$PARENT" -m "$MSG")"
  else
    NEW_COMMIT="$(git -C "$MIRROR" commit-tree "$TREE" -m "$MSG")"
  fi
  git -C "$MIRROR" update-ref "refs/heads/$GITHUB_BRANCH" "$NEW_COMMIT"
  git -C "$MIRROR" -c http.proxy="$GITHUB_PROXY" push origin "$GITHUB_BRANCH"
  echo "已推送快照 commit：$(git -C "$MIRROR" rev-parse --short "$NEW_COMMIT")（gitee@$SHORT）"
fi
unset GIT_INDEX_FILE

echo "完成：https://github.com/$GITHUB_REPO"