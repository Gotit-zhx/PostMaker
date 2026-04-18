@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM PostMaker 备份
REM 用法: 双击运行 或 scripts\backup.bat

cd /d "%~dp0\.."
set "PROJECT_ROOT=%cd%"

REM 生成时间戳
for /f "tokens=2 delims==" %%a in ('wmic os get localdatetime /value 2^>nul') do set "dt=%%a"
set "TIMESTAMP=!dt:~0,4!!dt:~4,2!!dt:~6,2!_!dt:~8,2!!dt:~10,2!!dt:~12,2!"
set "BACKUP_DIR=%PROJECT_ROOT%\backups\!TIMESTAMP!"

echo.
echo ==================================================
echo    PostMaker 备份
echo ==================================================
echo.

mkdir "%BACKUP_DIR%" 2>nul
echo [信息] 备份目录: %BACKUP_DIR%

REM 1. PostgreSQL 备份
echo.
echo [信息] 备份 PostgreSQL 数据库...
docker exec dataradar-postgres pg_isready -U dataradar >nul 2>&1
if !errorlevel! equ 0 (
    docker exec dataradar-postgres pg_dump -U dataradar knowledge_base > "%BACKUP_DIR%\database.sql" 2>nul
    if !errorlevel! equ 0 (
        echo [成功] 数据库备份完成
    ) else (
        echo [警告] 数据库备份失败
    )
) else (
    echo [警告] PostgreSQL 未运行，跳过数据库备份
)

REM 2. 配置文件备份
echo [信息] 备份配置文件...
mkdir "%BACKUP_DIR%\config" 2>nul

if exist "%PROJECT_ROOT%\DataRadar\config\config.yaml" (
    copy "%PROJECT_ROOT%\DataRadar\config\config.yaml" "%BACKUP_DIR%\config\dataradar-config.yaml" >nul 2>&1
)
if exist "%PROJECT_ROOT%\DataRadar\docker\.env" (
    copy "%PROJECT_ROOT%\DataRadar\docker\.env" "%BACKUP_DIR%\config\docker.env" >nul 2>&1
)
if exist "%PROJECT_ROOT%\PostMaker\config\config.yaml" (
    copy "%PROJECT_ROOT%\PostMaker\config\config.yaml" "%BACKUP_DIR%\config\postmaker-config.yaml" >nul 2>&1
)
if exist "%PROJECT_ROOT%\PostMaker\config\personas" (
    xcopy "%PROJECT_ROOT%\PostMaker\config\personas" "%BACKUP_DIR%\config\personas\" /E /I /Q >nul 2>&1
)
echo [成功] 配置文件备份完成

REM 3. 清理旧备份（30天前）
echo [信息] 清理 30 天前的旧备份...
forfiles /P "%PROJECT_ROOT%\backups" /D -30 /C "cmd /c if @isdir==TRUE rmdir /S /Q @path" 2>nul

REM 汇总
echo.
echo ==================================================
echo [成功] 备份完成！
echo ==================================================
echo.
echo   备份位置: %BACKUP_DIR%
dir /b "%BACKUP_DIR%" 2>nul
echo.
echo   恢复命令: scripts\restore.bat %BACKUP_DIR%\database.sql
echo.
pause
