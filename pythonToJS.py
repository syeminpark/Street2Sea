# node_runner.py
import os, sys, time, json, signal, atexit, pathlib, subprocess, platform
import requests
from constants import WebDirectory

BASE_URL = f"http://{WebDirectory.HOST.value}:{WebDirectory.PORT.value}"
HEALTH_URL = BASE_URL + "/health"

_PROC = None  # child node process handle


def _server_alive(timeout=0.25) -> bool:
    try:
        r = requests.get(HEALTH_URL, timeout=timeout)
        return r.text.strip() == "OK"
    except Exception:
        return False


def _best_effort_shutdown():
    """Ask an existing server (if any) to exit via /shutdown. Ignore errors."""
    try:
        requests.post(BASE_URL + "/shutdown", timeout=0.6)
        time.sleep(0.4)
    except Exception:
        pass


def _kill_on_port(port: int):
    """
    Kill whatever holds `port`. Works on macOS/Linux (lsof) and Windows (netstat).
    This is a last resort if /shutdown didn't clear the port.
    """
    system = platform.system().lower()

    if system in ("darwin", "linux"):
        try:
            pids = (
                subprocess.check_output(["lsof", "-ti", f":{port}"], text=True)
                .strip()
                .splitlines()
            )
        except Exception:
            pids = []
        for pid in pids:
            if not pid:
                continue
            # try TERM then KILL
            try:
                os.kill(int(pid), signal.SIGTERM)
            except Exception:
                pass
        if pids:
            time.sleep(0.5)
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGKILL)
            except Exception:
                pass

    elif system == "windows":
        # netstat -> PID(s), then taskkill
        try:
            out = subprocess.check_output(
                ["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL
            )
            pids = set()
            needle = f":{port} "
            for line in out.splitlines():
                if needle in line:
                    parts = line.split()
                    if parts:
                        pids.add(parts[-1])
        except Exception:
            pids = set()

        for pid in pids:
            try:
                subprocess.run(["taskkill", "/PID", pid, "/F"], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass


def start_node(restart: bool = True):
    """
    Start (and optionally restart) the Node server in cesium_sim/.
    Always returns only after the server is healthy.
    """
    global _PROC

    # 1) Best effort: tell any existing instance to shut down
    if restart:
        _best_effort_shutdown()

    # 2) If the port is still busy, kill whatever has it
    if restart and not _server_alive():
        _kill_on_port(int(WebDirectory.PORT.value))

    # 3) Launch fresh server
    root = pathlib.Path(__file__).resolve().parent / "cesium_sim"
    env = os.environ.copy()
    env["CESIUM_ION_TOKEN"] = os.getenv("CESIUM_ION_TOKEN", "")
    env["HOST"] = str(WebDirectory.HOST.value)
    env["PORT"] = str(WebDirectory.PORT.value)
    env["CAMERA_METADATA_ROUTE"] = str(WebDirectory.CAMERA_METADATA_ROUTE.value)

    _PROC = subprocess.Popen(
        ["node", "server.js"],
        cwd=str(root),
        env=env,
        stdout=None,
        stderr=None,
        text=False,
        close_fds=(platform.system().lower() != "windows"),
    )
    print(f"↪ Node server launched (pid {_PROC.pid}) at {BASE_URL} [cwd={root}]")

    # 4) Wait for health
    wait_health(HEALTH_URL)


def stop_node():
    """Gracefully stop the child Node process we started (if any)."""
    global _PROC
    if _PROC and _PROC.poll() is None:
        try:
            # Ask the running server to shutdown itself first
            _best_effort_shutdown()
            # Give it a moment, then terminate if still alive
            time.sleep(0.4)
            if _PROC.poll() is None:
                _PROC.terminate()
                try:
                    _PROC.wait(3)
                except Exception:
                    pass
            if _PROC.poll() is None:
                _PROC.kill()
        finally:
            _PROC = None


@atexit.register
def _cleanup():
    stop_node()


def sendToNode(payload, api_url):
    try:
        r = requests.post(
            api_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=5,
        )
        r.raise_for_status()
        print("Server replied →", r.json())
    except Exception as e:
        print("POST failed:", e)


def wait_health(url: str, tries: int = 60, delay: float = 0.15):
    for _ in range(tries):
        try:
            if requests.get(url, timeout=0.25).text.strip() == "OK":
                return
        except requests.RequestException:
            pass
        time.sleep(delay)
    raise RuntimeError("Node never reached /health")
