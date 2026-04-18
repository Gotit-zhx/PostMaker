@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM PostMaker 一键安装脚本
REM 用法: 双击运行 或 scripts\setup.bat

echo.
echo ==================================================
echo    PostMaker 一键安装
echo ==================================================
echo.

cd /d "%~dp0\.."
set "PROJECT_ROOT=%cd%"
set "DATARADAR_DIR=%PROJECT_ROOT%\DataRadar"
set "POSTMAKER_DIR=%PROJECT_ROOT%\PostMaker"

REM =================================================
REM  1. 检查 / 安装 uv
REM =================================================
echo [信息] 检查 uv 包管理器...
uv --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=*" %%v in ('uv --version 2^>^&1') do echo [成功] %%v
    goto :uv_ready
)

echo [信息] 正在安装 uv...
powershell -ExecutionPolicy ByPass -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex" 2>nul
if !errorlevel! neq 0 (
    echo [错误] uv 安装失败。
    echo         请手动安装: https://docs.astral.sh/uv/
    pause
    exit /b 1
)

set "PATH=%USERPROFILE%\.local\bin;%PATH%"
uv --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [错误] uv 已安装但未在 PATH 中。请关闭此窗口，重新打开后再试。
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('uv --version 2^>^&1') do echo [成功] %%v 已安装

:uv_ready

REM =================================================
REM  2. Python
REM =================================================
echo [信息] 确保 Python ^>= 3.12...
uv python install 3.12 >nul 2>&1
echo [成功] Python 就绪

REM =================================================
REM  3. DataRadar 依赖
REM =================================================
echo [信息] 安装 DataRadar 依赖...
pushd "%DATARADAR_DIR%"
uv sync --all-extras
if !errorlevel! neq 0 (
    echo [错误] DataRadar 依赖安装失败。请检查网络连接。
    popd
    pause
    exit /b 1
)
popd
echo [成功] DataRadar 依赖安装完成

REM =================================================
REM  4. PostMaker 依赖
REM =================================================
echo [信息] 安装 PostMaker 依赖...
pushd "%POSTMAKER_DIR%"
uv sync --all-extras
if !errorlevel! neq 0 (
    echo [错误] PostMaker 依赖安装失败。请检查网络连接。
    popd
    pause
    exit /b 1
)
popd
echo [成功] PostMaker 依赖安装完成

REM =================================================
REM  5. Playwright
REM =================================================
echo [信息] 安装 Playwright 浏览器...
pushd "%DATARADAR_DIR%"
uv run playwright install chromium >nul 2>&1
if !errorlevel! equ 0 (
    echo [成功] Playwright Chromium 已安装
) else (
    echo [警告] Playwright 安装失败，网页采集功能可能不可用（不影响 RSS 采集）
)
popd

REM =================================================
REM  6. Docker
REM =================================================
set "DOCKER_OK=false"
docker --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [警告] Docker 未安装。知识库功能需要 Docker（PostgreSQL + Redis）
    echo         请安装 Docker Desktop: https://www.docker.com/products/docker-desktop/
    goto :after_docker
)

docker info >nul 2>&1
if !errorlevel! neq 0 (
    echo [警告] Docker 已安装但未运行。请启动 Docker Desktop。
    goto :after_docker
)

set "DOCKER_OK=true"
echo [成功] Docker 可用

REM Docker .env
if not exist "%DATARADAR_DIR%\docker\.env" (
    copy "%DATARADAR_DIR%\docker\.env.example" "%DATARADAR_DIR%\docker\.env" >nul
    echo [信息] 已创建 docker\.env 配置文件
    echo [警告] 请编辑 %DATARADAR_DIR%\docker\.env 填入你的 AI_API_KEY
) else (
    echo [信息] docker\.env 已存在，跳过
)

echo [信息] 启动 Docker 基础设施...
docker compose -f "%DATARADAR_DIR%\docker\docker-compose.yml" up postgres redis rsshub -d 2>nul
if !errorlevel! neq 0 (
    docker-compose -f "%DATARADAR_DIR%\docker\docker-compose.yml" up postgres redis rsshub -d 2>nul
)

echo [信息] 等待服务启动...
timeout /t 8 /nobreak >nul
echo [成功] Docker 服务已启动

:after_docker

REM =================================================
REM  7. 验证
REM =================================================
echo.
echo [信息] 验证安装...
pushd "%DATARADAR_DIR%"
uv run python -m dataradar status 2>nul
if !errorlevel! equ 0 (
    echo [成功] DataRadar 工作正常
) else (
    echo [警告] DataRadar 状态检查未通过，请检查配置
)
popd

REM =================================================
REM  完成
REM =================================================
echo.
echo ==================================================
echo    安装完成！
echo ==================================================
echo.
echo   下一步操作：
echo.
echo   1. 编辑配置文件填入 AI 密钥：
echo      %DATARADAR_DIR%\docker\.env
echo.
echo   2. 启动所有服务：
echo      双击 scripts\start.bat
echo.
echo   3. 运行数据采集：
echo      双击 scripts\collect.bat
echo.
echo   4. 生成内容：
echo      双击 scripts\generate.bat
echo.
pause
