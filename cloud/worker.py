"""Supervised dispatcher: two slots, account leases, fixed-home child processes."""
import concurrent.futures
import json
import os
import signal
import subprocess
import sys
import time
from .config import Settings
from .db import Database, jobs


def run_job(settings, db, job):
    env = os.environ.copy()
    env["LECTIC_HOME"] = str(settings.home(job["owner"]))
    env["PYTHONUNBUFFERED"] = "1"
    # No ambient cookies/proxy settings are passed to acquisition subprocesses.
    for key in list(env):
        if key.lower() in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}: env.pop(key)
    module = __package__ + ".runner"
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    proc = subprocess.Popen([sys.executable, "-m", module, job["id"]], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", **options)
    started, last = time.monotonic(), 0
    cancelled = False
    while proc.poll() is None:
        now = time.monotonic()
        if now-last > 10:
            current = db.get(jobs, job["id"], job["owner"])
            cancelled = bool(current["cancelled"])
            db.heartbeat(job); last = now
        if cancelled or now-started > 1800:
            if os.name == "nt": subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
            else: os.killpg(proc.pid, signal.SIGTERM)
            break
        time.sleep(.3)
    try: stdout, stderr = proc.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill(); stdout, stderr = proc.communicate()
    if settings.dev and stderr: print(stderr[-6000:], file=sys.stderr)
    try:
        response = json.loads(stdout.strip().splitlines()[-1])
        if response.get("yield"): db.yield_job(job)
        elif response["ok"]: db.finish(job, response["result"])
        else: db.finish(job, error=response["error"], retry=response.get("retry", False))
    except (ValueError, IndexError, KeyError):
        db.finish(job, error="Processing was interrupted. Saved work is safe.", retry=not cancelled)


def main():
    settings = Settings(); settings.validate(); db = Database(settings)
    if settings.dev: db.initialize()
    stopping = False
    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        running = set()
        while not stopping:
            running = {f for f in running if not f.done()}
            if len(running) < 2:
                job = db.claim()
                if job: running.add(pool.submit(run_job, settings, db, job)); continue
            time.sleep(.5)


if __name__ == "__main__": main()
