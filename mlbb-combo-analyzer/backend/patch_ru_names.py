#!/usr/bin/env python3
"""Добавляет русские имена героев (name_ru) из API lang=ru."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "cache.json"
BASE = "https://mlbb.rone.dev/api"


def curl_json(url: str) -> dict:
    for attempt in range(3):
        try:
            raw = subprocess.check_output(
                ["curl", "-s", "--max-time", "30", url],
                text=True,
            )
            payload = json.loads(raw)
            if payload.get("code") == 0:
                return payload
        except Exception:
            pass
        time.sleep(1.2 * (attempt + 1))
    return {}


def fetch_ru_names_by_id(report: bool = False) -> dict[int, str]:
    from refresh_status import report_progress

    names: dict[int, str] = {}
    index = 1
    estimated_total = 132
    while True:
        payload = curl_json(f"{BASE}/heroes?size=8&index={index}&lang=ru")
        records = payload.get("data", {}).get("records", [])
        if not records:
            break
        for record in records:
            data = record.get("data", record)
            hero_id = data.get("hero_id")
            ru_name = data.get("hero", {}).get("data", {}).get("name")
            if hero_id and ru_name:
                names[int(hero_id)] = ru_name
        if report:
            report_progress(
                step="ru_names",
                current=len(names),
                total=estimated_total,
                heroes_loaded=len(names),
                heroes_total=estimated_total,
            )
        print(f"  страница {index}: {len(names)} русских имён", flush=True)
        if len(records) < 8:
            break
        index += 1
        time.sleep(0.15)
    return names


def main() -> None:
    cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    ru_names = fetch_ru_names_by_id(report=True)
    updated = 0
    for hid, hero in cache["heroes"].items():
        ru_name = ru_names.get(int(hid))
        if ru_name:
            hero["name_ru"] = ru_name
            updated += 1
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    from cache_utils import stamp_cache

    stamp_cache(CACHE_FILE)
    print(f"\nРусские имена добавлены для {updated}/{len(cache['heroes'])} героев", flush=True)


if __name__ == "__main__":
    main()
