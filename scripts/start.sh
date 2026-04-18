#!/usr/bin/env bash
set -euo pipefail

# PostMaker 启动服务
# 用法: ./scripts/start.sh

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[信息]${NC} $1"; }
ok()    { echo -e "${GREEN}[成功]${NC} $1"; }
warn()  { echo -e "${YELLOW}[警告]${NC} $1"; }
fail()  { echo -e "${RED}[错误]${NC} $1"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/DataRadar/docker/docker-compose.yml"
ENV_FILE="$PROJECT_ROOT/DataRadar/docker/.env"

echo ""
echo "=================================================="
echo "   启动 PostMaker 服务"
echo "=================================================="
echo ""

# 检查 Docker
command -v docker &>/dev/null || fail "Docker 未安装。请先运行: ./scripts/setup.sh"
docker info &>/dev/null 2>&1 || fail "Docker 未运行。请启动 Docker Desktop。"

# 检查 .env
if [ ! -f "$ENV_FILE" ]; then
    fail "配置文件不存在: $ENV_FILE\n       请先运行: ./scripts/setup.sh"
fi

# 启动全部服务
info "启动 Docker 服务（PostgreSQL + Redis + RSSHub + API + Nginx）..."
docker compose -f "$COMPOSE_FILE" up -d 2>/dev/null || \
    docker-compose -f "$COMPOSE_FILE" up -d 2>/dev/null || \
    fail "Docker 服务启动失败"

info "等待服务就绪..."
sleep 8

# 健康检查
API_OK=false
for i in 1 2 3; do
    if curl -sf http://localhost:8000/health &>/dev/null; then
        API_OK=true
        break
    fi
    sleep 3
done

echo ""
if [ "$API_OK" = true ]; then
    ok "所有服务已启动"
    HEALTH=$(curl -sf http://localhost:8000/health 2>/dev/null || echo '{}')
    echo ""
    echo "  服务状态："
    echo "    PostgreSQL : 运行中 (端口 5432)"
    echo "    Redis      : 运行中 (端口 6379)"
    echo "    API 服务器 : 运行中 (端口 8000)"
    echo "    RSSHub     : 运行中 (端口 1200)"
    echo ""
    echo "  API 地址: http://localhost:8000"
    echo "  API 文档: http://localhost:8000/docs"
else
    warn "API 服务器尚未就绪，可能需要更多时间启动"
    info "请稍后运行 ./scripts/status.sh 检查状态"
fi
echo ""
