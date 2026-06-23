"""Утилиты для кэша данных."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "cache.json"


def stamp_cache(path: Path | None = None) -> str:
    target = path or CACHE_FILE
    cache = json.loads(target.read_text(encoding="utf-8"))
    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cache["updated_at"] = updated_at
    target.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    return updated_at


def read_updated_at(path: Path | None = None) -> str | None:
    target = path or CACHE_FILE
    if not target.exists():
        return None
    cache = json.loads(target.read_text(encoding="utf-8"))
    return cache.get("updated_at")
