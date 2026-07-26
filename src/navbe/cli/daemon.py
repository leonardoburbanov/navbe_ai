"""Detached ``navbe serve`` lifecycle (pidfile under data home).

ponytail: pidfile daemon — ceiling: no reboot auto-start / crash restart
upgrade: OS user service (systemd --user / launchd / Scheduled Task)
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from navbe.core.paths import default_data_home

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def default_mcp_url(*, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> str:
    """HTTP MCP URL that Cursor / Claude Desktop should connect to."""
    return f"http://{host}:{port}/mcp"


def serve_pid_path() -> Path:
    """Path to the detached-serve pidfile."""
    return default_data_home() / "serve.pid"


def serve_log_path() -> Path:
    """Path to the detached-serve log file."""
    return default_data_home() / "serve.log"


@dataclass(frozen=True)
class ServeState:
    """Parsed pidfile + liveness."""

    pid: int
    host: str
    port: int
    alive: bool
    healthy: bool

    @property
    def mcp_url(self) -> str:
        """MCP endpoint for this serve instance."""
        return default_mcp_url(host=self.host, port=self.port)

    @property
    def health_url(self) -> str:
        """Liveness probe URL."""
        return f"http://{self.host}:{self.port}/health"


def _write_pidfile(path: Path, *, pid: int, host: str, port: int) -> None:
    """Persist detach metadata as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"pid": pid, "host": host, "port": port}, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_pidfile(path: Path | None = None) -> dict[str, Any] | None:
    """Load pidfile JSON, or None if missing/invalid."""
    target = path or serve_pid_path()
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or "pid" not in data:
        return None
    return data


def _pid_alive(pid: int) -> bool:
    """Return True if ``pid`` appears to be a live process."""
    if pid <= 0:
        return False
    if os.name == "nt":
        # ponytail: OpenProcess probe — upgrade: psutil
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def check_health(*, host: str, port: int, timeout: float = 1.0) -> bool:
    """GET /health and return True on HTTP 200."""
    url = f"http://{host}:{port}/health"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url)
        return response.status_code == 200
    except (httpx.HTTPError, OSError):
        return False


def wait_until_healthy(
    *,
    host: str,
    port: int,
    timeout_s: float = 15.0,
    interval_s: float = 0.2,
) -> bool:
    """Poll /health until ok or timeout."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if check_health(host=host, port=port):
            return True
        time.sleep(interval_s)
    return False


def read_serve_state() -> ServeState | None:
    """Return current detached serve state, or None if no pidfile."""
    data = _read_pidfile()
    if data is None:
        return None
    try:
        pid = int(data["pid"])
        host = str(data.get("host", DEFAULT_HOST))
        port = int(data.get("port", DEFAULT_PORT))
    except (KeyError, TypeError, ValueError):
        return None
    alive = _pid_alive(pid)
    healthy = check_health(host=host, port=port) if alive else False
    return ServeState(pid=pid, host=host, port=port, alive=alive, healthy=healthy)


def start_detached(*, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ServeState:
    """Spawn ``uvicorn`` in the background and write the pidfile.

    Raises ``RuntimeError`` if a live detached serve already exists or health never comes up.
    """
    existing = read_serve_state()
    if existing is not None and existing.alive:
        if existing.healthy and existing.host == host and existing.port == port:
            return existing
        raise RuntimeError(
            f"navbe serve already running (pid {existing.pid} on "
            f"{existing.host}:{existing.port}); run navbe stop first"
        )

    data_home = default_data_home()
    data_home.mkdir(parents=True, exist_ok=True)
    log_path = serve_log_path()
    pid_path = serve_pid_path()

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "navbe.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    log_file = log_path.open("a", encoding="utf-8")
    popen_kwargs: dict[str, Any] = {
        "args": cmd,
        "stdout": log_file,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        popen_kwargs["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(**popen_kwargs)
    log_file.close()
    _write_pidfile(pid_path, pid=proc.pid, host=host, port=port)

    if not wait_until_healthy(host=host, port=port):
        stop_detached(force=True)
        raise RuntimeError(
            f"navbe serve failed to become healthy at http://{host}:{port}/health; "
            f"see {log_path}"
        )
    state = read_serve_state()
    if state is None:
        raise RuntimeError("navbe serve started but pidfile is missing")
    return state


def stop_detached(*, force: bool = False) -> str:
    """Stop the detached serve process. Returns a short status string."""
    data = _read_pidfile()
    pid_path = serve_pid_path()
    if data is None:
        if pid_path.exists():
            pid_path.unlink(missing_ok=True)
            return "removed stale pidfile (no valid metadata)"
        return "navbe serve is not running"

    try:
        pid = int(data["pid"])
    except (KeyError, TypeError, ValueError):
        pid_path.unlink(missing_ok=True)
        return "removed corrupt pidfile"

    if not _pid_alive(pid):
        pid_path.unlink(missing_ok=True)
        return f"cleared stale pidfile (pid {pid} not running)"

    try:
        if os.name == "nt":
            # Windows: always force-kill the process tree (no graceful SIGTERM equivalent).
            _ = force
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False,
                capture_output=True,
                text=True,
            )
        else:
            os.kill(pid, signal.SIGTERM)
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline and _pid_alive(pid):
                time.sleep(0.1)
            if _pid_alive(pid) or force:
                if _pid_alive(pid):
                    os.kill(pid, signal.SIGKILL)
    except OSError as exc:
        raise RuntimeError(f"failed to stop pid {pid}: {exc}") from exc

    pid_path.unlink(missing_ok=True)
    return f"stopped navbe serve (pid {pid})"
