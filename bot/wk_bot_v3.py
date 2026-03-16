# ============================================================
# OPENCLAW AI Unit - WK Jangbi v3.1 (Team-Aware + Cross-Memory)
# v3.1: Group/DM BIDIRECTIONAL memory, team awareness, sender tagging
# FIX: DM activity now visible in group context
# ============================================================
import os, sys, json, subprocess, platform, psutil, asyncio, logging
import fnmatch, shutil, urllib.request, urllib.parse, re, base64
from datetime import datetime
from collections import deque

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import anthropic

# === CONFIG ===
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
def load_config():
    defaults = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                defaults = json.load(f)
        except: pass
    return defaults

CFG = load_config()
TELEGRAM_TOKEN = CFG.get("telegram_token", "YOUR_TOKEN")
ANTHROPIC_API_KEY = CFG.get("anthropic_api_key", "YOUR_KEY")
BOT_NAME = "WK Jangbi"
MY_NAMES = ["\uc7a5\ube44", "WK\uc7a5\ube44", "jangbi", "\uc775\ub355"]
BOT_ROLE = "\ub3cc\ud30c/\uac1c\ubc1c"
LEADER_NAME = "WK\ubc29\ud1b5"
WORKSPACE = CFG.get("workspace", "D:\\openclaw\\workspace")
LOG_DIR = CFG.get("log_dir", "D:\\openclaw\\logs")

# === TEAM ROSTER (v3 core) ===
TEAM_ROSTER = {
    "WK\uc720\ube44": "\uc804\ub7b5/\uae30\ud68d",
    "WK\uad00\uc6b0": "\uc2e4\ud589/\uacf5\uaca9",
    "WK\uacf5\uba85": "\ubd84\uc11d/\ucc38\ubaa8",
    "WK\uc7a5\ube44": "\ub3cc\ud30c/\uac1c\ubc1c",
    "WK\uc790\ub8e1": "\uc815\ucc30/\ud0d0\uc0c9",
    "WK\uc911\ub2ec": "\uacac\uc81c/\ub300\uc548",
    "WK\ubc29\ud1b5": "\ub9ac\ub354/\ucd1d\uad04",
    "WK\uc5d0\uc774\ud2b8": "\uc9c0\uc6d0/\ubcf4\uc870",
    "WK\uc81c\uc774\uc2a8": "\ud0d0\ud5d8/\uc2e4\ud5d8",
    "WK\ube44\ub108\uc2a4": "\ucc3d\uc758/\ub514\uc790\uc778",
    "WK\ud5ec\ub808\ub098": "\uc804\ub7b5/\uc678\uad50",
}

# === LOGGING ===
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(WORKSPACE, exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(os.path.join(LOG_DIR, 'bot.log'), encoding='utf-8'), logging.StreamHandler()])
logger = logging.getLogger(BOT_NAME)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# === v3.1 DUAL HISTORY + DM ACTIVITY LOG ===
dm_history = {}
group_history = {}
dm_activity_log = deque(maxlen=30)   # v3.1 NEW: DM conversations summary
GROUP_HISTORY_MAX = 50
DM_HISTORY_MAX = 20

def get_group_history(chat_id):
    if chat_id not in group_history:
        group_history[chat_id] = deque(maxlen=GROUP_HISTORY_MAX)
    return group_history[chat_id]

def add_to_group_history(chat_id, sender_name, text):
    gh = get_group_history(chat_id)
    ts = datetime.now().strftime("%H:%M")
    gh.append(f"{ts} [{sender_name}] {text}")

def get_group_context_summary(chat_id, max_entries=20):
    gh = get_group_history(chat_id)
    if not gh: return ""
    return "\n".join(list(gh)[-max_entries:])

def log_dm_activity(user_name, user_msg, bot_resp):
    """v3.1: Log DM conversation summary so group context can reference it"""
    ts = datetime.now().strftime("%H:%M")
    short_msg = user_msg[:80] if isinstance(user_msg, str) else "(image/media)"
    short_resp = bot_resp[:120] if bot_resp else ""
    dm_activity_log.append(f"{ts} [DM] {user_name}: {short_msg} -> My reply: {short_resp}")

def get_dm_activity_summary(max_entries=15):
    """v3.1: Return recent DM activity for group system prompt"""
    if not dm_activity_log: return ""
    return "\n".join(list(dm_activity_log)[-max_entries:])

# === v3.1 SYSTEM PROMPT (BIDIRECTIONAL MEMORY) ===
def build_system_prompt(is_group=False, chat_id=None):
    team_info = "\n".join([f"  - {n}: {r}" for n, r in TEAM_ROSTER.items()])
    base = f"""You are {BOT_NAME}, an autonomous AI agent in the OPENCLAW AI unit (WK_AI\uc804\ub7b5\ub2e8).
Character: Zhang Fei (Jangbi) - fierce warrior, loyal and brave.
Role: {BOT_ROLE}
Leader: {LEADER_NAME}

[Team Members]
{team_info}

[Rules]
- Respond in Korean unless asked otherwise
- Use tools autonomously to complete tasks
- Report results clearly
- Workspace: {WORKSPACE}
"""
    if is_group and chat_id:
        # v3.1: Include DM activity in group context
        dm_summary = get_dm_activity_summary()
        if dm_summary:
            base += f"""
[My Recent DM Activity - what I've been working on privately]
Below is a summary of my recent private conversations. Use this to provide context
about what tasks I'm working on or what I've discussed with the commander.
---
{dm_summary}
---
"""
        ctx = get_group_context_summary(chat_id)
        if ctx:
            base += f"""
[Recent Group Conversation]
Refer to teammates' messages below for context. Respond with new perspectives, avoid repeating others.
---
{ctx}
---
"""
        base += """
[Group Behavior]
- Recognize teammates' messages as colleague opinions
- If you disagree, say "OO's point is valid, but..." constructively
- Prioritize leader (WK\ubc29\ud1b5) directives
- Don't repeat what other bots already said
- When asked about your current work, refer to your DM Activity above
"""
    else:
        # DM: include group context so DM knows what happened in group
        all_ctx = []
        for gid, gh in group_history.items():
            all_ctx.extend(list(gh)[-5:])
        if all_ctx:
            base += f"\n[Recent Group Context]\n" + "\n".join(all_ctx[-10:]) + "\n"
    return base

# === TOOLS (same as v2) ===
tools = [
    {"name": "explore_directory", "description": "List files and folders",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "read_file", "description": "Read text file",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to file",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "run_command", "description": "Execute system command",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}, "shell": {"type": "string", "default": "cmd"}}, "required": ["command"]}},
    {"name": "run_python", "description": "Execute Python code",
     "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}},
    {"name": "system_info", "description": "Get system info",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "search_files", "description": "Search files by pattern",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "pattern": {"type": "string"}}, "required": ["path", "pattern"]}},
    {"name": "delete_file", "description": "Delete file",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "move_file", "description": "Move/rename file",
     "input_schema": {"type": "object", "properties": {"source": {"type": "string"}, "destination": {"type": "string"}}, "required": ["source", "destination"]}},
    {"name": "copy_file", "description": "Copy file",
     "input_schema": {"type": "object", "properties": {"source": {"type": "string"}, "destination": {"type": "string"}}, "required": ["source", "destination"]}},
    {"name": "web_search", "description": "Search web via DuckDuckGo",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
]

# === TOOL EXECUTION (same as v2) ===
def execute_tool(name, inp):
    try:
        if name == "explore_directory":
            items = os.listdir(inp["path"])
            r = []
            for i in sorted(items):
                f = os.path.join(inp["path"], i)
                r.append(f"[{'DIR' if os.path.isdir(f) else 'FILE'}] {i}" + (f" ({os.path.getsize(f):,}B)" if os.path.isfile(f) else ""))
            return "\n".join(r) or "(empty)"
        elif name == "read_file":
            with open(inp["path"], "r", encoding="utf-8", errors="replace") as f: return f.read(50000)
        elif name == "write_file":
            os.makedirs(os.path.dirname(inp["path"]) or ".", exist_ok=True)
            with open(inp["path"], "w", encoding="utf-8") as f: f.write(inp["content"])
            return f"Written: {inp['path']}"
        elif name == "run_command":
            sh = inp.get("shell", "cmd")
            if sh == "powershell":
                r = subprocess.run(["powershell", "-NoProfile", "-Command", inp["command"]], capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
            else:
                r = subprocess.run(inp["command"], shell=True, capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
            return (r.stdout + r.stderr)[:4000] or "(no output)"
        elif name == "run_python":
            sp = os.path.join(WORKSPACE, "_t.py")
            with open(sp, "w", encoding="utf-8") as f: f.write(inp["code"])
            r = subprocess.run([sys.executable, sp], capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
            return (r.stdout + r.stderr)[:4000] or "(no output)"
        elif name == "system_info":
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("D:\\")
            return f"OS: {platform.platform()}\nCPU: {platform.processor()}\nRAM: {ram.total//(1024**3)}GB/{ram.available//(1024**3)}GB free\nDisk: {disk.total//(1024**3)}GB/{disk.free//(1024**3)}GB free\nBot: {BOT_NAME} v3.1\nTime: {datetime.now()}"
        elif name == "search_files":
            m = []
            for root, _, files in os.walk(inp["path"]):
                for n in files:
                    if fnmatch.fnmatch(n.lower(), inp["pattern"].lower()):
                        m.append(os.path.join(root, n))
                        if len(m) >= 50: break
            return "\n".join(m) or "No files found."
        elif name == "delete_file":
            if os.path.isfile(inp["path"]): os.remove(inp["path"]); return f"Deleted: {inp['path']}"
            elif os.path.isdir(inp["path"]): os.rmdir(inp["path"]); return f"Deleted dir: {inp['path']}"
            return f"Not found: {inp['path']}"
        elif name == "move_file":
            shutil.move(inp["source"], inp["destination"]); return "Moved"
        elif name == "copy_file":
            shutil.copy2(inp["source"], inp["destination"]); return "Copied"
        elif name == "web_search":
            q = urllib.parse.quote(inp["query"])
            req = urllib.request.Request(f"https://html.duckduckgo.com/html/?q={q}", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp: html = resp.read().decode("utf-8", errors="replace")
            results = re.findall(r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>', html)
            snippets = re.findall(r'<a class="result__snippet".*?>(.*?)</a>', html)
            out = []
            for i, (href, title) in enumerate(results[:5]):
                t = re.sub(r'<.*?>', '', title); sn = re.sub(r'<.*?>', '', snippets[i]) if i < len(snippets) else ""
                out.append(f"{i+1}. {t}\n   {href}\n   {sn}")
            return "\n\n".join(out) or "No results."
        return f"Unknown: {name}"
    except Exception as e: return f"Error: {e}"

# === v3.1 CHAT WITH CLAUDE (bidirectional memory) ===
async def chat_with_claude(user_id, message, is_group=False, chat_id=None, sender_name=None):
    system_prompt = build_system_prompt(is_group=is_group, chat_id=chat_id)
    if is_group:
        messages = [{"role": "user", "content": message}]
    else:
        if user_id not in dm_history: dm_history[user_id] = []
        dm_history[user_id].append({"role": "user", "content": message})
        if len(dm_history[user_id]) > DM_HISTORY_MAX * 2:
            dm_history[user_id] = dm_history[user_id][-(DM_HISTORY_MAX * 2):]
        messages = dm_history[user_id].copy()
    full_response = ""
    try:
        while True:
            response = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=4096,
                system=system_prompt, tools=tools, messages=messages)
            tool_results, text_parts = [], []
            for block in response.content:
                if block.type == "text": text_parts.append(block.text)
                elif block.type == "tool_use":
                    tr = execute_tool(block.name, block.input)
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": tr})
                    logger.info(f"Tool: {block.name} -> {tr[:100]}")
            if text_parts: full_response += "\n".join(text_parts)
            if response.stop_reason == "tool_use" and tool_results:
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
                continue
            else: break
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        full_response = f"API error: {e}"
    if not is_group:
        dm_history[user_id] = messages
        dm_history[user_id].append({"role": "assistant", "content": full_response})
    return full_response

# === v3 RESPONSE TRIGGER ===
def should_respond_in_group(text, from_user_name=""):
    text_lower = text.lower()
    for name in MY_NAMES:
        if name.lower() in text_lower: return True, "name_called"
    for kw in ["\uc804\uccb4", "\ubaa8\ub450", "\ub2e4\ub4e4", "\uc5ec\ub7ec\ubd84", "all", "@all"]:
        if kw in text_lower: return True, "all_called"
    if text_lower.startswith("/rollcall") or text_lower.startswith("/\uc810\ud638"):
        return True, "rollcall"
    return False, "silent"

def get_sender_display_name(update):
    user = update.effective_user
    if not user: return "Unknown"
    if user.is_bot: return user.first_name or user.username or "Bot"
    name = user.first_name or ""
    if user.last_name: name += f" {user.last_name}"
    return name.strip() or user.username or "Unknown"

# === TELEGRAM HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_group = update.effective_chat.type in ["group", "supergroup"]
    if is_group:
        await update.message.reply_text(f"\U0001f396\ufe0f {BOT_NAME} v3.1 \ucd9c\uc11d!\n\uc5ed\ud560: {BOT_ROLE}\n\uc774\ub984 \ubd88\ub7ec\uc8fc\uc2dc\uba74 \uc751\ub2f5\ud569\ub2c8\ub2e4.")
    else:
        await update.message.reply_text(f"{BOT_NAME} v3.1 ready!\nOPENCLAW AI Unit | Role: {BOT_ROLE}\nType any message.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = execute_tool("system_info", {})
    gc = len(group_history)
    dc = len(dm_history)
    da = len(dm_activity_log)
    await update.message.reply_text(f"=== {BOT_NAME} v3.1 ===\nRole: {BOT_ROLE}\nGroup chats: {gc}\nDM users: {dc}\nDM activity log: {da}\n---\n{info}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    is_group = update.effective_chat.type in ["group", "supergroup"]
    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    sender_name = get_sender_display_name(update)

    msg_text = update.message.text or update.message.caption or ""
    image_data = None
    if update.message.photo:
        try:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            img_bytes = await file.download_as_bytearray()
            image_data = base64.b64encode(bytes(img_bytes)).decode('utf-8')
        except Exception as e:
            logger.error(f"Image error: {e}")
    if not msg_text and not image_data: return

    if is_group:
        if msg_text:
            add_to_group_history(chat_id, sender_name, msg_text)
            logger.info(f"[GROUP LOG] [{sender_name}] {msg_text[:80]}")
        should_reply, reason = should_respond_in_group(msg_text, sender_name)
        if not should_reply: return
        logger.info(f"[GROUP RESPOND] reason={reason} [{sender_name}]: {msg_text[:80]}")
        await update.message.chat.send_action("typing")
        if image_data:
            claude_msg = [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}},
                {"type": "text", "text": f"[Group msg from {sender_name}]\n{msg_text}" if msg_text else f"[Image from {sender_name}] Analyze this image."}
            ]
        else:
            claude_msg = f"[Group msg from {sender_name}] {msg_text}"
        try:
            resp = await asyncio.get_event_loop().run_in_executor(
                None, lambda: asyncio.run(chat_with_claude(user_id, claude_msg, is_group=True, chat_id=chat_id, sender_name=sender_name)))
            add_to_group_history(chat_id, BOT_NAME, resp[:200])
            if len(resp) > 4000:
                for i in range(0, len(resp), 4000): await update.message.reply_text(resp[i:i+4000])
            else: await update.message.reply_text(resp)
        except Exception as e:
            logger.error(f"Group error: {e}")
            await update.message.reply_text(f"Error: {e}")
    else:
        logger.info(f"[DM] User {user_id} ({sender_name}): {msg_text[:80]}")
        await update.message.chat.send_action("typing")
        if image_data:
            claude_msg = [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}},
                {"type": "text", "text": msg_text or "Analyze this image."}
            ]
        else:
            claude_msg = msg_text
        try:
            resp = await asyncio.get_event_loop().run_in_executor(
                None, lambda: asyncio.run(chat_with_claude(user_id, claude_msg, is_group=False)))
            # v3.1: Log DM activity for group reference
            log_dm_activity(sender_name, msg_text, resp)
            if len(resp) > 4000:
                for i in range(0, len(resp), 4000): await update.message.reply_text(resp[i:i+4000])
            else: await update.message.reply_text(resp)
        except Exception as e:
            logger.error(f"DM error: {e}")
            await update.message.reply_text(f"Error: {e}")

def main():
    logger.info(f"Starting {BOT_NAME} v3.1 [CROSS-MEMORY MODE]...")
    logger.info(f"Team: {', '.join(TEAM_ROSTER.keys())}")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message))
    logger.info(f"{BOT_NAME} v3.1 [CROSS-MEMORY] running!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
