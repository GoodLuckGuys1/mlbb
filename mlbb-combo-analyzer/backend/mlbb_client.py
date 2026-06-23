"""Клиент публичного API MLBB (mlbb.rone.dev)."""

from __future__ import annotations

import re
import time
from typing import Any

import httpx

BASE_URL = "https://mlbb.rone.dev/api"
USER_AGENT = "MLBB-Combo-Analyzer/1.0"
REQUEST_DELAY = 0.35


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


class MLBBClient:
    def __init__(self, lang: str = "en") -> None:
        self.lang = lang
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=60.0,
        )

    def close(self) -> None:
        self._client.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = {"lang": self.lang}
        if params:
            query.update(params)
        time.sleep(REQUEST_DELAY)
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self._client.get(path, params=query)
                response.raise_for_status()
                payload = response.json()
                if payload.get("code") != 0:
                    raise RuntimeError(payload.get("message", "API error"))
                return payload.get("data", {})
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        raise last_error  # type: ignore[misc]

    def fetch_heroes_page(self, size: int = 10, index: int = 1) -> list[dict[str, Any]]:
        data = self._get("/heroes", {"size": size, "index": index})
        return data.get("records", [])

    def fetch_all_heroes(self) -> list[dict[str, Any]]:
        heroes: list[dict[str, Any]] = []
        index = 1
        while True:
            page = self.fetch_heroes_page(size=10, index=index)
            if not page:
                break
            heroes.extend(page)
            if len(page) < 10:
                break
            index += 1
        return heroes

    def fetch_compatibility(self, hero_slug: str) -> list[dict[str, Any]]:
        data = self._get(f"/heroes/{hero_slug}/compatibility")
        records = data.get("records", [])
        if not records:
            return []
        return records[0].get("data", {}).get("sub_hero", [])

    def fetch_counters(self, hero_slug: str) -> list[dict[str, Any]]:
        data = self._get(f"/heroes/{hero_slug}/counters")
        records = data.get("records", [])
        if not records:
            return []
        return records[0].get("data", {}).get("sub_hero", [])
