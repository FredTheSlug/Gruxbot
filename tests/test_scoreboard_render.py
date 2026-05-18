"""Tests for scoreboard PNG rendering."""

from __future__ import annotations

from pred_bot.match_detail import MatchDetail, MatchPlayerLine
from pred_bot.scoreboard_render import render_scoreboard_png


def _sample_detail() -> MatchDetail:
    return MatchDetail(
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
                cs=25,
                rank_name="Platinum I",
                rank_abbrev="P1",
                rank_icon="82f82fede2ff80be",
                vp_change=22,
                hero_name="Muriel",
                hero_icon="2c827fcff5a02da5",
            ),
            MatchPlayerLine(
                player_id="p2",
                name="Other",
                team="dawn",
                role="jungle",
                kills=1,
                deaths=8,
                assists=4,
                performance_score=40.0,
                cs=147,
                vp_change=-20,
                hero_name="Grux",
            ),
        ],
    )


def test_render_scoreboard_png_bytes() -> None:
    png = render_scoreboard_png(_sample_detail(), highlight_player_id="p1")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 500
