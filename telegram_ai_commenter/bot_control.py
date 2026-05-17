import argparse
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
PID_PATH = DATA_DIR / "bot.pid"
PROCESS_LOG_PATH = DATA_DIR / "bot_process.log"


def python_path() -> Path:
    return ROOT_DIR / ".venv" / "Scripts" / "python.exe"


def is_running(pid: int) -> bool:
    completed = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return str(pid) in completed.stdout


def read_pid() -> int | None:
    if not PID_PATH.exists():
        return None
    try:
        return int(PID_PATH.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def status() -> str:
    pid = read_pid()
    if not pid:
        return "stopped"
    if is_running(pid):
        return f"running pid={pid}"
    return "stopped stale_pid"


def start() -> str:
    DATA_DIR.mkdir(exist_ok=True)
    pid = read_pid()
    if pid and is_running(pid):
        return f"already running pid={pid}"

    python = python_path()
    if not python.exists():
        raise RuntimeError(f"Python venv not found: {python}")

    command = [
        str(python),
        str(BASE_DIR / "main.py"),
        "--config",
        str(BASE_DIR / "config.json"),
    ]
    with PROCESS_LOG_PATH.open("a", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=str(ROOT_DIR),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    PID_PATH.write_text(str(process.pid), encoding="utf-8")
    return f"started pid={process.pid}"


def stop() -> str:
    pid = read_pid()
    if not pid:
        return "already stopped"
    if not is_running(pid):
        PID_PATH.unlink(missing_ok=True)
        return "already stopped stale_pid_removed"

    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    PID_PATH.unlink(missing_ok=True)
    return f"stopped pid={pid}"


def main() -> None:
    parser = argparse.ArgumentParser(description="A-Gid Telegram bot background controller")
    parser.add_argument("command", choices=["start", "stop", "status"])
    args = parser.parse_args()

    if args.command == "start":
        print(start())
    elif args.command == "stop":
        print(stop())
    else:
        print(status())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise
