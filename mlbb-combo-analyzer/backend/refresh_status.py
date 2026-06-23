"""Запись прогресса обновления данных в refresh_status.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUS_FILE = Path(__file__).resolve().parent.parent / "data" / "refresh_status.json"

STEP_LABELS = {
    "heroes_list": "Список героев",
    "ru_names": "Русские имена",
    "hero_details": "Синергии и контрпики",
    "meta": "Пики / баны / винрейт",
    "roles": "Роли и линии",
}


def read_status() -> dict[str, Any]:
    if not STATUS_FILE.exists():
        return {"status": "idle", "message": "Обновление не запускалось"}
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "idle", "message": "Статус недоступен"}


def _write(payload: dict[str, Any]) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def start_refresh(mode: str, message: str) -> None:
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write({
        "status": "running",
        "mode": mode,
        "started_at": started_at,
        "message": message,
        "step": "",
        "step_label": "",
        "current": 0,
        "total": 0,
        "percent": 0,
        "heroes_loaded": 0,
        "heroes_total": 0,
        "compat_loaded": 0,
        "counters_loaded": 0,
        "hero_name": "",
    })


def finish_refresh(success: bool, message: str, heroes_total: int = 0) -> None:
    prev = read_status()
    finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write({
        **prev,
        "status": "done" if success else "error",
        "finished_at": finished_at,
        "message": message,
        "percent": 100 if success else prev.get("percent", 0),
        "heroes_loaded": heroes_total or prev.get("heroes_loaded", 0),
        "heroes_total": heroes_total or prev.get("heroes_total", 0),
    })


def report_progress(
    *,
    step: str,
    current: int,
    total: int,
    hero_name: str = "",
    heroes_loaded: int | None = None,
    heroes_total: int | None = None,
    compat_loaded: int | None = None,
    counters_loaded: int | None = None,
    message: str = "",
) -> None:
    prev = read_status()
    if prev.get("status") != "running":
        return

    step_label = STEP_LABELS.get(step, step)
    percent = round(current / total * 100) if total > 0 else 0
    heroes_total_val = heroes_total if heroes_total is not None else prev.get("heroes_total", total)
    heroes_loaded_val = heroes_loaded if heroes_loaded is not None else prev.get("heroes_loaded", 0)

    if not message:
        message = f"{step_label}: {current}/{total}"
        if hero_name:
            message += f" — {hero_name}"

    payload = {
        **prev,
        "step": step,
        "step_label": step_label,
        "current": current,
        "total": total,
        "percent": percent,
        "hero_name": hero_name,
        "heroes_loaded": heroes_loaded_val,
        "heroes_total": heroes_total_val,
        "message": message,
    }
    if compat_loaded is not None:
        payload["compat_loaded"] = compat_loaded
    if counters_loaded is not None:
        payload["counters_loaded"] = counters_loaded
    _write(payload)
