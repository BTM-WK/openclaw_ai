"""
OPENCLAW Autonomous Worker - 자율 작업 루프 엔진
AI Router 통합: 작업 유형에 따라 최적 AI 자동 선택
"""
import asyncio, json, os, re, logging
from datetime import datetime

logger = logging.getLogger("autonomous_worker")

WORKER_SYSTEM_PROMPT = """You are an autonomous research and work agent.
You are NOT a chatbot. You are a worker that continuously executes tasks.
Workspace: {workspace}

RULES:
1. Execute the task thoroughly and produce a concrete output FILE.
2. Plans and promises are NOT completion. Only saved files count.
3. Research: depth over speed. Minimum 10+ sources. Cross-reference.
4. If blocked: try 3+ alternatives before declaring blocked.
5. After completing: suggest 1-3 follow-up tasks.
6. Write outputs in Korean.

End your response with:
```json
{{"status": "done" or "blocked", "output_file": "reports/filename.md",
  "output_summary": "What was produced", "new_tasks": [{{"title": "...", "priority": 1}}],
  "block_reason": "Only if blocked"}}
```"""

class AutonomousWorker:
    def __init__(self, task_manager, reporter, ai_router, bot_name, workspace_dir,
                 tools_list, execute_tool_fn, max_calls_per_hour=20, task_interval_seconds=60):
        self.tm = task_manager; self.reporter = reporter; self.router = ai_router
        self.bot_name = bot_name; self.workspace = workspace_dir
        self.tools = tools_list; self.execute_tool = execute_tool_fn
        self.max_calls_per_hour = max_calls_per_hour; self.task_interval = task_interval_seconds
        self.api_calls_this_hour = 0; self.hour_start = datetime.now()
        self.is_running = False; self.is_paused = False
    def _check_rate_limit(self):
        now = datetime.now()
        if (now - self.hour_start).total_seconds() > 3600: self.api_calls_this_hour = 0; self.hour_start = now
        return self.api_calls_this_hour < self.max_calls_per_hour
    async def _execute_task(self, task):
        if not self._check_rate_limit(): logger.warning("Rate limit, waiting 5min..."); await asyncio.sleep(300); return None
        mission = ""
        mp = os.path.join(self.workspace, "mission.md")
        if os.path.exists(mp):
            with open(mp, "r", encoding="utf-8") as f: mission = f.read()
        all_tasks = self.tm.get_all_tasks_text()
        system = WORKER_SYSTEM_PROMPT.format(workspace=self.workspace)
        user_msg = f"## Mission\n{mission}\n\n## Queue\n{all_tasks}\n\n## YOUR TASK\nID: {task['id']}\nTitle: {task['title']}\nNotes: {task.get('notes','')}\n\nExecute now. Save output to workspace/reports/."
        messages = [{"role": "user", "content": user_msg}]; full_response = ""
        try:
            route_info = self.router.get_route_info(task['title'])
            for _ in range(15):
                self.api_calls_this_hour += 1
                if route_info["actual_route"] == "anthropic":
                    result = self.router.call_anthropic(route_info["actual_model"], messages, system, self.tools, 4096)
                else:
                    result = self.router.call_openwebui(route_info["actual_model"], messages, system, 4096)
                if result.get("error"): logger.error(f"API error: {result['error']}"); return None
                if result.get("text"): full_response += result["text"]
                tool_uses = result.get("tool_uses", []); raw = result.get("raw_response")
                if result.get("stop_reason") == "tool_use" and tool_uses and raw:
                    tool_results = []
                    for tu in tool_uses:
                        tr = self.execute_tool(tu["name"], tu["input"])
                        tool_results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": str(tr)[:5000]})
                        logger.info(f"Worker tool: {tu['name']}")
                    messages.append({"role": "assistant", "content": raw.content})
                    messages.append({"role": "user", "content": tool_results}); continue
                break
            return full_response
        except Exception as e: logger.error(f"Worker API error: {e}"); return None
    def _parse_result(self, text):
        if not text: return None
        try:
            m = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
            if m: return json.loads(m.group(1))
            m = re.search(r'\{[^{}]*"status"[^{}]*\}', text, re.DOTALL)
            if m: return json.loads(m.group(0))
        except: pass
        return None
    async def work_loop(self):
        self.is_running = True; logger.info(f"[{self.bot_name}] Worker started"); self.tm.log_activity("Worker started")
        while self.is_running:
            try:
                if self.is_paused: await asyncio.sleep(10); continue
                if not self.tm.has_active_goal(): await asyncio.sleep(30); continue
                task = self.tm.get_next_task()
                if not task: self.tm.log_activity("All tasks done. Waiting."); await asyncio.sleep(60); continue
                logger.info(f"Exec: {task['id']} - {task['title']}"); self.tm.log_activity(f"Start: {task['id']} - {task['title']}")
                resp = await self._execute_task(task)
                if resp is None: self.tm.block_task(task["id"], "API failure"); await asyncio.sleep(60); continue
                result = self._parse_result(resp)
                if result:
                    if result.get("status") == "done":
                        of = result.get("output_file", ""); summary = result.get("output_summary", "")
                        self.tm.complete_task(task["id"], of, summary); self.tm.log_activity(f"Done: {task['id']} - {summary}")
                        if of: self.tm.log_output(of, summary); self.reporter.update_output_time()
                        for nt in result.get("new_tasks", []):
                            nid = self.tm.add_task(nt.get("title","Follow-up"), nt.get("priority",2))
                            self.tm.log_activity(f"New task: {nid} - {nt.get('title')}")
                    elif result.get("status") == "blocked": self.tm.block_task(task["id"], result.get("block_reason","Unknown"))
                else: self.tm.complete_task(task["id"], "", "Auto-completed (unstructured)")
                await asyncio.sleep(self.task_interval)
            except asyncio.CancelledError: break
            except Exception as e: logger.error(f"Worker error: {e}", exc_info=True); await asyncio.sleep(30)
        self.is_running = False
    def pause(self): self.is_paused = True; self.tm.log_activity("Worker paused")
    def resume(self): self.is_paused = False; self.tm.log_activity("Worker resumed")
    def stop(self): self.is_running = False
