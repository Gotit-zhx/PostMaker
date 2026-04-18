@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM PostMaker 数据库恢复
REM 用法: scripts\restore.bat <备份文件路径>
REM 示例: scripts\restore.bat backups\20250115_103000\database.sql

cd /d "%~dp0\.."

echo.
echo ==================================================
echo    数据库恢复
echo ==================================================
echo.

set "BACKUP_FILE=%~1"

if "!BACKUP_FILE!"=="" (
    echo [错误] 请指定备份文件路径。
    echo.
    echo         用法: scripts\restore.bat ^<备份文件^>
    echo         示例: scripts\restore.bat backups\20250115_103000\database.sql
    echo.
    pause
    exit /b 1
)

if not exist "!BACKUP_FILE!" (
    echo [错误] 备份文件不存在: !BACKUP_FILE!
    echo         请检查路径是否正确。
    pause
    exit /b 1
)

docker exec dataradar-postgres pg_isready -U dataradar >nul 2>&1
if !errorlevel! neq 0 (
    echo [错误] PostgreSQL 未运行。请先执行: scripts\start.bat
    pause
    exit /b 1
)

echo [警告] 恢复操作将覆盖当前数据库中的所有数据！
echo.
set /p "confirm=确认恢复？(y/N): "
if /i not "!confirm!"=="y" (
    echo [信息] 已取消
    pause
    exit /b 0
)

echo [信息] 正在恢复数据库...
type "!BACKUP_FILE!" | docker exec -i dataradar-postgres psql -U dataradar -d knowledge_base >nul 2>&1

echo.
echo [成功] 数据库恢复完成！
echo.
pause
