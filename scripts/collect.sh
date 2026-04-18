#!/usr/bin/env bash
set -euo pipefail

# PostMaker 数据采集
# 用法: ./scripts/collect.sh [--status]

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[信息]${NC} $1"; }
ok()    { echo -e "${GREEN}[成功]${NC} $1"; }
warn()  { echo -e "${YELLOW}[警告]${NC} $1"; }
fail()  { echo -e "${RED}[错误]${NC} $1"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATARADAR_DIR="$PROJECT_ROOT/DataRadar"
ENV_FILE="$PROJECT_ROOT/DataRadar/docker/.env"

echo ""
echo "=================================================="
echo "   数据采集"
echo "=================================================="
echo ""

# 检查 PostgreSQL
if ! docker exec dataradar-postgres pg_isready -U dataradar &>/dev/null 2>&1; then
    fail "PostgreSQL 未运行。请先执行: ./scripts/start.sh"
fi

# 加载环境变量
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE" 2>/dev/null || true
    set +a
fi

cd "$DATARADAR_DIR"

if [ "${1:-}" = "--status" ]; then
    info "查看采集统计..."
    uv run dataradar rss --status
else
    info "开始数据采集（RSS + 全文提取 + AI 摘要）..."
    info "这可能需要几分钟时间，请耐心等待..."
    echo ""

    START_TIME=$(date +%s)
    uv run dataradar fetch
    END_TIME=$(date +%s)
    ELAPSED=$(( END_TIME - START_TIME ))

    echo ""
    ok "数据采集完成！耗时 ${ELAPSED} 秒"
    echo ""
    echo "  下一步: 运行 ./scripts/generate.sh 生成内容"
fi
echo ""
