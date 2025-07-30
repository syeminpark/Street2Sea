# node_runner.py
import os, subprocess, signal, atexit, pathlib, sys

def start_node():
    # ── path/to/your_repo/cesium_sim
    root = pathlib.Path(__file__).parent / "cesium_sim"

    env = os.environ.copy()
    env["CESIUM_ION_TOKEN"] = os.getenv("CESIUM_ION_TOKEN", "")

    # launch: node cesium_sim/server.js
    proc = subprocess.Popen(
        ["node", "server.js"],
        cwd=root,              # ← **now inside cesium_sim/**
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    atexit.register(lambda: os.kill(proc.pid, signal.SIGTERM))
    print(f"↪ Node server launched on :8000 (pid {proc.pid}) in {root}")
