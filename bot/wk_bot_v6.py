"""
WK Bot v6 - OPENCLAW Autonomous Agent (Unified)
================================================
AI Router: 작업별 최적 AI 자동 선택 (Claude/Gemini/GPT)
Open WebUI: 없으면 자동 설치 + 자동 시작
Autonomous Worker: task_queue 기반 자율 작업
Scheduler: 주기 보고 + stall 감지
"""
import asyncio, os, sys, json, subprocess, platform, psutil, logging
import shutil, re, urllib.request, urllib.parse
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import anthropic

from task_manager import TaskManager
from autonomous_worker import AutonomousWorker
from reporter import Reporter
from ai_router import AIRouter
from setup_openwebui import ensure_openwebui, get_openwebui_info

def load_config():
    cp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if os.path.exists(cp):
        with open(cp, "r", encoding="utf-8") as f: return json.load(f)
    return {"telegram_token":"YOUR_TOKEN","anthropic_api_key":"YOUR_KEY","bot_name":"WK Agent","bot_character":"AI Agent",
        "workspace":"C:\\openclaw\\workspace","log_dir":"C:\\openclaw\\logs","owner_chat_id":None,
        "gmail_user":None,"gmail_app_password":None,"report_to_email":"wangki@wkmg.co.kr",
        "report_interval_minutes":120,"max_api_calls_per_hour":20,"task_interval_seconds":60,"stall_timeout_minutes":30,
        "openwebui_url":"http://localhost:8080","openwebui_api_key":"","default_route":"anthropic","auto_install_openwebui":True}

def save_config(cfg):
    cp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(cp, "w", encoding="utf-8") as f: json.dump(cfg, f, ensure_ascii=False, indent=2)

config = load_config()
TELEGRAM_TOKEN = config["telegram_token"]
ANTHROPIC_API_KEY = config["anthropic_api_key"]
BOT_NAME = config["bot_name"]
WORKSPACE = config["workspace"]
LOG_DIR = config.get("log_dir", "C:\\openclaw\\logs")
OWNER_CHAT_ID = config.get("owner_chat_id")
REPORT_INTERVAL = config.get("report_interval_minutes", 120)
STALL_TIMEOUT = config.get("stall_timeout_minutes", 30)

for d in [LOG_DIR, WORKSPACE, os.path.join(WORKSPACE,"reports"), os.path.join(WORKSPACE,"data"), os.path.join(WORKSPACE,"drafts")]:
    os.makedirs(d, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(os.path.join(LOG_DIR, 'bot_v6.log'), encoding='utf-8'), logging.StreamHandler()])
logger = logging.getLogger(BOT_NAME)

logger.info("Checking Open WebUI status...")
owui_installed, owui_running = ensure_openwebui(auto_install=config.get("auto_install_openwebui", True), auto_start=True)
if owui_running: logger.info("Open WebUI: RUNNING -> Multi-AI mode enabled")
else: logger.info("Open WebUI: NOT RUNNING -> Claude-only mode")

router = AIRouter(config)

tools = [
    {"name":"explore_directory","description":"List files/folders","input_schema":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}},
    {"name":"read_file","description":"Read text file","input_schema":{"type":"object","properties":{"path":{"type":"string"},"max_lines":{"type":"integer","default":300}},"required":["path"]}},
    {"name":"write_file","description":"Create/overwrite file","input_schema":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}},
    {"name":"append_file","description":"Append to file","input_schema":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}},
    {"name":"delete_file","description":"Delete file","input_schema":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}},
    {"name":"run_command","description":"Execute system command","input_schema":{"type":"object","properties":{"command":{"type":"string"},"timeout":{"type":"integer","default":30}},"required":["command"]}},
    {"name":"run_python","description":"Execute Python code","input_schema":{"type":"object","properties":{"code":{"type":"string"}},"required":["code"]}},
    {"name":"web_search","description":"Search web (DuckDuckGo)","input_schema":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}},
    {"name":"web_fetch","description":"Fetch URL text content","input_schema":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}},
    {"name":"system_info","description":"CPU/RAM/disk/uptime","input_schema":{"type":"object","properties":{}}},
    {"name":"move_file","description":"Move/rename file","input_schema":{"type":"object","properties":{"source":{"type":"string"},"destination":{"type":"string"}},"required":["source","destination"]}},
]

def execute_tool(name, params):
    try:
        if name == "explore_directory":
            path = params.get("path", WORKSPACE)
            if not os.path.exists(path): return f"Not found: {path}"
            items = []
            for item in sorted(os.listdir(path)):
                fp = os.path.join(path, item)
                if os.path.isdir(fp): items.append(f"[DIR] {item}/")
                else: items.append(f"[FILE] {item} ({os.path.getsize(fp):,}B)")
            return "\n".join(items) or "(empty)"
        elif name == "read_file":
            for enc in ['utf-8','cp949','euc-kr','latin-1']:
                try:
                    with open(params["path"],"r",encoding=enc) as f: lines = f.readlines()[:params.get("max_lines",300)]
                    return "".join(lines)
                except UnicodeDecodeError: continue
            return "Read failed"
        elif name == "write_file":
            os.makedirs(os.path.dirname(params["path"]) or ".", exist_ok=True)
            with open(params["path"],"w",encoding="utf-8") as f: f.write(params["content"])
            return f"Written: {params['path']}"
        elif name == "append_file":
            with open(params["path"],"a",encoding="utf-8") as f: f.write(params["content"])
            return f"Appended: {params['path']}"
        elif name == "delete_file":
            if os.path.exists(params["path"]): os.remove(params["path"]); return "Deleted"
            return "Not found"
        elif name == "run_command":
            r = subprocess.run(params["command"], shell=True, capture_output=True, text=True, timeout=params.get("timeout",30))
            return f"Exit:{r.returncode}\n{r.stdout[:3000]}\n{r.stderr[:1000]}".strip()
        elif name == "run_python":
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w',suffix='.py',delete=False,encoding='utf-8') as f:
                f.write(params["code"]); tmp=f.name
            try:
                r = subprocess.run([sys.executable,tmp], capture_output=True, text=True, timeout=60)
                return f"{r.stdout[:3000]}\n{r.stderr[:1000]}".strip() or "(no output)"
            finally: os.unlink(tmp)
        elif name == "web_search":
            q = urllib.parse.quote(params["query"])
            req = urllib.request.Request(f"https://html.duckduckgo.com/html/?q={q}", headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp: html = resp.read().decode('utf-8', errors='replace')
            results = re.findall(r'<a rel="nofollow" class="result__a" href="(.*?)".*?>(.*?)</a>', html)
            snippets = re.findall(r'<a class="result__snippet".*?>(.*?)</a>', html)
            out = []
            for i,(href,title) in enumerate(results[:7]):
                t = re.sub(r'<.*?>','',title); sn = re.sub(r'<.*?>','',snippets[i]) if i<len(snippets) else ""
                out.append(f"{i+1}. {t}\n   {href}\n   {sn}")
            return "\n\n".join(out) or "No results"
        elif name == "web_fetch":
            req = urllib.request.Request(params["url"], headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=20) as resp: html = resp.read().decode('utf-8', errors='replace')
            text = re.sub(r'<script.*?</script>','',html,flags=re.DOTALL)
            text = re.sub(r'<style.*?</style>','',text,flags=re.DOTALL)
            text = re.sub(r'<.*?>',' ',text)
            return re.sub(r'\s+',' ',text).strip()[:5000]
        elif name == "system_info":
            cpu=psutil.cpu_percent(interval=1); mem=psutil.virtual_memory(); disk=psutil.disk_usage('C:\\')
            return f"CPU:{cpu}% RAM:{mem.percent}% Disk:{disk.percent}% Host:{platform.node()}"
        elif name == "move_file":
            shutil.move(params["source"],params["destination"]); return "Moved"
        return f"Unknown: {name}"
    except Exception as e: return f"Error({name}): {e}"

CHAT_SYSTEM = f"""You are {BOT_NAME}, an autonomous AI agent. {config.get('bot_character','')}.
Part of WK Marketing Group's OPENCLAW AI system.
11 tools: file ops, commands, Python, web search.
Use tools autonomously. Respond in Korean. Workspace: {WORKSPACE}"""

conversation_history = {}

async def chat_with_ai(user_id, message):
    if user_id not in conversation_history: conversation_history[user_id] = []
    conversation_history[user_id].append({"role":"user","content":message})
    if len(conversation_history[user_id]) > 20: conversation_history[user_id] = conversation_history[user_id][-20:]
    messages = conversation_history[user_id]
    full_response = ""
    route_info = router.get_route_info(message)
    if route_info["actual_route"] == "openwebui":
        result = router.call_openwebui(route_info["actual_model"], messages, CHAT_SYSTEM)
        if result.get("error"): result = router.call_anthropic(route_info["model"], messages, CHAT_SYSTEM, tools)
        full_response = result.get("text", result.get("error", ""))
    else:
        for _ in range(15):
            result = router.call_anthropic(route_info["actual_model"], messages, CHAT_SYSTEM, tools)
            if result.get("text"): full_response += result["text"]
            tu = result.get("tool_uses", [])
            raw = result.get("raw_response")
            if result.get("stop_reason") == "tool_use" and tu and raw:
                trs = []
                for t in tu:
                    tr = execute_tool(t["name"], t["input"])
                    trs.append({"type":"tool_result","tool_use_id":t["id"],"content":str(tr)[:5000]})
                    logger.info(f"Tool: {t['name']}")
                messages.append({"role":"assistant","content":raw.content})
                messages.append({"role":"user","content":trs})
                continue
            break
    conversation_history[user_id].append({"role":"assistant","content":full_response})
    return full_response

worker = None; reporter_obj = None; task_mgr = None

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global OWNER_CHAT_ID
    OWNER_CHAT_ID = update.effective_chat.id
    config["owner_chat_id"] = OWNER_CHAT_ID; save_config(config)
    owui_status = "ON (Multi-AI)" if router.check_openwebui() else "OFF (Claude-only)"
    await update.message.reply_text(
        f"{BOT_NAME} v6 Ready!\nOpen WebUI: {owui_status}\n\n"
        f"/mission <goal> - Start autonomous work\n/addtask <task> - Add task\n"
        f"/status - Progress report\n/tasks - Task queue\n/models - AI models\n"
        f"/route <msg> - Preview routing\n/pause /resume - Control worker\n"
        f"/report - Force report\n/openwebui - Open WebUI control")

async def cmd_mission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global OWNER_CHAT_ID; OWNER_CHAT_ID = update.effective_chat.id
    text = " ".join(context.args) if context.args else ""
    if not text: await update.message.reply_text("Usage: /mission <goal>"); return
    mp = os.path.join(WORKSPACE, "mission.md")
    with open(mp,"w",encoding="utf-8") as f:
        f.write(f"# Mission\nGoal: {text}\nSet: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"Rules: autonomous, depth over speed, save outputs, report every {REPORT_INTERVAL}min")
    task_mgr.set_goal(text)
    try:
        result = router.call_anthropic("claude-sonnet-4-20250514",
            [{"role":"user","content":f"Break down into 5-10 tasks (JSON array).\nGoal: {text}\n"
              f'[{{"title":"..","priority":1,"notes":".."}},..]\nKorean titles.'}], max_tokens=2000)
        m = re.search(r'\[.*\]', result.get("text",""), re.DOTALL)
        if m:
            tds = json.loads(m.group(0))
            for td in tds: task_mgr.add_task(td.get("title","?"), td.get("priority",2), td.get("notes",""))
            await update.message.reply_text(f"Mission: {text}\n{len(tds)} tasks. Working autonomously.\n/tasks to see queue.")
        else: task_mgr.add_task(text, 1); await update.message.reply_text(f"Mission: {text}\n1 initial task.")
    except Exception as e: task_mgr.add_task(text, 1); await update.message.reply_text(f"Mission set. ({e})")

async def cmd_addtask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""
    if not text: await update.message.reply_text("Usage: /addtask <desc>"); return
    nid = task_mgr.add_task(text, 1); await update.message.reply_text(f"Added: {nid} - {text}")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = reporter_obj.save_report()
    for i in range(0,len(r),4000): await update.message.reply_text(r[i:i+4000])

async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Task Queue:\n\n{task_mgr.get_all_tasks_text()[:4000]}")

async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    worker.pause(); await update.message.reply_text("Worker PAUSED.")

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    worker.resume(); await update.message.reply_text("Worker RESUMED.")

async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global OWNER_CHAT_ID; OWNER_CHAT_ID = update.effective_chat.id
    await update.message.reply_text(reporter_obj.save_report()); reporter_obj.send_gmail_report()

async def cmd_models(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(router.get_status_text())

async def cmd_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""
    if not text: await update.message.reply_text("Usage: /route <message>"); return
    ri = router.get_route_info(text)
    fb = " (fallback)" if ri.get("fallback") else ""
    await update.message.reply_text(f"Category: {ri['category']}\nModel: {ri['actual_model']}\nRoute: {ri['actual_route']}{fb}")

async def cmd_openwebui(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args[0] if context.args else "status"
    info = get_openwebui_info()
    if args == "start":
        if info["running"]: await update.message.reply_text("Already running.")
        else:
            await update.message.reply_text("Starting Open WebUI... (wait 1-2min)")
            from setup_openwebui import start_openwebui_server
            ok = start_openwebui_server()
            if ok: router.reset_cache(); await update.message.reply_text("Started! Multi-AI enabled.")
            else: await update.message.reply_text("Failed. Check logs.")
    elif args == "install":
        await update.message.reply_text("Installing... (5-10min)")
        from setup_openwebui import install_openwebui
        await update.message.reply_text("Done!" if install_openwebui() else "Failed.")
    else:
        st = "RUNNING" if info["running"] else ("INSTALLED" if info["installed"] else "NOT INSTALLED")
        await update.message.reply_text(f"Open WebUI: {st}\nURL: {info['url']}\n\n/openwebui start\n/openwebui install")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global OWNER_CHAT_ID; OWNER_CHAT_ID = update.effective_chat.id
    uid = str(update.effective_user.id); msg = update.message.text
    logger.info(f"User {uid}: {msg}")
    await update.message.chat.send_action("typing")
    try:
        resp = await asyncio.get_event_loop().run_in_executor(None, lambda: asyncio.run(chat_with_ai(uid, msg)))
        for i in range(0,len(resp),4000): await update.message.reply_text(resp[i:i+4000])
    except Exception as e: logger.error(f"Chat error: {e}"); await update.message.reply_text(f"Error: {e}")

async def scheduler_loop(app):
    global OWNER_CHAT_ID
    while True:
        try:
            await asyncio.sleep(60)
            if reporter_obj.should_report(REPORT_INTERVAL) and OWNER_CHAT_ID:
                try:
                    await app.bot.send_message(chat_id=OWNER_CHAT_ID, text=reporter_obj.save_report())
                    reporter_obj.last_report_time = datetime.now(); reporter_obj.send_gmail_report()
                except Exception as e: logger.error(f"Report failed: {e}")
            if worker.is_running and not worker.is_paused and reporter_obj.check_stall(STALL_TIMEOUT):
                logger.warning(f"STALL: no output {STALL_TIMEOUT}+ min")
                if OWNER_CHAT_ID:
                    try: await app.bot.send_message(chat_id=OWNER_CHAT_ID, text=f"[STALL] {BOT_NAME}: No output {STALL_TIMEOUT}+ min")
                    except: pass
        except asyncio.CancelledError: break
        except Exception as e: logger.error(f"Scheduler: {e}"); await asyncio.sleep(30)

async def post_init(app):
    global worker, reporter_obj, task_mgr
    task_mgr = TaskManager(WORKSPACE)
    reporter_obj = Reporter(task_mgr, BOT_NAME, WORKSPACE,
        config.get("gmail_user"), config.get("gmail_app_password"), config.get("report_to_email"))
    worker = AutonomousWorker(task_manager=task_mgr, reporter=reporter_obj, ai_router=router,
        bot_name=BOT_NAME, workspace_dir=WORKSPACE, tools_list=tools, execute_tool_fn=execute_tool,
        max_calls_per_hour=config.get("max_api_calls_per_hour",20),
        task_interval_seconds=config.get("task_interval_seconds",60))
    asyncio.create_task(worker.work_loop())
    asyncio.create_task(scheduler_loop(app))
    logger.info(f"{BOT_NAME} v6 READY | Router: {'Multi-AI' if router.check_openwebui() else 'Claude-only'}")

def main():
    logger.info(f"Starting {BOT_NAME} v6...")
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    for cmd, fn in [("start",cmd_start),("mission",cmd_mission),("addtask",cmd_addtask),
                    ("status",cmd_status),("tasks",cmd_tasks),("pause",cmd_pause),
                    ("resume",cmd_resume),("report",cmd_report),("models",cmd_models),
                    ("route",cmd_route),("openwebui",cmd_openwebui)]:
        app.add_handler(CommandHandler(cmd, fn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info(f"{BOT_NAME} v6 running!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
