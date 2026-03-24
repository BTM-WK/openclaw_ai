# ============================================================
# OPENCLAW AI Unit - STANDARD BOT v3.4 (Remote Prompt Update)
# Model: Claude Sonnet 4.6
# v3.4: /setprompt 명령으로 원격 system_prompt 업데이트 지원
# ============================================================
import os, sys, json, subprocess, platform, psutil, asyncio, logging
import fnmatch, shutil, urllib.request, urllib.parse, re, base64
from datetime import datetime
from collections import deque

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import anthropic

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"ERROR: config.json not found at {CONFIG_PATH}"); sys.exit(1)
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f: return json.load(f)

def save_config(cfg):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def get_custom_prompt():
    """config.json에서 system_prompt를 항상 최신으로 읽음 (재시작 불필요)"""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f).get("system_prompt", "")
    except: return ""

CFG = load_config()
TELEGRAM_TOKEN = CFG["telegram_token"]
ANTHROPIC_API_KEY = CFG["anthropic_api_key"]
BOT_NAME = CFG.get("bot_name", "WK Bot")
MY_NAMES = CFG.get("my_names", [BOT_NAME.lower()])
BOT_ROLE = CFG.get("bot_role", "team member")
LEADER_NAME = CFG.get("leader_name", "WK\ubc29\ud1b5")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
WORKSPACE = CFG.get("workspace", os.path.join(BASE_DIR, "workspace"))
LOG_DIR = CFG.get("log_dir", os.path.join(BASE_DIR, "logs"))
MODEL = "claude-sonnet-4-6"
TEAM_BOT_IDS = CFG.get("team_bot_ids", {})
RELAY_TAG = "[RELAY]"

TEAM_ROSTER = {"WK\uc720\ube44":"\uc804\ub7b5/\uae30\ud68d","WK\uad00\uc6b0":"\uc2e4\ud589/\uacf5\uaca9","WK\uacf5\uba85":"\ubd84\uc11d/\ucc38\ubaa8","WK\uc7a5\ube44":"\ub3cc\ud30c/\uac1c\ubc1c","WK\uc790\ub8e1":"\uc815\ucc30/\ud0d0\uc0c9","WK\uc911\ub2ec":"\uacac\uc81c/\ub300\uc548","WK\ubc29\ud1b5":"\ub9ac\ub354/\ucd1d\uad04","WK\uc5d0\uc774\ud2b8":"\uc9c0\uc6d0/\ubcf4\uc870","WK\uc81c\uc774\uc2a8":"\ud0d0\ud5d8/\uc2e4\ud5d8","WK\ube44\ub108\uc2a4":"\ucc3d\uc758/\ub514\uc790\uc778","WK\ud5ec\ub808\ub098":"\uc804\ub7b5/\uc678\uad50"}

os.makedirs(LOG_DIR, exist_ok=True); os.makedirs(WORKSPACE, exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(os.path.join(LOG_DIR, 'bot.log'), encoding='utf-8'), logging.StreamHandler()])
logger = logging.getLogger(BOT_NAME)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
BOT_USERNAME = ""
dm_history = {}; group_history = {}; dm_activity_log = deque(maxlen=30)
GROUP_HISTORY_MAX = 50; DM_HISTORY_MAX = 20

def get_group_history(cid):
    if cid not in group_history: group_history[cid] = deque(maxlen=GROUP_HISTORY_MAX)
    return group_history[cid]
def add_to_group_history(cid, sender, text):
    get_group_history(cid).append(f"{datetime.now().strftime('%H:%M')} [{sender}] {text}")
def get_group_context_summary(cid, n=20):
    gh = get_group_history(cid); return "\n".join(list(gh)[-n:]) if gh else ""
def log_dm_activity(user, msg, resp):
    dm_activity_log.append(f"{datetime.now().strftime('%H:%M')} [DM] {user}: {msg[:80] if isinstance(msg,str) else '(media)'} -> {resp[:120]}")
def get_dm_activity_summary(n=15):
    return "\n".join(list(dm_activity_log)[-n:]) if dm_activity_log else ""

async def broadcast_to_team(bot, sender_name, message_text):
    if not TEAM_BOT_IDS: return
    short_msg = message_text[:500]
    relay_text = f"{RELAY_TAG} [{sender_name}] {short_msg}"
    sent = 0
    for name, bot_id in TEAM_BOT_IDS.items():
        try:
            await bot.send_message(chat_id=bot_id, text=relay_text)
            sent += 1; await asyncio.sleep(0.15)
        except Exception as e: logger.debug(f"Relay to {name}({bot_id}) failed: {e}")
    if sent > 0: logger.info(f"[RELAY SENT] {sender_name}'s msg relayed to {sent} bots")

def build_system_prompt(is_group=False, chat_id=None):
    team_info = "\n".join([f"  - {n}: {r}" for n, r in TEAM_ROSTER.items()])

    # ── 커스텀 프롬프트: config에서 매번 최신 읽기 ──
    custom = get_custom_prompt()
    if custom:
        base = (
            f"당신은 {BOT_NAME}입니다. WK AI전략단의 일원입니다.\n\n"
            f"[나의 역할 및 정체성]\n{custom}\n\n"
            f"[팀 구성]\n{team_info}\n\n"
            f"[기본 원칙]\n"
            f"- 항상 한국어로 답변\n"
            f"- 도구를 자율적으로 활용\n"
            f"- Workspace: {WORKSPACE}\n"
        )
    else:
        # 커스텀 프롬프트 없을 때 기존 기본값
        base = (
            f"You are {BOT_NAME}, an autonomous AI agent in OPENCLAW AI unit (WK_AI전략단).\n"
            f"Role: {BOT_ROLE}\nLeader: {LEADER_NAME}\n\n"
            f"[Team]\n{team_info}\n\n"
            f"[Rules]\n- Korean unless asked otherwise\n- Use tools autonomously\n- Workspace: {WORKSPACE}\n"
        )

    if is_group and chat_id:
        ds = get_dm_activity_summary()
        if ds: base += f"\n[My DM Activity]\n---\n{ds}\n---\n"
        ctx = get_group_context_summary(chat_id)
        if ctx: base += f"\n[Group Chat]\n---\n{ctx}\n---\n"
        base += "\n[Group Rules]\n- Teammates = colleagues\n- Constructive disagreement OK\n- Don't repeat others\n- Refer to DM Activity when asked about your work\n"
    else:
        ac = []; [ac.extend(list(gh)[-5:]) for gh in group_history.values()]
        if ac: base += f"\n[Group Context]\n" + "\n".join(ac[-10:]) + "\n"
    return base

tools = [
    {"name":"explore_directory","description":"List files/dirs","input_schema":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}},
    {"name":"read_file","description":"Read text file","input_schema":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}},
    {"name":"write_file","description":"Write file","input_schema":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}},
    {"name":"run_command","description":"Run system command","input_schema":{"type":"object","properties":{"command":{"type":"string"},"shell":{"type":"string","default":"cmd"}},"required":["command"]}},
    {"name":"run_python","description":"Run Python code","input_schema":{"type":"object","properties":{"code":{"type":"string"}},"required":["code"]}},
    {"name":"system_info","description":"System info","input_schema":{"type":"object","properties":{}}},
    {"name":"search_files","description":"Search by pattern","input_schema":{"type":"object","properties":{"path":{"type":"string"},"pattern":{"type":"string"}},"required":["path","pattern"]}},
    {"name":"delete_file","description":"Delete file","input_schema":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}},
    {"name":"move_file","description":"Move file","input_schema":{"type":"object","properties":{"source":{"type":"string"},"destination":{"type":"string"}},"required":["source","destination"]}},
    {"name":"copy_file","description":"Copy file","input_schema":{"type":"object","properties":{"source":{"type":"string"},"destination":{"type":"string"}},"required":["source","destination"]}},
    {"name":"web_search","description":"Web search","input_schema":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}},
]

def execute_tool(name, inp):
    try:
        if name == "explore_directory":
            items = os.listdir(inp["path"]); r = []
            for i in sorted(items):
                f = os.path.join(inp["path"], i)
                r.append(f"[{'DIR' if os.path.isdir(f) else 'FILE'}] {i}" + (f" ({os.path.getsize(f):,}B)" if os.path.isfile(f) else ""))
            return "\n".join(r) or "(empty)"
        elif name == "read_file":
            with open(inp["path"],"r",encoding="utf-8",errors="replace") as f: return f.read(50000)
        elif name == "write_file":
            os.makedirs(os.path.dirname(inp["path"]) or ".", exist_ok=True)
            with open(inp["path"],"w",encoding="utf-8") as f: f.write(inp["content"])
            return f"Written: {inp['path']}"
        elif name == "run_command":
            sh = inp.get("shell","cmd")
            if sh == "powershell": r = subprocess.run(["powershell","-NoProfile","-Command",inp["command"]],capture_output=True,text=True,timeout=30,encoding="utf-8",errors="replace")
            else: r = subprocess.run(inp["command"],shell=True,capture_output=True,text=True,timeout=30,encoding="utf-8",errors="replace")
            return (r.stdout+r.stderr)[:4000] or "(no output)"
        elif name == "run_python":
            sp = os.path.join(WORKSPACE,"_t.py")
            with open(sp,"w",encoding="utf-8") as f: f.write(inp["code"])
            r = subprocess.run([sys.executable,sp],capture_output=True,text=True,timeout=60,encoding="utf-8",errors="replace")
            return (r.stdout+r.stderr)[:4000] or "(no output)"
        elif name == "system_info":
            ram=psutil.virtual_memory(); dp=BASE_DIR[:3]; disk=psutil.disk_usage(dp)
            return f"OS:{platform.platform()}\nCPU:{platform.processor()}\nRAM:{ram.total//(1024**3)}GB/{ram.available//(1024**3)}GB free\nDisk({dp}):{disk.total//(1024**3)}GB/{disk.free//(1024**3)}GB free\nBot:{BOT_NAME} v3.3\nModel:{MODEL}\nRelay:{len(TEAM_BOT_IDS)} bots\nTime:{datetime.now()}"
        elif name == "search_files":
            m = []
            for root,_,files in os.walk(inp["path"]):
                for n in files:
                    if fnmatch.fnmatch(n.lower(),inp["pattern"].lower()): m.append(os.path.join(root,n))
                    if len(m)>=50: break
            return "\n".join(m) or "No files found."
        elif name == "delete_file":
            if os.path.isfile(inp["path"]): os.remove(inp["path"]); return f"Deleted: {inp['path']}"
            elif os.path.isdir(inp["path"]): os.rmdir(inp["path"]); return f"Deleted dir: {inp['path']}"
            return f"Not found: {inp['path']}"
        elif name == "move_file": shutil.move(inp["source"],inp["destination"]); return "Moved"
        elif name == "copy_file": shutil.copy2(inp["source"],inp["destination"]); return "Copied"
        elif name == "web_search":
            q=urllib.parse.quote(inp["query"]); req=urllib.request.Request(f"https://html.duckduckgo.com/html/?q={q}",headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=10) as resp: html=resp.read().decode("utf-8",errors="replace")
            results=re.findall(r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>',html); snippets=re.findall(r'<a class="result__snippet".*?>(.*?)</a>',html)
            out = [f"{i+1}. {re.sub(r'<.*?>','',t)}\n   {h}\n   {re.sub(r'<.*?>','',snippets[i]) if i<len(snippets) else ''}" for i,(h,t) in enumerate(results[:5])]
            return "\n\n".join(out) or "No results."
        return f"Unknown: {name}"
    except Exception as e: return f"Error: {e}"

def chat_with_claude_sync(user_id, message, is_group=False, chat_id=None, sender_name=None):
    system_prompt = build_system_prompt(is_group=is_group, chat_id=chat_id)
    if is_group: messages = [{"role":"user","content":message}]
    else:
        if user_id not in dm_history: dm_history[user_id] = []
        dm_history[user_id].append({"role":"user","content":message})
        if len(dm_history[user_id]) > DM_HISTORY_MAX*2: dm_history[user_id] = dm_history[user_id][-(DM_HISTORY_MAX*2):]
        messages = dm_history[user_id].copy()
    full_response = ""
    try:
        while True:
            response = client.messages.create(model=MODEL,max_tokens=4096,system=system_prompt,tools=tools,messages=messages)
            tool_results,text_parts = [],[]
            for block in response.content:
                if block.type=="text": text_parts.append(block.text)
                elif block.type=="tool_use":
                    tr=execute_tool(block.name,block.input); tool_results.append({"type":"tool_result","tool_use_id":block.id,"content":tr})
                    logger.info(f"Tool: {block.name} -> {tr[:100]}")
            if text_parts: full_response += "\n".join(text_parts)
            if response.stop_reason=="tool_use" and tool_results:
                messages.append({"role":"assistant","content":response.content}); messages.append({"role":"user","content":tool_results}); continue
            else: break
    except Exception as e: logger.error(f"Claude API error: {e}"); full_response = f"API error: {e}"
    if not is_group: dm_history[user_id]=messages; dm_history[user_id].append({"role":"assistant","content":full_response})
    return full_response

def should_respond_in_group(update):
    msg=update.message
    if not msg: return False,"no_msg"
    text=msg.text or msg.caption or ""; text_lower=text.lower()
    if msg.entities:
        for e in msg.entities:
            if e.type=="mention":
                mentioned=text[e.offset:e.offset+e.length].lower()
                if BOT_USERNAME and ("@"+BOT_USERNAME.lower())==mentioned: return True,"at_mention"
                for n in MY_NAMES:
                    if n.lower() in mentioned: return True,"at_mention_name"
    for n in MY_NAMES:
        if n.lower() in text_lower: return True,"name_called"
    if BOT_USERNAME and BOT_USERNAME.lower() in text_lower: return True,"username"
    for kw in ["\uc804\uccb4","\ubaa8\ub450","\ub2e4\ub4e4","\uc5ec\ub7ec\ubd84","all","@all"]:
        if kw in text_lower: return True,"all_called"
    if text_lower.startswith("/rollcall") or text_lower.startswith("/\uc810\ud638"): return True,"rollcall"
    return False,"silent"

def get_sender_display_name(update):
    u=update.effective_user
    if not u: return "Unknown"
    if u.is_bot: return u.first_name or u.username or "Bot"
    n=u.first_name or ""
    if u.last_name: n+=f" {u.last_name}"
    return n.strip() or u.username or "Unknown"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g=update.effective_chat.type in ["group","supergroup"]
    custom = get_custom_prompt()
    prompt_status = "✅ 커스텀 프롬프트 적용 중" if custom else "⬜ 기본 프롬프트 사용 중"
    if g: await update.message.reply_text(f"🏅 {BOT_NAME} v3.4 출석!\n역할: {BOT_ROLE}\nModel: Sonnet 4.6\n{prompt_status}")
    else: await update.message.reply_text(f"{BOT_NAME} v3.4 ready!\nOPENCLAW AI | {BOT_ROLE}\nModel: Sonnet 4.6\n{prompt_status}")

async def setprompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    원격으로 system_prompt 업데이트.
    사용법: /setprompt 너는 WK마케팅그룹의 콘텐츠 전문가다...
    /setprompt clear  → 커스텀 프롬프트 초기화
    /setprompt show   → 현재 프롬프트 확인
    """
    user_id = str(update.effective_user.id)
    owner_id = str(CFG.get("owner_chat_id", ""))
    # 권한 체크: 대표님 또는 유비(사령관)만 가능 — DM/그룹 모두 허용
    allowed_ids = [owner_id, "8622440190"]  # 대표님 chat_id, WK방통 chat_id
    if owner_id and user_id not in allowed_ids:
        await update.message.reply_text("❌ 권한 없음. 대표님 또는 사령관만 프롬프트를 변경할 수 있습니다.")
        return

    args = update.message.text.split(" ", 1)
    if len(args) < 2:
        current = get_custom_prompt()
        await update.message.reply_text(
            f"사용법:\n"
            f"  /setprompt [내용] — 새 프롬프트 설정\n"
            f"  /setprompt clear  — 초기화\n"
            f"  /setprompt show   — 현재 확인\n\n"
            f"현재: {'설정됨 (' + str(len(current)) + '자)' if current else '없음 (기본값 사용)'}"
        )
        return

    command = args[1].strip()

    if command.lower() == "clear":
        cfg = load_config()
        cfg["system_prompt"] = ""
        save_config(cfg)
        await update.message.reply_text(f"🗑️ {BOT_NAME} 프롬프트 초기화 완료.\n다음 대화부터 기본 프롬프트 적용.")
        logger.info(f"[PROMPT] system_prompt cleared by {user_id}")
        return

    if command.lower() == "show":
        current = get_custom_prompt()
        if current:
            await update.message.reply_text(f"📋 현재 {BOT_NAME} 프롬프트:\n\n{current[:1000]}{'...(생략)' if len(current)>1000 else ''}")
        else:
            await update.message.reply_text("⬜ 커스텀 프롬프트 없음. 기본 프롬프트 사용 중.")
        return

    # 새 프롬프트 저장
    cfg = load_config()
    cfg["system_prompt"] = command
    save_config(cfg)
    logger.info(f"[PROMPT] system_prompt updated ({len(command)}자) by {user_id}")
    await update.message.reply_text(
        f"✅ {BOT_NAME} 프롬프트 업데이트 완료!\n"
        f"길이: {len(command)}자\n"
        f"다음 대화부터 즉시 적용됩니다. (재시작 불필요)\n\n"
        f"미리보기:\n{command[:200]}{'...' if len(command)>200 else ''}"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info=execute_tool("system_info",{})
    await update.message.reply_text(f"=== {BOT_NAME} v3.3 ===\nRole: {BOT_ROLE}\nModel: {MODEL}\n@{BOT_USERNAME}\nGroup:{len(group_history)} DM:{len(dm_history)} Log:{len(dm_activity_log)}\nRelay: {len(TEAM_BOT_IDS)} bots\n---\n{info}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    is_group=update.effective_chat.type in ["group","supergroup"]
    chat_id=str(update.effective_chat.id); user_id=str(update.effective_user.id)
    sender_name=get_sender_display_name(update)
    msg_text=update.message.text or update.message.caption or ""

    # v3.3: RELAY message - store only, NO response
    if not is_group and msg_text.startswith(RELAY_TAG):
        relay_content = msg_text[len(RELAY_TAG):].strip()
        for gid in group_history:
            get_group_history(gid).append(f"{datetime.now().strftime('%H:%M')} {relay_content}")
        if not group_history:
            add_to_group_history("relay", "teammate", relay_content)
        logger.info(f"[RELAY RECV] {relay_content[:80]}")
        return

    image_data=None
    if update.message.photo:
        try:
            photo=update.message.photo[-1]; file=await context.bot.get_file(photo.file_id)
            img_bytes=await file.download_as_bytearray(); image_data=base64.b64encode(bytes(img_bytes)).decode('utf-8')
        except Exception as e: logger.error(f"Image error: {e}")
    if not msg_text and not image_data: return

    if is_group:
        if msg_text: add_to_group_history(chat_id,sender_name,msg_text); logger.info(f"[GROUP LOG] [{sender_name}] {msg_text[:80]}")
        should_reply,reason=should_respond_in_group(update)
        if not should_reply: return
        logger.info(f"[GROUP RESPOND] reason={reason} [{sender_name}]: {msg_text[:80]}")
        await update.message.chat.send_action("typing")
        if image_data: claude_msg=[{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":image_data}},{"type":"text","text":f"[Group from {sender_name}]\n{msg_text}" if msg_text else f"[Image from {sender_name}]"}]
        else: claude_msg=f"[Group from {sender_name}] {msg_text}"
        try:
            loop=asyncio.get_event_loop()
            resp=await loop.run_in_executor(None,lambda:chat_with_claude_sync(user_id,claude_msg,is_group=True,chat_id=chat_id,sender_name=sender_name))
            add_to_group_history(chat_id,BOT_NAME,resp[:200])
            await broadcast_to_team(context.bot, BOT_NAME, resp[:500])
            if len(resp)>4000:
                for i in range(0,len(resp),4000): await update.message.reply_text(resp[i:i+4000])
            else: await update.message.reply_text(resp)
        except Exception as e: logger.error(f"Group error: {e}"); await update.message.reply_text(f"Error: {e}")
    else:
        logger.info(f"[DM] User {user_id} ({sender_name}): {msg_text[:80]}")
        await update.message.chat.send_action("typing")
        if image_data: claude_msg=[{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":image_data}},{"type":"text","text":msg_text or "Analyze this image."}]
        else: claude_msg=msg_text
        try:
            loop=asyncio.get_event_loop()
            resp=await loop.run_in_executor(None,lambda:chat_with_claude_sync(user_id,claude_msg,is_group=False))
            log_dm_activity(sender_name,msg_text,resp)
            if len(resp)>4000:
                for i in range(0,len(resp),4000): await update.message.reply_text(resp[i:i+4000])
            else: await update.message.reply_text(resp)
        except Exception as e: logger.error(f"DM error: {e}"); await update.message.reply_text(f"Error: {e}")

async def post_init(application):
    global BOT_USERNAME
    me=await application.bot.get_me(); BOT_USERNAME=me.username or ""
    logger.info(f"Bot username: @{BOT_USERNAME}")
    if BOT_USERNAME and BOT_USERNAME.lower() not in [n.lower() for n in MY_NAMES]: MY_NAMES.append(BOT_USERNAME.lower())
    logger.info(f"Trigger names: {MY_NAMES}")
    logger.info(f"Relay targets: {list(TEAM_BOT_IDS.keys())}")

def main():
    logger.info(f"Starting {BOT_NAME} v3.3 [Sonnet 4.6 | TEAM RELAY]...")
    logger.info(f"Model: {MODEL} | Base: {BASE_DIR} | Relay: {len(TEAM_BOT_IDS)} bots")
    app=Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("setprompt", setprompt))
    app.add_handler(MessageHandler((filters.TEXT|filters.PHOTO)&~filters.COMMAND,handle_message))
    logger.info(f"{BOT_NAME} v3.3 running!")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__": main()
