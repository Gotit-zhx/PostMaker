@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM PostMaker 健康检查
REM 用法: 双击运行 或 scripts\health.bat

cd /d "%~dp0\.."
set "PROJECT_ROOT=%cd%"
set "ERRORS=0"

echo.
echo ==================================================
echo    PostMaker 健康检查
echo ==================================================

REM 环境
echo.
echo -- 环境检查 --
uv --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=*" %%v in ('uv --version 2^>^&1') do echo   [通过] uv: %%v
) else (
    echo   [失败] uv 未安装
    set /a ERRORS+=1
)

docker --version >nul 2>&1
if !errorlevel! equ 0 (
    docker info >nul 2>&1
    if !errorlevel! equ 0 (
        echo   [通过] Docker 可用
    ) else (
        echo   [失败] Docker 已安装但未运行
        set /a ERRORS+=1
    )
) else (
    echo   [失败] Docker 未安装
    set /a ERRORS+=1
)

REM 容器
echo.
echo -- Docker 容器 --
for %%s in (dataradar-postgres dataradar-redis dataradar-api) do (
    for /f "tokens=*" %%r in ('docker inspect -f "{{.State.Status}}" %%s 2^>nul') do set "state=%%r"
    if "!state!"=="running" (
        echo   [通过] %%s: 运行中
    ) else (
        echo   [失败] %%s: !state!
        set /a ERRORS+=1
    )
    set "state="
)

REM 数据库
echo.
echo -- 数据库 --
docker exec dataradar-postgres pg_isready -U dataradar -d knowledge_base >nul 2>&1
if !errorlevel! equ 0 (
    echo   [通过] PostgreSQL 连接正常
    for /f "tokens=*" %%c in ('docker exec dataradar-postgres psql -U dataradar -d knowledge_base -t -c "SELECT count(*) FROM content_items" 2^>nul') do (
        echo          内容条目: %%c
    )
) else (
    echo   [失败] PostgreSQL 连接失败
    set /a ERRORS+=1
)

REM Redis
echo.
echo -- 缓存 --
docker exec dataradar-redis redis-cli ping 2>nul | findstr "PONG" >nul 2>&1
if !errorlevel! equ 0 (
    echo   [通过] Redis 连接正常
) else (
    echo   [失败] Redis 连接失败
    set /a ERRORS+=1
)

REM API
echo.
echo -- API 服务 --
curl -sf http://localhost:8000/health >nul 2>&1
if !errorlevel! equ 0 (
    echo   [通过] API 服务正常 ^(http://localhost:8000^)
) else (
    echo   [失败] API 不可达
    set /a ERRORS+=1
)

REM 配置
echo.
echo -- 配置文件 --
if exist "%PROJECT_ROOT%\DataRadar\docker\.env" (
    echo   [通过] docker\.env 存在
) else (
    echo   [失败] docker\.env 不存在
    set /a ERRORS+=1
)
if exist "%PROJECT_ROOT%\PostMaker\config\config.yaml" (
    echo   [通过] PostMaker config.yaml 存在
) else (
    echo   [失败] PostMaker config.yaml 不存在
    set /a ERRORS+=1
)

REM 汇总
echo.
echo ==================================================
if !ERRORS! equ 0 (
    echo   所有检查通过
) else (
    echo   发现 !ERRORS! 个问题
)
echo ==================================================
echo.
pause
