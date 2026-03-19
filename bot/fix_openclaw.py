"""
OPENCLAW 복구 스크립트 v1.0
- wk_bot_v3.py 프로세스 전부 kill
- OpenClaw 토큰을 config.json에서 읽어서 자동 업데이트
- WATCHDOG을 OpenClaw gateway로 변경
- Gateway 시작

사용법: python fix_openclaw.py
"""
import subprocess, json, os, sys, signal, time

print("=" * 50)
print("OPENCLAW RECOVERY SCRIPT v1.0")
print("=" * 50)

# 1. config.json에서 현재 유효 토큰 읽기
config_paths = ['C:/openclaw/bot/config.json', 'D:/openclaw/bot/config.json']
token = None
bot_name = None
for cp in config_paths:
    if os.path.exists(cp):
        with open(cp, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        token = cfg.get('telegram_token', '')
        bot_name = cfg.get('bot_name', 'Unknown')
        print(f"[1] Config found: {cp}")
        print(f"    Bot: {bot_name}")
        print(f"    Token: {token[:20]}...")
        break

if not token:
    print("[ERROR] config.json not found!")
    sys.exit(1)

# 2. wk_bot_v3.py 프로세스 전부 kill
print("\n[2] Killing wk_bot processes...")
try:
    import psutil
    killed = 0
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = ' '.join(p.info['cmdline'] or [])
            if 'wk_bot' in cmd and p.info['pid'] != os.getpid():
                os.kill(p.info['pid'], signal.SIGTERM)
                print(f"    Killed PID {p.info['pid']}")
                killed += 1
        except:
            pass
    print(f"    Total killed: {killed}")
except ImportError:
    print("    psutil not available, using taskkill...")
    os.system('taskkill /f /im python.exe 2>nul')

# 3. OpenClaw 토큰 업데이트
print("\n[3] Updating OpenClaw telegram token...")
result = subprocess.run(
    f'openclaw config set channels.telegram.botToken "{token}"',
    shell=True, capture_output=True, text=True, timeout=15
)
if 'Updated' in result.stdout or 'overwrite' in result.stdout.lower():
    print(f"    Token updated OK")
else:
    print(f"    Result: {result.stdout.strip()}")
    if result.stderr:
        print(f"    Error: {result.stderr.strip()}")

# 4. Gateway 중지 (이전 것)
print("\n[4] Stopping old gateway...")
subprocess.run('openclaw gateway stop', shell=True, capture_output=True, timeout=15)
time.sleep(3)

# 5. 남은 gateway 프로세스 강제 kill
try:
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = ' '.join(p.info['cmdline'] or [])
            if 'openclaw' in cmd.lower() and 'gateway' in cmd.lower() and p.info['pid'] != os.getpid():
                os.kill(p.info['pid'], signal.SIGTERM)
                print(f"    Killed old gateway PID {p.info['pid']}")
        except:
            pass
except:
    pass

print("    Waiting 10s for telegram to release...")
time.sleep(10)

# 6. WATCHDOG 업데이트
print("\n[5] Updating WATCHDOG.bat...")
for bp in ['C:/openclaw/bot/WATCHDOG.bat', 'D:/openclaw/bot/WATCHDOG.bat']:
    if os.path.exists(os.path.dirname(bp)):
        with open(bp, 'w', encoding='utf-8') as f:
            f.write(f"""@echo off
title OPENCLAW Gateway Watchdog - {bot_name}
:LOOP
echo [%date% %time%] Starting OpenClaw Gateway for {bot_name}...
openclaw gateway --port 18789
echo [%date% %time%] Gateway stopped. Restart in 10s...
timeout /t 10 /nobreak
goto LOOP
""")
        print(f"    Written: {bp}")
        break

# 7. Gateway 시작
print("\n[6] Starting OpenClaw gateway...")
print("    Run this manually: openclaw gateway --port 18789")
print("    Or double-click WATCHDOG.bat")

# 8. 토큰 유효성 확인
print("\n[7] Verifying token...")
import urllib.request
try:
    bot_id = token.split(':')[0]
    r = urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
    data = json.loads(r.read().decode())
    if data.get('ok'):
        username = data['result'].get('username', '?')
        print(f"    Token VALID: @{username}")
    else:
        print(f"    Token INVALID - need new token from BotFather!")
except Exception as e:
    print(f"    Token check failed: {e}")
    print(f"    May need new token from BotFather!")

print("\n" + "=" * 50)
print("RECOVERY COMPLETE")
print(f"Next: Run 'openclaw gateway --port 18789' to start {bot_name}")
print("=" * 50)
