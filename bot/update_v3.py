"""
OPENCLAW v3.1 Auto-Update Script
Usage: Each bot runs this via run_command tool
  python update_v3.py
What it does:
  1. Downloads wk_bot_v3.py from GitHub raw
  2. Backs up current bot code
  3. Replaces with new code
  4. Reports result (bot needs manual restart via WATCHDOG)
"""
import os, sys, urllib.request, shutil, json
from datetime import datetime

# Auto-detect paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BOT_DIR = os.path.join(SCRIPT_DIR, "bot") if os.path.isdir(os.path.join(SCRIPT_DIR, "bot")) else SCRIPT_DIR
BACKUP_DIR = os.path.join(SCRIPT_DIR, "backup")
os.makedirs(BACKUP_DIR, exist_ok=True)

# GitHub raw URL for the template
GITHUB_RAW = "https://raw.githubusercontent.com/BTM-WK/openclaw_ai/master/bot/wk_bot_v3.py"

TARGET_FILE = os.path.join(BOT_DIR, "wk_bot_v3.py")
OLD_BOT = os.path.join(BOT_DIR, "wk_bot.py")

def update():
    print(f"=== OPENCLAW v3.1 Auto-Update ===")
    print(f"Target: {TARGET_FILE}")
    print(f"Source: {GITHUB_RAW}")
    
    # Step 1: Download from GitHub
    print("\n[1/4] Downloading from GitHub...")
    try:
        req = urllib.request.Request(GITHUB_RAW, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            new_code = resp.read().decode("utf-8")
        print(f"  Downloaded: {len(new_code)} chars, {new_code.count(chr(10))} lines")
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    
    # Step 2: Backup existing
    print("\n[2/4] Backing up current code...")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if os.path.exists(TARGET_FILE):
        backup_path = os.path.join(BACKUP_DIR, f"wk_bot_v3_backup_{ts}.py")
        shutil.copy2(TARGET_FILE, backup_path)
        print(f"  Backed up to: {backup_path}")
    elif os.path.exists(OLD_BOT):
        backup_path = os.path.join(BACKUP_DIR, f"wk_bot_backup_{ts}.py")
        shutil.copy2(OLD_BOT, backup_path)
        print(f"  Old bot backed up to: {backup_path}")
    else:
        print("  No existing bot file to backup (fresh install)")
    
    # Step 3: Write new code
    print("\n[3/4] Writing new code...")
    try:
        with open(TARGET_FILE, "w", encoding="utf-8") as f:
            f.write(new_code)
        print(f"  Written: {TARGET_FILE}")
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    
    # Step 4: Verify config.json exists
    print("\n[4/4] Checking config.json...")
    config_path = os.path.join(BOT_DIR, "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        needed = ["telegram_token", "anthropic_api_key", "bot_name", "my_names", "bot_role"]
        missing = [k for k in needed if k not in cfg]
        if missing:
            print(f"  WARNING: config.json missing keys: {missing}")
            print(f"  Add these to config.json before running the bot!")
        else:
            print(f"  config.json OK - bot_name: {cfg.get('bot_name')}")
    else:
        print(f"  WARNING: config.json not found at {config_path}")
        print(f"  Create config.json with: telegram_token, anthropic_api_key, bot_name, my_names, bot_role")
    
    print(f"\n=== UPDATE COMPLETE ===")
    print(f"Next: Restart bot (WATCHDOG will auto-restart, or run manually)")
    return True

if __name__ == "__main__":
    success = update()
    sys.exit(0 if success else 1)
