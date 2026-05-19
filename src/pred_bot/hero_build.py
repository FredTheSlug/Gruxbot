"""Parse pred.gg hero core build GraphQL payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pred_bot.jsonutil import pick_str


@dataclass
class BuildItemLine:
    name: str
    slug: str | None = None
    icon: str | None = None
    matches_played: int | None = None
    matches_won: int | None = None

    @property
    def winrate_pct(self) -> float | None:
        if self.matches_played is None or self.matches_played <= 0 or self.matches_won is None:
            return None
        return 100.0 * self.matches_won / self.matches_played


@dataclass
class BuildRecommendation:
    hero_name: str
    hero_slug: str
    hero_icon: str | None
    role: str
    core_items: list[BuildItemLine]
    crests: list[BuildItemLine]
    sample_size: int | None = None


def role_display_name(role_enum: str) -> str:
    key = role_enum.strip().upper()
    labels = {
        "CARRY": "Carry",
        "OFFLANE": "Offlane",
        "MIDLANE": "Midlane",
        "JUNGLE": "Jungle",
        "SUPPORT": "Support",
        "FILL": "Fill",
    }
    return labels.get(key, key.title())


def role_to_graphql_enum(role: str) -> str:
    key = role.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    aliases = {
        "adc": "CARRY",
        "carry": "CARRY",
        "offlane": "OFFLANE",
        "solo": "OFFLANE",
        "mid": "MIDLANE",
        "midlane": "MIDLANE",
        "jungle": "JUNGLE",
        "support": "SUPPORT",
        "fill": "FILL",
    }
    if key in aliases:
        return aliases[key]
    upper = role.strip().upper()
    if upper in aliases.values():
        return upper
    return upper


def _parse_item_node(node: dict[str, Any] | None) -> BuildItemLine | None:
    if not node or not isinstance(node, dict):
        return None
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    nested = data.get("item") if isinstance(data.get("item"), dict) else {}
    name = pick_str(data, "displayName", "name") or pick_str(node, "name") or "Unknown"
    slug = pick_str(nested, "slug") or pick_str(node, "slug")
    icon = pick_str(data, "icon", "smallIcon") or pick_str(node, "icon")
    played = node.get("matchesPlayedBuildOrder")
    won = node.get("matchesWonBuildOrder")
    return BuildItemLine(
        name=name,
        slug=slug,
        icon=icon,
        matches_played=int(played) if played is not None else None,
        matches_won=int(won) if won is not None else None,
    )


def _parse_core_slot(result: dict[str, Any], key: str) -> BuildItemLine | None:
    slot = result.get(key)
    if not isinstance(slot, dict):
        return None
    item = _parse_item_node(slot)
    if item is None:
        return None
    return BuildItemLine(
        name=item.name,
        slug=item.slug,
        icon=item.icon,
        matches_played=item.matches_played,
        matches_won=item.matches_won,
    )


def parse_core_build_response(
    raw: dict[str, Any],
    *,
    hero_slug: str,
    role: str,
    hero_name: str | None = None,
) -> BuildRecommendation | None:
    """Normalize get_hero_core_build() output into a BuildRecommendation."""
    hero = raw.get("hero") if isinstance(raw.get("hero"), dict) else {}
    if not hero:
        hero = raw
    hero_data = hero.get("data") if isinstance(hero.get("data"), dict) else {}
    slug = pick_str(hero, "slug") or hero_slug
    display = hero_name or pick_str(hero_data, "displayName", "name") or slug.title()
    icon = pick_str(hero_data, "icon")

    results = raw.get("results")
    if results is None:
        core = hero.get("coreBuild") if isinstance(hero.get("coreBuild"), dict) else {}
        results = core.get("results")
    if not isinstance(results, list) or not results:
        return None

    top = results[0]
    if not isinstance(top, dict):
        return None

    core_items: list[BuildItemLine] = []
    for key in ("core1Item", "core2Item", "core3Item"):
        line = _parse_core_slot(top, key)
        if line is not None:
            core_items.append(line)

    crests: list[BuildItemLine] = []
    crest_rows = top.get("crests")
    if isinstance(crest_rows, list):
        for row in crest_rows:
            if not isinstance(row, dict):
                continue
            crest_item = row.get("item") if isinstance(row.get("item"), dict) else {}
            data = crest_item.get("data") if isinstance(crest_item.get("data"), dict) else {}
            nested = data.get("item") if isinstance(data.get("item"), dict) else {}
            name = pick_str(data, "displayName", "name") or "Unknown"
            crest_slug = pick_str(nested, "slug")
            icon = pick_str(data, "icon", "smallIcon")
            played = row.get("matchesPlayedBuildOrder")
            won = row.get("matchesWonBuildOrder")
            crests.append(
                BuildItemLine(
                    name=name,
                    slug=crest_slug,
                    icon=icon,
                    matches_played=int(played) if played is not None else None,
                    matches_won=int(won) if won is not None else None,
                )
            )

    sample = top.get("matchesPlayedBuildOrder")
    return BuildRecommendation(
        hero_name=display,
        hero_slug=slug,
        hero_icon=icon,
        role=role_to_graphql_enum(role),
        core_items=core_items,
        crests=crests,
        sample_size=int(sample) if sample is not None else None,
    )


def format_item_line(item: BuildItemLine) -> str:
    parts = [item.name]
    if item.matches_played is not None:
        wr = item.winrate_pct
        if wr is not None:
            parts.append(f"{item.matches_played} matches · {wr:.1f}% WR")
        else:
            parts.append(f"{item.matches_played} matches")
    return " · ".join(parts)
