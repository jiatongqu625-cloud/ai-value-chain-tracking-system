#!/usr/bin/env bash
# setup.sh — 一键初始化并推送到 GitHub
# 用法：
#   1. 先在 GitHub 新建一个空 repo（不要勾选 README）
#   2. bash setup.sh https://github.com/YOUR_USERNAME/ai-chain-tracker.git
set -e

REPO_URL=${1:-""}
if [ -z "$REPO_URL" ]; then
  echo "用法: bash setup.sh https://github.com/YOUR_USERNAME/YOUR_REPO.git"
  exit 1
fi

echo "=== 1. 初始化 git ==="
git init
git add .
git commit -m "init: AI 产业链追踪项目"

echo "=== 2. 设置远端并推送 ==="
git remote add origin "$REPO_URL"
git branch -M main
git push -u origin main

echo ""
echo "✓ 推送完成！"
echo ""
echo "=== 下一步 ==="
echo "在 GitHub 仓库设置中添加 Secrets："
echo "  Settings → Secrets and variables → Actions → New repository secret"
echo ""
echo "  ANTHROPIC_API_KEY  = sk-ant-..."
echo "  NEWS_API_KEY       = (可选，从 newsapi.org 获取)"
echo ""
echo "然后进入 Actions 页面手动触发 'Daily AI Chain Update' 即可运行第一次。"
echo ""
echo "前端访问：将 frontend/index.html 和 data/ 目录部署到 GitHub Pages 即可。"
echo "  Settings → Pages → Source: Deploy from a branch → main / (root)"
