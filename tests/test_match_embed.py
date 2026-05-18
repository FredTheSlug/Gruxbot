"""Tests for match detail parsing and Discord embeds."""

from __future__ import annotations

from pred_bot.match_detail import MatchDetail, MatchPlayerLine, parse_pred_match
from pred_bot.match_embed import build_match_embed
from pred_bot.hero_portraits import portrait_url
from pred_bot.stats_client import StatsClient
from pred_bot.omeda_client import OmedaClient
from pred_bot.pred_client import PredGqlClient


def test_parse_pred_match_team_kills_and_vp() -> None:
    raw = {
        "uuid": "9d1794a79dae4c3ca4d32f8d1d8913df",
        "duration": 1603,
        "gameMode": "RANKED",
        "region": "NA",
        "startTime": "2026-02-07T02:38:45Z",
        "endTime": "2026-02-07T03:05:29Z",
        "winningTeam": "DUSK",
        "matchPlayers": [
            {
                "team": "DUSK",
                "kills": 2,
                "deaths": 1,
                "assists": 12,
                "role": "SUPPORT",
                "hero": {
                    "id": "12",
                    "slug": "muriel",
                    "data": {"displayName": "Muriel", "icon": "2c827fcff5a02da5"},
                },
                "player": {"name": "Seabass", "uuid": "41a5b34d-915c-4651-ac0e-0376fd23424c"},
                "rating": {
                    "points": 1100.0,
                    "newPoints": 1122.0,
                    "rank": {
                        "id": "32",
                        "name": "Platinum I",
                        "abbreviation": "P1",
                        "icon": "82f82fede2ff80be",
                    },
                },
                "minionsKilled": 25,
            },
            {
                "team": "DAWN",
                "kills": 1,
                "deaths": 8,
                "assists": 4,
                "role": "JUNGLE",
                "player": {"name": "Other", "uuid": "00000000-0000-0000-0000-000000000002"},
                "rating": {"points": 1120.0, "newPoints": 1100.0},
            },
        ],
    }
    detail = parse_pred_match(raw)
    assert detail is not None
    assert detail.team_kills["dusk"] == 2
    assert detail.team_kills["dawn"] == 1
    assert detail.winning_team == "dusk"
    seabass = next(p for p in detail.players if p.name == "Seabass")
    assert seabass.vp_change == 22
    assert seabass.hero_icon == "2c827fcff5a02da5"
    assert seabass.hero_id == "12"
    assert seabass.cs == 25
    assert seabass.rank_name == "Platinum I"
    assert seabass.rank_abbrev == "P1"
    assert seabass.rank_icon == "82f82fede2ff80be"
    assert seabass.rank_id == "32"


def test_build_match_embed_has_buttons() -> None:
    detail = MatchDetail(
        match_id="abc123",
        duration_seconds=1560,
        game_mode="Ranked",
        region="North America",
        start_time="2026-02-07T02:38:45Z",
        end_time="2026-02-07T03:05:29Z",
        winning_team="dusk",
        team_kills={"dusk": 28, "dawn": 17},
        players=[
            MatchPlayerLine(
                player_id="p1",
                name="Seabass",
                team="dusk",
                role="support",
                kills=2,
                deaths=1,
                assists=12,
                performance_score=166.4,
                vp_change=22,
                hero_name="Muriel",
                hero_icon="2c827fcff5a02da5",
            ),
        ],
    )
    stats = StatsClient(pred=PredGqlClient(), omeda=OmedaClient("https://omeda.city"))
    embeds, view = build_match_embed(detail, stats, highlight_player_id="p1")
    assert len(embeds) >= 2
    main, player = embeds[0], embeds[1]
    assert "Click here to view more" in (main.description or "")
    assert main.fields
    assert player.title and "Victory" in player.title
    assert player.author is not None
    assert player.author.icon_url == portrait_url("2c827fcff5a02da5")
    assert main.thumbnail is not None
    assert main.thumbnail.url == portrait_url("2c827fcff5a02da5")
    assert view is not None
    labels = [c.label for c in view.children]  # type: ignore[attr-defined]
    assert "Open" in labels
    assert "View Scoreboard" in labels
