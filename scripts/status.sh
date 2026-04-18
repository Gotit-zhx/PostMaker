#!/usr/bin/env bash
set -euo pipefail

# PostMaker 系统状态
# 用法: ./scripts/status.sh

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
pass()  { echo -e "  ${GREEN}[通过]${NC} $1"; }
fail_() { echo -e "  ${RED}[失败]${NC} $1"; }
warn()  { echo -e "  ${YELLOW}[警告]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/DataRadar/docker/docker-compose.yml"

echo ""
echo "=================================================="
echo "   PostMaker 系统状态"
echo "=================================================="

# Docker 容器
echo ""
echo "── Docker 容器 ──"
if ! command -v docker &>/dev/null || ! docker info &>/dev/null 2>&1; then
    fail_ "Docker 不可用"
else
    for svc in dataradar-postgres dataradar-redis dataradar-rsshub dataradar-api dataradar-nginx; do
        state=$(docker inspect -f '{{.State.Status}}' "$svc" 2>/dev/null || echo "未创建")
        if [ "$state" = "running" ]; then
            pass "$svc: 运行中"
        else
            fail_ "$svc: $state"
        fi
    done
fi

# 端口
echo ""
echo "── 端口检查 ──"
for port_info in "5432:PostgreSQL" "6379:Redis" "8000:API" "1200:RSSHub"; do
    port="${port_info%%:*}"
    name="${port_info##*:}"
    if command -v ss &>/dev/null; then
        ss -tlnp 2>/dev/null | grep -q ":$port " && pass "$name (端口 $port)" || fail_ "$name (端口 $port 未监听)"
    elif command -v netstat &>/dev/null; then
        netstat -tlnp 2>/dev/null | grep -q ":$port " && pass "$name (端口 $port)" || fail_ "$name (端口 $port 未监听)"
    else
        warn "$name (端口 $port) - 无法检测"
    fi
done

# PostgreSQL
echo ""
echo "── 数据库连接 ──"
if docker exec dataradar-postgres pg_isready -U dataradar -d knowledge_base &>/dev/null 2>&1; then
    pass "PostgreSQL 连接正常"
    count=$(docker exec dataradar-postgres psql -U dataradar -d knowledge_base -t -c "SELECT count(*) FROM content_items" 2>/dev/null | tr -d ' ' || echo "?")
    echo "       内容条目数: $count"
else
    fail_ "PostgreSQL 连接失败"
fi

# Redis
echo ""
echo "── Redis 缓存 ──"
if docker exec dataradar-redis redis-cli ping 2>/dev/null | grep -q PONG; then
    pass "Redis 连接正常"
    mem=$(docker exec dataradar-redis redis-cli info memory 2>/dev/null | grep "used_memory_human" | cut -d: -f2 | tr -d '\r' || echo "?")
    echo "       内存使用: $mem"
else
    fail_ "Redis 连接失败"
fi

# API
echo ""
echo "── API 服务 ──"
if curl -sf http://localhost:8000/health &>/dev/null; then
    health=$(curl -sf http://localhost:8000/health 2>/dev/null)
    pass "API 服务正常: $health"
else
    fail_ "API 服务不可达 (http://localhost:8000)"
fi

# 磁盘
echo ""
echo "── 磁盘空间 ──"
if command -v df &>/dev/null; then
    avail=$(df -h "$PROJECT_ROOT" 2>/dev/null | tail -1 | awk '{print $4}')
    echo "  可用空间: $avail"
fi

echo ""
