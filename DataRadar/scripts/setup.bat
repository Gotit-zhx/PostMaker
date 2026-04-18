@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM DataRadar - Windows Setup Script (uv)
REM Usage: scripts\setup.bat

echo.
echo ==================================================
echo    DataRadar Setup (Windows)
echo ==================================================
echo.

REM -- Navigate to project root --
cd /d "%~dp0\.."
set "PROJECT_DIR=%cd%"
echo [INFO] Project dir: %PROJECT_DIR%

REM =================================================
REM  1. Check / Install uv
REM =================================================
echo [INFO] Checking uv...

uv --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=*" %%v in ('uv --version 2^>^&1') do echo [OK] %%v
    goto :uv_ready
)

echo [INFO] uv not found, installing...
powershell -ExecutionPolicy ByPass -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex" 2>nul
if !errorlevel! neq 0 (
    echo [ERROR] uv installation failed.
    echo         Install manually: https://docs.astral.sh/uv/getting-started/installation/
    pause
    exit /b 1
)

REM Refresh PATH after install
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
uv --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] uv installed but not in PATH. Restart terminal and retry.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('uv --version 2^>^&1') do echo [OK] %%v installed

:uv_ready

REM =================================================
REM  2. Install Python 3.12+ via uv
REM =================================================
echo [INFO] Ensuring Python ^>= 3.12...
uv python install 3.12 >nul 2>&1
echo [OK] Python ready

REM =================================================
REM  3. Sync dependencies
REM =================================================
echo [INFO] Syncing dependencies (uv sync)...
uv sync --all-extras
if !errorlevel! neq 0 (
    echo [ERROR] uv sync failed
    pause
    exit /b 1
)
echo [OK] Dependencies installed

REM =================================================
REM  4. Install Playwright browser
REM =================================================
echo [INFO] Installing Playwright Chromium...
uv run playwright install chromium >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] Playwright Chromium installed
) else (
    echo [WARN] Playwright install failed. Web scraping may not work.
)

REM =================================================
REM  5. Docker infrastructure
REM =================================================
set "DOCKER_AVAILABLE=false"

docker --version >nul 2>&1
if !errorlevel! neq 0 goto :no_docker

docker info >nul 2>&1
if !errorlevel! neq 0 (
    echo [WARN] Docker installed but not running. Start Docker Desktop first.
    goto :after_docker
)

set "DOCKER_AVAILABLE=true"
echo [OK] Docker available
echo [INFO] Starting Docker infrastructure...

if not exist "docker\.env" (
    copy "docker\.env.example" "docker\.env" >nul
    echo [INFO] Created docker\.env from template
) else (
    echo [INFO] docker\.env exists, skipping
)

pushd docker
docker compose up postgres redis rsshub -d 2>nul
if !errorlevel! neq 0 (
    docker-compose up postgres redis rsshub -d 2>nul
)
popd

echo [INFO] Waiting for services...
timeout /t 5 /nobreak >nul
echo [OK] Docker services started
goto :after_docker

:no_docker
echo [WARN] Docker not installed, skipping infrastructure
echo        Knowledge base requires Docker (PostgreSQL + Redis + RSSHub)
echo        CLI-only mode available (RSS collect, SQLite storage)

:after_docker

REM =================================================
REM  6. Verify installation
REM =================================================
echo.
echo [INFO] Verifying installation...
uv run python -m dataradar status
if !errorlevel! neq 0 (
    echo [WARN] dataradar status failed. Check your config.
)

REM =================================================
REM  7. Done
REM =================================================
echo.
echo ==================================================
echo    Setup complete!
echo ==================================================
echo.
echo   Usage:
echo     uv run dataradar status          System status
echo     uv run dataradar fetch           Run data collection
echo     uv run dataradar rss --days 1    Query recent data
echo.

if "!DOCKER_AVAILABLE!"=="true" (
    echo   Docker:
    echo     cd docker ^&^& docker compose up -d       Start all
    echo     cd docker ^&^& docker compose down        Stop all
    echo     cd docker ^&^& docker compose ps          Check status
    echo.
)

echo   Config: edit config\config.yaml
echo     ai.api_key   - Your AI API key
echo     ai.model     - Model name (e.g. openai/gpt-4o)
echo     ai.api_base  - Custom endpoint (optional)
echo.
echo   Docs: see README.md
echo.
pause
