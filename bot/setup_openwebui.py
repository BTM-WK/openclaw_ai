"""
OPENCLAW Open WebUI Auto-Setup
봇 시작 시 Open WebUI 설치 여부 확인 → 없으면 자동 설치 → 자동 시작
"""
import subprocess, sys, os, time, logging, urllib.request, json

logger = logging.getLogger("openwebui_setup")

def is_openwebui_installed():
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "show", "open-webui"],
            capture_output=True, text=True, timeout=15)
        return result.returncode == 0
    except: return False

def is_openwebui_running(url="http://localhost:8080"):
    try:
        req = urllib.request.Request(f"{url}/api/version", headers={'User-Agent': 'OPENCLAW'})
        with urllib.request.urlopen(req, timeout=5) as resp: return resp.status == 200
    except: return False

def install_openwebui():
    logger.info("Installing Open WebUI (this may take a few minutes)...")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "install", "open-webui", "--quiet"],
            capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            logger.info("Open WebUI installed successfully"); return True
        else:
            logger.error(f"Install failed: {result.stderr[:500]}"); return False
    except subprocess.TimeoutExpired:
        logger.error("Install timed out (10min)"); return False
    except Exception as e:
        logger.error(f"Install error: {e}"); return False

def start_openwebui_server():
    logger.info("Starting Open WebUI server...")
    try:
        owui_path = None
        scripts_dirs = [
            os.path.join(os.path.dirname(sys.executable), "Scripts"),
            os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Python",
                        f"Python{sys.version_info.major}{sys.version_info.minor}", "Scripts"),
            os.path.join(os.path.expanduser("~"), "AppData", "Local", "Programs", "Python",
                        f"Python{sys.version_info.major}{sys.version_info.minor}", "Scripts"),
        ]
        for sd in scripts_dirs:
            candidate = os.path.join(sd, "open-webui.exe")
            if os.path.exists(candidate): owui_path = candidate; break
        if owui_path is None:
            try:
                result = subprocess.run("where open-webui", shell=True, capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and result.stdout.strip():
                    owui_path = result.stdout.strip().split('\n')[0]
            except: pass
        if owui_path is None:
            logger.info("Using 'python -m open_webui.main serve' as fallback")
            subprocess.Popen([sys.executable, "-m", "open_webui.main", "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        else:
            logger.info(f"Found open-webui at: {owui_path}")
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            subprocess.Popen([owui_path, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=env, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        logger.info("Waiting for Open WebUI server to start...")
        for i in range(24):
            time.sleep(5)
            if is_openwebui_running():
                logger.info(f"Open WebUI server started (took {(i+1)*5}s)"); return True
            if i % 6 == 5: logger.info(f"Still waiting... ({(i+1)*5}s)")
        logger.warning("Open WebUI server did not start within 120s"); return False
    except Exception as e:
        logger.error(f"Failed to start Open WebUI: {e}"); return False

def ensure_openwebui(auto_install=True, auto_start=True):
    if is_openwebui_running():
        logger.info("Open WebUI already running"); return True, True
    installed = is_openwebui_installed()
    if not installed:
        if auto_install:
            logger.info("Open WebUI not installed. Auto-installing...")
            installed = install_openwebui()
            if not installed:
                logger.warning("Auto-install failed. Claude-only mode."); return False, False
        else:
            logger.info("Open WebUI not installed. Skipping."); return False, False
    if auto_start:
        running = start_openwebui_server(); return installed, running
    return installed, False

def get_openwebui_info():
    installed = is_openwebui_installed()
    running = is_openwebui_running()
    info = {"installed": installed, "running": running, "url": "http://localhost:8080"}
    if running:
        try:
            req = urllib.request.Request("http://localhost:8080/api/version", headers={'User-Agent': 'OPENCLAW'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                info["version"] = data.get("version", "unknown")
        except: pass
    return info
