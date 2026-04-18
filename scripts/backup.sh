#!/usr/bin/env bash
set -euo pipefail

# PostMaker 备份
# 用法: ./scripts/backup.sh

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[信息]${NC} $1"; }
ok()    { echo -e "${GREEN}[成功]${NC} $1"; }
warn()  { echo -e "${YELLOW}[警告]${NC} $1"; }
fail()  { echo -e "${RED}[错误]${NC} $1"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$PROJECT_ROOT/backups/$TIMESTAMP"

echo ""
echo "=================================================="
echo "   PostMaker 备份"
echo "=================================================="
echo ""

mkdir -p "$BACKUP_DIR"
info "备份目录: $BACKUP_DIR"

# 1. PostgreSQL 备份
echo ""
info "备份 PostgreSQL 数据库..."
if docker exec dataradar-postgres pg_isready -U dataradar &>/dev/null 2>&1; then
    docker exec dataradar-postgres pg_dump -U dataradar knowledge_base 2>/dev/null | gzip > "$BACKUP_DIR/database.sql.gz"
    size=$(du -h "$BACKUP_DIR/database.sql.gz" 2>/dev/null | cut -f1)
    ok "数据库备份完成 ($size)"
else
    warn "PostgreSQL 未运行，跳过数据库备份"
fi

# 2. 配置文件备份
info "备份配置文件..."
mkdir -p "$BACKUP_DIR/config"

[ -f "$PROJECT_ROOT/DataRadar/config/config.yaml" ] && \
    cp "$PROJECT_ROOT/DataRadar/config/config.yaml" "$BACKUP_DIR/config/dataradar-config.yaml"
[ -f "$PROJECT_ROOT/DataRadar/docker/.env" ] && \
    cp "$PROJECT_ROOT/DataRadar/docker/.env" "$BACKUP_DIR/config/docker.env"
[ -f "$PROJECT_ROOT/PostMaker/config/config.yaml" ] && \
    cp "$PROJECT_ROOT/PostMaker/config/config.yaml" "$BACKUP_DIR/config/postmaker-config.yaml"

if [ -d "$PROJECT_ROOT/PostMaker/config/personas" ]; then
    cp -r "$PROJECT_ROOT/PostMaker/config/personas" "$BACKUP_DIR/config/personas"
fi

ok "配置文件备份完成"

# 3. SQLite 备份（如果有）
if ls "$PROJECT_ROOT/DataRadar/output/rss/"*.db &>/dev/null 2>&1; then
    info "备份 SQLite 数据..."
    mkdir -p "$BACKUP_DIR/sqlite"
    cp "$PROJECT_ROOT/DataRadar/output/rss/"*.db "$BACKUP_DIR/sqlite/" 2>/dev/null || true
    ok "SQLite 备份完成"
fi

# 4. 清理旧备份（30天前）
info "清理 30 天前的旧备份..."
find "$PROJECT_ROOT/backups" -maxdepth 1 -type d -mtime +30 -exec rm -rf {} \; 2>/dev/null || true

# 汇总
echo ""
echo "=================================================="
ok "备份完成！"
echo "=================================================="
echo ""
echo "  备份位置: $BACKUP_DIR"
ls -lh "$BACKUP_DIR/" 2>/dev/null | tail -n +2 | while read -r line; do
    echo "    $line"
done
echo ""
echo "  恢复命令: ./scripts/restore.sh $BACKUP_DIR/database.sql.gz"
echo ""
