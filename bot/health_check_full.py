import os, subprocess, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("=" * 50)
print("유비 PC 24시간 운영 점검")
print("=" * 50)

# 1. 절전
print("\n[1] SLEEP:")
r = subprocess.run('powercfg /q SCHEME_CURRENT SUB_SLEEP STANDBYIDLE', capture_output=True, text=True, shell=True)
for line in r.stdout.split('\n'):
    if '0x000000' in line:
        val = int(line.strip().split(':')[-1].strip(), 16)
        print(f"  {'Never sleep [OK]' if val == 0 else f'Sleep after {val}s [BAD]'}")

# 2. 덮개
print("\n[2] LID ACTION:")
r = subprocess.run('powercfg /q SCHEME_CURRENT SUB_BUTTONS 5ca83367-6e45-459f-a27b-476b1d01c936', capture_output=True, text=True, shell=True)
found = False
for line in r.stdout.split('\n'):
    if '0x000000' in line:
        val = int(line.strip().split(':')[-1].strip(), 16)
        action = {0:'Do nothing [OK]', 1:'Sleep [BAD]', 2:'Hibernate [BAD]', 3:'Shutdown [BAD]'}.get(val, f'Unknown({val})')
        print(f"  {action}")
        found = True
if not found:
    print("  LID setting not found (may be hidden or desktop PC)")

# 3. Startup
print("\n[3] STARTUP:")
startup = os.path.join(os.environ['APPDATA'], r'Microsoft\Windows\Start Menu\Programs\Startup')
for f in os.listdir(startup):
    fpath = os.path.join(startup, f)
    print(f"  {f}")
    if f.endswith('.bat'):
        with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
            content = fh.read().strip()
            for line in content.split('\n'):
                print(f"    > {line.strip()}")

# 4. OpenClaw gateway 실행 여부
print("\n[4] OPENCLAW GATEWAY:")
import psutil
found_gw = False
for p in psutil.process_iter(['pid','name','cmdline']):
    try:
        cmd = ' '.join(p.info['cmdline'] or [])
        if 'openclaw' in cmd.lower() and ('gateway' in cmd.lower() or '18789' in cmd):
            print(f"  PID {p.info['pid']}: RUNNING [OK]")
            found_gw = True
    except:
        pass
if not found_gw:
    print("  NOT RUNNING [BAD]")

# 5. wk_bot 충돌 체크
print("\n[5] WK_BOT CONFLICT CHECK:")
found_bot = False
for p in psutil.process_iter(['pid','name','cmdline']):
    try:
        cmd = ' '.join(p.info['cmdline'] or [])
        if 'wk_bot' in cmd:
            print(f"  PID {p.info['pid']}: wk_bot RUNNING [CONFLICT!]")
            found_bot = True
    except:
        pass
if not found_bot:
    print("  No wk_bot processes [OK]")

print("\n" + "=" * 50)
