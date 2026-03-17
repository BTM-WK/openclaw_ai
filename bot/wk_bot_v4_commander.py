# ============================================================
# OPENCLAW AI Unit - COMMANDER BOT v4.0
# 유비가 방통 부재 시 임시 사령관 역할 수행
#
# 핵심 기능:
#   1. 매일 스케줄에 따라 각 봇에게 임무 자동 지시
#   2. workspace 결과물 자동 수집 및 품질 검수
#   3. 기준 미달 시 해당 봇에게 재작업 지시
#   4. 대표님께 하루 1회 요약 보고 (텔레그램)
#   5. 대표님 확인 필요 항목만 ⚠️ 태그로 분리
# ============================================================
import os, sys, json, subprocess, platform, psutil, asyncio, logging
import fnmatch, shutil, urllib.request, urllib.parse, re, base64
from datetime import datetime, time as dtime
from collections import deque

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import anthropic

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f: return json.load(f)

CFG = load_config()
TELEGRAM_TOKEN   = CFG["telegram_token"]
ANTHROPIC_API_KEY = CFG["anthropic_api_key"]
BOT_NAME         = CFG.get("bot_name", "WK유비")
MY_NAMES         = CFG.get("my_names", ["유비"])
BOT_ROLE         = CFG.get("bot_role", "전략/기획")
LEADER_NAME      = CFG.get("leader_name", "WK방통")
SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
BASE_DIR         = os.path.dirname(SCRIPT_DIR)
WORKSPACE        = CFG.get("workspace", os.path.join(BASE_DIR, "workspace"))
LOG_DIR          = CFG.get("log_dir", os.path.join(BASE_DIR, "logs"))
OWNER_CHAT_ID    = CFG.get("owner_chat_id")
TEAM_BOT_IDS     = CFG.get("team_bot_ids", {})
MODEL            = "claude-sonnet-4-6"
RELAY_TAG        = "[RELAY]"
TASK_TAG         = "[MISSION]"
REPORT_TAG       = "[REPORT]"

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(WORKSPACE, exist_ok=True)
os.makedirs(os.path.join(WORKSPACE, "drafts"), exist_ok=True)
os.makedirs(os.path.join(WORKSPACE, "reports"), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'commander.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(BOT_NAME)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
BOT_USERNAME = ""
dm_history = {}
group_history = {}
dm_activity_log = deque(maxlen=50)
DM_HISTORY_MAX = 20
GROUP_HISTORY_MAX = 50

# ── 에스컬레이션 규칙: 대표님 확인 필요 키워드 ──────────────────
ESCALATE_KEYWORDS = [
    "예산", "금액", "계약", "법무", "신규 클라이언트", "가격",
    "투자", "대출", "채용", "해고", "소송", "특허", "수출 계약"
]

# ── 품질 검수 기준 ──────────────────────────────────────────────
QUALITY_RUBRIC = """
[품질 검수 기준]
공통:
- 분량: 최소 300자 이상 (단순 메모 제외)
- 한국어 기준, 맞춤법 오류 없을 것
- WKMG 또는 피플파이 관련 내용과 연관성 있을 것

콘텐츠(블로그/SNS/뉴스레터):
- 제목 포함 여부
- CTA 문구(행동유도) 포함 여부
- 브랜드 톤앤매너 유지 여부

제안서/보고서:
- 목차 또는 구조 포함 여부
- 클라이언트/상황 맥락 반영 여부
- 핵심 메시지 명확성

리서치/분석:
- 출처 또는 근거 포함 여부
- 핵심 인사이트 요약 포함 여부
"""

# ── 일일 임무 스케줄 정의 ────────────────────────────────────────
# 각 봇이 매일 자동으로 수행할 임무
DAILY_MISSIONS = {
    "WK공명": {
        "chat_id": 8018992962,
        "mission": (
            "오늘의 자동 임무를 수행해줘.\n\n"
            "1. WKMG 브랜드마케팅 컨설팅 관련 블로그 포스팅 초안 1건 작성\n"
            "   - 주제: 최근 마케팅 트렌드 또는 WKMG 서비스 소개\n"
            "   - 분량: 800자 이상\n"
            "   - 저장: {workspace}/drafts/공명_블로그_{date}.md\n\n"
            "2. WKMG 뉴스레터 콘텐츠 아이디어 3개 목록 작성\n"
            "   - 저장: {workspace}/drafts/공명_뉴스레터아이디어_{date}.md\n\n"
            "완료 후 '[REPORT] 공명 임무완료' 로 시작하는 완료 보고 메시지를 보내줘."
        )
    },
    "WK에이트": {
        "chat_id": 8356634124,
        "mission": (
            "오늘의 자동 임무를 수행해줘.\n\n"
            "1. WKMG SNS(인스타그램/블로그) 콘텐츠 텍스트 3건 작성\n"
            "   - 각 200자 내외, 해시태그 포함\n"
            "   - 저장: {workspace}/drafts/에이트_SNS콘텐츠_{date}.md\n\n"
            "2. 교육 프로그램 모집 홍보 문구 2가지 버전 작성\n"
            "   - 저장: {workspace}/drafts/에이트_교육모집문구_{date}.md\n\n"
            "완료 후 '[REPORT] 에이트 임무완료' 로 시작하는 완료 보고 메시지를 보내줘."
        )
    },
    "WK자룡": {
        "chat_id": 8633203908,
        "mission": (
            "오늘의 자동 임무를 수행해줘.\n\n"
            "1. 웹 검색으로 오늘의 마케팅/브랜드 업계 주요 뉴스 5건 수집\n"
            "2. 올리브영/뷰티 시장 경쟁사 동향 조사 (최신 프로모션, 신제품)\n"
            "3. 결과 요약 저장: {workspace}/reports/자룡_시장동향_{date}.md\n\n"
            "완료 후 '[REPORT] 자룡 임무완료' 로 시작하는 완료 보고 메시지를 보내줘."
        )
    },
    "WK관우": {
        "chat_id": 8347664997,
        "mission": (
            "오늘의 자동 임무를 수행해줘.\n\n"
            "1. 공공기관 마케팅 용역 제안서 표준 템플릿 1건 정비\n"
            "   - WKMG 강점 및 실적 반영\n"
            "   - 저장: {workspace}/drafts/관우_제안서템플릿_{date}.md\n\n"
            "2. 신규 영업 대상 리스트업 아이디어 5건 (업종별)\n"
            "   - 저장: {workspace}/drafts/관우_영업리스트_{date}.md\n\n"
            "완료 후 '[REPORT] 관우 임무완료' 로 시작하는 완료 보고 메시지를 보내줘."
        )
    },
    "WK비너스": {
        "chat_id": 8520577635,
        "mission": (
            "오늘의 자동 임무를 수행해줘.\n\n"
            "1. 메디힐리 이번 달 프로모션 기획안 초안 작성\n"
            "   - 직영몰/올리브영/스마트스토어 채널별 전략 포함\n"
            "   - 저장: {workspace}/drafts/비너스_프로모션기획_{date}.md\n\n"
            "2. 메디힐리 제품 중 이달 주력 상품 선정 이유 및 마케팅 포인트 정리\n"
            "   - 저장: {workspace}/drafts/비너스_주력상품분석_{date}.md\n\n"
            "완료 후 '[REPORT] 비너스 임무완료' 로 시작하는 완료 보고 메시지를 보내줘."
        )
    },
    "WK중달": {
        "chat_id": 8384421212,
        "mission": (
            "오늘의 자동 임무를 수행해줘.\n\n"
            "1. 최근 완료 컨설팅 결과보고서 표준 목차 및 템플릿 정비\n"
            "   - 저장: {workspace}/drafts/중달_보고서템플릿_{date}.md\n\n"
            "2. 공공기관 용역 RFP 대응 체크리스트 작성\n"
            "   - 저장: {workspace}/drafts/중달_RFP체크리스트_{date}.md\n\n"
            "완료 후 '[REPORT] 중달 임무완료' 로 시작하는 완료 보고 메시지를 보내줘."
        )
    },
}

# ── 도구 정의 ────────────────────────────────────────────────────
tools = [
    {"name":"explore_directory","description":"List files/dirs","input_schema":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}},
    {"name":"read_file","description":"Read text file","input_schema":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}},
    {"name":"write_file","description":"Write file","input_schema":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}},
    {"name":"run_command","description":"Run system command","input_schema":{"type":"object","properties":{"command":{"type":"string"},"shell":{"type":"string","default":"cmd"}},"required":["command"]}},
    {"name":"run_python","description":"Run Python code","input_schema":{"type":"object","properties":{"code":{"type":"string"}},"required":["code"]}},
    {"name":"web_search","description":"Web search","input_schema":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}},
    {"name":"search_files","description":"Search files by pattern","input_schema":{"type":"object","properties":{"path":{"type":"string"},"pattern":{"type":"string"}},"required":["path","pattern"]}},
]

def execute_tool(name, inp):
    try:
        if name == "explore_directory":
            items = os.listdir(inp["path"]); r = []
            for i in sorted(items):
                f = os.path.join(inp["path"], i)
                r.append(f"[{'DIR' if os.path.isdir(f) else 'FILE'}] {i}")
            return "\n".join(r) or "(empty)"
        elif name == "read_file":
            with open(inp["path"],"r",encoding="utf-8",errors="replace") as f: return f.read(50000)
        elif name == "write_file":
            os.makedirs(os.path.dirname(inp["path"]) or ".", exist_ok=True)
            with open(inp["path"],"w",encoding="utf-8") as f: f.write(inp["content"])
            return f"Written: {inp['path']}"
        elif name == "run_command":
            sh = inp.get("shell","cmd")
            if sh == "powershell":
                r = subprocess.run(["powershell","-NoProfile","-Command",inp["command"]],capture_output=True,text=True,timeout=30,encoding="utf-8",errors="replace")
            else:
                r = subprocess.run(inp["command"],shell=True,capture_output=True,text=True,timeout=30,encoding="utf-8",errors="replace")
            return (r.stdout+r.stderr)[:4000] or "(no output)"
        elif name == "run_python":
            sp = os.path.join(WORKSPACE,"_t.py")
            with open(sp,"w",encoding="utf-8") as f: f.write(inp["code"])
            r = subprocess.run([sys.executable,sp],capture_output=True,text=True,timeout=60,encoding="utf-8",errors="replace")
            return (r.stdout+r.stderr)[:4000] or "(no output)"
        elif name == "web_search":
            q=urllib.parse.quote(inp["query"]); req=urllib.request.Request(f"https://html.duckduckgo.com/html/?q={q}",headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=10) as resp: html=resp.read().decode("utf-8",errors="replace")
            results=re.findall(r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>',html)
            snippets=re.findall(r'<a class="result__snippet".*?>(.*?)</a>',html)
            out = [f"{i+1}. {re.sub(r'<.*?>','',t)}\n   {h}" for i,(h,t) in enumerate(results[:5])]
            return "\n\n".join(out) or "No results."
        elif name == "search_files":
            m = []
            for root,_,files in os.walk(inp["path"]):
                for n in files:
                    if fnmatch.fnmatch(n.lower(),inp["pattern"].lower()): m.append(os.path.join(root,n))
                    if len(m)>=50: break
            return "\n".join(m) or "No files found."
        return f"Unknown tool: {name}"
    except Exception as e: return f"Error: {e}"

# ── Claude API 호출 ──────────────────────────────────────────────
def call_claude(system_prompt, user_message, use_tools=False):
    messages = [{"role":"user","content":user_message}]
    kwargs = dict(model=MODEL, max_tokens=4096, system=system_prompt, messages=messages)
    if use_tools: kwargs["tools"] = tools
    full_response = ""
    try:
        while True:
            response = client.messages.create(**kwargs)
            tool_results, text_parts = [], []
            for block in response.content:
                if block.type == "text": text_parts.append(block.text)
                elif block.type == "tool_use":
                    tr = execute_tool(block.name, block.input)
                    tool_results.append({"type":"tool_result","tool_use_id":block.id,"content":tr})
            if text_parts: full_response += "\n".join(text_parts)
            if response.stop_reason == "tool_use" and tool_results:
                kwargs["messages"].append({"role":"assistant","content":response.content})
                kwargs["messages"].append({"role":"user","content":tool_results})
            else: break
    except Exception as e:
        logger.error(f"Claude error: {e}"); full_response = f"[ERROR] {e}"
    return full_response

def chat_with_claude(user_id, message, is_group=False):
    system_prompt = (
        f"당신은 {BOT_NAME}입니다. WK AI전략단의 임시 사령관 역할을 수행 중입니다.\n"
        f"원래 역할: {BOT_ROLE}\n"
        f"현재 임무: 방통 부재 시 팀 전체 운영 총괄\n\n"
        f"[팀원]\n"
        + "\n".join([f"  - {k}" for k in TEAM_BOT_IDS.keys()]) +
        f"\n\n[원칙]\n"
        f"- 항상 한국어로 답변\n"
        f"- 대표님 확인이 필요한 사항은 ⚠️ 표시\n"
        f"- workspace: {WORKSPACE}\n"
    )
    if not is_group:
        if user_id not in dm_history: dm_history[user_id] = []
        dm_history[user_id].append({"role":"user","content":message})
        if len(dm_history[user_id]) > DM_HISTORY_MAX*2:
            dm_history[user_id] = dm_history[user_id][-(DM_HISTORY_MAX*2):]
        messages = dm_history[user_id].copy()
    else:
        messages = [{"role":"user","content":message}]
    try:
        response = client.messages.create(
            model=MODEL, max_tokens=4096,
            system=system_prompt, tools=tools, messages=messages
        )
        tool_results, text_parts = [], []
        full_response = ""
        while True:
            for block in response.content:
                if block.type == "text": text_parts.append(block.text)
                elif block.type == "tool_use":
                    tr = execute_tool(block.name, block.input)
                    tool_results.append({"type":"tool_result","tool_use_id":block.id,"content":tr})
            if text_parts: full_response += "\n".join(text_parts)
            if response.stop_reason == "tool_use" and tool_results:
                messages.append({"role":"assistant","content":response.content})
                messages.append({"role":"user","content":tool_results})
                tool_results, text_parts = [], []
                response = client.messages.create(model=MODEL,max_tokens=4096,system=system_prompt,tools=tools,messages=messages)
            else: break
        if not is_group:
            dm_history[user_id] = messages
            dm_history[user_id].append({"role":"assistant","content":full_response})
        return full_response
    except Exception as e: return f"[ERROR] {e}"

# ── 핵심: 품질 검수 함수 ─────────────────────────────────────────
def quality_check(file_path, bot_name, mission_type="general"):
    """결과물 파일을 읽고 품질 검수 후 (pass/fail, feedback) 반환"""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if len(content.strip()) < 100:
            return False, f"내용이 너무 짧습니다 (현재 {len(content)}자). 최소 300자 이상 작성 필요."
        system = (
            "당신은 WK마케팅그룹의 품질 검수 AI입니다.\n"
            "결과물을 검토하고 합격/불합격을 판정해주세요.\n\n"
            + QUALITY_RUBRIC
        )
        prompt = (
            f"다음은 {bot_name}이 작성한 결과물입니다.\n"
            f"임무 유형: {mission_type}\n\n"
            f"--- 결과물 ---\n{content[:3000]}\n---\n\n"
            f"검수 결과를 다음 형식으로만 답해주세요:\n"
            f"RESULT: PASS 또는 FAIL\n"
            f"REASON: (한 문장으로 이유)\n"
            f"FEEDBACK: (개선이 필요한 경우 구체적인 지시사항, 합격이면 '없음')"
        )
        resp = call_claude(system, prompt, use_tools=False)
        lines = resp.strip().split("\n")
        result_line = next((l for l in lines if l.startswith("RESULT:")), "RESULT: FAIL")
        feedback_line = next((l for l in lines if l.startswith("FEEDBACK:")), "FEEDBACK: 재작업 필요")
        passed = "PASS" in result_line.upper()
        feedback = feedback_line.replace("FEEDBACK:", "").strip()
        return passed, feedback
    except Exception as e:
        return False, f"검수 오류: {e}"

def needs_escalation(content):
    """대표님 확인이 필요한 내용인지 판단"""
    content_lower = content.lower()
    for kw in ESCALATE_KEYWORDS:
        if kw in content_lower: return True, kw
    return False, None

# ── 임무 발송 함수 ────────────────────────────────────────────────
async def send_mission(bot, bot_name, chat_id, mission_text):
    """특정 봇에게 임무 메시지 발송"""
    date_str = datetime.now().strftime("%Y%m%d")
    mission = mission_text.replace("{workspace}", WORKSPACE).replace("{date}", date_str)
    full_msg = f"{TASK_TAG} [{bot_name}에게 임무 지시]\n\n{mission}"
    try:
        await bot.send_message(chat_id=chat_id, text=full_msg)
        logger.info(f"[MISSION SENT] → {bot_name}")
        return True
    except Exception as e:
        logger.error(f"[MISSION FAIL] → {bot_name}: {e}")
        return False

# ── 결과물 수집 함수 ─────────────────────────────────────────────
def collect_today_results():
    """오늘 생성된 결과물 파일 목록 수집"""
    today = datetime.now().strftime("%Y%m%d")
    results = []
    for folder in ["drafts", "reports"]:
        path = os.path.join(WORKSPACE, folder)
        if not os.path.exists(path): continue
        for f in os.listdir(path):
            if today in f and f.endswith((".md", ".txt", ".docx")):
                results.append({
                    "path": os.path.join(path, f),
                    "name": f,
                    "folder": folder,
                    "bot": f.split("_")[0] if "_" in f else "unknown"
                })
    return results

# ── 핵심: 스케줄 작업 ─────────────────────────────────────────────

async def job_send_daily_missions(app):
    """오전 7:00 — 모든 봇에게 오늘의 임무 자동 발송"""
    logger.info("[SCHEDULE] 일일 임무 발송 시작")
    sent, failed = [], []
    for bot_name, info in DAILY_MISSIONS.items():
        ok = await send_mission(app.bot, bot_name, info["chat_id"], info["mission"])
        if ok: sent.append(bot_name)
        else: failed.append(bot_name)
        await asyncio.sleep(1)
    # 대표님께 임무 발송 완료 알림
    if OWNER_CHAT_ID:
        msg = (
            f"📋 [{datetime.now().strftime('%m/%d')} 오전 7:00] 일일 임무 발송 완료\n\n"
            f"✅ 발송 성공: {', '.join(sent)}\n"
        )
        if failed: msg += f"❌ 발송 실패: {', '.join(failed)}\n"
        msg += f"\n⏰ 결과 수집·보고: 오후 3:00"
        try: await app.bot.send_message(chat_id=OWNER_CHAT_ID, text=msg)
        except Exception as e: logger.error(f"Owner notify fail: {e}")
    logger.info(f"[SCHEDULE] 임무 발송 완료: {sent}")

async def job_collect_and_report(app):
    """오후 3:00 — 결과물 수집·검수·보고"""
    logger.info("[SCHEDULE] 결과물 수집 및 보고 시작")
    results = collect_today_results()
    passed_items, failed_items, escalate_items = [], [], []

    for item in results:
        bot_name = item["bot"]
        passed, feedback = quality_check(item["path"], bot_name)
        # 에스컬레이션 체크
        try:
            with open(item["path"], "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            need_esc, esc_kw = needs_escalation(content)
        except:
            need_esc, esc_kw = False, None

        if need_esc:
            escalate_items.append({
                "bot": bot_name, "file": item["name"],
                "reason": f"'{esc_kw}' 관련 내용 포함"
            })
        elif passed:
            passed_items.append({"bot": bot_name, "file": item["name"]})
        else:
            failed_items.append({
                "bot": bot_name, "file": item["name"], "feedback": feedback
            })

    # 불합격 봇에게 재작업 지시
    for fi in failed_items:
        target_info = next((v for k, v in DAILY_MISSIONS.items() if k in fi["bot"] or fi["bot"] in k), None)
        if target_info:
            rework_msg = (
                f"{TASK_TAG} [재작업 요청]\n\n"
                f"파일: {fi['file']}\n"
                f"검수 결과: ❌ 불합격\n"
                f"피드백: {fi['feedback']}\n\n"
                f"위 내용을 반영해서 재작업 후 같은 경로에 저장해줘."
            )
            try:
                await app.bot.send_message(chat_id=target_info["chat_id"], text=rework_msg)
                logger.info(f"[REWORK] → {fi['bot']}")
            except Exception as e:
                logger.error(f"[REWORK FAIL] {fi['bot']}: {e}")
        await asyncio.sleep(0.5)

    # 대표님께 일일 보고
    await send_daily_report(app, passed_items, failed_items, escalate_items, results)

async def send_daily_report(app, passed, failed, escalate, all_results):
    """대표님께 일일 요약 보고 발송"""
    if not OWNER_CHAT_ID: return
    date_str = datetime.now().strftime("%m/%d (%a)")
    msg = f"📊 [{date_str}] WK AI전략단 일일 보고\n{'='*30}\n\n"

    if passed:
        msg += f"✅ 완료 ({len(passed)}건)\n"
        for p in passed:
            msg += f"  • {p['bot']}: {p['file']}\n"
        msg += "\n"

    if failed:
        msg += f"🔄 재작업 중 ({len(failed)}건)\n"
        for f in failed:
            msg += f"  • {f['bot']}: {f['feedback'][:60]}\n"
        msg += "\n"

    if escalate:
        msg += f"⚠️ 대표님 확인 필요 ({len(escalate)}건)\n"
        for e in escalate:
            msg += f"  • {e['bot']}: {e['file']}\n    → {e['reason']}\n"
        msg += "\n"

    if not all_results:
        msg += "📭 오늘 수집된 결과물 없음\n\n"

    msg += f"📁 전체 결과물 위치\n{WORKSPACE}\\drafts\\ / reports\\"
    try:
        await app.bot.send_message(chat_id=OWNER_CHAT_ID, text=msg)
        logger.info("[REPORT] 일일 보고 발송 완료")
    except Exception as e:
        logger.error(f"[REPORT FAIL] {e}")

# ── 텔레그램 핸들러 ──────────────────────────────────────────────

def should_respond_in_group(update):
    msg = update.message
    if not msg: return False
    text = (msg.text or msg.caption or "").lower()
    for n in MY_NAMES:
        if n.lower() in text: return True
    for kw in ["전체","모두","다들","여러분","all","@all"]:
        if kw in text: return True
    return False

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_group = update.effective_chat.type in ["group","supergroup"]
    msg = (
        f"🏛️ {BOT_NAME} v4.0 Commander 가동!\n"
        f"임시 사령관 모드 (방통 부재 대행)\n\n"
        f"[스케줄]\n"
        f"  07:00 — 팀 전체 임무 발송\n"
        f"  15:00 — 결과 수집·검수·보고\n\n"
        f"[명령어]\n"
        f"  /mission — 지금 임무 발송\n"
        f"  /collect — 지금 결과 수집\n"
        f"  /report — 지금 보고\n"
        f"  /squad — 팀 현황"
    )
    await update.message.reply_text(msg)

async def cmd_mission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """수동으로 즉시 임무 발송"""
    await update.message.reply_text("📋 임무 발송 시작...")
    await job_send_daily_missions(context.application)

async def cmd_collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """수동으로 즉시 결과 수집·검수·보고"""
    await update.message.reply_text("🔍 결과 수집 및 검수 시작...")
    await job_collect_and_report(context.application)

async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """수동으로 즉시 보고"""
    results = collect_today_results()
    await update.message.reply_text(
        f"📁 오늘 수집된 파일: {len(results)}건\n" +
        "\n".join([f"  • {r['name']}" for r in results]) if results else "📭 없음"
    )

async def cmd_squad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """팀 현황 출력"""
    msg = f"👥 WK AI전략단 현황\n{'='*25}\n\n"
    for name, info in DAILY_MISSIONS.items():
        msg += f"  {name} (ID: {info['chat_id']})\n"
    msg += f"\n총 {len(DAILY_MISSIONS)}개 봇 관리 중"
    await update.message.reply_text(msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    is_group = update.effective_chat.type in ["group","supergroup"]
    user_id = str(update.effective_user.id)
    msg_text = update.message.text or update.message.caption or ""

    # RELAY 수신 — 로그만
    if not is_group and msg_text.startswith(RELAY_TAG):
        logger.info(f"[RELAY RECV] {msg_text[:80]}")
        return
    # REPORT 수신 — 검수 후 기록
    if not is_group and msg_text.startswith(REPORT_TAG):
        logger.info(f"[REPORT RECV] {msg_text[:80]}")
        return

    if is_group and not should_respond_in_group(update): return

    if not msg_text: return
    await update.message.chat.send_action("typing")
    try:
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(None, lambda: chat_with_claude(user_id, msg_text, is_group))
        dm_activity_log.append(f"{datetime.now().strftime('%H:%M')} {msg_text[:60]} → {resp[:80]}")
        for i in range(0, len(resp), 4000):
            await update.message.reply_text(resp[i:i+4000])
    except Exception as e:
        logger.error(f"Handle error: {e}")
        await update.message.reply_text(f"오류: {e}")

# ── 스케줄러 및 메인 ─────────────────────────────────────────────
async def post_init(application):
    global BOT_USERNAME
    me = await application.bot.get_me()
    BOT_USERNAME = me.username or ""
    logger.info(f"Commander ready: @{BOT_USERNAME}")

    scheduler = AsyncIOScheduler()
    # 오전 7:00 임무 발송
    scheduler.add_job(
        lambda: asyncio.ensure_future(job_send_daily_missions(application)),
        'cron', hour=7, minute=0, id='daily_mission'
    )
    # 오후 3:00 결과 수집·보고
    scheduler.add_job(
        lambda: asyncio.ensure_future(job_collect_and_report(application)),
        'cron', hour=15, minute=0, id='daily_collect'
    )
    scheduler.start()
    logger.info("스케줄러 가동: 07:00 임무발송 / 15:00 수집보고")

def main():
    logger.info(f"Starting {BOT_NAME} v4.0 Commander...")
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("mission", cmd_mission))
    app.add_handler(CommandHandler("collect", cmd_collect))
    app.add_handler(CommandHandler("report",  cmd_report))
    app.add_handler(CommandHandler("squad",   cmd_squad))
    app.add_handler(MessageHandler((filters.TEXT|filters.PHOTO)&~filters.COMMAND, handle_message))
    logger.info(f"{BOT_NAME} v4.0 Commander running!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__": main()
