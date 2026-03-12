import re
with open(r'C:\openclaw\bot\wk_bot.py', 'r', encoding='utf-8-sig') as f:
    code = f.read()

# Replace hardcoded tokens with config.json loading
old = '''TELEGRAM_TOKEN = "8622440190:AAHKRulYn8gEDCwPoLUqKUSuroqteZp8kJI"
ANTHROPIC_API_KEY = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), encoding="utf-8"))["anthropic_api_key"]'''

new = '''_CFG = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), encoding="utf-8"))
TELEGRAM_TOKEN = _CFG["telegram_token"]
ANTHROPIC_API_KEY = _CFG["anthropic_api_key"]'''

code = code.replace(old, new)
with open(r'C:\openclaw\bot\wk_bot.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Token replaced with config.json")

# Verify no secrets remain
for i, line in enumerate(code.split('\n'), 1):
    if 'sk-ant' in line or ('AAH' in line and 'token' not in line.lower()):
        print(f"WARNING line {i}: {line.strip()[:80]}")
print("CHECK DONE")
