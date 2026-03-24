@echo off
title OPENCLAW Gateway Watchdog - WK방통
:LOOP
echo [%date% %time%] Starting OpenClaw Gateway for WK방통...
openclaw gateway --port 18789
echo [%date% %time%] Gateway stopped. Restart in 10s...
timeout /t 10 /nobreak
goto LOOP
