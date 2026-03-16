@echo off
title OPENCLAW v3 Watchdog - WK Jangbi
:LOOP
echo [%date% %time%] Starting WK Jangbi v3...
taskkill /f /fi "WINDOWTITLE eq wk_bot*" >nul 2>&1
timeout /t 3 /nobreak >nul
C:\Python313\python.exe D:\openclaw\bot\wk_bot_v3.py
echo [%date% %time%] Bot stopped. Restart in 10s...
timeout /t 10 /nobreak
goto LOOP
