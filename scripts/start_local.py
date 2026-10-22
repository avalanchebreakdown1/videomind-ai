"""Start both local production servers; Ctrl+C stops only their own process groups."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time


def main():
    project = Path(__file__).resolve().parents[1]
    frontend = project / "frontend"
    node = frontend / "node_modules/node/bin/node"
    if not node.is_file() or not (frontend / ".next/BUILD_ID").is_file():
        raise SystemExit("Install and build frontend first: cd frontend && npm ci && npm run build")
    for port in (8000, 3000):
        with socket.socket() as connection:
            if connection.connect_ex(("127.0.0.1", port)) == 0:
                raise SystemExit(f"Port {port} is already in use. Stop its existing server before starting another.")
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.setdefault("VIDEOMIND_MODEL", "small")
    environment.setdefault("VIDEOMIND_LOCAL_FILES_ONLY", "true")
    environment.setdefault("VIDEOMIND_WRITE_MODEL", "llama3.1:8b")
    environment.setdefault("NEXT_TELEMETRY_DISABLED", "1")
    environment.setdefault("VIDEOMIND_API_URL", "http://127.0.0.1:8000")
    processes = []
    try:
        processes.append(subprocess.Popen([str(project / ".venv/bin/python"), "-m", "uvicorn",
            "videomind.api:create_app", "--factory", "--host", "127.0.0.1", "--port", "8000"],
            cwd=project, env=environment, start_new_session=True))
        processes.append(subprocess.Popen([str(node), "node_modules/next/dist/bin/next", "start",
            "--hostname", "127.0.0.1", "--port", "3000"], cwd=frontend, env=environment, start_new_session=True))
        print("Frontend: http://127.0.0.1:3000\nBackend: http://127.0.0.1:8000/docs\nCtrl+C stops both servers.", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(.5)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process in processes:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
