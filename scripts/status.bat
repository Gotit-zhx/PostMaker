@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM PostMaker 系统状态
REM 用法: 双击运行 或 scripts\status.bat

cd /d "%~dp0\.."
set "PROJECT_ROOT=%cd%"

echo.
echo ==================================================
echo    PostMaker 系统状态
echo ==================================================

REM Docker 容器
echo.
echo -- Docker 容器 --
docker --version >nul 2>&1
if !errorlevel! neq 0 (
    echo   [失败] Docker 不可用
    goto :skip_docker
)

for %%s in (dataradar-postgres dataradar-redis dataradar-rsshub dataradar-api dataradar-nginx) do (
    for /f "tokens=*" %%r in ('docker inspect -f "{{.State.Status}}" %%s 2^>nul') do set "state=%%r"
    if "!state!"=="running" (
        echo   [通过] %%s: 运行中
    ) else (
        echo   [失败] %%s: !state!
    )
    set "state="
)

:skip_docker

REM 端口
echo.
echo -- 端口检查 --
for %%p in (5432 6379 8000 1200) do (
    netstat -an 2>nul | findstr "LISTENING" | findstr ":%%p " >nul 2>&1
    if !errorlevel! equ 0 (
        echo   [通过] 端口 %%p 已监听
    ) else (
        echo   [失败] 端口 %%p 未监听
    )
)

REM PostgreSQL
echo.
echo -- 数据库连接 --
docker exec dataradar-postgres pg_isready -U dataradar -d knowledge_base >nul 2>&1
if !errorlevel! equ 0 (
    echo   [通过] PostgreSQL 连接正常
    for /f "tokens=*" %%c in ('docker exec dataradar-postgres psql -U dataradar -d knowledge_base -t -c "SELECT count(*) FROM content_items" 2^>nul') do (
        echo          内容条目数: %%c
    )
) else (
    echo   [失败] PostgreSQL 连接失败
)

REM Redis
echo.
echo -- Redis 缓存 --
docker exec dataradar-redis redis-cli ping 2>nul | findstr "PONG" >nul 2>&1
if !errorlevel! equ 0 (
    echo   [通过] Redis 连接正常
) else (
    echo   [失败] Redis 连接失败
)

REM API
echo.
echo -- API 服务 --
curl -sf http://localhost:8000/health >nul 2>&1
if !errorlevel! equ 0 (
    echo   [通过] API 服务正常
    echo          地址: http://localhost:8000
) else (
    echo   [失败] API 服务不可达
)

echo.
pause
