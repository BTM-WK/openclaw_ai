# -*- coding: utf-8 -*-
"""
WK관우 v5.0 — Autonomous Agent
WK마케팅그룹 | 2025
Claude Tool Use 기반 자율 에이전트
"""
import json, os, sys, glob, shutil, logging, subprocess, threading
import concurrent.futures, asyncio
from datetime import datetime
from pathlib import Path
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes)
import anthropic

# ══ 설정 ══
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
OPENCLAW_ROOT = os.path.dirname(BOT_DIR)
CONFIG_PATH = os.path.join(BOT_DIR, "config.json")
JOBS_DIR = os.path.join(OPENCLAW_ROOT, "jobs")
WORKSPACE_DIR = os.path.join(OPENCLAW_ROOT, "workspace")
os.makedirs(JOBS_DIR, exist_ok=True)
os.makedirs(WORKSPACE_DIR, exist_ok=True)

if not os.path.exists(CONFIG_PATH):
    print("config.json missing!"); sys.exit(1)
with open(CONFIG_PATH, 'r', encoding='utf-8') as f: CONFIG = json.load(f)

TELEGRAM_TOKEN = CONFIG["telegram_token"]
ANTHROPIC_API_KEY = CONFIG["anthropic_api_key"]
BOT_NAME = CONFIG.get("bot_name", "WK관우")
ALLOWED_USERS = CONFIG.get("allowed_users", [])
MODEL = CONFIG.get("model", "claude-sonnet-4-20250514")
WORKSPACE = CONFIG.get("workspace", WORKSPACE_DIR)

SYSTEM_PROMPT = f"""너는 '{BOT_NAME}'이라는 이름의 AI 에이전트야.
너는 이 PC에서 직접 파일을 읽고, 쓰고, 실행할 수 있는 능력이 있어.
사용자가 요청하면 적극적으로 도구를 활용해서 작업을 수행해.
OPENCLAW 루트: {OPENCLAW_ROOT}
작업 범위: {WORKSPACE}
현재 시간: 매 요청 시 자동 갱신
운영체제: Windows
규칙:
1. 파일 작업 전 반드시 경로 확인
2. 위험한 시스템 명령은 사용자 확인 후 실행
3. 작업 결과를 간결하게 보고
4. 한국어로 대화"""

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO,
    handlers=[logging.FileHandler(os.path.join(BOT_DIR,"bot.log"),encoding='utf-8'),logging.StreamHandler()])
logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
conversations = {}
MAX_HISTORY = 30

# ══ 도구 정의 ══
TOOLS = [
    {"name":"list_directory","description":"디렉토리의 파일/폴더 목록을 확인한다.",
     "input_schema":{"type":"object","properties":{"path":{"type":"string","description":"탐색할 경로"},
     "recursive":{"type":"boolean","description":"하위 탐색","default":False},
     "pattern":{"type":"string","description":"파일명 필터","default":"*"}},"required":["path"]}},
    {"name":"read_file","description":"파일 내용을 읽는다. 텍스트 파일 읽기 가능.",
     "input_schema":{"type":"object","properties":{"path":{"type":"string","description":"파일 경로"},
     "max_lines":{"type":"integer","description":"최대 줄수","default":200},
     "encoding":{"type":"string","description":"인코딩","default":"utf-8"}},"required":["path"]}},
    {"name":"write_file","description":"파일을 생성하거나 덮어쓴다.",
     "input_schema":{"type":"object","properties":{"path":{"type":"string","description":"파일 경로"},
     "content":{"type":"string","description":"내용"},
     "mode":{"type":"string","enum":["write","append"],"default":"write"}},"required":["path","content"]}},
    {"name":"edit_file","description":"기존 파일의 특정 텍스트를 찾아서 교체한다.",
     "input_schema":{"type":"object","properties":{"path":{"type":"string","description":"파일 경로"},
     "old_text":{"type":"string","description":"찾을 텍스트"},
     "new_text":{"type":"string","description":"교체 텍스트"}},"required":["path","old_text","new_text"]}},
    {"name":"run_command","description":"시스템 명령어를 실행한다.",
     "input_schema":{"type":"object","properties":{"command":{"type":"string","description":"명령어"},
     "timeout":{"type":"integer","description":"최대 시간(초)","default":60},
     "cwd":{"type":"string","description":"작업 디렉토리","default":""}},"required":["command"]}},
    {"name":"run_python","description":"Python 코드를 실행하고 결과를 반환한다.",
     "input_schema":{"type":"object","properties":{"code":{"type":"string","description":"Python 코드"},
     "timeout":{"type":"integer","description":"최대 시간(초)","default":120}},"required":["code"]}},
    {"name":"search_files","description":"파일명이나 내용으로 파일을 검색한다.",
     "input_schema":{"type":"object","properties":{"directory":{"type":"string","description":"검색 디렉토리"},
     "filename_pattern":{"type":"string","description":"파일명 패턴","default":"*"},
     "content_keyword":{"type":"string","description":"내용 키워드","default":""},
     "max_results":{"type":"integer","description":"최대 결과","default":30}},"required":["directory"]}},
    {"name":"file_info","description":"파일의 상세 정보를 확인한다.",
     "input_schema":{"type":"object","properties":{"path":{"type":"string","description":"경로"}},"required":["path"]}},
    {"name":"copy_move_file","description":"파일이나 폴더를 복사하거나 이동한다.",
     "input_schema":{"type":"object","properties":{"source":{"type":"string","description":"원본"},
     "destination":{"type":"string","description":"대상"},
     "action":{"type":"string","enum":["copy","move"],"default":"copy"}},"required":["source","destination"]}},
    {"name":"create_directory","description":"새 디렉토리를 생성한다.",
     "input_schema":{"type":"object","properties":{"path":{"type":"string","description":"경로"}},"required":["path"]}},
    {"name":"delete_file","description":"파일이나 빈 폴더를 삭제한다.",
     "input_schema":{"type":"object","properties":{"path":{"type":"string","description":"경로"}},"required":["path"]}}
]

# ══ 도구 실행 ══
def format_size(b):
    if b<1024: return f"{b}B"
    elif b<1024**2: return f"{b/1024:.1f}KB"
    elif b<1024**3: return f"{b/1024**2:.1f}MB"
    else: return f"{b/1024**3:.1f}GB"

def execute_tool(name, inp):
    try:
        fn={"list_directory":tool_list_directory,"read_file":tool_read_file,"write_file":tool_write_file,
            "edit_file":tool_edit_file,"run_command":tool_run_command,"run_python":tool_run_python,
            "search_files":tool_search_files,"file_info":tool_file_info,"copy_move_file":tool_copy_move_file,
            "create_directory":tool_create_directory,"delete_file":tool_delete_file}.get(name)
        return fn(**inp) if fn else f"Unknown tool: {name}"
    except Exception as e: return f"Tool error ({name}): {str(e)}"

def tool_list_directory(path, recursive=False, pattern="*"):
    path=os.path.expanduser(path)
    if not os.path.exists(path): return f"Path not found: {path}"
    result=[]
    try:
        if recursive:
            for root,dirs,files in os.walk(path):
                depth=root.replace(path,'').count(os.sep)
                if depth>1: continue
                indent="  "*depth; result.append(f"{indent}[DIR] {os.path.basename(root)}/")
                for f in sorted(files):
                    if glob.fnmatch.fnmatch(f,pattern):
                        try: sz=format_size(os.path.getsize(os.path.join(root,f)))
                        except: sz="?"
                        result.append(f"{indent}  [F] {f} ({sz})")
        else:
            for item in sorted(os.listdir(path)):
                full=os.path.join(path,item)
                if os.path.isdir(full):
                    try: cnt=len(os.listdir(full))
                    except: cnt="?"
                    result.append(f"[DIR] {item}/ ({cnt})")
                elif glob.fnmatch.fnmatch(item,pattern):
                    try: sz=format_size(os.path.getsize(full))
                    except: sz="?"
                    result.append(f"[F] {item} ({sz})")
        if not result: return f"{path} - (empty)"
        return f"{path} - {len(result)} items\n"+"\n".join(result[:100])
    except PermissionError: return f"Access denied: {path}"

def tool_read_file(path, max_lines=200, encoding="utf-8"):
    path=os.path.expanduser(path)
    if not os.path.exists(path): return f"File not found: {path}"
    size=os.path.getsize(path)
    if size>5*1024*1024: return f"File too large ({format_size(size)})"
    bin_ext={'.exe','.dll','.zip','.rar','.7z','.png','.jpg','.jpeg','.gif','.mp3','.mp4','.pptx','.xlsx','.docx','.hwp'}
    ext=os.path.splitext(path)[1].lower()
    if ext in bin_ext: return f"Binary file ({ext}, {format_size(size)}): {path}"
    for enc in [encoding,'utf-8','cp949','euc-kr','utf-8-sig']:
        try:
            with open(path,'r',encoding=enc) as f: lines=f.readlines()
            total=len(lines); content="".join(lines[:max_lines])
            h=f"{os.path.basename(path)} ({total}lines, {format_size(size)}, {enc})\n"
            if total>max_lines: h+=f"Showing {max_lines}/{total} lines\n"
            return h+"="*40+"\n"+content[:8000]
        except: continue
    return f"Cannot read (encoding): {path}"

def tool_write_file(path, content, mode="write"):
    path=os.path.expanduser(path)
    d=os.path.dirname(path)
    if d: os.makedirs(d,exist_ok=True)
    with open(path,'w' if mode=='write' else 'a',encoding='utf-8') as f: f.write(content)
    return f"OK {'created' if mode=='write' else 'appended'}: {path} ({format_size(os.path.getsize(path))})"

def tool_edit_file(path, old_text, new_text):
    path=os.path.expanduser(path)
    if not os.path.exists(path): return f"Not found: {path}"
    for enc in ['utf-8','cp949','euc-kr','utf-8-sig']:
        try:
            with open(path,'r',encoding=enc) as f: content=f.read()
            break
        except: continue
    else: return f"Cannot read: {path}"
    cnt=content.count(old_text)
    if cnt==0: return f"Text not found: {old_text[:100]}"
    with open(path,'w',encoding=enc) as f: f.write(content.replace(old_text,new_text))
    return f"OK {cnt} replaced: {path}"

def tool_run_command(command, timeout=60, cwd=""):
    wd=cwd if cwd and os.path.exists(cwd) else BOT_DIR
    try:
        r=subprocess.run(command,shell=True,capture_output=True,text=True,timeout=timeout,
                         encoding='utf-8',errors='replace',cwd=wd)
        out=r.stdout[-3000:] if r.stdout else ""; err=r.stderr[-1000:] if r.stderr else ""
        res=f"CMD: {command}\nCWD: {wd}\nCode: {r.returncode}\n"
        if out: res+=f"--- output ---\n{out}\n"
        if err: res+=f"--- error ---\n{err}\n"
        if not out and not err: res+="(no output)\n"
        return res
    except subprocess.TimeoutExpired: return f"Timeout ({timeout}s): {command}"
    except Exception as e: return f"Error: {e}"

def tool_run_python(code, timeout=120):
    tmp=os.path.join(BOT_DIR,"_temp_exec.py")
    with open(tmp,'w',encoding='utf-8') as f: f.write(code)
    try:
        r=subprocess.run([sys.executable,tmp],capture_output=True,text=True,timeout=timeout,
                         encoding='utf-8',errors='replace',cwd=BOT_DIR)
        out=r.stdout[-3000:] if r.stdout else ""; err=r.stderr[-1000:] if r.stderr else ""
        res=f"Python (code:{r.returncode})\n"
        if out: res+=f"--- output ---\n{out}\n"
        if err: res+=f"--- error ---\n{err}\n"
        if not out and not err: res+="(no output)\n"
        return res
    except subprocess.TimeoutExpired: return f"Timeout ({timeout}s)"
    finally:
        if os.path.exists(tmp): os.remove(tmp)

def tool_search_files(directory, filename_pattern="*", content_keyword="", max_results=30):
    directory=os.path.expanduser(directory)
    if not os.path.exists(directory): return f"Dir not found: {directory}"
    results=[]; text_ext={'.txt','.py','.md','.csv','.json','.bat','.log','.html','.css','.js','.xml','.ini','.yaml','.yml'}
    skip={'.git','node_modules','__pycache__','venv','AppData','.vscode'}
    for root,dirs,files in os.walk(directory):
        dirs[:]=[d for d in dirs if d not in skip and not d.startswith('.')]
        for fn in files:
            if not glob.fnmatch.fnmatch(fn,filename_pattern): continue
            fp=os.path.join(root,fn)
            if content_keyword:
                ext=os.path.splitext(fn)[1].lower()
                if ext not in text_ext: continue
                try:
                    for enc in ['utf-8','cp949']:
                        try:
                            with open(fp,'r',encoding=enc) as f: txt=f.read(100000)
                            break
                        except: continue
                    else: continue
                    if content_keyword.lower() not in txt.lower(): continue
                except: continue
            try:
                sz=os.path.getsize(fp); mt=datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d %H:%M")
                results.append({"path":fp,"name":fn,"size":sz,"mod":mt})
            except: pass
            if len(results)>=max_results: break
        if len(results)>=max_results: break
    if not results: return f"No results ({directory}, {filename_pattern})"
    r=f"Found {len(results)} files in {directory}\n"
    if content_keyword: r+=f"Keyword: {content_keyword}\n"
    r+="="*40+"\n"
    for x in results: r+=f"[F] {x['name']} ({format_size(x['size'])}) {x['mod']}\n   {x['path']}\n"
    return r

def tool_file_info(path):
    path=os.path.expanduser(path)
    if not os.path.exists(path): return f"Not found: {path}"
    st=os.stat(path); isd=os.path.isdir(path)
    info=f"{'[DIR]' if isd else '[F]'} {os.path.basename(path)}\n  Path: {path}\n"
    info+=f"  Type: {'folder' if isd else os.path.splitext(path)[1] or 'none'}\n"
    info+=f"  Size: {format_size(st.st_size)}\n"
    info+=f"  Created: {datetime.fromtimestamp(st.st_ctime).strftime('%Y-%m-%d %H:%M')}\n"
    info+=f"  Modified: {datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M')}\n"
    if isd:
        items=os.listdir(path)
        info+=f"  Contents: {sum(1 for i in items if os.path.isdir(os.path.join(path,i)))} dirs, {sum(1 for i in items if os.path.isfile(os.path.join(path,i)))} files\n"
    return info

def tool_copy_move_file(source, destination, action="copy"):
    source,destination=os.path.expanduser(source),os.path.expanduser(destination)
    if not os.path.exists(source): return f"Source not found: {source}"
    d=os.path.dirname(destination)
    if d: os.makedirs(d,exist_ok=True)
    if action=="copy":
        if os.path.isdir(source): shutil.copytree(source,destination)
        else: shutil.copy2(source,destination)
        return f"OK copied: {source} -> {destination}"
    else:
        shutil.move(source,destination)
        return f"OK moved: {source} -> {destination}"

def tool_create_directory(path):
    path=os.path.expanduser(path); os.makedirs(path,exist_ok=True)
    return f"OK created: {path}"

def tool_delete_file(path):
    path=os.path.expanduser(path)
    if not os.path.exists(path): return f"Not found: {path}"
    if os.path.isfile(path): os.remove(path); return f"OK deleted: {path}"
    elif os.path.isdir(path):
        if len(os.listdir(path))==0: os.rmdir(path); return f"OK deleted empty dir: {path}"
        return f"Dir not empty ({len(os.listdir(path))} items)"

# ══ 에이전트 루프 ══
MAX_TOOL_ROUNDS = 15

def agent_loop(user_id, user_message, progress_callback=None):
    if user_id not in conversations: conversations[user_id]=[]
    conversations[user_id].append({"role":"user","content":user_message})
    if len(conversations[user_id])>MAX_HISTORY:
        conversations[user_id]=conversations[user_id][-MAX_HISTORY:]
    sys_prompt=SYSTEM_PROMPT+f"\nCurrent time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    tool_log=[]
    for rnd in range(MAX_TOOL_ROUNDS):
        try:
            response=client.messages.create(model=MODEL,max_tokens=4096,system=sys_prompt,
                                            tools=TOOLS,messages=conversations[user_id])
        except Exception as e:
            logger.error(f"API error: {e}"); return f"Claude API Error: {str(e)}"
        if response.stop_reason=="tool_use":
            ac=response.content; conversations[user_id].append({"role":"assistant","content":ac})
            tr=[]
            for block in ac:
                if block.type=="tool_use":
                    logger.info(f"Tool [{rnd+1}] {block.name}")
                    if progress_callback: progress_callback(f"Tool: {block.name} ({rnd+1}/{MAX_TOOL_ROUNDS})")
                    result=execute_tool(block.name,block.input)
                    tool_log.append(f"[{rnd+1}] {block.name} -> {result[:80]}...")
                    tr.append({"type":"tool_result","tool_use_id":block.id,"content":result[:10000]})
            conversations[user_id].append({"role":"user","content":tr})
        elif response.stop_reason=="end_turn":
            text="".join(b.text for b in response.content if hasattr(b,'text'))
            conversations[user_id].append({"role":"assistant","content":text})
            if tool_log:
                text+=f"\n\n=== Tool Log ({len(tool_log)}) ==="
                for log in tool_log: text+=f"\n{log}"
            return text
        else:
            text="".join(b.text for b in response.content if hasattr(b,'text'))
            conversations[user_id].append({"role":"assistant","content":text or "(no response)"})
            return text or "(no response)"
    return "Tool limit reached (15)"

# ══ 텔레그램 핸들러 ══
def is_allowed(uid): return not ALLOWED_USERS or uid in ALLOWED_USERS
JOBS_REGISTRY=os.path.join(JOBS_DIR,"jobs_registry.json")
pending_jobs={}

def load_jobs():
    if os.path.exists(JOBS_REGISTRY):
        with open(JOBS_REGISTRY,'r',encoding='utf-8') as f: return json.load(f)
    return {}

def save_jobs(jobs):
    with open(JOBS_REGISTRY,'w',encoding='utf-8') as f: json.dump(jobs,f,ensure_ascii=False,indent=2)

def build_menu():
    kb=[[f"{BOT_NAME} 질문","STATUS"],["CLEAR","JOBS"]]
    jobs=load_jobs(); row=[]
    for k,v in jobs.items():
        row.append(v.get("button",k))
        if len(row)==2: kb.append(row); row=[]
    if row: kb.append(row)
    return ReplyKeyboardMarkup(kb,resize_keyboard=True)

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): await update.message.reply_text("Access denied"); return
    await update.message.reply_text(
        f"{BOT_NAME} v5.0 - Autonomous Agent\n\n"
        f"AI can directly control this PC!\n"
        f"  File browse/read/write\n  Search\n  Code execution\n  System commands\n\n"
        f"Use natural language.\nModel: {MODEL}",reply_markup=build_menu())

async def status(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    uid=update.effective_user.id; jobs=load_jobs()
    try:
        import psutil; si=f"CPU: {psutil.cpu_percent(1)}% | RAM: {psutil.virtual_memory().percent}%"
    except: si="psutil not installed"
    await update.message.reply_text(
        f"{BOT_NAME} v5.0\n{'='*30}\n{MODEL}\nTools: {len(TOOLS)}\n"
        f"History: {len(conversations.get(uid,[]))}\nJobs: {len(jobs)}\n"
        f"{si}\n{WORKSPACE}\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

async def clear(update:Update,context:ContextTypes.DEFAULT_TYPE):
    conversations.pop(update.effective_user.id,None)
    await update.message.reply_text("Cleared!",reply_markup=build_menu())

async def change_model(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    kb=[[InlineKeyboardButton("Sonnet",callback_data="model_sonnet")],
        [InlineKeyboardButton("Opus",callback_data="model_opus")],
        [InlineKeyboardButton("Haiku",callback_data="model_haiku")]]
    await update.message.reply_text("Model:",reply_markup=InlineKeyboardMarkup(kb))

async def add_job(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    parts=update.message.text.split(maxsplit=3)
    if len(parts)<4: await update.message.reply_text("/addjob key button desc"); return
    _,key,btn,desc=parts
    pending_jobs[update.effective_user.id]={"key":key,"button":btn,"desc":desc}
    await update.message.reply_text(f"'{key}' ready. Send Python code. (/canceljob)")

async def list_jobs(update:Update,context:ContextTypes.DEFAULT_TYPE):
    jobs=load_jobs()
    if not jobs: await update.message.reply_text("No jobs"); return
    t="Jobs\n"+"="*30+"\n"
    for k,v in jobs.items(): t+=f"\n{v.get('button',k)} ({k})\n  {v.get('desc','')}\n"
    await update.message.reply_text(t)

async def remove_job(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    parts=update.message.text.split()
    if len(parts)<2: await update.message.reply_text("/removejob key"); return
    key=parts[1]; jobs=load_jobs()
    if key in jobs:
        del jobs[key]; save_jobs(jobs)
        f=os.path.join(JOBS_DIR,f"{key}.py")
        if os.path.exists(f): os.remove(f)
        await update.message.reply_text(f"'{key}' removed",reply_markup=build_menu())
    else: await update.message.reply_text(f"'{key}' not found")

async def cancel_job(update:Update,context:ContextTypes.DEFAULT_TYPE):
    pending_jobs.pop(update.effective_user.id,None)
    await update.message.reply_text("Cancelled")

async def update_code(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    parts=update.message.text.split()
    if len(parts)<2: await update.message.reply_text("/updatecode key"); return
    key=parts[1]; jobs=load_jobs()
    if key not in jobs: await update.message.reply_text(f"'{key}' not found"); return
    pending_jobs[update.effective_user.id]={"key":key,"button":jobs[key].get("button",key),
        "desc":jobs[key].get("desc",""),"update_only":True}
    await update.message.reply_text(f"'{key}' send new code.")

def run_job_bg(job_key,chat_id,bot):
    jf=os.path.join(JOBS_DIR,f"{job_key}.py")
    try:
        r=subprocess.run([sys.executable,jf],capture_output=True,text=True,timeout=600,
                         encoding='utf-8',errors='replace',cwd=JOBS_DIR)
        msg=f"{job_key} done!\n{r.stdout[-1500:]}" if r.returncode==0 else f"{job_key}\n{r.stdout[-800:]}\n{r.stderr[-500:]}"
    except subprocess.TimeoutExpired: msg=f"{job_key} timeout"
    except Exception as e: msg=f"{job_key}: {e}"
    loop=asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    loop.run_until_complete(bot.send_message(chat_id=chat_id,text=msg[:4000])); loop.close()

async def callback_handler(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); data=q.data
    if data.startswith("model_"):
        global MODEL
        m={"model_sonnet":"claude-sonnet-4-20250514","model_opus":"claude-opus-4-20250514","model_haiku":"claude-haiku-4-20250514"}
        MODEL=m.get(data,MODEL); CONFIG["model"]=MODEL
        with open(CONFIG_PATH,'w',encoding='utf-8') as f: json.dump(CONFIG,f,ensure_ascii=False,indent=2)
        await q.edit_message_text(f"Model: {MODEL}"); return
    if data.startswith("run_"):
        key=data.replace("run_",""); jf=os.path.join(JOBS_DIR,f"{key}.py")
        if not os.path.exists(jf): await q.edit_message_text(f"{key}.py not found"); return
        await q.edit_message_text(f"{key} running...")
        t=threading.Thread(target=run_job_bg,args=(key,q.message.chat_id,context.bot)); t.daemon=True; t.start(); return
    if data=="cancel_run": await q.edit_message_text("Cancelled")

async def handle_message(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): await update.message.reply_text("Access denied"); return
    uid=update.effective_user.id; text=update.message.text

    if uid in pending_jobs:
        code_kw=['import ','def ','class ','print(','from ','#!','# -*-']
        if any(text.strip().startswith(k) for k in code_kw):
            ji=pending_jobs[uid]; jf=os.path.join(JOBS_DIR,f"{ji['key']}.py")
            with open(jf,'w',encoding='utf-8') as f: f.write(text)
            if not ji.get("update_only"):
                jobs=load_jobs()
                jobs[ji["key"]]={"button":ji["button"],"desc":ji["desc"],"file":f"{ji['key']}.py",
                                 "created":datetime.now().strftime("%Y-%m-%d %H:%M")}
                save_jobs(jobs)
            del pending_jobs[uid]
            await update.message.reply_text(f"'{ji['key']}' done!",reply_markup=build_menu()); return
        else: await update.message.reply_text("Send Python code or /canceljob"); return

    if text==f"{BOT_NAME} 질문": await update.message.reply_text("Send message!"); return
    if text=="STATUS": await status(update,context); return
    if text=="CLEAR": await clear(update,context); return
    if text=="JOBS":
        await update.message.reply_text("JOBS\n/addjob key button desc\n/listjobs\n/removejob key\n/updatecode key"); return

    jobs=load_jobs()
    for k,v in jobs.items():
        if text==v.get("button",""):
            kb=[[InlineKeyboardButton("RUN",callback_data=f"run_{k}"),
                 InlineKeyboardButton("CANCEL",callback_data="cancel_run")]]
            await update.message.reply_text(f"{v.get('button',k)}\n{v.get('desc','')}\n\nRun?",
                                            reply_markup=InlineKeyboardMarkup(kb)); return

    thinking=await update.message.reply_text("Analyzing...")
    with concurrent.futures.ThreadPoolExecutor() as ex:
        future=ex.submit(agent_loop,uid,text); result=future.result()
    try: await thinking.delete()
    except: pass
    if len(result)>4000:
        chunks=[result[i:i+4000] for i in range(0,len(result),4000)]
        for i,c in enumerate(chunks):
            if i==len(chunks)-1: await update.message.reply_text(c,reply_markup=build_menu())
            else: await update.message.reply_text(c)
    else: await update.message.reply_text(result,reply_markup=build_menu())

def main():
    sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    sys.stderr.reconfigure(encoding='utf-8',errors='replace')
    print("="*50)
    print(f"  [BOT] {BOT_NAME} v5.0 - Autonomous Agent")
    print(f"  Model: {MODEL}")
    print(f"  Tools: {len(TOOLS)}")
    print(f"  Root: {OPENCLAW_ROOT}")
    print("="*50)
    app=Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("status",status))
    app.add_handler(CommandHandler("clear",clear))
    app.add_handler(CommandHandler("model",change_model))
    app.add_handler(CommandHandler("addjob",add_job))
    app.add_handler(CommandHandler("listjobs",list_jobs))
    app.add_handler(CommandHandler("removejob",remove_job))
    app.add_handler(CommandHandler("canceljob",cancel_job))
    app.add_handler(CommandHandler("updatecode",update_code))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_message))
    print(f"\n[OK] {BOT_NAME} v5.0 running!\n")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__": main()
