#!/usr/bin/env python3
"""Загрузка и кэширование данных всех героев MLBB."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from mlbb_client import slugify

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_FILE = DATA_DIR / "cache.json"
BASE = "https://mlbb.rone.dev/api"

ROLE_KEYWORDS = {
    "tigreal": "Tank", "akai": "Tank", "khufra": "Tank", "gatot": "Tank",
    "belerick": "Tank", "barats": "Tank", "grock": "Tank", "hylos": "Tank",
    "minotaur": "Tank", "lolita": "Tank", "franco": "Tank", "johnson": "Tank",
    "uranus": "Tank", "baxia": "Tank", "atlas": "Tank", "fredrinn": "Tank",
    "edith": "Tank", "gloo": "Tank", "carmilla": "Support", "rafaela": "Support",
    "estes": "Support", "floryn": "Support", "diggie": "Support", "angela": "Support",
    "kaja": "Support", "nana": "Support", "mathilda": "Support", "lolita": "Tank",
    "ling": "Assassin", "lancelot": "Assassin", "hayabusa": "Assassin", "natalia": "Assassin",
    "saber": "Assassin", "karina": "Assassin", "fanny": "Assassin", "helcurt": "Assassin",
    "miya": "Marksman", "claude": "Marksman", "bruno": "Marksman", "wanwan": "Marksman",
    "layla": "Marksman", "moskov": "Marksman", "karrie": "Marksman", "beatrix": "Marksman",
    "kagura": "Mage", "eudora": "Mage", "lunox": "Mage", "pharsa": "Mage",
    "valir": "Mage", "chang'e": "Mage", "change": "Mage", "yve": "Mage",
}


def curl_json(url: str) -> dict:
    for attempt in range(4):
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
        time.sleep(1.5 * (attempt + 1))
    return {}


def parse_hero_record(record: dict) -> dict | None:
    data = record.get("data", record)
    hero_id = data.get("hero_id")
    hero_block = data.get("hero", {}).get("data", {})
    name = hero_block.get("name")
    if not hero_id or not name:
        return None

    relation = data.get("relation", {})
    slug = slugify(name)

    return {
        "id": hero_id,
        "name": name,
        "slug": slug,
        "image": hero_block.get("smallmap") or hero_block.get("head", ""),
        "role": ROLE_KEYWORDS.get(slug, "Fighter"),
        "lane": "",
        "assist": [x for x in relation.get("assist", {}).get("target_hero_id", []) if x],
        "strong": [x for x in relation.get("strong", {}).get("target_hero_id", []) if x],
        "weak": [x for x in relation.get("weak", {}).get("target_hero_id", []) if x],
    }


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
        if len(records) < 8:
            break
        index += 1
        time.sleep(0.15)
    return names


def attach_ru_names(heroes: dict[str, dict], report: bool = False) -> None:
    ru_names = fetch_ru_names_by_id(report=report)
    for hid, hero in heroes.items():
        ru_name = ru_names.get(int(hid))
        if ru_name:
            hero["name_ru"] = ru_name


def fetch_all_heroes(report: bool = False) -> list[dict]:
    from refresh_status import report_progress

    heroes: dict[str, dict] = {}
    index = 1
    estimated_total = 132
    while True:
        payload = curl_json(f"{BASE}/heroes?size=8&index={index}&lang=en")
        records = payload.get("data", {}).get("records", [])
        if not records:
            break
        for record in records:
            parsed = parse_hero_record(record)
            if parsed:
                heroes[str(parsed["id"])] = parsed
        if report:
            report_progress(
                step="heroes_list",
                current=len(heroes),
                total=estimated_total,
                heroes_loaded=len(heroes),
                heroes_total=estimated_total,
            )
        print(f"  страница {index}: всего {len(heroes)} героев", flush=True)
        if len(records) < 8:
            break
        index += 1
        time.sleep(0.2)
    print("Загрузка русских имён...", flush=True)
    attach_ru_names(heroes, report=report)
    return sorted(heroes.values(), key=lambda h: h["id"], reverse=True)


def fetch_compat(slug: str) -> dict[str, float]:
    payload = curl_json(f"{BASE}/heroes/{slug}/compatibility?lang=en")
    records = payload.get("data", {}).get("records", [])
    result: dict[str, float] = {}
    if records:
        for sub in records[0].get("data", {}).get("sub_hero", []):
            if sub.get("heroid") is not None and sub.get("increase_win_rate") is not None:
                result[str(sub["heroid"])] = float(sub["increase_win_rate"])
    return result


def fetch_role_lane(slug: str) -> tuple[str, str]:
    payload = curl_json(f"{BASE}/heroes/{slug}?lang=en")
    records = payload.get("data", {}).get("records", [])
    if not records:
        return "Fighter", ""
    hero = records[0].get("data", {}).get("hero", {}).get("data", {})
    role = (hero.get("sortlabel") or ["Fighter"])[0] or "Fighter"
    lane = (hero.get("roadsortlabel") or [""])[0] or ""
    return role, lane


def fetch_counters(slug: str) -> dict[str, float]:
    payload = curl_json(f"{BASE}/heroes/{slug}/counters?lang=en")
    records = payload.get("data", {}).get("records", [])
    result: dict[str, float] = {}
    if records:
        for sub in records[0].get("data", {}).get("sub_hero", []):
            if sub.get("heroid") is not None and sub.get("increase_win_rate") is not None:
                result[str(sub["heroid"])] = float(sub["increase_win_rate"])
    return result


def sync(limit: int | None = None, report: bool = False) -> dict:
    from refresh_status import report_progress

    print("Загрузка списка героев...", flush=True)
    hero_list = fetch_all_heroes(report=report)
    if limit:
        hero_list = hero_list[:limit]

    compatibility: dict[str, dict[str, float]] = {}
    counters: dict[str, dict[str, float]] = {}
    total = len(hero_list)

    for i, hero in enumerate(hero_list, 1):
        hid = str(hero["id"])
        slug = hero["slug"]
        if report:
            report_progress(
                step="hero_details",
                current=i,
                total=total,
                hero_name=hero["name"],
                heroes_loaded=i,
                heroes_total=total,
                compat_loaded=i,
                counters_loaded=i,
            )
        print(f"[{i}/{total}] {hero['name']}", flush=True)
        role, lane = fetch_role_lane(slug)
        hero["role"] = role
        hero["lane"] = lane
        compatibility[hid] = fetch_compat(slug)
        counters[hid] = fetch_counters(slug)
        time.sleep(0.2)

    return {
        "version": 1,
        "heroes": {str(h["id"]): h for h in hero_list},
        "compatibility": compatibility,
        "counters": counters,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Синхронизация данных MLBB")
    parser.add_argument("--limit", type=int, default=None, help="Ограничить число героев")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache = sync(limit=args.limit, report=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    from cache_utils import stamp_cache

    stamp_cache(CACHE_FILE)
    print(f"\nГотово: {len(cache['heroes'])} героев → {CACHE_FILE}", flush=True)


if __name__ == "__main__":
    main()
