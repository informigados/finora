@echo off
setlocal
title Finora - Release Builder

echo.
echo ==================================================
echo              FINORA - RELEASE BUILDER
echo ==================================================
echo.

if not exist "VERSION" (
    echo [ERROR] VERSION file not found.
    pause
    exit /b 1
)

set /p RELEASE_VERSION=<VERSION
if "%RELEASE_VERSION%"=="" (
    echo [ERROR] VERSION file is empty.
    pause
    exit /b 1
)

echo [INFO] Target version: %RELEASE_VERSION%

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in PATH.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [SETUP] Creating virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [INFO] Activating virtual environment...
call .venv\Scripts\activate
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

echo [INFO] Installing dependencies...
pip install -q -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install project dependencies.
    pause
    exit /b 1
)

pip install -q pyinstaller pyinstaller-hooks-contrib
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install build dependencies.
    pause
    exit /b 1
)

echo [INFO] Running tests...
python -m pytest tests -q
if %errorlevel% neq 0 (
    echo [ERROR] Tests failed. Release canceled.
    pause
    exit /b 1
)

echo [INFO] Building executable and installer...
python create_installer.py
if %errorlevel% neq 0 (
    echo [ERROR] Release build failed.
    pause
    exit /b 1
)

echo.
echo ==================================================
echo [SUCCESS] Release %RELEASE_VERSION% generated.
echo ==================================================
echo Executable: dist\Finora\Finora.exe
echo Installer : dist_setup\Finora_Setup_v%RELEASE_VERSION%.exe
echo.
pause
endlocal
