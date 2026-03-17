@echo off
chcp 65001 >nul
title WK Yubi v6 - First Start

echo ========================================
echo   WK Yubi v6 - First Start
echo ========================================
echo.

echo [1/3] Installing packages...
"C:\Users\yso\AppData\Local\Programs\Python\Python311\python.exe" -m pip install python-telegram-bot anthropic psutil --quiet
echo   Done.
echo.

echo [2/3] Stopping old bot...
taskkill /f /im python.exe >nul 2>&1
timeout /t 3 /nobreak >nul
echo   Done.
echo.

echo [3/3] Starting WK Yubi v6...
echo.
"C:\Users\yso\AppData\Local\Programs\Python\Python311\python.exe" D:\openclaw\bot\wk_bot_v6.py

pause
