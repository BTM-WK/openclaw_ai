@echo off
chcp 65001 >nul
title OPENCLAW v6 Installer
echo.
echo  ============================================
echo    OPENCLAW v6 Autonomous Agent Installer
echo  ============================================
echo.
python "%~dp0install_v6.py"
echo.
pause
