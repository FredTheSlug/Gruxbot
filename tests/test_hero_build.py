"""Tests for hero build parsing and embed helpers."""

from __future__ import annotations

from pred_bot.commands.build import build_recommendation_embed
from pred_bot.hero_build import (
    BuildItemLine,
    format_item_line,
    parse_core_build_response,
    role_to_graphql_enum,
)
from pred_bot.stats_client import StatsClient
from pred_bot.pred_client import PredGqlClient


def _sample_build_payload() -> dict:
    return {
        "hero": {
            "slug": "boris",
            "data": {"displayName": "Boris", "icon": "abc123"},
            "coreBuild": {
                "results": [
                    {
                        "matchesPlayedBuildOrder": 23,
                        "matchesWonBuildOrder": 18,
                        "core1Item": {
                            "id": "1",
                            "data": {
                                "displayName": "Soul Reaper",
                                "icon": "item1",
                                "item": {"slug": "soul-reaper"},
                            },
                        },
                        "core2Item": {
                            "id": "2",
                            "data": {
                                "displayName": "Brutalisk",
                                "icon": "item2",
                                "item": {"slug": "brutalisk"},
                            },
                        },
                        "core3Item": {
                            "id": "3",
                            "data": {
                                "displayName": "Wind Wall",
                                "icon": "item3",
                                "item": {"slug": "wind-wall"},
                            },
                        },
                        "crests": [
                            {
                                "matchesPlayedBuildOrder": 21,
                                "matchesWonBuildOrder": 18,
                                "item": {
                                    "id": "c1",
                                    "data": {
                                        "displayName": "Agility Crest",
                                        "icon": "crest1",
                                        "item": {"slug": "agility-crest"},
                                    },
                                },
                            },
                            {
                                "matchesPlayedBuildOrder": 2,
                                "matchesWonBuildOrder": 1,
                                "item": {
                                    "id": "c2",
                                    "data": {
                                        "displayName": "Vitality Crest",
                                        "icon": "crest2",
                                        "item": {"slug": "vitality-crest"},
                                    },
                                },
                            },
                        ],
                    }
                ]
            },
        },
    }


def test_role_to_graphql_enum() -> None:
    assert role_to_graphql_enum("jungle") == "JUNGLE"
    assert role_to_graphql_enum("mid") == "MIDLANE"
    assert role_to_graphql_enum("OFFLANE") == "OFFLANE"


def test_parse_core_build_response() -> None:
    raw = _sample_build_payload()
    rec = parse_core_build_response(raw, hero_slug="boris", role="JUNGLE")
    assert rec is not None
    assert rec.hero_name == "Boris"
    assert rec.hero_slug == "boris"
    assert len(rec.core_items) == 3
    assert rec.core_items[0].name == "Soul Reaper"
    assert len(rec.crests) == 2
    assert rec.crests[0].name == "Agility Crest"
    assert rec.sample_size == 23
    assert rec.crests[0].winrate_pct is not None
    assert rec.crests[0].winrate_pct > 80


def test_format_item_line() -> None:
    line = BuildItemLine(name="Test Item", matches_played=10, matches_won=7)
    text = format_item_line(line)
    assert "Test Item" in text
    assert "10 matches" in text
    assert "70.0% WR" in text


def test_build_recommendation_embed_fields() -> None:
    raw = _sample_build_payload()
    rec = parse_core_build_response(raw, hero_slug="boris", role="JUNGLE")
    assert rec is not None
    stats = StatsClient(pred=PredGqlClient(), omeda=None, use_omeda_fallback=False)
    embed = build_recommendation_embed(
        rec,
        stats=stats,
        build_url="https://pred.gg/heroes/boris?gameModes=RANKED&role=JUNGLE&ranks=36",
    )
    assert "Boris" in embed.title
    field_names = {f.name for f in embed.fields}
    assert "Core 1" in field_names
    assert "Crest 1" in field_names


def test_parse_empty_results() -> None:
    raw = {"hero": {"slug": "boris", "coreBuild": {"results": []}}}
    assert parse_core_build_response(raw, hero_slug="boris", role="JUNGLE") is None
