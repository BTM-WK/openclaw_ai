# ============================================================
# OPENCLAW AI v3.1 - DEPLOYMENT GUIDE
# ============================================================
# 
# 핵심 원칙: wk_bot_v3.py 코드는 모든 PC에서 동일.
#            차이점은 config.json에만 있음.
#
# ============================================================
# PC별 드라이브 맵
# ============================================================
#
# BOT         | PC           | DRIVE | PATH
# WK유비      | 회사PC       | D:    | D:\openclaw
# WK관우      | 4호기        | C:    | C:\openclaw
# WK공명      | 1호기        | (확인) | ?:\openclaw
# WK장비      | 개인노트북   | D:    | D:\openclaw   ★ v3.1 배포완료
# WK자룡      | 10호기       | C:    | C:\openclaw
# WK중달      | 9호기        | C:    | C:\openclaw
# WK방통      | 집PC         | C:    | C:\openclaw
# WK에이트    | 8호기        | C:    | C:\openclaw
# WK제이슨    | 7호기        | (확인) | ?:\openclaw
# WK비너스    | 5호기        | (확인) | ?:\openclaw   미배치
# WK헬레나    | 2호기        | (확인) | ?:\openclaw   미배치
#
# ============================================================
# 배포 절차 (PC당 5분)
# ============================================================
#
# 1. GitHub에서 코드 가져오기
#    cd C:\openclaw  (또는 D:\openclaw)
#    git clone https://github.com/BTM-WK/openclaw_ai.git temp_repo
#    copy temp_repo\bot\wk_bot_v3.py bot\wk_bot_v3.py
#    rmdir /s /q temp_repo
#
#    또는 이미 git init된 PC라면:
#    git pull origin master
#
# 2. config.json 수정 (bot/ 폴더 안에)
#    - telegram_token: 해당 봇의 텔레그램 토큰
#    - anthropic_api_key: 공유 API 키
#    - bot_name: "WK관우" 등
#    - my_names: ["관우", "WK관우", "guan_yu"]
#    - bot_role: "실행/공격" 등
#    - workspace: "C:\\openclaw\\workspace" (드라이브에 맞게!)
#    - log_dir: "C:\\openclaw\\logs" (드라이브에 맞게!)
#
# 3. Python 패키지 확인
#    pip install python-telegram-bot anthropic psutil
#    (관리자 CMD에서 실행하되, python 경로 확인!)
#
# 4. 실행 테스트
#    python bot\wk_bot_v3.py
#
# 5. WATCHDOG.bat 업데이트
#    Python 경로와 wk_bot_v3.py 경로를 맞추기
#
# ============================================================
# config.json 예시 (C 드라이브 PC용)
# ============================================================
#
# {
#   "telegram_token": "BOT_TOKEN_HERE",
#   "anthropic_api_key": "sk-ant-api03-...",
#   "bot_name": "WK관우",
#   "my_names": ["관우", "WK관우", "guan_yu", "운장"],
#   "bot_role": "실행/공격",
#   "workspace": "C:\\openclaw\\workspace",
#   "log_dir": "C:\\openclaw\\logs"
# }
#
# ============================================================
# config.json 예시 (D 드라이브 PC용)
# ============================================================
#
# {
#   "telegram_token": "BOT_TOKEN_HERE",
#   "anthropic_api_key": "sk-ant-api03-...",
#   "bot_name": "WK유비",
#   "my_names": ["유비", "WK유비", "liu_bei", "현덕"],
#   "bot_role": "전략/기획",
#   "workspace": "D:\\openclaw\\workspace",
#   "log_dir": "D:\\openclaw\\logs"
# }
#
# ============================================================
# WATCHDOG.bat 예시 (Python 경로 확인 필수!)
# ============================================================
#
# @echo off
# title OPENCLAW v3.1 Watchdog - [봇이름]
# :LOOP
# echo [%date% %time%] Starting bot v3.1...
# taskkill /f /fi "WINDOWTITLE eq wk_bot*" >nul 2>&1
# timeout /t 3 /nobreak >nul
# [PYTHON경로]\python.exe [드라이브]:\openclaw\bot\wk_bot_v3.py
# echo [%date% %time%] Restart in 10s...
# timeout /t 10 /nobreak
# goto LOOP
#
# ============================================================
# Git 관련 주의사항
# ============================================================
#
# - config.json은 .gitignore에 포함 (API 키 보호)
# - wk_bot_v3.py만 git으로 공유
# - 각 PC에서 git pull 시 config.json은 영향 없음
# - C: PC와 D: PC 모두 같은 repo에서 코드만 가져감
# - workspace/, logs/ 도 .gitignore 처리
