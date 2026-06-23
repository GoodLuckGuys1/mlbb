#!/usr/bin/env python3
"""Обновляет роли и линии героев из API деталей."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from mlbb_client import slugify

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "cache.json"
BASE = "https://mlbb.rone.dev/api"


def curl_json(url: str) -> dict:
    for attempt in range(3):
        try:
            raw = subprocess.check_output(
                ["curl", "-s", "--max-time", "20", url],
                text=True,
            )
            return json.loads(raw)
        except Exception:
            time.sleep(1.2 * (attempt + 1))
    return {}


def fetch_role_lane(slug: str) -> tuple[str, str]:
    payload = curl_json(f"{BASE}/heroes/{slug}?lang=en")
    records = payload.get("data", {}).get("records", [])
    if not records:
        return "Fighter", ""
    hero = records[0].get("data", {}).get("hero", {}).get("data", {})
    role = (hero.get("sortlabel") or ["Fighter"])[0] or "Fighter"
    lane = (hero.get("roadsortlabel") or [""])[0] or ""
    return role, lane


def main() -> None:
    cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    heroes = list(cache["heroes"].values())
    total = len(heroes)

    from refresh_status import report_progress

    for i, hero in enumerate(heroes, 1):
        report_progress(
            step="roles",
            current=i,
            total=total,
            hero_name=hero["name"],
            heroes_loaded=i,
            heroes_total=total,
        )
        slug = hero.get("slug") or slugify(hero["name"])
        role, lane = fetch_role_lane(slug)
        hero["role"] = role
        hero["lane"] = lane
        print(f"[{i}/{total}] {hero['name']}: {role} / {lane}", flush=True)
        time.sleep(0.15)

    from cache_utils import stamp_cache

    stamp_cache(CACHE_FILE)
    print(f"\nРоли обновлены для {total} героев", flush=True)


if __name__ == "__main__":
    main()
