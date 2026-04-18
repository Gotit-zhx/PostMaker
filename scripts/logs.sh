#!/usr/bin/env bash
set -euo pipefail

# PostMaker 查看日志
# 用法: ./scripts/logs.sh [--api|--postgres|--redis|--rsshub] [--follow] [--lines N]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/DataRadar/docker/docker-compose.yml"

SERVICE=""
FOLLOW=""
LINES=100

while [ $# -gt 0 ]; do
    case "$1" in
        --api)      SERVICE="api-server" ;;
        --postgres) SERVICE="postgres" ;;
        --redis)    SERVICE="redis" ;;
        --rsshub)   SERVICE="rsshub" ;;
        --nginx)    SERVICE="nginx" ;;
        --follow|-f) FOLLOW="--follow" ;;
        --lines)    shift; LINES="${1:-100}" ;;
        *)
            echo "用法: ./scripts/logs.sh [选项]"
            echo ""
            echo "选项:"
            echo "  --api        API 服务器日志"
            echo "  --postgres   数据库日志"
            echo "  --redis      缓存日志"
            echo "  --rsshub     RSSHub 日志"
            echo "  --follow     实时跟踪（按 Ctrl+C 退出）"
            echo "  --lines N    显示行数（默认 100）"
            echo ""
            echo "不带参数: 显示所有服务最近 100 行日志"
            exit 0
            ;;
    esac
    shift
done

if [ -n "$SERVICE" ]; then
    docker compose -f "$COMPOSE_FILE" logs "$SERVICE" --tail "$LINES" $FOLLOW
else
    docker compose -f "$COMPOSE_FILE" logs --tail "$LINES" $FOLLOW
fi
