#!/usr/bin/env python3
import argparse
import uvicorn
from stonepanel.config import Settings


def main():
    parser = argparse.ArgumentParser(description="StonePanel Server")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--dev", action="store_true", help="Enable dev mode")
    args = parser.parse_args()

    overrides = {}
    if args.host:
        overrides["host"] = args.host
    if args.port:
        overrides["port"] = args.port
    if args.dev:
        overrides["dev_mode"] = True

    settings = Settings(**overrides)
    uvicorn.run(
        "stonepanel.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.dev_mode,
    )


if __name__ == "__main__":
    main()
