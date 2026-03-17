@echo off
title OPENCLAW v3.1 Watchdog - WK Yubi (Sonnet 4.6)
:LOOP
echo [%date% %time%] Starting WK Yubi v3.1...
taskkill /f /fi "WINDOWTITLE eq wk_bot*" >nul 2>&1
timeout /t 3 /nobreak >nul
"C:\Users\yso\AppData\Local\Programs\Python\Python311\python.exe" D:\openclaw\bot\wk_bot_v3.py
echo [%date% %time%] Restart in 10s...
timeout /t 10 /nobreak
goto LOOP
