"""Движок оценки дабл/трипл связок против вражеского состава."""

from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional


ROLES = ("Tank", "Fighter", "Assassin", "Mage", "Marksman", "Support")
TEAM_SIZE = 5
DAMAGE_ROLES = frozenset({"Mage", "Marksman", "Assassin"})
FRONTLINE_ROLES = frozenset({"Tank", "Fighter"})
PHASE_WEIGHTS = {"early": 0.20, "mid": 0.30, "late": 0.50}
ROLE_PHASE_POWER: dict[str, dict[str, float]] = {
    "Tank": {"early": 0.78, "mid": 0.70, "late": 0.45},
    "Fighter": {"early": 0.72, "mid": 0.74, "late": 0.66},
    "Assassin": {"early": 0.84, "mid": 0.72, "late": 0.50},
    "Mage": {"early": 0.55, "mid": 0.76, "late": 0.88},
    "Marksman": {"early": 0.40, "mid": 0.65, "late": 0.94},
    "Support": {"early": 0.66, "mid": 0.72, "late": 0.56},
}
DUO_SAME_ROLE_BLOCK = frozenset({"Support", "Mage", "Marksman", "Assassin", "Tank"})
ROLE_PICK_LIMITS: dict[str, int] = {
    "Support": 1,
    "Marksman": 1,
    "Mage": 2,
    "Tank": 2,
    "Assassin": 2,
    "Fighter": 3,
}
SINGLE_LANE_ROLES = frozenset({"Gold Lane", "Mid Lane", "Exp Lane", "Roam"})
COMPLEMENTARY_PAIRS = (
    ({"Tank", "Support"}, {"Mage", "Marksman", "Assassin", "Fighter"}),
    ({"Support"}, {"Marksman", "Mage", "Assassin"}),
    ({"Tank"}, {"Marksman", "Mage", "Assassin"}),
    ({"Fighter"}, {"Mage", "Marksman"}),
)


@dataclass
class MatchPrediction:
    winner: str
    winner_label: str
    ally_win_chance: float
    ally_score: float
    enemy_score: float
    ally_synergy: float
    enemy_synergy: float
    ally_counter: float
    enemy_counter: float
    notes: list[str]
    ally_phases: dict[str, float] = field(default_factory=dict)
    enemy_phases: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "winner": self.winner,
            "winner_label": self.winner_label,
            "ally_win_chance": round(self.ally_win_chance, 1),
            "ally_score": round(self.ally_score, 2),
            "enemy_score": round(self.enemy_score, 2),
            "ally_synergy": round(self.ally_synergy, 4),
            "enemy_synergy": round(self.enemy_synergy, 4),
            "ally_counter": round(self.ally_counter, 4),
            "enemy_counter": round(self.enemy_counter, 4),
            "notes": self.notes,
            "ally_phases": self.ally_phases,
            "enemy_phases": self.enemy_phases,
        }


@dataclass
class ComboResult:
    heroes: list[int]
    hero_names: list[str]
    synergy: float
    counter: float
    threat: float
    score: float
    roles: list[str]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "heroes": self.heroes,
            "hero_names": self.hero_names,
            "synergy": round(self.synergy, 4),
            "counter": round(self.counter, 4),
            "threat": round(self.threat, 4),
            "score": round(self.score, 2),
            "roles": self.roles,
            "notes": self.notes,
        }


class ComboEngine:
    def __init__(self, cache: dict[str, Any]) -> None:
        self.heroes: dict[str, dict[str, Any]] = cache["heroes"]
        self.compatibility: dict[str, dict[str, float]] = cache["compatibility"]
        self.counters: dict[str, dict[str, float]] = cache["counters"]
        self._ids = {int(k) for k in self.heroes}

    def hero_name(self, hero_id: int) -> str:
        return self.heroes[str(hero_id)]["name"]

    def hero_role(self, hero_id: int) -> str:
        return self.heroes[str(hero_id)].get("role", "Fighter")

    def hero_lane(self, hero_id: int) -> str:
        return self.heroes[str(hero_id)].get("lane", "")

    def hero_image(self, hero_id: int) -> str:
        return self.heroes[str(hero_id)].get("image", "")

    def get_meta_tops(
        self,
        limit: int = 15,
        role_filter: Optional[str] = None,
    ) -> dict[str, Any]:
        heroes: list[dict[str, Any]] = []
        for hid, hero in self.heroes.items():
            if role_filter and hero.get("role") != role_filter:
                continue
            pick = float(hero.get("pick_rate") or 0)
            ban = float(hero.get("ban_rate") or 0)
            win = float(hero.get("win_rate") or 0)
            if pick == 0 and ban == 0 and win == 0:
                continue
            heroes.append({
                "hero_id": int(hid),
                "hero_name": hero["name"],
                "role": hero.get("role", "Fighter"),
                "lane": hero.get("lane", ""),
                "image": hero.get("image", ""),
                "pick_rate": round(pick, 5),
                "pick_percent": round(pick * 100, 2),
                "ban_rate": round(ban, 5),
                "ban_percent": round(ban * 100, 2),
                "win_rate": round(win, 5),
                "win_percent": round(win * 100, 2),
            })

        return {
            "top_picks": sorted(heroes, key=lambda h: h["pick_rate"], reverse=True)[:limit],
            "top_bans": sorted(heroes, key=lambda h: h["ban_rate"], reverse=True)[:limit],
            "top_winrate": sorted(heroes, key=lambda h: h["win_rate"], reverse=True)[:limit],
            "has_meta": bool(heroes),
        }

    def _percentile_ranks(self, values: list[float]) -> list[float]:
        if not values:
            return []
        indexed = sorted(enumerate(values), key=lambda item: item[1])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(indexed):
            j = i
            while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
                j += 1
            rank = (i + j) / (2 * max(len(indexed) - 1, 1))
            for k in range(i, j + 1):
                ranks[indexed[k][0]] = rank
            i = j + 1
        return ranks

    def _tier_from_percentile(self, percentile: float) -> str:
        if percentile >= 0.85:
            return "S"
        if percentile >= 0.65:
            return "A"
        if percentile >= 0.40:
            return "B"
        if percentile >= 0.20:
            return "C"
        return "D"

    def _avg_top_values(self, values: list[float], top_n: int = 5) -> float:
        if not values:
            return 0.0
        picked = sorted(values, reverse=True)[:top_n]
        return sum(picked) / len(picked)

    def _hero_synergy_score(self, hero_id: int) -> float:
        return self._avg_top_values(list(self.compatibility.get(str(hero_id), {}).values()))

    def _hero_counter_score(self, hero_id: int) -> float:
        return self._avg_top_values(list(self.counters.get(str(hero_id), {}).values()))

    def _hero_vulnerability(self, hero_id: int) -> float:
        sid = str(hero_id)
        rates = [targets[sid] for targets in self.counters.values() if sid in targets]
        return self._avg_top_values(rates)

    def _hero_meta_tags(self, hero: dict[str, Any]) -> list[str]:
        tags: list[str] = []
        win = hero["win_percent"]
        pick = hero["pick_percent"]
        ban = hero["ban_percent"]
        synergy = hero.get("synergy_score", 0.0)
        counter = hero.get("counter_score", 0.0)
        vulnerability = hero.get("vulnerability", 0.0)

        if ban >= 15:
            tags.append("must-ban")
        elif ban >= 8:
            tags.append("частый бан")
        if pick >= 2.5 and win < 49:
            tags.append("перепик")
        elif pick < 0.8 and win >= 52:
            tags.append("недооценён")
        if synergy >= 0.025:
            tags.append("синергист")
        if counter >= 0.02:
            tags.append("контрпикер")
        if vulnerability >= 0.018:
            tags.append("уязвим")
        if win >= 53 and pick >= 1.5:
            tags.append("стабилен")
        return tags[:3]

    def _hero_insight(self, hero: dict[str, Any], tags: list[str]) -> str:
        if "must-ban" in tags:
            return "Опасен в мете — почти всегда бан или первый пик."
        if "перепик" in tags:
            return "Популярен, но винрейт ниже среднего — рискованный пик."
        if "недооценён" in tags:
            return "Редко берут, но статистика побед сильная — потенциальный сюрприз."
        if "синергист" in tags and "контрпикер" in tags:
            return "Универсален: хорош в связках и в точечных контрпиках."
        if "синергист" in tags:
            return "Лучше раскрывается в составе с сильными напарниками."
        if "контрпикер" in tags:
            return "Силён против отдельных целей — хорош как ответный пик."
        if "уязвим" in tags:
            return "Есть жёсткие контрпики — берите с осторожностью."
        if hero["win_percent"] >= 52:
            return "Стабильный винрейт в текущей мете."
        return "Ситуативный герой — зависит от драфта и скилла."

    def _tier_mode_label(self, mode: str) -> str:
        labels = {
            "overall": "Общий рейтинг (WR 50% + pick 30% + ban 20%)",
            "winrate": "По винрейту",
            "pick": "По пикрейту",
            "ban": "По банрейту",
            "draft": "Драфт-ценность (WR + синергии + контрпики)",
            "early": "Сила в ранней игре",
            "mid": "Сила в средней игре",
            "late": "Сила в поздней игре",
        }
        return labels.get(mode, labels["overall"])

    def get_tier_list(
        self,
        role_filter: Optional[str] = None,
        lane_filter: Optional[str] = None,
        mode: str = "overall",
    ) -> dict[str, Any]:
        empty_tiers = {t: [] for t in ("S", "A", "B", "C", "D")}
        heroes: list[dict[str, Any]] = []
        for hid, hero in self.heroes.items():
            if role_filter and hero.get("role") != role_filter:
                continue
            if lane_filter and hero.get("lane") != lane_filter:
                continue
            pick = float(hero.get("pick_rate") or 0)
            ban = float(hero.get("ban_rate") or 0)
            win = float(hero.get("win_rate") or 0)
            if pick == 0 and ban == 0 and win == 0:
                continue
            hero_id = int(hid)
            phases = self._hero_phase_power(hero_id)
            heroes.append({
                "hero_id": hero_id,
                "hero_name": hero["name"],
                "role": hero.get("role", "Fighter"),
                "lane": hero.get("lane", ""),
                "image": hero.get("image", ""),
                "pick_rate": pick,
                "pick_percent": round(pick * 100, 2),
                "ban_rate": ban,
                "ban_percent": round(ban * 100, 2),
                "win_rate": win,
                "win_percent": round(win * 100, 2),
                "synergy_score": round(self._hero_synergy_score(hero_id), 4),
                "counter_score": round(self._hero_counter_score(hero_id), 4),
                "vulnerability": round(self._hero_vulnerability(hero_id), 4),
                "phases": {
                    phase: self._phase_percent(phases[phase]) for phase in PHASE_WEIGHTS
                },
            })

        if not heroes:
            return {
                "has_meta": False,
                "mode": mode,
                "mode_label": self._tier_mode_label(mode),
                "tiers": empty_tiers,
                "highlights": {},
                "tier_counts": empty_tiers,
            }

        win_ranks = self._percentile_ranks([h["win_rate"] for h in heroes])
        pick_ranks = self._percentile_ranks([h["pick_rate"] for h in heroes])
        ban_ranks = self._percentile_ranks([h["ban_rate"] for h in heroes])
        synergy_ranks = self._percentile_ranks([h["synergy_score"] for h in heroes])
        counter_ranks = self._percentile_ranks([h["counter_score"] for h in heroes])
        vuln_ranks = self._percentile_ranks([h["vulnerability"] for h in heroes])

        for idx, hero in enumerate(heroes):
            hero["scores"] = {
                "win": round(win_ranks[idx] * 100, 1),
                "pick": round(pick_ranks[idx] * 100, 1),
                "ban": round(ban_ranks[idx] * 100, 1),
                "synergy": round(synergy_ranks[idx] * 100, 1),
                "counter": round(counter_ranks[idx] * 100, 1),
                "vulnerability": round(vuln_ranks[idx] * 100, 1),
            }
            draft_score = (
                win_ranks[idx] * 0.35
                + synergy_ranks[idx] * 0.25
                + counter_ranks[idx] * 0.25
                - vuln_ranks[idx] * 0.15
            )
            hero["scores"]["draft"] = round(max(0.0, draft_score) * 100, 1)

            if mode == "winrate":
                hero["score"] = hero["win_rate"]
            elif mode == "pick":
                hero["score"] = hero["pick_rate"]
            elif mode == "ban":
                hero["score"] = hero["ban_rate"]
            elif mode == "draft":
                hero["score"] = draft_score
            elif mode in PHASE_WEIGHTS:
                hero["score"] = hero["phases"][mode] / 100
            else:
                hero["score"] = win_ranks[idx] * 0.5 + pick_ranks[idx] * 0.3 + ban_ranks[idx] * 0.2

            hero["score_percent"] = round(hero["score"] * 100, 1)
            hero["tags"] = self._hero_meta_tags(hero)
            hero["insight"] = self._hero_insight(hero, hero["tags"])

        score_ranks = self._percentile_ranks([h["score"] for h in heroes])
        tiers: dict[str, list[dict[str, Any]]] = {t: [] for t in ("S", "A", "B", "C", "D")}

        ranked = sorted(
            zip(heroes, score_ranks),
            key=lambda item: item[0]["score"],
            reverse=True,
        )
        for rank, (hero, percentile) in enumerate(ranked, 1):
            tier = self._tier_from_percentile(percentile)
            hero["tier"] = tier
            hero["rank"] = rank
            hero["tier_percentile"] = round(percentile * 100, 1)
            hero.pop("pick_rate", None)
            hero.pop("ban_rate", None)
            hero.pop("win_rate", None)
            hero.pop("score", None)
            hero.pop("synergy_score", None)
            hero.pop("counter_score", None)
            hero.pop("vulnerability", None)
            tiers[tier].append(hero)

        def compact(hero: dict[str, Any]) -> dict[str, Any]:
            return {
                "hero_id": hero["hero_id"],
                "hero_name": hero["hero_name"],
                "role": hero["role"],
                "image": hero["image"],
                "win_percent": hero["win_percent"],
                "pick_percent": hero["pick_percent"],
                "ban_percent": hero["ban_percent"],
            }

        highlights = {
            "must_ban": [
                compact(h) for h in sorted(heroes, key=lambda x: x["ban_percent"], reverse=True)[:5]
                if h["ban_percent"] >= 8
            ],
            "hidden_gems": [
                compact(h) for h in sorted(heroes, key=lambda x: x["win_percent"], reverse=True)[:8]
                if h["pick_percent"] < 1.2 and h["win_percent"] >= 51
            ][:5],
            "overpicked": [
                compact(h) for h in sorted(heroes, key=lambda x: x["pick_percent"], reverse=True)[:8]
                if h["pick_percent"] >= 2.0 and h["win_percent"] < 49.5
            ][:5],
        }

        return {
            "has_meta": True,
            "mode": mode,
            "mode_label": self._tier_mode_label(mode),
            "total": len(heroes),
            "tiers": tiers,
            "tier_counts": {tier: len(items) for tier, items in tiers.items()},
            "highlights": highlights,
        }

    def counter_difficulty(self, rate: float) -> str:
        if rate >= 0.025:
            return "easy"
        if rate >= 0.015:
            return "medium"
        return "hard"

    def counter_difficulty_label(self, rate: float) -> str:
        mapping = {"easy": "Легко", "medium": "Средне", "hard": "Сложно"}
        return mapping[self.counter_difficulty(rate)]

    def get_counter_picks(
        self,
        target_id: int,
        exclude: Optional[set[int]] = None,
        limit: int = 15,
        role_filter: Optional[str] = None,
        lane_filter: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        exclude = exclude or set()
        exclude.add(target_id)
        picks: list[dict[str, Any]] = []

        for hero_id in self._ids:
            if hero_id in exclude:
                continue
            if role_filter and self.hero_role(hero_id) != role_filter:
                continue
            if lane_filter and self.hero_lane(hero_id) != lane_filter:
                continue
            rate = self._counter(hero_id, target_id)
            if rate <= 0:
                continue
            picks.append({
                "hero_id": hero_id,
                "hero_name": self.hero_name(hero_id),
                "role": self.hero_role(hero_id),
                "lane": self.hero_lane(hero_id),
                "image": self.hero_image(hero_id),
                "counter_rate": round(rate, 4),
                "counter_percent": round(rate * 100, 2),
                "difficulty": self.counter_difficulty(rate),
                "difficulty_label": self.counter_difficulty_label(rate),
            })

        picks.sort(key=lambda p: p["counter_rate"], reverse=True)
        return picks[:limit]

    def best_partners(
        self,
        anchor: int,
        enemies: list[int],
        exclude: set[int] | None = None,
        limit: int = 12,
    ) -> list[ComboResult]:
        exclude = exclude or set()
        exclude.add(anchor)
        results: list[ComboResult] = []
        for partner in self._ids:
            if partner in exclude:
                continue
            if not self.is_valid_duo(anchor, partner):
                continue
            results.append(self.score_combo((anchor, partner), enemies, allies=[anchor]))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def _compat(self, a: int, b: int) -> float:
        sa, sb = str(a), str(b)
        return self.compatibility.get(sa, {}).get(sb, 0.0)

    def _counter(self, a: int, b: int) -> float:
        sa, sb = str(a), str(b)
        return self.counters.get(sa, {}).get(sb, 0.0)

    def _relation_bonus(self, a: int, b: int) -> float:
        ha = self.heroes.get(str(a), {})
        hb = self.heroes.get(str(b), {})
        bonus = 0.0
        if b in ha.get("assist", []):
            bonus += 0.012
        if a in hb.get("assist", []):
            bonus += 0.012
        if b in ha.get("strong", []):
            bonus += 0.006
        if a in hb.get("strong", []):
            bonus += 0.006
        return bonus

    def pair_synergy(self, a: int, b: int) -> float:
        if a == b:
            return 0.0
        return self._compat(a, b) + self._compat(b, a) + self._relation_bonus(a, b)

    def combo_synergy(self, combo: tuple[int, ...]) -> float:
        return sum(self.pair_synergy(x, y) for x, y in itertools.combinations(combo, 2))

    def combo_counter_vs(self, combo: tuple[int, ...], enemies: list[int]) -> float:
        if not enemies:
            return 0.0
        total = 0.0
        for enemy in enemies:
            best = max(self._counter(hero, enemy) for hero in combo)
            total += best
        return total / len(enemies)

    def combo_threat_from(self, combo: tuple[int, ...], enemies: list[int]) -> float:
        if not enemies:
            return 0.0
        total = 0.0
        for enemy in enemies:
            best = max(self._counter(enemy, hero) for hero in combo)
            total += best
        return total / len(enemies)

    def role_balance_bonus(self, combo: tuple[int, ...]) -> float:
        roles = {self.hero_role(h) for h in combo}
        bonus = 0.0
        if len(combo) <= 2:
            if "Tank" in roles and roles & {"Marksman", "Mage", "Assassin"}:
                bonus += 0.012
            if "Support" in roles and roles & {"Marksman", "Mage", "Assassin", "Fighter"}:
                bonus += 0.012
            if len(roles) == 2:
                bonus += 0.006
            return bonus

        if "Tank" in roles or "Support" in roles:
            bonus += 0.008
        damage = roles & {"Mage", "Marksman", "Assassin", "Fighter"}
        if len(damage) >= 2 and len(roles) >= 3:
            bonus += 0.006
        if len(roles) >= min(3, len(combo)):
            bonus += 0.004
        if len(combo) >= TEAM_SIZE:
            if "Tank" in roles and ("Marksman" in roles or "Mage" in roles):
                bonus += 0.01
            if len(roles) >= 4:
                bonus += 0.008
        return bonus

    def _pair_role_penalty(self, role_a: str, role_b: str) -> float:
        if role_a != role_b:
            return 0.0
        penalties = {
            "Support": 0.10,
            "Mage": 0.09,
            "Marksman": 0.09,
            "Assassin": 0.08,
            "Tank": 0.06,
            "Fighter": 0.04,
        }
        return penalties.get(role_a, 0.05)

    def _pair_lane_penalty(self, lane_a: str, lane_b: str) -> float:
        if not lane_a or not lane_b or lane_a != lane_b:
            return 0.0
        if lane_a == "Roam":
            return 0.12
        if lane_a == "Jungle":
            return 0.10
        return 0.10

    def _pair_complement_bonus(self, role_a: str, role_b: str, lane_a: str, lane_b: str) -> float:
        roles = {role_a, role_b}
        bonus = 0.0
        for front, back in COMPLEMENTARY_PAIRS:
            if roles & front and roles & back:
                bonus += 0.014
                break
        if lane_a and lane_b and lane_a != lane_b:
            bonus += 0.010
        return bonus

    def draft_composition_adjustment(
        self,
        combo: tuple[int, ...],
        allies: Optional[list[int]] = None,
    ) -> float:
        if len(combo) < 2:
            return 0.0

        adjustment = 0.0
        scale = 1.0 if len(combo) == 2 else 0.55

        for hero_a, hero_b in itertools.combinations(combo, 2):
            role_a, role_b = self.hero_role(hero_a), self.hero_role(hero_b)
            lane_a, lane_b = self.hero_lane(hero_a), self.hero_lane(hero_b)
            adjustment -= self._pair_role_penalty(role_a, role_b)
            adjustment -= self._pair_lane_penalty(lane_a, lane_b)
            adjustment += self._pair_complement_bonus(role_a, role_b, lane_a, lane_b)

        if allies:
            team_roles = [self.hero_role(h) for h in allies]
            team_lanes = [lane for h in allies if (lane := self.hero_lane(h))]
            for hero_id in combo:
                role = self.hero_role(hero_id)
                lane = self.hero_lane(hero_id)
                if role in team_roles and role in DUO_SAME_ROLE_BLOCK:
                    adjustment -= 0.05
                if lane and lane in team_lanes:
                    adjustment -= 0.07

        return adjustment * scale

    def is_valid_duo(self, hero_a: int, hero_b: int) -> bool:
        role_a, role_b = self.hero_role(hero_a), self.hero_role(hero_b)
        lane_a, lane_b = self.hero_lane(hero_a), self.hero_lane(hero_b)
        if lane_a and lane_b and lane_a == lane_b:
            return False
        if role_a == role_b and role_a in DUO_SAME_ROLE_BLOCK:
            return False
        return True

    def team_completeness(self, team: list[int]) -> float:
        missing = max(0, TEAM_SIZE - len(team))
        return max(0.35, 1 - missing * 0.13)

    def _hero_phase_power(self, hero_id: int) -> dict[str, float]:
        role = self.hero_role(hero_id)
        profile = ROLE_PHASE_POWER.get(role, ROLE_PHASE_POWER["Fighter"])
        win_rate = float(self.heroes[str(hero_id)].get("win_rate") or 0.5)
        strength = max(0.75, min(1.15, 0.85 + (win_rate - 0.5) * 0.6))
        return {phase: round(value * strength, 4) for phase, value in profile.items()}

    def team_composition_profile(self, team: list[int]) -> dict[str, Any]:
        if not team:
            return {
                "phases": {"early": 0.5, "mid": 0.5, "late": 0.5},
                "composition": 0.0,
                "damage": 0,
                "tanks": 0,
                "marksmen": 0,
                "mages": 0,
                "supports": 0,
                "frontline": 0,
            }

        roles = [self.hero_role(h) for h in team]
        counts = Counter(roles)
        tanks = counts.get("Tank", 0)
        marksmen = counts.get("Marksman", 0)
        mages = counts.get("Mage", 0)
        supports = counts.get("Support", 0)
        damage = sum(1 for role in roles if role in DAMAGE_ROLES)
        frontline = sum(1 for role in roles if role in FRONTLINE_ROLES)
        team_size = len(team)

        phase_totals = {"early": 0.0, "mid": 0.0, "late": 0.0}
        for hero_id in team:
            hero_phases = self._hero_phase_power(hero_id)
            for phase in phase_totals:
                phase_totals[phase] += hero_phases[phase]
        phases = {phase: round(total / team_size, 4) for phase, total in phase_totals.items()}

        composition = 0.0
        if tanks >= team_size and team_size >= 3:
            composition -= 0.48
        elif tanks >= 4:
            composition -= 0.36
        elif tanks >= 3 and marksmen + mages == 0:
            composition -= 0.30

        if damage == 0 and team_size >= 2:
            composition -= 0.34
        elif damage == 1 and team_size >= 4 and marksmen == 0 and mages == 0:
            composition -= 0.18

        if marksmen >= 4:
            composition -= 0.24
        if frontline == 0 and team_size >= 4:
            composition -= 0.20
        if supports >= 3:
            composition -= 0.14
        if len(set(roles)) == 1 and team_size >= 3:
            composition -= 0.22

        if tanks >= 1 and marksmen >= 1 and (mages >= 1 or supports >= 1):
            composition += 0.12
        if damage >= 2 and frontline >= 2 and team_size >= 4:
            composition += 0.10
        if len(set(roles)) >= 4 and team_size >= 5:
            composition += 0.08
        if supports == 1 and tanks >= 1 and damage >= 2:
            composition += 0.06

        return {
            "phases": phases,
            "composition": round(composition, 4),
            "damage": damage,
            "tanks": tanks,
            "marksmen": marksmen,
            "mages": mages,
            "supports": supports,
            "frontline": frontline,
        }

    def _phase_percent(self, value: float) -> float:
        return round(max(0.0, min(100.0, value * 100)), 1)

    def _phase_matchup_diff(
        self,
        ally_profile: dict[str, Any],
        enemy_profile: dict[str, Any],
    ) -> float:
        diff = 0.0
        for phase, weight in PHASE_WEIGHTS.items():
            diff += weight * (
                ally_profile["phases"][phase] - enemy_profile["phases"][phase]
            )
        return diff

    def _composition_notes(
        self,
        profile: dict[str, Any],
        label: str,
        team_size: int,
    ) -> list[str]:
        notes: list[str] = []
        if profile["tanks"] >= team_size and team_size >= 3:
            notes.append(f"{label}: только танки — в лейте не хватит урона")
        elif profile["damage"] == 0 and team_size >= 3:
            notes.append(f"{label}: нет мага/стрелка/ассасина — состав без дамага")
        elif profile["tanks"] >= 3 and profile["marksmen"] + profile["mages"] == 0:
            notes.append(f"{label}: слишком много танков, мало источников урона")
        elif profile["marksmen"] >= 4:
            notes.append(f"{label}: слишком много стрелков — нет фронтлайна")
        elif profile["frontline"] == 0 and team_size >= 4:
            notes.append(f"{label}: нет танка/бойца — сложно инициировать файты")
        return notes

    def _phase_notes(
        self,
        ally_profile: dict[str, Any],
        enemy_profile: dict[str, Any],
    ) -> list[str]:
        notes: list[str] = []
        for phase, label in (("early", "ранняя"), ("mid", "средняя"), ("late", "поздняя")):
            ally_val = ally_profile["phases"][phase]
            enemy_val = enemy_profile["phases"][phase]
            if ally_val - enemy_val >= 0.12:
                notes.append(f"Союзники сильнее в {label} игре")
            elif enemy_val - ally_val >= 0.12:
                notes.append(f"Враги сильнее в {label} игре")
        return notes[:2]

    def team_power(self, team: list[int], opponents: list[int]) -> dict[str, float]:
        if not team:
            return {
                "score": 0.0,
                "synergy": 0.0,
                "counter": 0.0,
                "threat": 0.0,
                "composition": 0.0,
                "phases": {"early": 0.5, "mid": 0.5, "late": 0.5},
            }
        combo = tuple(team)
        synergy = self.combo_synergy(combo)
        counter = self.combo_counter_vs(combo, opponents) if opponents else 0.0
        threat = self.combo_threat_from(combo, opponents) if opponents else 0.0
        role_bonus = self.role_balance_bonus(combo)
        profile = self.team_composition_profile(team)
        phase_score = sum(
            PHASE_WEIGHTS[phase] * profile["phases"][phase]
            for phase in PHASE_WEIGHTS
        )
        completeness = self.team_completeness(team)
        score = (
            synergy * 35
            + counter * 40
            - threat * 12
            + role_bonus * 80
            + phase_score * 28
            + profile["composition"] * 35
        ) * completeness
        return {
            "score": score,
            "synergy": synergy,
            "counter": counter,
            "threat": threat,
            "composition": profile["composition"],
            "phases": profile["phases"],
        }

    def predict_match(self, allies: list[int], enemies: list[int]) -> MatchPrediction | None:
        if not allies or not enemies:
            return None

        ally_stats = self.team_power(allies, enemies)
        enemy_stats = self.team_power(enemies, allies)
        ally_profile = self.team_composition_profile(allies)
        enemy_profile = self.team_composition_profile(enemies)

        base_diff = ally_stats["score"] - enemy_stats["score"]
        phase_diff = self._phase_matchup_diff(ally_profile, enemy_profile)
        comp_diff = ally_profile["composition"] - enemy_profile["composition"]

        ally_chance = 50 + base_diff * 0.9 + phase_diff * 48 + comp_diff * 32
        ally_chance = max(5.0, min(95.0, ally_chance))

        if ally_chance >= 58:
            winner = "allies"
            winner_label = "Союзники"
        elif ally_chance <= 42:
            winner = "enemies"
            winner_label = "Враги"
        else:
            winner = "even"
            winner_label = "Примерно равны"

        notes: list[str] = []
        notes.extend(self._composition_notes(ally_profile, "Союзники", len(allies)))
        notes.extend(self._composition_notes(enemy_profile, "Враги", len(enemies)))
        notes.extend(self._phase_notes(ally_profile, enemy_profile))

        if ally_stats["counter"] > enemy_stats["counter"] + 0.005:
            notes.append("Союзники выигрывают по контрпикам")
        elif enemy_stats["counter"] > ally_stats["counter"] + 0.005:
            notes.append("Враги сильнее по контрпикам")

        if ally_stats["synergy"] > enemy_stats["synergy"] + 0.03:
            notes.append("У союзников связки сильнее")
        elif enemy_stats["synergy"] > ally_stats["synergy"] + 0.03:
            notes.append("У врагов связки сильнее")

        if len(allies) < TEAM_SIZE:
            notes.append(f"Союзники: выбрано {len(allies)}/{TEAM_SIZE} — прогноз приблизительный")
        if len(enemies) < TEAM_SIZE:
            notes.append(f"Враги: выбрано {len(enemies)}/{TEAM_SIZE} — прогноз приблизительный")

        best_ally_counter = max(
            ((self._counter(a, e), a, e) for a in allies for e in enemies),
            key=lambda x: x[0],
            default=None,
        )
        if best_ally_counter and best_ally_counter[0] > 0.012:
            notes.append(
                f"Ключевой контр: {self.hero_name(best_ally_counter[1])} → {self.hero_name(best_ally_counter[2])}"
            )

        return MatchPrediction(
            winner=winner,
            winner_label=winner_label,
            ally_win_chance=ally_chance,
            ally_score=ally_stats["score"],
            enemy_score=enemy_stats["score"],
            ally_synergy=ally_stats["synergy"],
            enemy_synergy=enemy_stats["synergy"],
            ally_counter=ally_stats["counter"],
            enemy_counter=enemy_stats["counter"],
            notes=list(dict.fromkeys(notes))[:6],
            ally_phases={
                phase: self._phase_percent(ally_profile["phases"][phase])
                for phase in PHASE_WEIGHTS
            },
            enemy_phases={
                phase: self._phase_percent(enemy_profile["phases"][phase])
                for phase in PHASE_WEIGHTS
            },
        )

    def build_notes(self, combo: tuple[int, ...], enemies: list[int]) -> list[str]:
        notes: list[str] = []
        if enemies:
            best_match = max(
                ((self._counter(h, e), h, e) for h in combo for e in enemies),
                key=lambda x: x[0],
                default=None,
            )
            if best_match and best_match[0] > 0.015:
                notes.append(
                    f"{self.hero_name(best_match[1])} силён против {self.hero_name(best_match[2])}"
                )
        assist_pairs = []
        for a, b in itertools.combinations(combo, 2):
            if b in self.heroes.get(str(a), {}).get("assist", []):
                assist_pairs.append(f"{self.hero_name(a)} + {self.hero_name(b)}")
        if assist_pairs:
            notes.append("Синергия: " + ", ".join(assist_pairs[:2]))
        return notes[:3]

    def score_combo(
        self,
        combo: tuple[int, ...],
        enemies: list[int],
        allies: Optional[list[int]] = None,
    ) -> ComboResult:
        synergy = self.combo_synergy(combo)
        counter = self.combo_counter_vs(combo, enemies)
        threat = self.combo_threat_from(combo, enemies)
        role_bonus = self.role_balance_bonus(combo)
        draft_adj = self.draft_composition_adjustment(combo, allies)
        score = synergy * 40 + counter * 45 - threat * 15 + role_bonus * 100 + draft_adj * 100
        return ComboResult(
            heroes=list(combo),
            hero_names=[self.hero_name(h) for h in combo],
            synergy=synergy,
            counter=counter,
            threat=threat,
            score=score,
            roles=[self.hero_role(h) for h in combo],
            notes=self.build_notes(combo, enemies),
        )

    def _candidate_pool(
        self,
        allies: list[int],
        exclude: set[int],
    ) -> list[int]:
        pool = [hid for hid in self._ids if hid not in exclude]
        if allies:
            pool = [hid for hid in pool if hid not in allies]
        return pool

    def analyze(
        self,
        allies: list[int],
        enemies: list[int],
        size: int = 2,
        limit: int = 15,
        ally_bans: Optional[list[int]] = None,
        enemy_bans: Optional[list[int]] = None,
    ) -> list[ComboResult]:
        exclude = self._draft_excluded(allies, enemies, ally_bans, enemy_bans)
        pool = self._candidate_pool(allies, exclude)

        combos: list[tuple[int, ...]] = []
        need = size - len(allies)

        if need <= 0 and len(allies) >= size:
            combos = [tuple(allies[:size])]
        elif need > 0 and allies:
            combos = [tuple(allies) + extra for extra in itertools.combinations(pool, need)]
        else:
            combos = list(itertools.combinations(pool, size))

        results: list[ComboResult] = []
        for combo in combos:
            if len(combo) != size:
                continue
            if size == 2 and not self.is_valid_duo(combo[0], combo[1]):
                continue
            results.append(self.score_combo(combo, enemies, allies=allies))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def _solo_vs_enemies(self, hero: int, enemies: list[int]) -> float:
        if not enemies:
            return 0.0
        counter = sum(self._counter(hero, e) for e in enemies) / len(enemies)
        threat = sum(self._counter(e, hero) for e in enemies) / len(enemies)
        return counter - threat

    def _prune_pool(self, pool: list[int], enemies: list[int], max_size: int = 25) -> list[int]:
        if len(pool) <= max_size:
            return pool
        return sorted(pool, key=lambda h: self._solo_vs_enemies(h, enemies), reverse=True)[:max_size]

    def suggest_teams(
        self,
        allies: list[int],
        enemies: list[int],
        limit: int = 10,
        ally_bans: Optional[list[int]] = None,
        enemy_bans: Optional[list[int]] = None,
    ) -> list[ComboResult]:
        exclude = self._draft_excluded(allies, enemies, ally_bans, enemy_bans)
        pool = self._candidate_pool(allies, exclude)
        pool = self._prune_pool(pool, enemies)

        combos: list[tuple[int, ...]] = []
        need = TEAM_SIZE - len(allies)

        if need <= 0 and len(allies) >= TEAM_SIZE:
            combos = [tuple(allies[:TEAM_SIZE])]
        elif need > 0 and allies:
            combos = [tuple(allies) + extra for extra in itertools.combinations(pool, need)]
        elif enemies:
            combos = list(itertools.combinations(pool, TEAM_SIZE))
        else:
            return []

        results = [
            self.score_combo(c, enemies, allies=allies)
            for c in combos
            if len(c) == TEAM_SIZE
        ]
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def suggest_complete(
        self,
        allies: list[int],
        enemies: list[int],
        target_size: int = TEAM_SIZE,
        limit: int = 10,
    ) -> list[ComboResult]:
        if not allies:
            return self.suggest_teams([], enemies, limit=limit)
        need = target_size - len(allies)
        if need <= 0:
            return [self.score_combo(tuple(allies[:target_size]), enemies, allies=allies)]
        return self.suggest_teams(allies, enemies, limit=limit)

    def _team_role_counts(self, allies: list[int]) -> Counter:
        return Counter(self.hero_role(h) for h in allies)

    def _team_lane_counts(self, allies: list[int]) -> Counter:
        return Counter(
            lane for h in allies if (lane := self.hero_lane(h)) and lane in SINGLE_LANE_ROLES
        )

    def _missing_roles(self, allies: list[int]) -> list[str]:
        counts = self._team_role_counts(allies)
        missing: list[str] = []
        frontline = counts["Tank"] + counts["Fighter"]
        damage = sum(counts[role] for role in DAMAGE_ROLES)

        if counts["Tank"] == 0 and frontline == 0:
            missing.append("Tank")
        if damage == 0:
            missing.append("Marksman")
        if counts["Support"] == 0 and len(allies) >= 2:
            missing.append("Support")
        if counts["Fighter"] == 0 and counts["Assassin"] == 0 and len(allies) >= 1:
            missing.append("Fighter")
        if counts["Mage"] == 0 and counts["Marksman"] >= 1:
            missing.append("Mage")
        return missing

    def _pick_role_priorities(self, allies: list[int]) -> list[tuple[str, float]]:
        counts = self._team_role_counts(allies)
        n = len(allies)
        priorities: list[tuple[str, float]] = []
        frontline = counts["Tank"] + counts["Fighter"]
        damage = sum(counts[role] for role in DAMAGE_ROLES)

        if counts["Tank"] == 0:
            priorities.append(("Tank", 1.0))
        if damage == 0:
            priorities.append(("Marksman", 0.96))
            priorities.append(("Mage", 0.92))
        if counts["Support"] == 0 and n >= 1:
            priorities.append(("Support", 0.88))
        if frontline < 2 and n >= 1:
            priorities.append(("Fighter", 0.84))
        if counts["Assassin"] == 0 and n >= 2:
            priorities.append(("Assassin", 0.78))
        if counts["Mage"] == 0 and counts["Marksman"] >= 1:
            priorities.append(("Mage", 0.74))

        blocked = {
            role for role, limit in ROLE_PICK_LIMITS.items() if counts[role] >= limit
        }
        return [(role, weight) for role, weight in priorities if role not in blocked]

    def _pick_fits_composition(self, hero_id: int, allies: list[int]) -> bool:
        role = self.hero_role(hero_id)
        lane = self.hero_lane(hero_id)
        counts = self._team_role_counts(allies)
        lane_counts = self._team_lane_counts(allies)
        slots_left = TEAM_SIZE - len(allies)
        damage = sum(counts[r] for r in DAMAGE_ROLES)

        if counts[role] >= ROLE_PICK_LIMITS.get(role, 2):
            return False

        if lane and lane in SINGLE_LANE_ROLES and lane_counts[lane] >= 1:
            return False

        if slots_left <= 2 and damage == 0 and role in {"Tank", "Support"}:
            return False
        if slots_left == 1:
            if damage == 0 and role not in DAMAGE_ROLES:
                return False
            if counts["Support"] == 0 and role not in {"Support", "Tank", "Fighter"} and damage >= 1:
                return False

        if counts["Tank"] >= 2 and role == "Tank":
            return False
        if counts["Support"] >= 1 and role == "Support":
            return False
        if counts["Marksman"] >= 1 and role == "Marksman":
            return False

        if len(allies) >= 3:
            if counts["Support"] >= 1 and role == "Support":
                return False
            if damage == 0 and role in {"Tank", "Support"} and slots_left <= 3:
                return False
            if counts["Tank"] >= 1 and counts["Support"] >= 1 and damage == 0 and role in {"Tank", "Support"}:
                return False

        return True

    def _pick_composition_delta(self, hero_id: int, allies: list[int]) -> float:
        if not allies:
            return self.team_composition_profile([hero_id])["composition"]
        before = self.team_composition_profile(allies)["composition"]
        after = self.team_composition_profile(allies + [hero_id])["composition"]
        return after - before

    def _pick_role_need_bonus(self, hero_id: int, allies: list[int]) -> float:
        role = self.hero_role(hero_id)
        for need_role, weight in self._pick_role_priorities(allies):
            if role == need_role:
                return weight * 0.035
        if role in self._missing_roles(allies):
            return 0.02
        counts = self._team_role_counts(allies)
        if counts[role] >= ROLE_PICK_LIMITS.get(role, 2) - 1:
            return -0.03
        return 0.0

    def _select_diverse_picks(
        self,
        candidates: list[dict[str, Any]],
        limit: int,
        allies: Optional[list[int]] = None,
    ) -> list[dict[str, Any]]:
        allies = allies or []
        team_counts = self._team_role_counts(allies)
        selected: list[dict[str, Any]] = []
        role_seen: Counter = Counter()

        for candidate in candidates:
            role = candidate["role"]
            team_limit = ROLE_PICK_LIMITS.get(role, 2)
            if team_counts[role] >= team_limit:
                continue

            list_cap = 1 if role in {"Support", "Marksman", "Mage", "Tank", "Assassin"} else 2
            if role_seen[role] >= list_cap:
                continue

            selected.append(candidate)
            role_seen[role] += 1
            if len(selected) >= limit:
                break
        return selected

    def _pick_reasons(
        self,
        hero_id: int,
        allies: list[int],
        enemies: list[int],
        anchor: Optional[int] = None,
    ) -> list[str]:
        reasons: list[str] = []

        if enemies:
            best_counter = max(
                ((self._counter(hero_id, e), e) for e in enemies),
                key=lambda x: x[0],
                default=(0, 0),
            )
            if best_counter[0] >= 0.012:
                reasons.append(
                    f"Контрпик против {self.hero_name(best_counter[1])} "
                    f"(+{best_counter[0] * 100:.1f}%)"
                )

        for ally in allies:
            syn = self.pair_synergy(hero_id, ally)
            if syn >= 0.02:
                reasons.append(f"Связка с {self.hero_name(ally)}")
                break

        if anchor and anchor not in allies:
            anchor = None
        if anchor and anchor != hero_id:
            syn = self.pair_synergy(anchor, hero_id)
            if syn >= 0.015:
                reasons.append(f"Напарник для {self.hero_name(anchor)}")

        role = self.hero_role(hero_id)
        missing = self._missing_roles(allies)
        if role in missing:
            role_names = {
                "Tank": "Закрывает роль танка",
                "Marksman": "Нужен стрелок в составе",
                "Mage": "Нужен маг в составе",
                "Support": "Нужен саппорт",
                "Fighter": "Нужен боец / инициатор",
            }
            reasons.append(role_names.get(role, f"Роль: {role}"))

        lane = self.hero_lane(hero_id)
        ally_lanes = self._team_lane_counts(allies)
        if lane and lane in SINGLE_LANE_ROLES and ally_lanes[lane] >= 1:
            reasons.append(f"Линия {lane} уже занята")
        elif lane and enemies:
            enemy_lanes = {self.hero_lane(e) for e in enemies if self.hero_lane(e)}
            if lane in enemy_lanes:
                reasons.append(f"Конкурирует линию ({lane})")

        comp_delta = self._pick_composition_delta(hero_id, allies)
        if comp_delta >= 0.04:
            reasons.append("Улучшает баланс состава")
        elif comp_delta <= -0.04:
            reasons.append("Ухудшает баланс состава")

        if not reasons and enemies:
            solo = self._solo_vs_enemies(hero_id, enemies)
            if solo > 0:
                reasons.append(f"Хорош в матчапе (+{solo * 100:.1f}%)")

        return reasons[:4]

    def _draft_tips(
        self,
        allies: list[int],
        enemies: list[int],
    ) -> list[str]:
        tips: list[str] = []

        if not enemies:
            if not allies:
                tips.append("Сначала добавьте вражеских героев — так советы будут точнее")
            elif len(allies) < TEAM_SIZE:
                tips.append(f"Доберите состав: {len(allies)}/{TEAM_SIZE} героев")
            return tips[:5]

        if len(allies) < TEAM_SIZE:
            tips.append(f"Следующий пик: осталось {TEAM_SIZE - len(allies)} слотов")

        missing = self._missing_roles(allies)
        if "Tank" in missing:
            tips.append("В вашем составе нет танка — возьмите инициатора с контролем")
        if "Marksman" in missing:
            tips.append("Нужен источник урона — стрелок или маг")
        if "Support" in missing:
            tips.append("Рекомендуем саппорта для защиты и усиления команды")

        for a, b in itertools.combinations(enemies, 2):
            if self.pair_synergy(a, b) >= 0.035:
                tips.append(
                    f"У врагов опасная связка {self.hero_name(a)} + {self.hero_name(b)}"
                )

        for enemy in enemies:
            counters = self.get_counter_picks(enemy, exclude=set(allies) | set(enemies), limit=1)
            if counters:
                c = counters[0]
                tips.append(
                    f"Против {self.hero_name(enemy)} лучше {c['hero_name']} "
                    f"(+{c['counter_percent']}%)"
                )

        if len(tips) < 3 and allies:
            teams = self.suggest_complete(allies, enemies, limit=1)
            if teams:
                names = ", ".join(teams[0].hero_names)
                tips.append(f"Оптимальная пятёрка сейчас: {names}")

        return list(dict.fromkeys(tips))[:6]

    def suggest_picks(
        self,
        allies: list[int],
        enemies: list[int],
        anchor: Optional[int] = None,
        limit: int = 8,
        role_filter: Optional[str] = None,
        lane_filter: Optional[str] = None,
        ally_bans: Optional[list[int]] = None,
        enemy_bans: Optional[list[int]] = None,
    ) -> dict[str, Any]:
        if len(allies) >= TEAM_SIZE:
            return {"picks": [], "tips": ["Состав полный — фокус на контрпики и позиционку"]}

        exclude = self._draft_excluded(allies, enemies, ally_bans, enemy_bans)
        candidates: list[dict[str, Any]] = []

        for hero_id in self._ids:
            if hero_id in exclude:
                continue
            if role_filter and self.hero_role(hero_id) != role_filter:
                continue
            if lane_filter and self.hero_lane(hero_id) != lane_filter:
                continue
            if allies and not self._pick_fits_composition(hero_id, allies):
                continue

            counter_score = self._solo_vs_enemies(hero_id, enemies) if enemies else 0.0
            synergy_score = 0.0
            if allies:
                synergy_score = sum(self.pair_synergy(hero_id, a) for a in allies) / len(allies)
            anchor_score = 0.0
            if anchor and anchor in allies:
                anchor_score = self.pair_synergy(anchor, hero_id)

            role_bonus = self._pick_role_need_bonus(hero_id, allies)
            comp_delta = self._pick_composition_delta(hero_id, allies)
            score = (
                counter_score * 45
                + synergy_score * 28
                + anchor_score * 18
                + role_bonus * 120
                + comp_delta * 90
            )

            reasons = self._pick_reasons(hero_id, allies, enemies, anchor)
            if not reasons and not enemies:
                reasons = [f"Роль: {self.hero_role(hero_id)}"]

            candidates.append({
                "hero_id": hero_id,
                "hero_name": self.hero_name(hero_id),
                "role": self.hero_role(hero_id),
                "lane": self.hero_lane(hero_id),
                "image": self.hero_image(hero_id),
                "score": round(score, 2),
                "priority": "high" if score >= 1.0 or role_bonus >= 0.03 else "medium",
                "reasons": reasons or ["Подходит под текущий драфт"],
            })

        candidates.sort(key=lambda c: c["score"], reverse=True)
        return {
            "picks": self._select_diverse_picks(candidates, limit, allies),
            "tips": self._draft_tips(allies, enemies),
        }

    def _draft_excluded(
        self,
        allies: list[int],
        enemies: list[int],
        ally_bans: Optional[list[int]] = None,
        enemy_bans: Optional[list[int]] = None,
    ) -> set[int]:
        excluded = set(allies) | set(enemies)
        excluded |= {b for b in (ally_bans or []) if b}
        excluded |= {b for b in (enemy_bans or []) if b}
        return excluded

    def suggest_bans(
        self,
        allies: list[int],
        enemies: list[int],
        ally_bans: Optional[list[int]] = None,
        enemy_bans: Optional[list[int]] = None,
        limit: int = 8,
    ) -> dict[str, Any]:
        excluded = self._draft_excluded(allies, enemies, ally_bans, enemy_bans)
        candidates: list[dict[str, Any]] = []

        for hero_id in self._ids:
            if hero_id in excluded:
                continue
            hero = self.heroes[str(hero_id)]
            ban_rate = float(hero.get("ban_rate") or 0)
            counter_us = 0.0
            if allies:
                counter_us = sum(self._counter(hero_id, a) for a in allies) / len(allies)
            threat_to_us = 0.0
            if allies:
                threat_to_us = sum(self._counter(hero_id, a) for a in allies) / len(allies)
            enemy_synergy = 0.0
            if enemies:
                enemy_synergy = sum(self.pair_synergy(hero_id, e) for e in enemies) / len(enemies)
            vuln_us = self._hero_vulnerability(hero_id)

            score = (
                ban_rate * 45
                + counter_us * 40
                + enemy_synergy * 25
                + vuln_us * 15
            )
            reasons: list[str] = []
            if ban_rate >= 0.08:
                reasons.append(f"Часто банят ({round(ban_rate * 100, 1)}%)")
            if counter_us >= 0.015 and allies:
                reasons.append("Силён против ваших пиков")
            if enemy_synergy >= 0.02 and enemies:
                reasons.append("Усиливает вражеский состав")
            if vuln_us >= 0.018:
                reasons.append("Опасен в мете")

            candidates.append({
                "hero_id": hero_id,
                "hero_name": hero["name"],
                "role": hero.get("role", "Fighter"),
                "lane": hero.get("lane", ""),
                "image": hero.get("image", ""),
                "ban_percent": round(ban_rate * 100, 2),
                "score": round(score, 3),
                "reasons": reasons or ["Приоритетный бан по мете"],
            })

        candidates.sort(key=lambda c: c["score"], reverse=True)
        return {
            "bans": candidates[:limit],
            "tips": self._ban_tips(allies, enemies, ally_bans, enemy_bans),
        }

    def _ban_tips(
        self,
        allies: list[int],
        enemies: list[int],
        ally_bans: Optional[list[int]] = None,
        enemy_bans: Optional[list[int]] = None,
    ) -> list[str]:
        tips: list[str] = []
        if not allies and not enemies:
            tips.append("Баньте must-ban героев меты или контрпики под вашу роль")
        if enemies:
            tips.append("Учитывайте первые пики врага — баньте их сильные связки")
        if allies and not enemies:
            tips.append("Союзники уже выбраны — баньте тех, кто контрит ваш состав")
        banned_count = len([b for b in (ally_bans or []) if b]) + len([b for b in (enemy_bans or []) if b])
        if banned_count >= 8:
            tips.append("Фаза банов почти завершена — переходите к пикам")
        return tips[:4]

    def suggest_pick_vs_enemy(
        self,
        enemy_id: int,
        allies: list[int],
        enemies: list[int],
        ally_bans: Optional[list[int]] = None,
        enemy_bans: Optional[list[int]] = None,
        limit: int = 8,
    ) -> dict[str, Any]:
        if str(enemy_id) not in self.heroes:
            return {"error": "Герой не найден"}

        draft_enemies = list(enemies)
        if enemy_id not in draft_enemies:
            draft_enemies.append(enemy_id)

        excluded = self._draft_excluded(allies, draft_enemies, ally_bans, enemy_bans)
        counters = self.get_counter_picks(enemy_id, exclude=excluded, limit=limit)
        picks = self.suggest_picks(
            allies,
            draft_enemies,
            limit=limit,
            ally_bans=ally_bans,
            enemy_bans=enemy_bans,
        )

        tips = [
            f"Враг взял {self.hero_name(enemy_id)} — ниже лучшие ответы",
            *picks.get("tips", [])[:3],
        ]
        return {
            "enemy": {
                "id": enemy_id,
                "name": self.hero_name(enemy_id),
                "role": self.hero_role(enemy_id),
                "lane": self.hero_lane(enemy_id),
                "image": self.hero_image(enemy_id),
            },
            "counters": counters,
            "picks": picks["picks"],
            "tips": tips[:5],
        }

    def ingame_advice(
        self,
        allies: list[int],
        enemies: list[int],
        phase: str = "mid",
        gold: str = "even",
        situation: str = "",
    ) -> dict[str, Any]:
        if not allies:
            return {
                "tips": ["Добавьте своих героев на вкладке «Драфт» — тогда советы будут точнее"],
                "ally_phases": {},
                "enemy_phases": {},
            }

        phase = phase if phase in PHASE_WEIGHTS else "mid"
        gold = gold if gold in {"ahead", "even", "behind"} else "even"

        ally_profile = self.team_composition_profile(allies)
        enemy_profile = self.team_composition_profile(enemies) if enemies else None

        phase_labels = {"early": "ранней", "mid": "средней", "late": "поздней"}
        tips: list[str] = []

        ally_phase = ally_profile["phases"][phase]
        if enemy_profile:
            enemy_phase = enemy_profile["phases"][phase]
            if ally_phase - enemy_phase >= 0.1:
                tips.append(f"Ваш состав сильнее в {phase_labels[phase]} игре — можно давить")
            elif enemy_phase - ally_phase >= 0.1:
                tips.append(f"Враги сильнее в {phase_labels[phase]} игре — играйте осторожно")

        if gold == "ahead":
            tips.append("Впереди по золоту — давите линии, забирайте черепаху и лорда")
        elif gold == "behind":
            tips.append("Отстаёте по золоту — фармите безопасно, избегайте рискованных файтов")
        else:
            tips.append("Золото примерно равно — ищите пиковые окна по кд врагов")

        if situation == "teamfight":
            tips.append("Готовьтесь к командному бою — держитесь рядом с танком/инициатором")
        elif situation == "split":
            tips.append("Сплит-пуш — следите за картой, отступайте при пропаже врагов")
        elif situation == "defend":
            tips.append("Защита базы — не выходите один, чистите волны под башней")

        if phase == "late" and ally_profile["damage"] < 2:
            tips.append("В лейте мало урона — не затягивайте файты без численного преимущества")
        if phase == "early" and ally_profile["frontline"] >= 2:
            tips.append("Ранняя игра — используйте силу фронтлайна для инвейдов")

        if enemies:
            pred = self.predict_match(allies, enemies)
            if pred:
                tips.extend(pred.notes[:3])

        missing = self._missing_roles(allies)
        if missing and len(allies) < TEAM_SIZE:
            role_hints = {
                "Tank": "нужен танк для инициации",
                "Marksman": "нужен источник урона",
                "Support": "нужен саппорт для защиты",
                "Mage": "нужен маг для контроля",
                "Fighter": "нужен боец для давления",
            }
            for role in missing[:2]:
                if role in role_hints:
                    tips.append(f"В драфте {role_hints[role]}")

        return {
            "tips": list(dict.fromkeys(tips))[:8],
            "ally_phases": {
                p: self._phase_percent(ally_profile["phases"][p]) for p in PHASE_WEIGHTS
            },
            "enemy_phases": {
                p: self._phase_percent(enemy_profile["phases"][p])
                for p in PHASE_WEIGHTS
            } if enemy_profile else {},
            "phase": phase,
            "gold": gold,
        }
