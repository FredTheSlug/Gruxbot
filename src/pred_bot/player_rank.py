"""Resolve a player's current ranked tier from profile payloads."""

from __future__ import annotations

from typing import Any

from pred_bot.jsonutil import pick_str
from pred_bot.match_detail import MatchPlayerLine


def rank_info_from_graphql_rank(rank: dict[str, Any] | None) -> dict[str, str] | None:
    if not rank or not isinstance(rank, dict):
        return None
    name = pick_str(rank, "name", "tierName")
    if not name:
        return None
    return {
        "rank_name": name,
        "rank_abbrev": pick_str(rank, "abbreviation") or "",
        "rank_icon": pick_str(rank, "icon") or "",
        "rank_id": pick_str(rank, "id") or "",
    }


def pick_rank_from_player_ratings(
    ratings: list[dict[str, Any]],
    *,
    preferred_season_id: str | None = None,
) -> dict[str, str] | None:
    """Choose current-season rank from pred.gg player.ratings rows."""
    rows = [r for r in ratings if isinstance(r, dict) and not r.get("unranked")]
    if not rows:
        return None

    if preferred_season_id:
        for row in rows:
            season = row.get("rating") if isinstance(row.get("rating"), dict) else {}
            if str(season.get("id") or "") == preferred_season_id:
                info = rank_info_from_graphql_rank(
                    row.get("rank") if isinstance(row.get("rank"), dict) else None
                )
                if info:
                    return info

    def season_key(row: dict[str, Any]) -> int:
        season = row.get("rating") if isinstance(row.get("rating"), dict) else {}
        try:
            return int(season.get("id") or 0)
        except (TypeError, ValueError):
            return 0

    for row in sorted(rows, key=season_key, reverse=True):
        info = rank_info_from_graphql_rank(row.get("rank") if isinstance(row.get("rank"), dict) else None)
        if info:
            return info
    return None


def rank_info_from_omeda_profile(profile: dict[str, Any], *, base_url: str) -> dict[str, str] | None:
    title = pick_str(profile, "rank_title", "rank_name")
    if not title:
        return None
    image = pick_str(profile, "rank_image")
    icon = ""
    if image:
        if image.startswith("http"):
            icon = image
        else:
            root = base_url.rstrip("/")
            icon = f"{root}{image}" if image.startswith("/") else f"{root}/{image}"
    return {
        "rank_name": title,
        "rank_abbrev": "",
        "rank_icon": icon,
        "rank_id": pick_str(profile, "rank", "rank_id") or "",
    }


def apply_rank_info(player: MatchPlayerLine, info: dict[str, str]) -> None:
    if not player.rank_name and info.get("rank_name"):
        player.rank_name = info["rank_name"]
    if not player.rank_abbrev and info.get("rank_abbrev"):
        player.rank_abbrev = info["rank_abbrev"]
    if not player.rank_icon and info.get("rank_icon"):
        player.rank_icon = info["rank_icon"]
    if not player.rank_id and info.get("rank_id"):
        player.rank_id = info["rank_id"]
