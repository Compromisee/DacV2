"""
Main.py - PythonMedia Suite Entry Point
API caller, hosts and creates status.json, runs tool nix, ollama, ai models,
dependencies. Serves as the host for the HTML dashboard and CLI interface.
"""

import os
import sys
import json
import time
import threading
import subprocess
import webbrowser
import http.server
import socketserver
from pathlib import Path
from datetime import datetime


# ─── Paths ────────────────────────────────────────────────────────────────────
APP_DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "PythonMedia"
HISTORY_FILE = APP_DATA_DIR / "History.json"
STATUS_FILE  = APP_DATA_DIR / "status.json"
DASHBOARD    = Path(__file__).parent / "Dashboard.html"
PROJECTS_DIR = Path(__file__).parent / "projects"

APP_DATA_DIR.mkdir(parents=True, exist_ok=True)


# ─── Status JSON ──────────────────────────────────────────────────────────────
def write_status(data: dict):
    """Write/update status.json so the HTML dashboard can poll it."""
    existing = {}
    if STATUS_FILE.exists():
        try:
            existing = json.loads(STATUS_FILE.read_text())
        except json.JSONDecodeError:
            pass
    existing.update(data)
    STATUS_FILE.write_text(json.dumps(existing, indent=2))


def clear_status():
    STATUS_FILE.write_text(json.dumps({
        "running": False,
        "project": None,
        "progress": 0,
        "message": "Idle",
        "timestamp": datetime.now().isoformat(),
    }, indent=2))


# ─── History JSON ─────────────────────────────────────────────────────────────
def load_history() -> dict:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {
        "files": [],
        "total_files_processed": 0,
        "combined_size_bytes": 0,
        "project_usage": {},
        "project_file_counts": {},
    }


def save_history(history: dict):
    HISTORY_FILE.write_text(json.dumps(history, indent=2))


def record_run(project: str, files: list[dict]):
    """
    Append a run to the history log.
    Each file dict should have: {"name": str, "size_bytes": int}
    """
    history = load_history()
    now = datetime.now().isoformat()

    for f in files:
        entry = {**f, "project": project, "timestamp": now}
        history["files"].insert(0, entry)

    # keep last 200
    history["files"] = history["files"][:200]
    history["total_files_processed"] += len(files)
    history["combined_size_bytes"]   += sum(f.get("size_bytes", 0) for f in files)
    history["project_usage"][project] = history["project_usage"].get(project, 0) + 1
    history["project_file_counts"][project] = (
        history["project_file_counts"].get(project, 0) + len(files)
    )

    save_history(history)


# ─── Dependency / Tool Checks ─────────────────────────────────────────────────
def check_dependencies():
    """Check that external binaries are available."""
    tools = {
        "mkvtoolnix (mkvmerge)": ["mkvmerge", "--version"],
        "ffmpeg":                ["ffmpeg",   "-version"],
    }
    missing = []
    for name, cmd in tools.items():
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            print(f"  [OK]  {name}")
        except (FileNotFoundError, subprocess.CalledProcessError):
            print(f"  [!!]  {name} not found")
            missing.append(name)
    return missing


def check_ollama():
    """Check if Ollama (local AI) is running."""
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434", timeout=2)
        print("  [OK]  Ollama is running")
        return True
    except Exception:
        print("  [!!]  Ollama not reachable (AI features may be limited)")
        return False


# ─── Dashboard / HTTP Server ───────────────────────────────────────────────────
def serve_dashboard(port: int = 8765):
    """Serve the HTML dashboard on localhost."""
    os.chdir(Path(__file__).parent)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # silence request logs

    with socketserver.TCPServer(("", port), Handler) as httpd:
        print(f"\n  Dashboard → http://localhost:{port}/Dashboard.html\n")
        webbrowser.open(f"http://localhost:{port}/Dashboard.html")
        httpd.serve_forever()


# ─── Project Launchers ────────────────────────────────────────────────────────
def run_project(name: str, args: list[str] = None):
    """Launch a project Python script as a subprocess."""
    script_map = {
        "merger":     PROJECTS_DIR / "Merger.py",
        "upscaler":   PROJECTS_DIR / "AI_Upscaler.py",
        "renamer":    PROJECTS_DIR / "File_renamer.py",
        "dac":        PROJECTS_DIR / "Defaultaudiochanger.py",
    }
    script = script_map.get(name.lower())
    if not script or not script.exists():
        print(f"[ERROR] Unknown project or script not found: {name}")
        return

    write_status({"running": True, "project": name, "progress": 0, "message": f"Starting {name}..."})
    cmd = [sys.executable, str(script)] + (args or [])
    subprocess.run(cmd)
    write_status({"running": False, "project": None, "progress": 100, "message": "Done"})


# ─── CLI ──────────────────────────────────────────────────────────────────────
CLI_HELP = """
PythonMedia Suite — Main.py
────────────────────────────────────────
Usage:
  python Main.py                   Launch dashboard in browser
  python Main.py --cli             Interactive CLI mode
  python Main.py --run <project>   Run a project directly
  python Main.py --check           Check dependencies

Projects: merger | upscaler | renamer | dac
"""


def cli_mode():
    print("\nPythonMedia Suite — CLI Mode")
    print("Type 'help' for commands, 'quit' to exit.\n")
    while True:
        try:
            cmd = input("pm> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if cmd in ("quit", "exit", "q"):
            break
        elif cmd == "help":
            print(CLI_HELP)
        elif cmd == "check":
            print("\nChecking dependencies...")
            check_dependencies()
            check_ollama()
        elif cmd.startswith("run "):
            project = cmd.split(None, 1)[1]
            run_project(project)
        elif cmd == "history":
            h = load_history()
            print(f"  Total files processed : {h['total_files_processed']}")
            print(f"  Combined size         : {h['combined_size_bytes'] / 1e9:.2f} GB")
            print(f"  Project usage         : {h['project_usage']}")
        elif cmd == "dashboard":
            threading.Thread(target=serve_dashboard, daemon=True).start()
            input("  Press Enter to stop dashboard...\n")
        else:
            print(f"  Unknown command: '{cmd}'. Type 'help'.")


# ─── Entry ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    clear_status()

    if "--check" in sys.argv:
        print("\nDependency check:")
        check_dependencies()
        check_ollama()
        sys.exit(0)

    elif "--cli" in sys.argv:
        cli_mode()

    elif "--run" in sys.argv:
        idx = sys.argv.index("--run")
        project = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        extra   = sys.argv[idx + 2:] if idx + 2 < len(sys.argv) else []
        run_project(project, extra)

    else:
        # Default: launch dashboard
        print("\n  PythonMedia Suite starting...")
        print("  Checking dependencies...")
        check_dependencies()
        check_ollama()
        serve_dashboard()
