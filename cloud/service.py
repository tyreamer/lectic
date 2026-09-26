"""Render entrypoint. Failure of API or worker terminates both for supervisor restart."""
import os
import signal
import subprocess
import sys
import time


def main():
    from .config import Settings
    settings = Settings(); settings.validate()
    host = "127.0.0.1" if settings.dev else "0.0.0.0"
    port = os.getenv("PORT", "8780" if settings.dev else "10000")
    commands = [[sys.executable, "-m", "uvicorn", __package__+".api:create_app", "--factory", "--host", host, "--port", port, "--no-access-log"],
                [sys.executable, "-m", __package__+".worker"]]
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    children = [subprocess.Popen(cmd, **options) for cmd in commands]
    stopping = False
    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    try:
        while not stopping and all(p.poll() is None for p in children): time.sleep(.5)
    finally:
        for p in children:
            if p.poll() is None: p.terminate()
        for p in children:
            try: p.wait(timeout=25)
            except subprocess.TimeoutExpired: p.kill()
    if not stopping: raise SystemExit(1)


if __name__ == "__main__": main()
