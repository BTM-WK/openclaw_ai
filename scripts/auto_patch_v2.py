"""
OPENCLAW Bot Auto-Patcher v2 (Simple)
Copies wk_bot_template_v2.py and replaces TOKEN/NAME/NAMES.
Usage: python auto_patch_v2.py
"""
import os, sys, re, shutil, json
from datetime import datetime

# Find bot file
DRIVES = ["C", "D"]
BOT_FILE = None
for d in DRIVES:
    for fname in ["wk_bot.py", "claude_bot_v5.py"]:
        path = f"{d}:\\openclaw\\bot\\{fname}"
        if os.path.exists(path):
            BOT_FILE = path
            break
    if BOT_FILE: break

if not BOT_FILE:
    print("ERROR: Bot file not found!"); sys.exit(1)

print(f"Found: {BOT_FILE}")

# Read existing code to extract config
with open(BOT_FILE, 'r', encoding='utf-8') as f:
    old = f.read()

# Extract token and name
token = ""
bot_name = ""
# From code
m = re.search(r'TELEGRAM_TOKEN\s*=\s*["\']([^"\']+)', old)
if m: token = m.group(1)
m = re.search(r'BOT_NAME\s*=\s*["\']([^"\']+)', old)
if m: bot_name = m.group(1)
# From config.json
cfg_path = os.path.join(os.path.dirname(BOT_FILE), "config.json")
if os.path.exists(cfg_path):
    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    if not token: token = cfg.get("telegram_token", "")
    if not bot_name: bot_name = cfg.get("bot_name", "")

if not token:
    print("ERROR: No token found!"); sys.exit(1)

print(f"Bot: {bot_name}")
print(f"Token: {token[:20]}...")

# Generate MY_NAMES
my_names = set()
for k in re.findall(r'[가-힣]+', bot_name): my_names.add(k)
for e in re.findall(r'[A-Za-z]+', bot_name):
    if e.upper() != "WK" and len(e) > 1: my_names.add(e.lower())
my_names.add(bot_name)
for k in re.findall(r'[가-힣]+', bot_name): my_names.add(f"WK{k}")
my_names = list(my_names)

# Backup
backup_dir = BOT_FILE[0:2] + "\\openclaw\\backup"
os.makedirs(backup_dir, exist_ok=True)
bk = os.path.join(backup_dir, f"bot_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py")
shutil.copy2(BOT_FILE, bk)
print(f"Backup: {bk}")

# Find template
TEMPLATE = None
for d in DRIVES:
    t = f"{d}:\\openclaw\\scripts\\wk_bot_template_v2.py"
    if os.path.exists(t):
        TEMPLATE = t; break

if not TEMPLATE:
    print("ERROR: Template v2 not found!"); sys.exit(1)

# Read template and replace placeholders
with open(TEMPLATE, 'r', encoding='utf-8') as f:
    tmpl = f.read()

# Detect workspace drive
drive = BOT_FILE[0:2]
tmpl = tmpl.replace('TELEGRAM_TOKEN = "YOUR_TOKEN_HERE"', f'TELEGRAM_TOKEN = "{token}"')
tmpl = tmpl.replace('BOT_NAME = "WK BotName (N)"', f'BOT_NAME = "{bot_name}"')
tmpl = tmpl.replace('MY_NAMES = ["botname", "봇이름"]', f'MY_NAMES = {my_names}')
tmpl = tmpl.replace('WORKSPACE = "C:\\\\openclaw\\\\workspace"', f'WORKSPACE = "{drive}\\\\openclaw\\\\workspace"')
tmpl = tmpl.replace('LOG_DIR = "C:\\\\openclaw\\\\logs"', f'LOG_DIR = "{drive}\\\\openclaw\\\\logs"')

# Write new bot file (always as wk_bot.py)
out_path = os.path.join(os.path.dirname(BOT_FILE), "wk_bot.py")
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(tmpl)

print(f"Patched: {out_path}")
print(f"Names: {my_names}")
print("=== PATCH COMPLETE ===")
print("Restart bot with: WATCHDOG.bat")
