@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ================================================================
REM DataRadar 数据备份脚本 (Windows)
REM
REM 用法: scripts\backup.bat [备份目录]
REM 示例: scripts\backup.bat D:\backups
REM ================================================================

set "BACKUP_DIR=%~1"
if "%BACKUP_DIR%"=="" set "BACKUP_DIR=backups"

for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set "DATESTAMP=%%c%%a%%b"
for /f "tokens=1-2 delims=:." %%a in ('time /t') do set "TIMESTAMP=%%a%%b"
set "STAMP=%DATESTAMP%_%TIMESTAMP: =0%"

cd /d "%~dp0\.."

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

echo ========================================
echo   DataRadar 数据备份
echo   目标: %BACKUP_DIR%
echo ========================================

REM PostgreSQL 备份
docker ps --format "{{.Names}}" 2>nul | findstr /C:"dataradar-postgres" >nul 2>&1
if %errorlevel%==0 (
    echo [备份] PostgreSQL...
    docker exec dataradar-postgres pg_dump -U dataradar knowledge_base > "%BACKUP_DIR%\pg_%STAMP%.sql"
    echo [备份] PostgreSQL 完成
) else (
    echo [跳过] PostgreSQL 容器未运行
)

REM SQLite 备份
if exist "output\rss" (
    echo [备份] SQLite 数据库...
    xcopy /Y /Q "output\rss\*.db" "%BACKUP_DIR%\sqlite_%STAMP%\" >nul 2>&1
    echo [备份] SQLite 完成
) else (
    echo [跳过] 未找到 SQLite 数据目录
)

REM 配置备份
echo [备份] 配置文件...
if exist "config\config.yaml" copy /Y "config\config.yaml" "%BACKUP_DIR%\config_%STAMP%.yaml" >nul 2>&1

echo.
echo [完成] 备份已保存到: %BACKUP_DIR%
dir "%BACKUP_DIR%\*%STAMP%*" 2>nul

pause
