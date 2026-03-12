"""
OPENCLAW Reporter - 주기적 보고 (Telegram + Gmail) + Stall 감지
"""
import os, smtplib, logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

logger = logging.getLogger("reporter")

class Reporter:
    def __init__(self, task_manager, bot_name, workspace_dir,
                 gmail_user=None, gmail_app_password=None, report_to_email=None):
        self.tm = task_manager
        self.bot_name = bot_name
        self.workspace = workspace_dir
        self.gmail_user = gmail_user
        self.gmail_app_password = gmail_app_password
        self.report_to_email = report_to_email
        self.last_report_time = datetime.now()
        self.last_output_time = datetime.now()
        self.report_count = 0

    def generate_report(self):
        s = self.tm.get_status_summary()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        r = f"[{self.bot_name} Report #{self.report_count+1}]\nTime: {now}\nGoal: {s['goal']}\n\n"
        r += f"Done ({s['done']}/{s['total_tasks']}):\n"
        for t in s['done_tasks'][-5:]: r += f"  V {t}\n"
        r += f"\nCurrent: {s['current_task']}\n\nNext:\n"
        for t in s['next_tasks']: r += f"  - {t}\n"
        if s['blocked_tasks']:
            r += "\nBlocked:\n"
            for title, reason in s['blocked_tasks']: r += f"  X {title}: {reason}\n"
        if s['output_files']:
            r += f"\nFiles ({len(s['output_files'])}):\n"
            for f in s['output_files'][-10:]: r += f"  {f}\n"
        self.report_count += 1
        return r

    def save_report(self):
        report = self.generate_report()
        with open(os.path.join(self.workspace, "status_report.md"), "w", encoding="utf-8") as f:
            f.write(report)
        return report

    def send_gmail_report(self, subject_prefix=""):
        if not all([self.gmail_user, self.gmail_app_password, self.report_to_email]): return False
        report = self.generate_report()
        msg = MIMEMultipart()
        msg['From'] = self.gmail_user
        msg['To'] = self.report_to_email
        msg['Subject'] = f"{subject_prefix}[{self.bot_name}] Report #{self.report_count}"
        msg.attach(MIMEText(report, 'plain', 'utf-8'))
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(self.gmail_user, self.gmail_app_password)
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"Gmail failed: {e}")
            return False

    def check_stall(self, stall_minutes=30):
        rd = os.path.join(self.workspace, "reports")
        if not os.path.exists(rd): return True
        latest = None
        for f in os.listdir(rd):
            mt = datetime.fromtimestamp(os.path.getmtime(os.path.join(rd, f)))
            if latest is None or mt > latest: latest = mt
        if latest is None: return True
        return (datetime.now() - latest).total_seconds() / 60 > stall_minutes

    def update_output_time(self):
        self.last_output_time = datetime.now()

    def should_report(self, interval_minutes=120):
        return (datetime.now() - self.last_report_time).total_seconds() / 60 >= interval_minutes
