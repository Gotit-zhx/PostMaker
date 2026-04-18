@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM PostMaker 查看日志
REM 用法: scripts\logs.bat [--api|--postgres|--redis] [--follow] [--lines N]

cd /d "%~dp0\.."
set "PROJECT_ROOT=%cd%"
set "COMPOSE_FILE=%PROJECT_ROOT%\DataRadar\docker\docker-compose.yml"

set "SERVICE="
set "FOLLOW="
set "LINES=100"

:parse_args
if "%~1"=="" goto :run
if "%~1"=="--api" set "SERVICE=api-server" & shift & goto :parse_args
if "%~1"=="--postgres" set "SERVICE=postgres" & shift & goto :parse_args
if "%~1"=="--redis" set "SERVICE=redis" & shift & goto :parse_args
if "%~1"=="--rsshub" set "SERVICE=rsshub" & shift & goto :parse_args
if "%~1"=="--follow" set "FOLLOW=--follow" & shift & goto :parse_args
if "%~1"=="-f" set "FOLLOW=--follow" & shift & goto :parse_args
if "%~1"=="--lines" set "LINES=%~2" & shift & shift & goto :parse_args
if "%~1"=="--help" goto :usage
shift
goto :parse_args

:usage
echo 用法: scripts\logs.bat [选项]
echo.
echo 选项:
echo   --api        API 服务器日志
echo   --postgres   数据库日志
echo   --redis      缓存日志
echo   --rsshub     RSSHub 日志
echo   --follow     实时跟踪（按 Ctrl+C 退出）
echo   --lines N    显示行数（默认 100）
echo.
echo 不带参数: 显示所有服务最近 100 行日志
pause
exit /b 0

:run
if not "!SERVICE!"=="" (
    docker compose -f "%COMPOSE_FILE%" logs !SERVICE! --tail !LINES! !FOLLOW!
) else (
    docker compose -f "%COMPOSE_FILE%" logs --tail !LINES! !FOLLOW!
)
if "!FOLLOW!"=="" pause
