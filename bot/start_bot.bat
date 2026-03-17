@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo WK관우 v5.0 starting...
cd /d D:\openclaw\bot
python claude_bot_v5.py
pause
