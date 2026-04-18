#!/usr/bin/env bash
set -euo pipefail

# PostMaker 停止服务
# 用法: ./scripts/stop.sh [--clean]

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[信息]${NC} $1"; }
ok()    { echo -e "${GREEN}[成功]${NC} $1"; }
warn()  { echo -e "${YELLOW}[警告]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/DataRadar/docker/docker-compose.yml"

echo ""
echo "=================================================="
echo "   停止 PostMaker 服务"
echo "=================================================="
echo ""

if [ "${1:-}" = "--clean" ]; then
    warn "⚠ --clean 模式将删除所有数据（数据库、缓存）！"
    warn "  如果需要保留数据，请按 Ctrl+C 取消，然后不带参数运行。"
    echo ""
    read -p "确认删除所有数据？(y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        info "已取消"
        exit 0
    fi
    info "停止服务并清除数据..."
    docker compose -f "$COMPOSE_FILE" down -v 2>/dev/null || docker-compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true
    ok "所有服务已停止，数据已清除"
else
    info "停止服务（保留数据）..."
    docker compose -f "$COMPOSE_FILE" down 2>/dev/null || docker-compose -f "$COMPOSE_FILE" down 2>/dev/null || true
    ok "所有服务已停止（数据已保留，下次启动时恢复）"
fi
echo ""
