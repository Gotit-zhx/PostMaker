@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM PostMaker 内容生成
REM 用法: 双击运行（默认热门5篇）或 scripts\generate.bat [参数]
REM 参数: --trending --topic 主题 --limit N --dry-run --persona ID --refine

cd /d "%~dp0\.."
set "PROJECT_ROOT=%cd%"
set "POSTMAKER_DIR=%PROJECT_ROOT%\PostMaker"
set "ENV_FILE=%PROJECT_ROOT%\DataRadar\docker\.env"

echo.
echo ==================================================
echo    内容生成
echo ==================================================
echo.

REM 检查 API
curl -sf http://localhost:8000/health >nul 2>&1
if !errorlevel! neq 0 (
    echo [错误] DataRadar API 未运行。请先执行: scripts\start.bat
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

REM 检查 AI_API_KEY
if "!AI_API_KEY!"=="" (
    echo [错误] 未设置 AI_API_KEY。请编辑 %ENV_FILE% 填入你的 AI 密钥。
    pause
    exit /b 1
)

pushd "%POSTMAKER_DIR%"

if "%~1"=="" (
    echo [信息] 使用默认参数: --trending --limit 5
    echo [信息] 开始生成内容...
    echo.
    uv run postmaker generate --trending --limit 5
) else (
    echo [信息] 开始生成内容...
    echo.
    uv run postmaker generate %*
)

popd

echo.
echo [成功] 内容生成完成！
echo.
echo   输出目录: %POSTMAKER_DIR%\output\
echo   每篇文章有 .md 和 .html 两种格式
echo.
pause
