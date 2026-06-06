"""
Dashboard 静默守护进程 — 监控 8501 端口，挂了自动拉起。
完全后台运行，不弹窗。日志写入 dashboard_guard.log。
"""
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

PORT = 8501
CHECK_URL = f"http://localhost:{PORT}"
CHECK_INTERVAL = 30  # 每30秒检查一次
LOG_FILE = Path(__file__).parent / "dashboard_guard.log"
APP_DIR = Path(__file__).parent
STREAMLIT_EXE = r"C:\Python314\Scripts\streamlit.exe"


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def check() -> bool:
    try:
        req = urllib.request.Request(CHECK_URL)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_dashboard() -> subprocess.Popen | None:
    try:
        log_file = (APP_DIR / "streamlit.log").open("a")
        proc = subprocess.Popen(
            [STREAMLIT_EXE, "run", "app.py", "--server.port", str(PORT), "--server.headless", "true"],
            cwd=str(APP_DIR),
            stdout=log_file,
            stderr=log_file,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        log(f"Dashboard 已拉起 (PID={proc.pid})")
        return proc
    except Exception as e:
        log(f"拉起失败: {e}")
        return None


def main() -> None:
    log("Dashboard Guard 启动")
    proc = None

    while True:
        if check():
            pass  # 正常运行
        else:
            log("Dashboard 无响应，正在重启...")
            proc = start_dashboard()

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
