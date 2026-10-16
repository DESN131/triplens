#!/usr/bin/env python3
"""Start TripLens:  python run.py [--port 8090] [--host 127.0.0.1] [--open]"""

import argparse
import sys
import webbrowser

import uvicorn


def main() -> None:
    ap = argparse.ArgumentParser(description="TripLens server")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--reload", action="store_true")
    args = ap.parse_args()
    url = f"http://{args.host}:{args.port}/"
    print(f"\n  TripLens  ·  悉尼交通查询\n  {url}\n")
    if args.open:
        webbrowser.open(url)
    uvicorn.run("app.main:app", host=args.host, port=args.port,
                reload=args.reload, log_level="info")


if __name__ == "__main__":
    sys.exit(main())
