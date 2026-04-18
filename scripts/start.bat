@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM PostMaker 启动服务
REM 用法: 双击运行 或 scripts\start.bat

cd /d "%~dp0\.."
set "PROJECT_ROOT=%cd%"
set "COMPOSE_FILE=%PROJECT_ROOT%\DataRadar\docker\docker-compose.yml"
set "ENV_FILE=%PROJECT_ROOT%\DataRadar\docker\.env"

echo.
echo ==================================================
echo    启动 PostMaker 服务
echo ==================================================
echo.

REM 检查 Docker
docker --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [错误] Docker 未安装。请先运行: scripts\setup.bat
    pause
    exit /b 1
)

docker info >nul 2>&1
if !errorlevel! neq 0 (
    echo [错误] Docker 未运行。请启动 Docker Desktop。
    pause
    exit /b 1
)

REM 检查 .env
if not exist "%ENV_FILE%" (
    echo [错误] 配置文件不存在: %ENV_FILE%
    echo         请先运行: scripts\setup.bat
    pause
    exit /b 1
)

REM 启动全部服务
echo [信息] 启动 Docker 服务（PostgreSQL + Redis + RSSHub + API + Nginx）...
docker compose -f "%COMPOSE_FILE%" up -d 2>nul
if !errorlevel! neq 0 (
    docker-compose -f "%COMPOSE_FILE%" up -d 2>nul
    if !errorlevel! neq 0 (
        echo [错误] Docker 服务启动失败
        pause
        exit /b 1
    )
)

echo [信息] 等待服务就绪...
timeout /t 8 /nobreak >nul

REM 健康检查
set "API_OK=false"
for /l %%i in (1,1,3) do (
    curl -sf http://localhost:8000/health >nul 2>&1
    if !errorlevel! equ 0 (
        set "API_OK=true"
        goto :health_done
    )
    timeout /t 3 /nobreak >nul
)
:health_done

echo.
if "!API_OK!"=="true" (
    echo [成功] 所有服务已启动
    echo.
    echo   服务状态：
    echo     PostgreSQL : 运行中 ^(端口 5432^)
    echo     Redis      : 运行中 ^(端口 6379^)
    echo     API 服务器 : 运行中 ^(端口 8000^)
    echo     RSSHub     : 运行中 ^(端口 1200^)
    echo.
    echo   API 地址: http://localhost:8000
    echo   API 文档: http://localhost:8000/docs
) else (
    echo [警告] API 服务器尚未就绪，可能需要更多时间启动
    echo [信息] 请稍后运行 scripts\status.bat 检查状态
)
echo.
pause
