@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM PostMaker 数据采集
REM 用法: 双击运行 或 scripts\collect.bat [--status]

cd /d "%~dp0\.."
set "PROJECT_ROOT=%cd%"
set "DATARADAR_DIR=%PROJECT_ROOT%\DataRadar"
set "ENV_FILE=%PROJECT_ROOT%\DataRadar\docker\.env"

echo.
echo ==================================================
echo    数据采集
echo ==================================================
echo.

REM 检查 PostgreSQL
docker exec dataradar-postgres pg_isready -U dataradar >nul 2>&1
if !errorlevel! neq 0 (
    echo [错误] PostgreSQL 未运行。请先执行: scripts\start.bat
    pause
    exit /b 1
)

REM 加载环境变量
if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%ENV_FILE%") do (
        set "line=%%a"
        if not "!line:~0,1!"=="#" if not "!line!"=="" (
            set "%%a=%%b"
        )
    )
)

pushd "%DATARADAR_DIR%"

if "%~1"=="--status" (
    echo [信息] 查看采集统计...
    uv run dataradar rss --status
) else (
    echo [信息] 开始数据采集（RSS + 全文提取 + AI 摘要）...
    echo [信息] 这可能需要几分钟时间，请耐心等待...
    echo.

    uv run dataradar fetch

    echo.
    echo [成功] 数据采集完成！
    echo.
    echo   下一步: 双击 scripts\generate.bat 生成内容
)

popd
echo.
pause
