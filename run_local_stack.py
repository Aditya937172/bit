from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn


ROOT_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the BodyWise local stack. The frontend is served by the FastAPI backend."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the backend server to.")
    parser.add_argument("--port", type=int, default=8511, help="Port to bind the backend server to.")
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the dashboard automatically in the default browser after startup.",
    )
    return parser.parse_args()


def maybe_open_browser(host: str, port: int) -> None:
    time.sleep(1.5)
    webbrowser.open(f"http://{host}:{port}/ui/index.html")


def main() -> int:
    args = parse_args()
    os.chdir(ROOT_DIR)

    print("Starting BodyWise local stack...")
    print(f"Backend API: http://{args.host}:{args.port}/api/health")
    print(f"Frontend UI: http://{args.host}:{args.port}/ui/index.html")
    print("Press Ctrl+C to stop the server.")

    if args.open:
        threading.Thread(
            target=maybe_open_browser,
            args=(args.host, args.port),
            daemon=True,
        ).start()

    uvicorn.run(
        "dashboard_backend.app:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nStopped BodyWise local stack.")
        raise SystemExit(0)
