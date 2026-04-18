#!/usr/bin/env bash
set -euo pipefail

# PostMaker 数据库恢复
# 用法: ./scripts/restore.sh <备份文件路径>
# 示例: ./scripts/restore.sh backups/20250115_103000/database.sql.gz

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[信息]${NC} $1"; }
ok()    { echo -e "${GREEN}[成功]${NC} $1"; }
warn()  { echo -e "${YELLOW}[警告]${NC} $1"; }
fail()  { echo -e "${RED}[错误]${NC} $1"; exit 1; }

echo ""
echo "=================================================="
echo "   数据库恢复"
echo "=================================================="
echo ""

BACKUP_FILE="${1:-}"

if [ -z "$BACKUP_FILE" ]; then
    fail "请指定备份文件路径。\n       用法: ./scripts/restore.sh <备份文件>\n       示例: ./scripts/restore.sh backups/20250115_103000/database.sql.gz"
fi

if [ ! -f "$BACKUP_FILE" ]; then
    fail "备份文件不存在: $BACKUP_FILE\n       请检查路径是否正确。"
fi

if ! docker exec dataradar-postgres pg_isready -U dataradar &>/dev/null 2>&1; then
    fail "PostgreSQL 未运行。请先执行: ./scripts/start.sh"
fi

warn "⚠ 恢复操作将覆盖当前数据库中的所有数据！"
echo ""
read -p "确认恢复？(y/N): " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    info "已取消"
    exit 0
fi

info "正在恢复数据库..."

if [[ "$BACKUP_FILE" == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" | docker exec -i dataradar-postgres psql -U dataradar -d knowledge_base 2>/dev/null
else
    docker exec -i dataradar-postgres psql -U dataradar -d knowledge_base < "$BACKUP_FILE" 2>/dev/null
fi

# 验证
count=$(docker exec dataradar-postgres psql -U dataradar -d knowledge_base -t -c "SELECT count(*) FROM content_items" 2>/dev/null | tr -d ' ' || echo "0")
echo ""
ok "数据库恢复完成！当前内容条目数: $count"
echo ""
