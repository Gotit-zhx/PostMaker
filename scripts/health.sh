#!/usr/bin/env bash
set -euo pipefail

# PostMaker 健康检查
# 用法: ./scripts/health.sh

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
pass()  { echo -e "  ${GREEN}[通过]${NC} $1"; }
fail_() { echo -e "  ${RED}[失败]${NC} $1"; ERRORS=$((ERRORS+1)); }
warn()  { echo -e "  ${YELLOW}[警告]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ERRORS=0

echo ""
echo "=================================================="
echo "   PostMaker 健康检查"
echo "=================================================="

# 环境
echo ""
echo "── 环境检查 ──"
command -v uv &>/dev/null && pass "uv: $(uv --version 2>/dev/null)" || fail_ "uv 未安装"

PY_VER=$(uv run python --version 2>/dev/null || echo "未安装")
if [[ "$PY_VER" == *"3.1"[2-9]* ]] || [[ "$PY_VER" == *"3.2"* ]]; then
    pass "Python: $PY_VER"
else
    fail_ "Python: $PY_VER (需要 3.12+)"
fi

if command -v docker &>/dev/null; then
    if docker info &>/dev/null 2>&1; then
        pass "Docker: $(docker --version 2>/dev/null | head -1)"
    else
        fail_ "Docker 已安装但未运行"
    fi
else
    fail_ "Docker 未安装"
fi

# 容器
echo ""
echo "── Docker 容器 ──"
for svc in dataradar-postgres dataradar-redis dataradar-api; do
    state=$(docker inspect -f '{{.State.Status}}' "$svc" 2>/dev/null || echo "未创建")
    health=$(docker inspect -f '{{.State.Health.Status}}' "$svc" 2>/dev/null || echo "无")
    if [ "$state" = "running" ]; then
        if [ "$health" = "healthy" ]; then
            pass "$svc: 运行中 (健康)"
        else
            pass "$svc: 运行中"
        fi
    else
        fail_ "$svc: $state"
    fi
done

# 数据库
echo ""
echo "── 数据库 ──"
if docker exec dataradar-postgres pg_isready -U dataradar -d knowledge_base &>/dev/null 2>&1; then
    pass "PostgreSQL 连接正常"
    count=$(docker exec dataradar-postgres psql -U dataradar -d knowledge_base -t -c "SELECT count(*) FROM content_items" 2>/dev/null | tr -d ' ' || echo "?")
    echo "       内容条目: $count"
    latest=$(docker exec dataradar-postgres psql -U dataradar -d knowledge_base -t -c "SELECT max(date_partition) FROM content_items" 2>/dev/null | tr -d ' ' || echo "?")
    echo "       最新日期: $latest"
else
    fail_ "PostgreSQL 连接失败"
fi

# Redis
echo ""
echo "── 缓存 ──"
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
    health_json=$(curl -sf http://localhost:8000/health 2>/dev/null || echo "{}")
    pass "API 正常: $health_json"
else
    fail_ "API 不可达 (http://localhost:8000)"
fi

# 配置
echo ""
echo "── 配置文件 ──"
[ -f "$PROJECT_ROOT/DataRadar/docker/.env" ] && pass "docker/.env 存在" || fail_ "docker/.env 不存在"
[ -f "$PROJECT_ROOT/DataRadar/config/config.yaml" ] && pass "DataRadar config.yaml 存在" || warn "DataRadar config.yaml 不存在（使用 config.example.yaml）"
[ -f "$PROJECT_ROOT/PostMaker/config/config.yaml" ] && pass "PostMaker config.yaml 存在" || fail_ "PostMaker config.yaml 不存在"

# AI 密钥
ENV_FILE="$PROJECT_ROOT/DataRadar/docker/.env"
if [ -f "$ENV_FILE" ]; then
    key=$(grep "^AI_API_KEY=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "")
    if [ -n "$key" ] && [ "$key" != "your-api-key-here" ]; then
        pass "AI_API_KEY 已配置 (${key:0:8}...)"
    else
        warn "AI_API_KEY 未配置（AI 摘要和内容生成需要）"
    fi
fi

# 磁盘
echo ""
echo "── 磁盘空间 ──"
if command -v df &>/dev/null; then
    avail=$(df -h "$PROJECT_ROOT" 2>/dev/null | tail -1 | awk '{print $4}')
    echo "  可用空间: $avail"
fi
if command -v docker &>/dev/null; then
    docker system df 2>/dev/null | head -4 | while read -r line; do echo "  $line"; done
fi

# 汇总
echo ""
echo "=================================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "  ${GREEN}所有检查通过${NC}"
else
    echo -e "  ${RED}发现 $ERRORS 个问题${NC}"
fi
echo "=================================================="
echo ""
