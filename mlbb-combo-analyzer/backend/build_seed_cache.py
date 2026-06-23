#!/usr/bin/env python3
"""Быстрая сборка стартового кэша через curl (устойчивее к таймаутам)."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from mlbb_client import slugify

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "cache.json"
BASE = "https://mlbb.rone.dev/api"
HERO_LIMIT = 20


def curl_json(url: str) -> dict:
    for attempt in range(3):
        try:
            raw = subprocess.check_output(
                ["curl", "-s", "--max-time", "25", url],
                text=True,
            )
            return json.loads(raw)
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return {}


def main() -> None:
    heroes: dict[str, dict] = {}
    index = 1
    while len(heroes) < 130:
        payload = curl_json(f"{BASE}/heroes?size=8&index={index}&lang=en")
        records = payload.get("data", {}).get("records", [])
        if not records:
            break
        for record in records:
            data = record.get("data", record)
            hero_id = data.get("hero_id")
            hero_data = data.get("hero", {}).get("data", {})
            name = hero_data.get("name")
            if not hero_id or not name:
                continue
            slug = slugify(name)
            relation = data.get("relation", {})
            heroes[str(hero_id)] = {
                "id": hero_id,
                "name": name,
                "slug": slug,
                "image": hero_data.get("smallmap") or hero_data.get("head", ""),
                "role": "Fighter",
                "assist": [x for x in relation.get("assist", {}).get("target_hero_id", []) if x],
                "strong": [x for x in relation.get("strong", {}).get("target_hero_id", []) if x],
                "weak": [x for x in relation.get("weak", {}).get("target_hero_id", []) if x],
            }
        if len(records) < 8:
            break
        index += 1
        time.sleep(0.2)

    hero_items = sorted(heroes.values(), key=lambda h: h["id"], reverse=True)[:HERO_LIMIT]
    selected = {str(h["id"]): h for h in hero_items}

    compatibility: dict[str, dict[str, float]] = {}
    counters: dict[str, dict[str, float]] = {}

    for i, hero in enumerate(hero_items, 1):
        hid = str(hero["id"])
        slug = hero["slug"]
        print(f"[{i}/{len(hero_items)}] {hero['name']}")

        compat_payload = curl_json(f"{BASE}/heroes/{slug}/compatibility?lang=en")
        compat_records = compat_payload.get("data", {}).get("records", [])
        compat_map: dict[str, float] = {}
        if compat_records:
            for sub in compat_records[0].get("data", {}).get("sub_hero", []):
                if sub.get("heroid") is not None and sub.get("increase_win_rate") is not None:
                    compat_map[str(sub["heroid"])] = float(sub["increase_win_rate"])
        compatibility[hid] = compat_map

        counter_payload = curl_json(f"{BASE}/heroes/{slug}/counters?lang=en")
        counter_records = counter_payload.get("data", {}).get("records", [])
        counter_map: dict[str, float] = {}
        if counter_records:
            for sub in counter_records[0].get("data", {}).get("sub_hero", []):
                if sub.get("heroid") is not None and sub.get("increase_win_rate") is not None:
                    counter_map[str(sub["heroid"])] = float(sub["increase_win_rate"])
        counters[hid] = counter_map
        time.sleep(0.25)

    cache = {
        "version": 1,
        "heroes": selected,
        "compatibility": compatibility,
        "counters": counters,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Seed cache: {len(selected)} heroes -> {OUT}")


if __name__ == "__main__":
    main()
