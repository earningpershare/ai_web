#!/bin/bash
# 部署腳本：將最新 main 分支部署到 VPS
# 用法：bash deploy.sh
# 前提：本地已 git push origin main

set -e

VPS="opc@161.33.17.40"
KEY="$(dirname "$0")/oracle_vm/ssh-key-2026-04-03.key"
REMOTE_DIR="/home/opc/ai_web"

echo "==> 推送到 GitHub..."
git push origin main

echo "==> 連線 VPS，拉取最新程式碼..."
ssh -i "$KEY" "$VPS" "
  set -e
  cd $REMOTE_DIR
  git pull origin main
  echo '==> 重新 build 並重啟服務...'
  sudo docker-compose -f docker-compose.prod.yml build --no-cache airflow-webserver airflow-scheduler api dashboard
  sudo docker-compose -f docker-compose.prod.yml up -d
  echo '==> 部署完成！'
  sudo docker-compose -f docker-compose.prod.yml ps
"
