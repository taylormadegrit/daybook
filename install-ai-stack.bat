@echo off
setlocal enabledelayedexpansion
title Daybook 1-Click AI Stack Installer

echo ========================================================
echo    Daybook 1-Click AI Stack Installer
echo    Installs: Node.js LTS, Claude Code CLI, and Ollama
echo ========================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-ai-stack.ps1" %*

set EXITCODE=%ERRORLEVEL%
if %EXITCODE% NEQ 0 (
    echo.
    echo [ERROR] AI Stack installation encountered code %EXITCODE%.
)

if "%~1"=="" (
    echo.
    echo Press any key to exit...
    pause >nul
)

exit /b %EXITCODE%
