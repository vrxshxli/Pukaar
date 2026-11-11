"""Pukaar backend.

A local .env file (repo root or backend/) is read here, before any module
reads its settings, so a free Groq key can live outside git. Real environment
variables always win.
"""
import os
from pathlib import Path


def _load_env():
    here = Path(__file__).resolve().parents[1]
    for path in (here.parent / ".env", here / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value


if not os.environ.get("PUKAAR_NO_DOTENV"):
    _load_env()
