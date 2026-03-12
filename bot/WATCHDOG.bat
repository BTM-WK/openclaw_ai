@echo off
title OPENCLAW v6 Watchdog - WK Bangtong
:LOOP
echo [%date% %time%] Starting WK Bangtong v6...
taskkill /f /fi "WINDOWTITLE eq wk_bot*" >nul 2>&1
timeout /t 3 /nobreak >nul
C:\Python311\python.exe C:\openclaw\bot\wk_bot_v6.py
echo [%date% %time%] Bot stopped. Restart in 10s...
timeout /t 10 /nobreak
goto LOOP
