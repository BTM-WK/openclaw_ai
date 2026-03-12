"""
OPENCLAW Task Manager - task_queue.json 기반 작업 상태 관리
"""
import json, os
from datetime import datetime

class TaskManager:
    def __init__(self, workspace_dir):
        self.workspace = workspace_dir
        self.queue_path = os.path.join(workspace_dir, "task_queue.json")
        self.output_log_path = os.path.join(workspace_dir, "output_log.md")
        self.activity_log_path = os.path.join(workspace_dir, "activity_log.md")
        self._ensure_files()

    def _ensure_files(self):
        os.makedirs(self.workspace, exist_ok=True)
        for d in ["reports", "data", "drafts"]:
            os.makedirs(os.path.join(self.workspace, d), exist_ok=True)
        if not os.path.exists(self.queue_path):
            self._save_queue({"goal": "", "project_status": "idle", "last_updated": self._now(), "tasks": [], "completed_count": 0})
        for p in [self.output_log_path, self.activity_log_path]:
            if not os.path.exists(p):
                with open(p, "w", encoding="utf-8") as f:
                    f.write(f"# {'Output' if 'output' in p else 'Activity'} Log\n\n")

    def _now(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _load_queue(self):
        try:
            with open(self.queue_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"goal": "", "project_status": "idle", "tasks": [], "last_updated": self._now()}

    def _save_queue(self, data):
        data["last_updated"] = self._now()
        with open(self.queue_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_goal(self):
        return self._load_queue().get("goal", "")

    def set_goal(self, goal):
        q = self._load_queue()
        q["goal"] = goal
        q["project_status"] = "in_progress"
        self._save_queue(q)

    def get_next_task(self):
        q = self._load_queue()
        for t in q["tasks"]:
            if t["status"] == "in_progress":
                return t
        pending = [t for t in q["tasks"] if t["status"] == "pending"]
        if pending:
            pending.sort(key=lambda x: x.get("priority", 99))
            task = pending[0]
            task["status"] = "in_progress"
            task["started_at"] = self._now()
            self._save_queue(q)
            return task
        return None

    def complete_task(self, task_id, output_file=None, notes=None):
        q = self._load_queue()
        for t in q["tasks"]:
            if t["id"] == task_id:
                t["status"] = "done"
                t["completed_at"] = self._now()
                if output_file: t["output_file"] = output_file
                if notes: t["completion_notes"] = notes
                q["completed_count"] = q.get("completed_count", 0) + 1
                break
        self._save_queue(q)

    def block_task(self, task_id, reason):
        q = self._load_queue()
        for t in q["tasks"]:
            if t["id"] == task_id:
                t["status"] = "blocked"
                t["block_reason"] = reason
                t["blocked_at"] = self._now()
                break
        self._save_queue(q)

    def add_task(self, title, priority=2, notes="", parent_id=None):
        q = self._load_queue()
        max_num = 0
        for tid in [t["id"] for t in q["tasks"]]:
            try: max_num = max(max_num, int(tid.replace("T", "")))
            except: pass
        new_id = f"T{max_num + 1:03d}"
        new_task = {"id": new_id, "title": title, "status": "pending", "priority": priority,
                    "notes": notes, "created_at": self._now(), "output_file": ""}
        if parent_id: new_task["parent_task"] = parent_id
        q["tasks"].append(new_task)
        self._save_queue(q)
        return new_id

    def get_status_summary(self):
        q = self._load_queue()
        tasks = q.get("tasks", [])
        done = [t for t in tasks if t["status"] == "done"]
        in_prog = [t for t in tasks if t["status"] == "in_progress"]
        pending = [t for t in tasks if t["status"] == "pending"]
        blocked = [t for t in tasks if t["status"] == "blocked"]
        outputs = []
        rd = os.path.join(self.workspace, "reports")
        if os.path.exists(rd):
            for f in os.listdir(rd):
                outputs.append(f"{f} ({os.path.getsize(os.path.join(rd, f)):,}B)")
        return {"goal": q.get("goal",""), "total_tasks": len(tasks), "done": len(done),
                "in_progress": len(in_prog), "pending": len(pending), "blocked": len(blocked),
                "done_tasks": [t["title"] for t in done], "current_task": in_prog[0]["title"] if in_prog else "None",
                "next_tasks": [t["title"] for t in pending[:3]],
                "blocked_tasks": [(t["title"], t.get("block_reason","")) for t in blocked],
                "output_files": outputs, "last_updated": q.get("last_updated","")}

    def log_activity(self, msg):
        with open(self.activity_log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{self._now()} - {msg}")

    def log_output(self, filename, desc):
        with open(self.output_log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{self._now()} - {filename}: {desc}")

    def has_active_goal(self):
        q = self._load_queue()
        return bool(q.get("goal","").strip()) and q.get("project_status") == "in_progress"

    def get_all_tasks_text(self):
        q = self._load_queue()
        lines = [f"Goal: {q.get('goal','N/A')}"]
        for t in q.get("tasks", []):
            icon = {"done":"V","in_progress":">","pending":"-","blocked":"X"}.get(t["status"],"?")
            lines.append(f"[{icon}] {t['id']}: {t['title']} (p:{t.get('priority','-')})")
            if t.get("output_file"): lines.append(f"    -> {t['output_file']}")
        return "\n".join(lines)
