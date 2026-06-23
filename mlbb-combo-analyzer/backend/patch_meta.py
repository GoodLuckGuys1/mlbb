#!/usr/bin/env python3
"""Добавляет pick/ban/win rate в кэш героев."""

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
                ["curl", "-s", "--max-time", "20", url],
                text=True,
            )
            return json.loads(raw)
        except Exception:
            time.sleep(1.2 * (attempt + 1))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def hero_has_meta(hero: dict) -> bool:
    return hero.get("pick_rate") is not None or hero.get("ban_rate") is not None


def main() -> None:
    cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    heroes = list(cache["heroes"].values())
    total = len(heroes)
    updated = 0

    from refresh_status import report_progress

    for i, hero in enumerate(heroes, 1):
        report_progress(
            step="meta",
            current=i,
            total=total,
            hero_name=hero["name"],
            heroes_loaded=i,
            heroes_total=total,
        )
        if hero_has_meta(hero):
            print(f"[{i}/{total}] {hero['name']}: уже есть, пропуск", flush=True)
            continue

        slug = hero["slug"]
        payload = curl_json(f"{BASE}/heroes/{slug}/stats?lang=en")
        records = payload.get("data", {}).get("records", [])
        pick = ban = win = 0.0
        if records:
            data = records[0].get("data", {})
            pick = float(data.get("main_hero_appearance_rate") or 0)
            ban = float(data.get("main_hero_ban_rate") or 0)
            win = float(data.get("main_hero_win_rate") or 0)
        hero["pick_rate"] = pick
        hero["ban_rate"] = ban
        hero["win_rate"] = win
        cache["heroes"][str(hero["id"])] = hero
        save_cache(cache)
        updated += 1
        print(
            f"[{i}/{total}] {hero['name']}: pick {pick*100:.2f}% ban {ban*100:.2f}% win {win*100:.2f}%",
            flush=True,
        )
        time.sleep(0.12)

    from cache_utils import stamp_cache

    stamp_cache(CACHE_FILE)
    print(f"\nМета-статистика обновлена: {updated} новых, {total} всего", flush=True)


if __name__ == "__main__":
    main()
