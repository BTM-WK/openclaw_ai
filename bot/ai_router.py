"""
OPENCLAW Multi-AI Router - 작업 유형별 최적 AI 자동 선택
Open WebUI 있으면 경유 (Gemini/GPT/Claude 선택), 없으면 Claude 직접 호출
"""
import json, os, logging, urllib.request
import anthropic

logger = logging.getLogger("ai_router")

DEFAULT_MODEL_MAP = {
    "strategy":      {"model": "claude-sonnet-4-20250514", "owui": "anthropic/claude-sonnet-4",       "route": "anthropic",        "desc": "전략/제안서"},
    "research":      {"model": "claude-sonnet-4-20250514", "owui": "google/gemini-2.5-pro-preview",   "route": "prefer_openwebui", "desc": "시장조사/딥리서치"},
    "coding":        {"model": "claude-sonnet-4-20250514", "owui": "anthropic/claude-sonnet-4",       "route": "anthropic",        "desc": "코드/기술"},
    "writing":       {"model": "claude-sonnet-4-20250514", "owui": "anthropic/claude-sonnet-4",       "route": "anthropic",        "desc": "문서/보고서"},
    "creative":      {"model": "claude-sonnet-4-20250514", "owui": "google/gemini-2.5-pro-preview",   "route": "prefer_openwebui", "desc": "창작/아이디어"},
    "translation":   {"model": "claude-sonnet-4-20250514", "owui": "google/gemini-2.5-pro-preview",   "route": "prefer_openwebui", "desc": "번역"},
    "data_analysis": {"model": "claude-sonnet-4-20250514", "owui": "anthropic/claude-sonnet-4",       "route": "anthropic",        "desc": "데이터분석"},
    "general":       {"model": "claude-sonnet-4-20250514", "owui": "anthropic/claude-sonnet-4",       "route": "anthropic",        "desc": "기본대화"},
}
TASK_KEYWORDS = {
    "strategy": ["전략","기획","제안서","사업계획","포지셔닝","비전","strategy","proposal"],
    "research": ["조사","리서치","시장","경쟁사","트렌드","벤치마킹","현황","research","market","trend"],
    "coding": ["코드","코딩","파이썬","스크립트","프로그램","개발","API","code","python","dev"],
    "writing": ["보고서","문서","작성","글쓰기","이메일","리포트","report","document","write"],
    "creative": ["아이디어","창작","브레인스토밍","컨셉","creative","brainstorm"],
    "translation": ["번역","영어로","한국어로","translate","English","Korean"],
    "data_analysis": ["데이터","분석","통계","차트","엑셀","data","analysis","chart"],
}

class AIRouter:
    def __init__(self, config):
        self.anthropic_key = config.get("anthropic_api_key", "")
        self.owui_url = config.get("openwebui_url", "http://localhost:8080")
        self.owui_key = config.get("openwebui_api_key", "")
        self.model_map = config.get("model_map", DEFAULT_MODEL_MAP)
        self.anthropic_client = anthropic.Anthropic(api_key=self.anthropic_key) if self.anthropic_key else None
        self._owui_ok = None
    def check_openwebui(self):
        if self._owui_ok is not None: return self._owui_ok
        try:
            req = urllib.request.Request(f"{self.owui_url}/api/version", headers={'User-Agent': 'OPENCLAW'})
            with urllib.request.urlopen(req, timeout=5) as resp: self._owui_ok = resp.status == 200
        except: self._owui_ok = False
        return self._owui_ok
    def reset_cache(self): self._owui_ok = None
    def get_openwebui_models(self):
        if not self.check_openwebui(): return []
        try:
            headers = {'User-Agent': 'OPENCLAW'}
            if self.owui_key: headers['Authorization'] = f'Bearer {self.owui_key}'
            req = urllib.request.Request(f"{self.owui_url}/api/models", headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if isinstance(data, list): return [m.get("id","") for m in data]
                if isinstance(data, dict) and "data" in data: return [m.get("id","") for m in data["data"]]
        except: pass
        return []
    def classify_task(self, text):
        tl = text.lower()
        scores = {cat: sum(1 for kw in kws if kw in tl) for cat, kws in TASK_KEYWORDS.items()}
        scores = {k:v for k,v in scores.items() if v > 0}
        return max(scores, key=scores.get) if scores else "general"
    def get_route_info(self, task_text):
        cat = self.classify_task(task_text)
        info = self.model_map.get(cat, self.model_map["general"]).copy(); info["category"] = cat
        route = info.get("route", "anthropic")
        if route in ("prefer_openwebui", "openwebui") and self.check_openwebui():
            info["actual_route"] = "openwebui"; info["actual_model"] = info.get("owui", info["model"])
        else:
            info["actual_route"] = "anthropic"; info["actual_model"] = info["model"]
            if route in ("prefer_openwebui", "openwebui"): info["fallback"] = True
        return info
    def call_anthropic(self, model, messages, system="", tools=None, max_tokens=4096):
        if not self.anthropic_client: return {"error": "No Anthropic key", "text": ""}
        try:
            kw = {"model": model, "max_tokens": max_tokens, "messages": messages}
            if system: kw["system"] = system
            if tools: kw["tools"] = tools
            resp = self.anthropic_client.messages.create(**kw)
            texts, tool_uses = [], []
            for b in resp.content:
                if b.type == "text": texts.append(b.text)
                elif b.type == "tool_use": tool_uses.append({"id": b.id, "name": b.name, "input": b.input})
            return {"text": "\n".join(texts), "tool_uses": tool_uses, "stop_reason": resp.stop_reason,
                    "model": model, "route": "anthropic", "raw_response": resp}
        except Exception as e: return {"error": str(e), "text": ""}
    def call_openwebui(self, model, messages, system="", max_tokens=4096):
        if not self.check_openwebui(): return {"error": "OpenWebUI unavailable", "text": ""}
        try:
            api_msgs = []
            if system: api_msgs.append({"role": "system", "content": system})
            api_msgs.extend(messages)
            payload = json.dumps({"model": model, "messages": api_msgs, "max_tokens": max_tokens, "stream": False}).encode()
            headers = {'Content-Type': 'application/json', 'User-Agent': 'OPENCLAW'}
            if self.owui_key: headers['Authorization'] = f'Bearer {self.owui_key}'
            req = urllib.request.Request(f"{self.owui_url}/api/chat/completions", data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
                text = data.get("choices",[{}])[0].get("message",{}).get("content","")
                return {"text": text, "tool_uses": [], "model": model, "route": "openwebui"}
        except Exception as e: return {"error": str(e), "text": ""}
    def call(self, task_text, messages, system="", tools=None, max_tokens=4096, force_model=None, force_route=None):
        if force_model and force_route:
            if force_route == "openwebui": return self.call_openwebui(force_model, messages, system, max_tokens)
            return self.call_anthropic(force_model, messages, system, tools, max_tokens)
        ri = self.get_route_info(task_text)
        logger.info(f"Route: [{ri['category']}] -> {ri['actual_model']} via {ri['actual_route']}" + (" (fallback)" if ri.get("fallback") else ""))
        if ri["actual_route"] == "openwebui":
            result = self.call_openwebui(ri["actual_model"], messages, system, max_tokens)
            if result.get("error"):
                result = self.call_anthropic(ri["model"], messages, system, tools, max_tokens); result["fallback"] = True
            return result
        return self.call_anthropic(ri["actual_model"], messages, system, tools, max_tokens)
    def get_status_text(self):
        owui = self.check_openwebui()
        lines = [f"=== AI Router ===", f"Anthropic: {'OK' if self.anthropic_client else 'N/A'}",
                 f"OpenWebUI ({self.owui_url}): {'OK' if owui else 'Unavailable'}", ""]
        if owui:
            models = self.get_openwebui_models()
            if models:
                lines.append(f"Models ({len(models)}):")
                for m in models[:15]: lines.append(f"  - {m}")
        lines.append("\nTask Routing:")
        for cat, info in self.model_map.items():
            ri = self.get_route_info(f"test {cat}"); lines.append(f"  {cat}: {ri['actual_model']} via {ri['actual_route']}")
        return "\n".join(lines)
