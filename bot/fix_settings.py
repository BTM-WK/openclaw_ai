import os, subprocess, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("FIXING YuBi PC settings...")

# 1. Fix sleep
subprocess.run('powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_SLEEP STANDBYIDLE 0', shell=True)
subprocess.run('powercfg /SETDCVALUEINDEX SCHEME_CURRENT SUB_SLEEP STANDBYIDLE 0', shell=True)
subprocess.run('powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_SLEEP HYBRIDSLEEP 0', shell=True)
subprocess.run('powercfg /SETDCVALUEINDEX SCHEME_CURRENT SUB_SLEEP HYBRIDSLEEP 0', shell=True)
subprocess.run('powercfg /SETDCVALUEINDEX SCHEME_CURRENT SUB_SLEEP HIBERNATEIDLE 0', shell=True)
print("[1] Sleep: FIXED")

# 2. Fix lid (unhide + set to do nothing)
subprocess.run('reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Power\\PowerSettings\\4f971e89-eebd-4455-a8de-9e59040e7347\\5ca83367-6e45-459f-a27b-476b1d01c936" /v Attributes /t REG_DWORD /d 2 /f', shell=True, capture_output=True)
subprocess.run('powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_BUTTONS LIDACTION 0', shell=True)
subprocess.run('powercfg /SETDCVALUEINDEX SCHEME_CURRENT SUB_BUTTONS LIDACTION 0', shell=True)
subprocess.run('powercfg /SETACTIVE SCHEME_CURRENT', shell=True)
print("[2] Lid action: FIXED")

# 3. Fix Startup - replace old python bot with OpenClaw gateway
startup = os.path.join(os.environ['APPDATA'], r'Microsoft\Windows\Start Menu\Programs\Startup')

# Remove old autostart
old_files = [f for f in os.listdir(startup) if 'autostart' in f.lower() and f.endswith('.bat')]
for f in old_files:
    fpath = os.path.join(startup, f)
    os.remove(fpath)
    print(f"[3] Removed old: {f}")

# Write new OpenClaw gateway autostart
new_bat = os.path.join(startup, 'openclaw_gateway.bat')
with open(new_bat, 'w') as f:
    f.write('@echo off\n')
    f.write('title OpenClaw Gateway - WK Yubi\n')
    f.write('timeout /t 30 /nobreak >nul\n')
    f.write('openclaw gateway --port 18789\n')
print(f"[3] Created: openclaw_gateway.bat")

print("\nALL FIXES APPLIED")
