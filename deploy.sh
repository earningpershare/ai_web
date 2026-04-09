#!/bin/bash
# deploy.sh — 本地確認後一鍵部署到 VPS
#
# 用法：
#   bash deploy.sh              # 部署 api + dashboard（最常用）
#   bash deploy.sh api          # 只部署 api
#   bash deploy.sh dashboard    # 只部署 dashboard
#   bash deploy.sh airflow      # 只部署 airflow
#   bash deploy.sh all          # 重建所有服務

set -e

SSH_KEY="$(dirname "$0")/oracle_vm/ssh-key-2026-04-03.key"
VPS_USER="opc"
VPS_IP="161.33.17.40"
VPS_DIR="/home/opc/ai_web"
COMPOSE_FILE="docker-compose.prod.yml"
SERVICES="${1:-api dashboard}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[deploy]${NC} $1"; }
warn() { echo -e "${YELLOW}[warn]${NC}   $1"; }
err()  { echo -e "${RED}[error]${NC}  $1"; exit 1; }

# ── 1. 檢查 git 狀態 ──────────────────────────────────────────────────────────
log "檢查 git 狀態..."

BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "main" ]; then
    warn "目前在 '$BRANCH' 分支，不是 main"
    read -p "是否繼續部署？(y/N) " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || err "部署取消"
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
    warn "有未 commit 的變更："
    git status --short
    echo ""
    read -p "仍要部署目前已 commit 的版本？(y/N) " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || err "部署取消"
fi

# ── 2. Push 到 GitHub ─────────────────────────────────────────────────────────
log "推送到 GitHub (branch: $BRANCH)..."
git push origin "$BRANCH"
LOCAL_COMMIT=$(git rev-parse --short HEAD)
log "本地 commit: $LOCAL_COMMIT"

# ── 3. VPS pull + rebuild ─────────────────────────────────────────────────────
log "連線 VPS ($VPS_IP)，部署服務: $SERVICES ..."

if [ "$SERVICES" = "all" ]; then
    DOCKER_BUILD="sudo docker-compose -f $COMPOSE_FILE up -d --build"
else
    DOCKER_BUILD="sudo docker-compose -f $COMPOSE_FILE up -d --build $SERVICES"
fi

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$VPS_USER@$VPS_IP" bash << ENDSSH
set -e
cd $VPS_DIR

echo "[VPS] git pull..."
git pull
VPS_COMMIT=\$(git rev-parse --short HEAD)
echo "[VPS] commit: \$VPS_COMMIT"

echo "[VPS] 重建容器 ($SERVICES)..."
$DOCKER_BUILD 2>&1 | grep -E "Step|Successfully|error|ERROR|Starting|Started|Recreat" || true

echo "[VPS] 等待服務啟動 (5s)..."
sleep 5

echo "[VPS] 健康檢查..."
HTTP_STATUS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "\$HTTP_STATUS" = "200" ]; then
    echo "[VPS] ✅ API 正常 (HTTP \$HTTP_STATUS)"
else
    echo "[VPS] ❌ API 異常 (HTTP \$HTTP_STATUS)"
    sudo docker logs financial_api --tail 20
    exit 1
fi
ENDSSH

echo ""
log "✅ 部署完成！commit: $LOCAL_COMMIT"
log "   網站：https://16888u.com"
log "   API： https://api.16888u.com/docs"
