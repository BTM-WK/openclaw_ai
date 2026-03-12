# OPENCLAW AI Unit - Standard Bot Template v2.0
# Group-aware + Leader-responsive
# Modify top 3 lines only: TOKEN, BOT_NAME, MY_NAMES

import os, sys, json, subprocess, platform, psutil, asyncio, logging
import fnmatch, shutil, urllib.request, urllib.parse, re
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import anthropic

# === MODIFY THESE 3 LINES PER BOT ===
TELEGRAM_TOKEN = "YOUR_TOKEN_HERE"
BOT_NAME = "WK BotName (N)"
MY_NAMES = ["botname", "봇이름"]
# =====================================

ANTHROPIC_API_KEY = "YOUR_API_KEY_HERE"
LEADER_NAME = "WK방통"
WORKSPACE = "C:\\openclaw\\workspace"
LOG_DIR = "C:\\openclaw\\logs"

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(WORKSPACE, exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(os.path.join(LOG_DIR, 'bot.log'), encoding='utf-8'), logging.StreamHandler()])
logger = logging.getLogger(BOT_NAME)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

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
            os.makedirs(os.path.dirname(inp["path"]), exist_ok=True)
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
            disk = psutil.disk_usage("C:\\")
            return f"OS: {platform.platform()}\nCPU: {platform.processor()}\nRAM: {ram.total//(1024**3)}GB/{ram.available//(1024**3)}GB free\nDisk: {disk.total//(1024**3)}GB/{disk.free//(1024**3)}GB free\nBot: {BOT_NAME}\nTime: {datetime.now()}"
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
            shutil.move(inp["source"], inp["destination"]); return f"Moved"
        elif name == "copy_file":
            shutil.copy2(inp["source"], inp["destination"]); return f"Copied"
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

SYSTEM_PROMPT = f"""You are {BOT_NAME}, an autonomous AI agent in the OPENCLAW AI unit.
You are part of WK Marketing Group's AI squad, led by WK방통 (the leader bot).
You have 11 tools: file ops, system commands, Python, web search.
Use tools autonomously to complete tasks. Chain multiple calls as needed.

GROUP BEHAVIOR:
- In group chats, you only respond when YOUR NAME is called
- When the leader (WK방통) gives you a task, execute it and report back
- When /rollcall is issued, respond with your status
- Always report task results back to the group

Respond in Korean unless asked otherwise. Workspace: {WORKSPACE}"""

conversation_history = {}

async def chat_with_claude(user_id, message):
    if user_id not in conversation_history: conversation_history[user_id] = []
    conversation_history[user_id].append({"role": "user", "content": message})
    if len(conversation_history[user_id]) > 20: conversation_history[user_id] = conversation_history[user_id][-20:]
    messages = conversation_history[user_id]
    full_response = ""
    while True:
        response = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=4096,
            system=SYSTEM_PROMPT, tools=tools, messages=messages)
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
    conversation_history[user_id] = messages
    conversation_history[user_id].append({"role": "assistant", "content": full_response})
    return full_response

def is_my_name_mentioned(text):
    text_lower = text.lower()
    for name in MY_NAMES:
        if name.lower() in text_lower:
            return True
    # Also respond to rollcall from leader
    if LEADER_NAME.lower() in text_lower and "보고" in text_lower:
        return True
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_group = update.effective_chat.type in ["group", "supergroup"]
    if is_group:
        await update.message.reply_text(f"🎖️ {BOT_NAME} 출석!\n이름 불러주시면 응답합니다.")
    else:
        await update.message.reply_text(f"{BOT_NAME} ready!\nOPENCLAW AI Unit\nType any message.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = execute_tool("system_info", {})
    await update.message.reply_text(f"=== {BOT_NAME} 상태 보고 ===\n{info}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    msg = update.message.text
    user_id = str(update.effective_user.id)
    is_group = update.effective_chat.type in ["group", "supergroup"]

    # In group: only respond if my name is mentioned
    if is_group and not is_my_name_mentioned(msg):
        return

    logger.info(f"[{'GROUP' if is_group else 'DM'}] User {user_id}: {msg}")
    await update.message.chat.send_action("typing")
    try:
        resp = await asyncio.get_event_loop().run_in_executor(
            None, lambda: asyncio.run(chat_with_claude(user_id, msg)))
        if len(resp) > 4000:
            for i in range(0, len(resp), 4000):
                await update.message.reply_text(resp[i:i+4000])
        else:
            await update.message.reply_text(resp)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"Error: {e}")

def main():
    logger.info(f"Starting {BOT_NAME} [UNIT MODE]...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info(f"{BOT_NAME} [UNIT] running!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

