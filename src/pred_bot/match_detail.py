"""Normalize pred.gg GraphQL and omeda.city match payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pred_bot.jsonutil import pick_str


@dataclass
class MatchPlayerLine:
    player_id: str | None
    name: str
    team: str
    role: str
    kills: int
    deaths: int
    assists: int
    performance_score: float | None = None
    cs: int | None = None
    rank_name: str | None = None
    rank_abbrev: str | None = None
    rank_icon: str | None = None
    rank_id: str | None = None
    vp_change: int | None = None
    hero_name: str | None = None
    hero_slug: str | None = None
    hero_icon: str | None = None
    hero_id: str | None = None


@dataclass
class MatchDetail:
    match_id: str
    duration_seconds: int
    game_mode: str
    region: str
    start_time: str | None
    end_time: str | None
    winning_team: str
    team_kills: dict[str, int] = field(default_factory=dict)
    players: list[MatchPlayerLine] = field(default_factory=list)

    def team_display_name(self, team: str) -> str:
        t = team.strip().lower()
        if t == "dusk":
            return "Dusk"
        if t == "dawn":
            return "Dawn"
        return team.title()

    def winning_team_key(self) -> str:
        return self.winning_team.strip().lower()


def _parse_dt(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _team_key(raw: Any) -> str:
    return str(raw or "").strip().lower()


def _role_key(raw: Any) -> str:
    return str(raw or "").strip().lower()


def _vp_change_from_rating(rating: dict[str, Any] | None) -> int | None:
    if not rating:
        return None
    points = rating.get("points")
    new_points = rating.get("newPoints")
    if points is not None and new_points is not None:
        return int(round(float(new_points) - float(points)))
    return None


def _rank_from_rating(
    rating: dict[str, Any] | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    if not rating:
        return None, None, None, None
    rank = rating.get("rank") if isinstance(rating.get("rank"), dict) else {}
    name = pick_str(rank, "name", "tierName")
    abbrev = pick_str(rank, "abbreviation")
    icon = pick_str(rank, "icon")
    rank_id = pick_str(rank, "id")
    return name or None, abbrev or None, icon or None, rank_id or None


def parse_pred_match(raw: dict[str, Any]) -> MatchDetail | None:
    if not raw:
        return None
    match_id = str(raw.get("uuid") or raw.get("id") or "")
    if not match_id:
        return None

    players: list[MatchPlayerLine] = []
    team_kills: dict[str, int] = {"dawn": 0, "dusk": 0}

    for row in raw.get("matchPlayers") or []:
        if not isinstance(row, dict):
            continue
        team = _team_key(row.get("team"))
        kills = int(row.get("kills") or 0)
        deaths = int(row.get("deaths") or 0)
        assists = int(row.get("assists") or 0)
        if team in team_kills:
            team_kills[team] += kills

        hero = row.get("hero") if isinstance(row.get("hero"), dict) else {}
        hero_data = hero.get("data") if isinstance(hero.get("data"), dict) else {}
        hero_row_data = row.get("heroData") if isinstance(row.get("heroData"), dict) else {}
        player = row.get("player") if isinstance(row.get("player"), dict) else {}
        rating = row.get("rating") if isinstance(row.get("rating"), dict) else {}
        hero_icon = pick_str(hero_data, "icon") or pick_str(hero_row_data, "icon")

        minions = row.get("minionsKilled")
        rank_name, rank_abbrev, rank_icon, rank_id = _rank_from_rating(rating)
        players.append(
            MatchPlayerLine(
                player_id=pick_str(player, "uuid") or pick_str(player, "id"),
                name=pick_str(player, "name") or pick_str(row, "name") or "Unknown",
                team=team,
                role=_role_key(row.get("role")),
                kills=kills,
                deaths=deaths,
                assists=assists,
                cs=int(minions) if minions is not None else None,
                rank_name=rank_name,
                rank_abbrev=rank_abbrev,
                rank_icon=rank_icon,
                rank_id=rank_id,
                vp_change=_vp_change_from_rating(rating),
                hero_name=pick_str(hero_data, "displayName", "name")
                or pick_str(hero_row_data, "displayName")
                or pick_str(hero, "slug"),
                hero_slug=pick_str(hero, "slug"),
                hero_icon=hero_icon,
                hero_id=pick_str(hero, "id"),
            )
        )

    mode = raw.get("gameMode")
    region = raw.get("region")
    return MatchDetail(
        match_id=match_id.replace("-", ""),
        duration_seconds=int(raw.get("duration") or 0),
        game_mode=str(mode).replace("_", " ").title() if mode else "Unknown",
        region=_format_region(str(region) if region else ""),
        start_time=_parse_dt(raw.get("startTime")),
        end_time=_parse_dt(raw.get("endTime")),
        winning_team=_team_key(raw.get("winningTeam")),
        team_kills=team_kills,
        players=players,
    )


def parse_omeda_match(raw: dict[str, Any]) -> MatchDetail | None:
    if not raw:
        return None
    match_id = str(raw.get("id") or "").replace("-", "")
    if not match_id:
        return None

    players: list[MatchPlayerLine] = []
    team_kills: dict[str, int] = {"dawn": 0, "dusk": 0}

    for row in raw.get("players") or []:
        if not isinstance(row, dict):
            continue
        team = _team_key(row.get("team"))
        kills = int(row.get("kills") or 0)
        deaths = int(row.get("deaths") or 0)
        assists = int(row.get("assists") or 0)
        if team in team_kills:
            team_kills[team] += kills

        vp = row.get("vp_change")
        ps = row.get("performance_score")
        minions = row.get("minions_killed")
        players.append(
            MatchPlayerLine(
                player_id=pick_str(row, "id"),
                name=pick_str(row, "display_name", "name") or "Unknown",
                team=team,
                role=_role_key(row.get("role")),
                kills=kills,
                deaths=deaths,
                assists=assists,
                performance_score=float(ps) if ps is not None else None,
                cs=int(minions) if minions is not None else None,
                vp_change=int(vp) if vp is not None else None,
                hero_name=pick_str(row, "hero_name", "hero"),
                hero_slug=pick_str(row, "hero_slug"),
                hero_id=pick_str(row, "hero_id", "heroId"),
            )
        )

    duration = int(raw.get("game_duration") or raw.get("duration") or 0)
    mode = raw.get("game_mode") or raw.get("gameMode")
    region = raw.get("game_region") or raw.get("region")
    return MatchDetail(
        match_id=match_id,
        duration_seconds=duration,
        game_mode=str(mode).replace("_", " ").title() if mode else "Unknown",
        region=_format_region(str(region) if region else ""),
        start_time=_parse_dt(raw.get("start_time")),
        end_time=_parse_dt(raw.get("end_time")),
        winning_team=_team_key(raw.get("winning_team")),
        team_kills=team_kills,
        players=players,
    )


def parse_match_payload(raw: Any) -> MatchDetail | None:
    """Parse API response (pred normalized dict, omeda JSON, or GraphQL match node)."""
    if not isinstance(raw, dict):
        return None
    if raw.get("matchPlayers"):
        return parse_pred_match(raw)
    if raw.get("players") and isinstance(raw.get("players"), list):
        return parse_omeda_match(raw)
    if raw.get("matches"):
        return None
    if raw.get("id") and raw.get("winning_team"):
        return parse_omeda_match(raw)
    if raw.get("uuid") or raw.get("winningTeam"):
        return parse_pred_match(raw)
    return None


def _format_region(code: str) -> str:
    mapping = {
        "NA": "North America",
        "EU": "Europe",
        "OCE": "Oceania",
        "APAC": "Asia Pacific",
        "BR": "Brazil",
    }
    c = code.strip().upper()
    return mapping.get(c, code)


def format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "—"
    minutes = max(1, round(seconds / 60))
    return f"{minutes} Minute{'s' if minutes != 1 else ''}"


def format_match_timestamp(end_time: str | None, start_time: str | None) -> str:
    raw = end_time or start_time
    if not raw:
        return ""
    try:
        s = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone()
        hour = local.strftime("%I").lstrip("0") or "12"
        return f"{local.month}/{local.day}/{local.year} {hour}:{local.strftime('%M %p')}"
    except (ValueError, OSError, TypeError):
        return raw
