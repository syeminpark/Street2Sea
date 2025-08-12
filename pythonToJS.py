# node_runner.py
import os, subprocess, signal, atexit, pathlib, sys
import requests, json
from constants import WebDirectory
import requests, time


BASE_URL = f"http://{WebDirectory.HOST.value}:{WebDirectory.PORT.value}"

def start_node():
    # ── path/to/your_repo/cesium_sim
    root = pathlib.Path(__file__).parent / "cesium_sim"

    env = os.environ.copy()
    env["CESIUM_ION_TOKEN"] = os.getenv("CESIUM_ION_TOKEN", "")
    env["HOST"] = WebDirectory.HOST.value       
    env["PORT"] = WebDirectory.PORT.value       
    env["CAMERA_METADATA_ROUTE"] =  WebDirectory.CAMERA_METADATA_ROUTE.value

    # launch: node cesium_sim/server.js
    proc = subprocess.Popen(
        ["node", "server.js"],
        cwd=root,              # ← **now inside cesium_sim/**
        env=env,
          stdout=None,          # inherit
    stderr=None
    )

    atexit.register(lambda: os.kill(proc.pid, signal.SIGTERM))
    print(f"↪ Node server launched on :{WebDirectory.PORT.value} (pid {proc.pid}) in {root}")

def sendToNode(payload,api_url):
    try:
        r = requests.post(api_url,
                        headers={'Content-Type': 'application/json'},
                        data=json.dumps(payload),
                        timeout=5)
        r.raise_for_status()
        print("Server replied →", r.json())
    except Exception as e:
        print("POST failed:", e)

def wait_health(url, tries=20):
    for _ in range(tries):
        try:
            if requests.get(url, timeout=0.2).text == 'OK':
                return
        except requests.ConnectionError:
            pass
        time.sleep(0.1)
    raise RuntimeError("Node never reached /health")


