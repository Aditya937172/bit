from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn


ROOT_DIR = Path(__file__).resolve().parent
APP_IMPORT = "dashboard_backend.app:app"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the MediCore AI local dashboard server."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the server to.")
    parser.add_argument("--port", type=int, default=8511, help="Port to bind the server to.")
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the dashboard in the default browser after startup.",
    )
    return parser.parse_args()


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.75)
        return sock.connect_ex((host, port)) == 0


def maybe_open_browser(host: str, port: int) -> None:
    time.sleep(1.5)
    webbrowser.open(f"http://{host}:{port}/ui/index.html")


def main() -> int:
    args = parse_args()
    os.chdir(ROOT_DIR)

    if port_in_use(args.host, args.port):
        print(f"Server already appears to be running on http://{args.host}:{args.port}")
        print(f"Dashboard: http://{args.host}:{args.port}/ui/index.html")
        return 0

    print("Starting MediCore AI local server...")
    print(f"Backend health: http://{args.host}:{args.port}/api/health")
    print(f"Dashboard UI:   http://{args.host}:{args.port}/ui/index.html")
    print("Press Ctrl+C to stop the server.")

    if args.open:
        threading.Thread(
            target=maybe_open_browser,
            args=(args.host, args.port),
            daemon=True,
        ).start()

    uvicorn.run(
        APP_IMPORT,
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
        print("\nServer stopped.")
        raise SystemExit(0)
