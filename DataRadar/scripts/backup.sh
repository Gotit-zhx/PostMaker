#!/bin/bash
# ================================================================
# DataRadar 数据备份脚本
#
# 用法: ./scripts/backup.sh [备份目录]
# 示例: ./scripts/backup.sh /mnt/backups
# ================================================================

set -euo pipefail

BACKUP_DIR="${1:-./backups}"
DATE=$(date +%Y%m%d_%H%M%S)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$BACKUP_DIR"

echo "========================================"
echo "  DataRadar 数据备份"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  目标: $BACKUP_DIR"
echo "========================================"

# PostgreSQL 备份
if docker ps --format '{{.Names}}' | grep -q dataradar-postgres; then
    echo "[备份] PostgreSQL..."
    docker exec dataradar-postgres pg_dump -U dataradar knowledge_base \
        | gzip > "$BACKUP_DIR/pg_${DATE}.sql.gz"
    echo "[备份] PostgreSQL 完成: pg_${DATE}.sql.gz"
else
    echo "[跳过] PostgreSQL 容器未运行"
fi

# SQLite 备份（仅最近 7 天）
if [ -d "$PROJECT_ROOT/output/rss" ]; then
    echo "[备份] SQLite 数据库..."
    cd "$PROJECT_ROOT"
    find output/rss -name "*.db" -mtime -7 -print0 2>/dev/null \
        | tar czf "$BACKUP_DIR/sqlite_${DATE}.tar.gz" --null -T - 2>/dev/null || true
    echo "[备份] SQLite 完成: sqlite_${DATE}.tar.gz"
else
    echo "[跳过] 未找到 SQLite 数据目录"
fi

# 配置备份
echo "[备份] 配置文件..."
cd "$PROJECT_ROOT"
tar czf "$BACKUP_DIR/config_${DATE}.tar.gz" \
    config/config.yaml docker/.env 2>/dev/null || true
echo "[备份] 配置完成: config_${DATE}.tar.gz"

# 清理 30 天前的备份
CLEANED=$(find "$BACKUP_DIR" -name "*.gz" -mtime +30 -delete -print 2>/dev/null | wc -l)
if [ "$CLEANED" -gt 0 ]; then
    echo "[清理] 已删除 $CLEANED 个过期备份文件"
fi

echo ""
echo "[完成] 备份已保存到: $BACKUP_DIR"
ls -lh "$BACKUP_DIR"/*_${DATE}.* 2>/dev/null
