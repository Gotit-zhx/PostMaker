#!/usr/bin/env bash
set -euo pipefail

# PostMaker 内容生成
# 用法: ./scripts/generate.sh [--trending] [--topic 主题] [--limit N] [--dry-run] [--persona ID] [--refine]
# 默认: ./scripts/generate.sh --trending --limit 5

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[信息]${NC} $1"; }
ok()    { echo -e "${GREEN}[成功]${NC} $1"; }
fail()  { echo -e "${RED}[错误]${NC} $1"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
POSTMAKER_DIR="$PROJECT_ROOT/PostMaker"
ENV_FILE="$PROJECT_ROOT/DataRadar/docker/.env"

echo ""
echo "=================================================="
echo "   内容生成"
echo "=================================================="
echo ""

# 检查 API
if ! curl -sf http://localhost:8000/health &>/dev/null; then
    fail "DataRadar API 未运行。请先执行: ./scripts/start.sh"
fi

# 加载环境变量
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE" 2>/dev/null || true
    set +a
fi

# 检查 AI_API_KEY
if [ -z "${AI_API_KEY:-}" ]; then
    fail "未设置 AI_API_KEY。请编辑 $ENV_FILE 填入你的 AI 密钥。"
fi

cd "$POSTMAKER_DIR"

# 默认参数
if [ $# -eq 0 ]; then
    info "使用默认参数: --trending --limit 5"
    info "开始生成内容..."
    echo ""
    uv run postmaker generate --trending --limit 5
else
    info "开始生成内容..."
    echo ""
    uv run postmaker generate "$@"
fi

echo ""
ok "内容生成完成！"
echo ""
echo "  输出目录: $POSTMAKER_DIR/output/"
echo "  每篇文章有 .md 和 .html 两种格式"
echo ""
