"""Run the local review and editing workstation."""

import argparse
import os
from pathlib import Path

import uvicorn

from .app import create_app
from .local_config import load_local_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local photo review workstation")
    parser.add_argument("--data-dir", type=Path, default=Path("data/catalog"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    access_password = os.environ.get("PHOTO_EDITOR_ACCESS_PASSWORD", "")
    if args.host not in ("127.0.0.1", "localhost", "::1") and not access_password:
        raise SystemExit("Network binding requires PHOTO_EDITOR_ACCESS_PASSWORD; use scripts/start.ps1")
    try:
        loaded = load_local_config()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    if loaded:
        print("Loaded private server configuration from config/openAI.env")
    uvicorn.run(create_app(args.data_dir, access_password=access_password), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
