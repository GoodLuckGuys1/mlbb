"""FastAPI-сервер: API + статика фронтенда."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from cache_utils import read_updated_at
from combo_engine import ComboEngine

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "cache.json"
STATUS_FILE = ROOT / "data" / "refresh_status.json"
FRONTEND = ROOT / "frontend"
UPDATE_SCRIPT = ROOT / "scripts" / "update_data.sh"
UPDATE_FULL_SCRIPT = ROOT / "scripts" / "update_data_full.sh"


def read_refresh_status() -> dict[str, Any]:
    if not STATUS_FILE.exists():
        return {"status": "idle", "message": "Обновление не запускалось"}
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "idle", "message": "Статус недоступен"}

app = FastAPI(title="MLBB Combo Analyzer", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_engine: ComboEngine | None = None


def load_engine() -> ComboEngine:
    global _engine
    if _engine is not None:
        return _engine
    if not DATA_FILE.exists():
        raise HTTPException(
            status_code=503,
            detail="Кэш данных не найден. Запустите: python backend/sync_data.py",
        )
    cache = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    _engine = ComboEngine(cache)
    return _engine


class AnalyzeRequest(BaseModel):
    allies: list[int] = Field(default_factory=list)
    enemies: list[int] = Field(default_factory=list)
    ally_bans: list[int] = Field(default_factory=list)
    enemy_bans: list[int] = Field(default_factory=list)
    anchor: Optional[int] = None
    mode: str = Field(default="all", pattern="^(duo|trio|team|all|complete|partner)$")
    limit: int = Field(default=12, ge=1, le=50)


class BanSuggestRequest(BaseModel):
    allies: list[int] = Field(default_factory=list)
    enemies: list[int] = Field(default_factory=list)
    ally_bans: list[int] = Field(default_factory=list)
    enemy_bans: list[int] = Field(default_factory=list)
    limit: int = Field(default=8, ge=1, le=20)


class IngameAdviceRequest(BaseModel):
    allies: list[int] = Field(default_factory=list)
    enemies: list[int] = Field(default_factory=list)
    phase: str = Field(default="mid", pattern="^(early|mid|late)$")
    gold: str = Field(default="even", pattern="^(ahead|even|behind)$")
    situation: str = Field(default="")


@app.post("/api/reload")
def reload_cache() -> dict[str, Any]:
    global _engine
    _engine = None
    engine = load_engine()
    return {"ok": True, "heroes": len(engine.heroes)}


@app.get("/api/health")
def health() -> dict[str, Any]:
    refresh = read_refresh_status()
    return {
        "ok": True,
        "cache_exists": DATA_FILE.exists(),
        "heroes": len(load_engine().heroes) if DATA_FILE.exists() else 0,
        "updated_at": read_updated_at(),
        "refresh": refresh,
    }


@app.get("/api/refresh-status")
def refresh_status() -> dict[str, Any]:
    return read_refresh_status()


@app.post("/api/refresh-data")
def refresh_data(full: bool = False) -> dict[str, Any]:
    status = read_refresh_status()
    if status.get("status") == "running":
        raise HTTPException(status_code=409, detail="Обновление уже выполняется")

    script = UPDATE_FULL_SCRIPT if full else UPDATE_SCRIPT
    if not script.exists():
        raise HTTPException(status_code=500, detail=f"Скрипт не найден: {script}")

    subprocess.Popen(
        ["/bin/bash", str(script)],
        cwd=str(ROOT),
        start_new_session=True,
    )
    return {
        "ok": True,
        "status": "running",
        "message": "Полное обновление запущено" if full else "Обновление запущено",
    }


@app.get("/api/heroes")
def list_heroes() -> dict[str, Any]:
    engine = load_engine()
    heroes = sorted(
        engine.heroes.values(),
        key=lambda h: h["name"].lower(),
    )
    return {"heroes": heroes}


@app.get("/api/meta/tops")
def meta_tops(limit: int = 15, role: str = "") -> dict[str, Any]:
    engine = load_engine()
    role_filter = role if role in {"Tank", "Fighter", "Assassin", "Mage", "Marksman", "Support"} else None
    data = engine.get_meta_tops(limit=min(limit, 30), role_filter=role_filter)
    if not data["has_meta"]:
        raise HTTPException(
            status_code=503,
            detail="Нет данных пиков/банов. Запустите: python backend/patch_meta.py",
        )
    return data


@app.get("/api/meta/tierlist")
def meta_tierlist(
    role: str = "",
    lane: str = "",
    mode: str = "overall",
) -> dict[str, Any]:
    engine = load_engine()
    role_filter = role if role in {"Tank", "Fighter", "Assassin", "Mage", "Marksman", "Support"} else None
    lane_filter = lane if lane in {"Gold Lane", "Mid Lane", "Exp Lane", "Roam", "Jungle"} else None
    metric = mode if mode in {
        "overall", "winrate", "pick", "ban", "draft", "early", "mid", "late",
    } else "overall"
    data = engine.get_tier_list(role_filter=role_filter, lane_filter=lane_filter, mode=metric)
    if not data["has_meta"]:
        raise HTTPException(
            status_code=503,
            detail="Нет данных пиков/банов. Запустите: python backend/patch_meta.py",
        )
    return data


@app.get("/api/counters/{hero_id}")
def counter_picks(
    hero_id: int,
    limit: int = 15,
    exclude: str = "",
    role: str = "",
    lane: str = "",
) -> dict[str, Any]:
    engine = load_engine()
    if str(hero_id) not in engine.heroes:
        raise HTTPException(status_code=404, detail=f"Герой не найден: {hero_id}")

    exclude_ids: set[int] = set()
    if exclude:
        for part in exclude.split(","):
            part = part.strip()
            if part.isdigit():
                exclude_ids.add(int(part))

    target = engine.heroes[str(hero_id)]
    role_filter = role if role in {"Tank", "Fighter", "Assassin", "Mage", "Marksman", "Support"} else None
    lane_filter = lane if lane in {"Gold Lane", "Mid Lane", "Exp Lane", "Roam", "Jungle"} else None
    picks = engine.get_counter_picks(
        hero_id,
        exclude=exclude_ids,
        limit=min(limit, 30),
        role_filter=role_filter,
        lane_filter=lane_filter,
    )

    return {
        "target": {
            "id": hero_id,
            "name": target["name"],
            "role": target.get("role", "Fighter"),
            "lane": target.get("lane", ""),
            "image": target.get("image", ""),
        },
        "my_role": role_filter,
        "my_lane": lane_filter,
        "counters": picks,
        "advice": engine.suggest_picks(
            [],
            [hero_id],
            limit=5,
            role_filter=role_filter,
            lane_filter=lane_filter,
        ),
    }


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest) -> dict[str, Any]:
    engine = load_engine()

    if not req.enemies and not req.allies:
        raise HTTPException(status_code=400, detail="Укажите врагов или своих героев")

    check_ids = req.allies + req.enemies + ([req.anchor] if req.anchor else [])
    for hid in check_ids:
        if str(hid) not in engine.heroes:
            raise HTTPException(status_code=400, detail=f"Неизвестный герой: {hid}")

    duos: list[dict] = []
    partners: list[dict] = []
    anchor_id: Optional[int] = None
    trios: list[dict] = []
    teams: list[dict] = []
    complete: list[dict] = []

    if req.mode in ("duo", "all"):
        duos = [
            r.to_dict()
            for r in engine.analyze(
                req.allies, req.enemies, size=2, limit=req.limit,
                ally_bans=req.ally_bans, enemy_bans=req.enemy_bans,
            )
        ]

    if req.mode in ("trio", "all"):
        trios = [
            r.to_dict()
            for r in engine.analyze(
                req.allies, req.enemies, size=3, limit=req.limit,
                ally_bans=req.ally_bans, enemy_bans=req.enemy_bans,
            )
        ]

    if req.mode in ("team", "all"):
        teams = [
            r.to_dict()
            for r in engine.suggest_teams(
                req.allies, req.enemies, limit=req.limit,
                ally_bans=req.ally_bans, enemy_bans=req.enemy_bans,
            )
        ]

    if req.mode == "complete" and req.allies:
        complete = [
            r.to_dict()
            for r in engine.suggest_complete(req.allies, req.enemies, limit=req.limit)
        ]

    anchor_id = req.anchor
    if anchor_id is None and req.allies:
        anchor_id = req.allies[-1]
    if anchor_id is not None and req.mode in ("partner", "all", "duo", "complete"):
        exclude = set(req.allies) | set(req.enemies)
        partners = [
            r.to_dict()
            for r in engine.best_partners(anchor_id, req.enemies, exclude=exclude, limit=req.limit)
        ]

    prediction = engine.predict_match(req.allies, req.enemies)
    if req.allies and not req.enemies:
        prediction = None

    advice = engine.suggest_picks(
        req.allies,
        req.enemies,
        anchor=anchor_id,
        limit=8,
        ally_bans=req.ally_bans,
        enemy_bans=req.enemy_bans,
    )

    ban_advice = engine.suggest_bans(
        req.allies,
        req.enemies,
        ally_bans=req.ally_bans,
        enemy_bans=req.enemy_bans,
        limit=6,
    )

    return {
        "allies": req.allies,
        "enemies": req.enemies,
        "ally_bans": req.ally_bans,
        "enemy_bans": req.enemy_bans,
        "duos": duos,
        "trios": trios,
        "teams": teams,
        "complete": complete,
        "partners": partners,
        "anchor": anchor_id,
        "anchor_name": engine.hero_name(anchor_id) if anchor_id else None,
        "prediction": prediction.to_dict() if prediction else None,
        "advice": advice,
        "ban_advice": ban_advice,
    }


@app.post("/api/bans/suggest")
def suggest_bans(req: BanSuggestRequest) -> dict[str, Any]:
    engine = load_engine()
    return engine.suggest_bans(
        req.allies,
        req.enemies,
        ally_bans=req.ally_bans,
        enemy_bans=req.enemy_bans,
        limit=req.limit,
    )


@app.get("/api/pick-vs/{hero_id}")
def pick_vs_enemy(
    hero_id: int,
    allies: str = "",
    enemies: str = "",
    ally_bans: str = "",
    enemy_bans: str = "",
    limit: int = 8,
) -> dict[str, Any]:
    engine = load_engine()
    if str(hero_id) not in engine.heroes:
        raise HTTPException(status_code=404, detail=f"Герой не найден: {hero_id}")

    def parse_ids(raw: str) -> list[int]:
        return [int(p) for p in raw.split(",") if p.strip().isdigit()]

    return engine.suggest_pick_vs_enemy(
        hero_id,
        parse_ids(allies),
        parse_ids(enemies),
        ally_bans=parse_ids(ally_bans),
        enemy_bans=parse_ids(enemy_bans),
        limit=min(limit, 15),
    )


@app.post("/api/ingame/advice")
def ingame_advice(req: IngameAdviceRequest) -> dict[str, Any]:
    engine = load_engine()
    for hid in req.allies + req.enemies:
        if str(hid) not in engine.heroes:
            raise HTTPException(status_code=400, detail=f"Неизвестный герой: {hid}")
    situation = req.situation if req.situation in {"teamfight", "split", "defend"} else ""
    return engine.ingame_advice(
        req.allies,
        req.enemies,
        phase=req.phase,
        gold=req.gold,
        situation=situation,
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


app.mount("/css", StaticFiles(directory=FRONTEND / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND / "js"), name="js")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
