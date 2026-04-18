@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM PostMaker 停止服务
REM 用法: 双击运行 或 scripts\stop.bat [--clean]

cd /d "%~dp0\.."
set "PROJECT_ROOT=%cd%"
set "COMPOSE_FILE=%PROJECT_ROOT%\DataRadar\docker\docker-compose.yml"

echo.
echo ==================================================
echo    停止 PostMaker 服务
echo ==================================================
echo.

if "%~1"=="--clean" (
    echo [警告] --clean 模式将删除所有数据（数据库、缓存）！
    echo [警告] 如果需要保留数据，请关闭此窗口，然后不带参数运行。
    echo.
    set /p "confirm=确认删除所有数据？(y/N): "
    if /i not "!confirm!"=="y" (
        echo [信息] 已取消
        pause
        exit /b 0
    )
    echo [信息] 停止服务并清除数据...
    docker compose -f "%COMPOSE_FILE%" down -v 2>nul
    echo [成功] 所有服务已停止，数据已清除
) else (
    echo [信息] 停止服务（保留数据）...
    docker compose -f "%COMPOSE_FILE%" down 2>nul
    echo [成功] 所有服务已停止（数据已保留，下次启动时恢复）
)
echo.
pause
