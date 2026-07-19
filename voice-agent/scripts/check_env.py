#!/usr/bin/env python3
"""Validate required env vars without printing secret values."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

load_dotenv(ROOT / ".env.local")

from config import missing_required_env_vars  # noqa: E402


def main() -> int:
    missing = missing_required_env_vars()
    if missing:
        print("Missing required environment variables:")
        for name in missing:
            print(f"  - {name}")
        print("Copy voice-agent/.env.example to .env.local and fill values.")
        return 1

    print("All required environment variables are set.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
