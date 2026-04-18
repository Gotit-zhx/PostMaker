#!/usr/bin/env bash
set -euo pipefail

# PostMaker 一键安装脚本
# 用法: ./scripts/setup.sh

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[信息]${NC} $1"; }
ok()    { echo -e "${GREEN}[成功]${NC} $1"; }
warn()  { echo -e "${YELLOW}[警告]${NC} $1"; }
fail()  { echo -e "${RED}[错误]${NC} $1"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATARADAR_DIR="$PROJECT_ROOT/DataRadar"
POSTMAKER_DIR="$PROJECT_ROOT/PostMaker"

echo ""
echo "=================================================="
echo "   PostMaker 一键安装"
echo "=================================================="
echo ""

# 1. uv
info "检查 uv 包管理器..."
if command -v uv &>/dev/null; then
    ok "uv 已安装: $(uv --version)"
else
    info "正在安装 uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh || fail "uv 安装失败。请手动安装: https://docs.astral.sh/uv/"
    export PATH="$HOME/.local/bin:$PATH"
    command -v uv &>/dev/null || fail "uv 安装完成但未在 PATH 中找到。请重新打开终端后重试。"
    ok "uv 已安装: $(uv --version)"
fi

# 2. Python
info "确保 Python >= 3.12..."
uv python install 3.12 2>/dev/null || true
ok "Python 就绪"

# 3. DataRadar 依赖
info "安装 DataRadar 依赖..."
cd "$DATARADAR_DIR"
uv sync --all-extras || fail "DataRadar 依赖安装失败。请检查网络连接。"
ok "DataRadar 依赖安装完成"

# 4. PostMaker 依赖
info "安装 PostMaker 依赖..."
cd "$POSTMAKER_DIR"
uv sync --all-extras || fail "PostMaker 依赖安装失败。请检查网络连接。"
ok "PostMaker 依赖安装完成"

# 5. Playwright
info "安装 Playwright 浏览器（用于网页采集）..."
cd "$DATARADAR_DIR"
if uv run playwright install chromium 2>/dev/null; then
    ok "Playwright Chromium 已安装"
else
    warn "Playwright 安装失败，网页采集功能可能不可用（不影响 RSS 采集）"
fi

# 6. Docker
info "检查 Docker..."
if ! command -v docker &>/dev/null; then
    warn "Docker 未安装。知识库功能需要 Docker（PostgreSQL + Redis）"
    warn "请安装 Docker Desktop: https://www.docker.com/products/docker-desktop/"
    DOCKER_OK=false
elif ! docker info &>/dev/null 2>&1; then
    warn "Docker 已安装但未运行。请启动 Docker Desktop。"
    DOCKER_OK=false
else
    ok "Docker 可用"
    DOCKER_OK=true
fi

# 7. Docker .env
if [ "$DOCKER_OK" = true ]; then
    ENV_FILE="$DATARADAR_DIR/docker/.env"
    if [ ! -f "$ENV_FILE" ]; then
        cp "$DATARADAR_DIR/docker/.env.example" "$ENV_FILE"
        info "已创建 docker/.env 配置文件"
        warn "请编辑 $ENV_FILE 填入你的 AI_API_KEY"
    else
        info "docker/.env 已存在，跳过"
    fi

    # 8. 启动基础设施
    info "启动 Docker 基础设施..."
    docker compose -f "$DATARADAR_DIR/docker/docker-compose.yml" up postgres redis rsshub -d 2>/dev/null || \
        docker-compose -f "$DATARADAR_DIR/docker/docker-compose.yml" up postgres redis rsshub -d 2>/dev/null || \
        warn "Docker 服务启动失败，请手动运行: docker compose up -d"

    info "等待服务启动..."
    sleep 8
    ok "Docker 服务已启动"
fi

# 9. 验证
echo ""
info "验证安装..."
cd "$DATARADAR_DIR"
uv run python -m dataradar status 2>/dev/null && ok "DataRadar 工作正常" || warn "DataRadar 状态检查未通过，请检查配置"

# 完成
echo ""
echo "=================================================="
echo "   安装完成！"
echo "=================================================="
echo ""
echo "  下一步操作："
echo ""
echo "  1. 编辑配置文件填入 AI 密钥："
echo "     $DATARADAR_DIR/docker/.env"
echo ""
echo "  2. 启动所有服务："
echo "     ./scripts/start.sh"
echo ""
echo "  3. 运行数据采集："
echo "     ./scripts/collect.sh"
echo ""
echo "  4. 生成内容："
echo "     ./scripts/generate.sh"
echo ""
