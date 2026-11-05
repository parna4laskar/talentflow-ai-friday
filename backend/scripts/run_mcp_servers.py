"""Run all TalentFlow MCP servers (employee :8101, jobs :8102, knowledge :8103) and supervise them.

    python backend/scripts/run_mcp_servers.py
Ctrl+C stops all servers. A crashed server is restarted automatically.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "mcp_servers"
SERVERS = {"employee": 8101, "jobs": 8102, "knowledge": 8103}


def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def spawn(name: str) -> subprocess.Popen:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    print(f"[mcp] starting {name}-mcp", flush=True)
    return subprocess.Popen([sys.executable, f"{name}_server.py"], cwd=HERE, env=env)


def main():
    busy = [f"{n}:{p}" for n, p in SERVERS.items() if port_busy(p)]
    if busy:
        sys.exit(f"[mcp] ports already in use ({', '.join(busy)}) - stop the other MCP servers first")
    procs = {n: spawn(n) for n in SERVERS}
    restarts = {n: 0 for n in SERVERS}
    try:
        while True:
            time.sleep(3)
            for n, p in procs.items():
                if p.poll() is not None:
                    restarts[n] += 1
                    print(f"[mcp] {n}-mcp exited with {p.returncode}; restart #{restarts[n]}", flush=True)
                    time.sleep(min(30, 2 ** restarts[n]))
                    procs[n] = spawn(n)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs.values():
            p.terminate()


if __name__ == "__main__":
    main()
