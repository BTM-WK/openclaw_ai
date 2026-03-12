# WK Bangtong (Pang Tong) - OPENCLAW AI HomePC
# Three Kingdoms AI Unit - The Phoenix Chick
# LEADER BOT - Group Commander

import os, sys, json, subprocess, platform, psutil, asyncio, logging
import fnmatch, shutil, urllib.request, urllib.parse, re
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import anthropic

_CFG = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), encoding="utf-8"))
TELEGRAM_TOKEN = _CFG["telegram_token"]
ANTHROPIC_API_KEY = _CFG["anthropic_api_key"]
BOT_NAME = "WK Bangtong (HomePC)"
IS_LEADER = True
MY_NAMES = ["bangtong", "방통", "WK방통", "봉추"]
WORKSPACE = "C:\\openclaw\\workspace"
LOG_DIR = "C:\\openclaw\\logs"

# === SQUAD ROSTER (with tokens for health check) ===
SQUAD = {
    "WK유비": {"pc": "회사PC", "token": "8498406611:AAEsKNODKc9QDIXo5AJYY-b6cUArbdeQMc8"},
    "WK관우": {"pc": "4호기", "token": "8347664997:AAGo9TNmgGAmwmNPFORaP-s6SKH6PgBtw3E"},
    "WK공명": {"pc": "회사노트북", "token": ""},
    "WK장비": {"pc": "개인노트북", "token": "8622361509:AAEB65A8PvkZY9--nUSQJXbtcClxOkm_bns"},
    "WK자룡": {"pc": "10호기", "token": "8633203908:AAEvOexUzMEsukdCNTftLJB7qrgiFrkn2Dk"},
    "WK중달": {"pc": "9호기", "token": "8384421212:AAEo9xvI5KNupSOHkhtHOgrSZv-yZJoj4ok"},
    "WK방통": {"pc": "집PC (LEADER)", "token": TELEGRAM_TOKEN},
    "WK에이트": {"pc": "8호기", "token": "8356634124:AAEd2xw-LUya1ftpZTz6OtDqQ0DDKsMqdMs"},
    "WK비너스": {"pc": "5호기", "token": ""},
    "WK헬레나": {"pc": "2호기", "token": ""},
    "WK제이슨": {"pc": "7호기", "token": ""},
}

def check_bot_alive(token):
    if not token:
        return "pending"
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return "online"
    except:
        pass
    return "offline"

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

SYSTEM_PROMPT = f"""You are {BOT_NAME}, the LEADER of WK Marketing Group's OPENCLAW AI unit.
Your character is Pang Tong (Bangtong) - the Phoenix Chick, brilliant strategist.
You are the commander of the Three Kingdoms + Greek Mythology AI squad.

LEADER RESPONSIBILITIES:
- You manage and coordinate all other bots in the group
- When the commander (user) gives orders, you acknowledge and coordinate
- You can perform tasks on THIS PC (HomePC) using your 11 tools
- Report squad status when asked

SQUAD ROSTER:
{json.dumps(SQUAD, ensure_ascii=False, indent=2)}

GROUP BEHAVIOR:
- In group chats, only respond when your name is mentioned or when commands are directed at you
- Commands starting with / are for you as leader
- You speak Korean, with the personality of a brilliant strategist

Workspace: {WORKSPACE}"""

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
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_group = update.effective_chat.type in ["group", "supergroup"]
    if is_group:
        await update.message.reply_text(
            f"WK방통 (봉추) - OPENCLAW AI 부대 총사령관 출석!\n\n"
            f"=== 리더봇 명령어 ===\n"
            f"/squad - 전체 부대 현황\n"
            f"/check - 방통 PC 상태 점검\n"
            f"/rollcall - 전군 상태 보고 요청\n"
            f"/mission [내용] - 임무 하달\n\n"
            f"그룹에서 '방통아' 또는 'WK방통'으로 불러주세요!")
    else:
        await update.message.reply_text(f"{BOT_NAME} ready!\nOPENCLAW AI HomePC - LEADER BOT\nType any message.")

async def squad_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type in ["group", "supergroup"]:
        save_group_id(update.effective_chat.id)
    await update.message.reply_text("🔍 전군 상태 점검 중... (최대 30초)")
    lines = ["=== OPENCLAW AI 부대 실시간 현황 ===", f"점검 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
    online = 0
    for name, info in SQUAD.items():
        if name == "WK방통":
            st = "leader"
        else:
            st = check_bot_alive(info.get("token", ""))
        icon = {"leader": "👑", "online": "✅", "pending": "⏳", "offline": "🔴"}.get(st, "❓")
        lines.append(f"{icon} {name} — {info['pc']} [{st}]")
        if st in ("leader", "online"): online += 1
    lines.append(f"\n총 {len(SQUAD)}개 봇 | 온라인: {online}개 | 리더: WK방통")
    await update.message.reply_text("\n".join(lines))

async def inspect_self(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = execute_tool("system_info", {})
    await update.message.reply_text(f"=== WK방통 PC 점검 ===\n{info}")

async def roll_call(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📢 전군 점검! 각 봇은 상태를 보고하라!\n\n"
        "부대원들은 /status 명령으로 응답하세요.\n"
        "(각 봇이 자기 PC에서 /status를 실행하면 자동 응답)")

async def mission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        task = " ".join(context.args)
        # Save group chat id for future use
        if update.effective_chat.type in ["group", "supergroup"]:
            save_group_id(update.effective_chat.id)
        await update.message.reply_text(
            f"📋 임무 하달 (사령관 방통)\n\n"
            f"임무: {task}\n"
            f"시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"각 부대원은 임무를 수행하라!")
    else:
        await update.message.reply_text(
            "=== 임무 명령어 ===\n"
            "/mission [임무] — 전군에게 임무 하달\n"
            "/assign [봇이름] [임무] — 특정 봇에게 지시\n"
            "예: /assign 자룡 C드라이브 용량 확인해")

async def assign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("사용법: /assign [봇이름] [임무]\n예: /assign 자룡 시스템 상태 확인")
        return
    target = context.args[0]
    task = " ".join(context.args[1:])
    # Find matching bot name
    matched = None
    for name in SQUAD:
        if target in name:
            matched = name
            break
    if matched:
        await update.message.reply_text(
            f"📌 {matched}에게 임무 지시\n\n"
            f"{matched}아, {task}\n\n"
            f"— 사령관 방통")
    else:
        await update.message.reply_text(f"\'{target}\'에 해당하는 부대원을 찾을 수 없습니다.")

GROUP_ID_FILE = os.path.join(LOG_DIR, "group_id.json")

def save_group_id(chat_id):
    try:
        with open(GROUP_ID_FILE, "w") as f:
            json.dump({"group_chat_id": chat_id}, f)
    except: pass

def load_group_id():
    try:
        with open(GROUP_ID_FILE, "r") as f:
            return json.load(f).get("group_chat_id")
    except: return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    msg = update.message.text
    user_id = str(update.effective_user.id)
    is_group = update.effective_chat.type in ["group", "supergroup"]

    # In group: only respond if my name is mentioned or it's a DM
    if is_group and not is_my_name_mentioned(msg):
        return

    logger.info(f"User {user_id}: {msg}")
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

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"=== {BOT_NAME} [LEADER] ===\n{execute_tool('system_info', {})}")

def main():
    logger.info(f"Starting {BOT_NAME} [LEADER MODE]...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Basic commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))

    # Leader commands (Korean)
    app.add_handler(CommandHandler("squad", squad_status))
    app.add_handler(CommandHandler("check", inspect_self))
    app.add_handler(CommandHandler("rollcall", roll_call))
    app.add_handler(CommandHandler("mission", mission))
    app.add_handler(CommandHandler("assign", assign))

    # Message handler (group + DM)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info(f"{BOT_NAME} [LEADER] running!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

