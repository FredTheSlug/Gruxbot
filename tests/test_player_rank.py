"""Tests for profile rank resolution."""

from __future__ import annotations

from pred_bot.match_detail import MatchPlayerLine
from pred_bot.player_rank import (
    apply_rank_info,
    pick_rank_from_player_ratings,
    rank_info_from_omeda_profile,
)


def test_pick_rank_prefers_current_season() -> None:
    ratings = [
        {
            "unranked": False,
            "rating": {"id": "10", "name": "Season 1 - Split 3"},
            "rank": {"id": "31", "name": "Platinum II", "abbreviation": "P2", "icon": "abc"},
        },
        {
            "unranked": False,
            "rating": {"id": "11", "name": "Season 1 - Split 4"},
            "rank": {"id": "32", "name": "Platinum I", "abbreviation": "P1", "icon": "def"},
        },
    ]
    info = pick_rank_from_player_ratings(ratings, preferred_season_id="11")
    assert info is not None
    assert info["rank_name"] == "Platinum I"
    assert info["rank_icon"] == "def"


def test_pick_rank_skips_unranked_rows() -> None:
    ratings = [
        {"unranked": True, "rating": {"id": "11"}, "rank": {"name": "Gold I"}},
        {
            "unranked": False,
            "rating": {"id": "11"},
            "rank": {"id": "28", "name": "Gold II", "abbreviation": "G2", "icon": "x"},
        },
    ]
    info = pick_rank_from_player_ratings(ratings, preferred_season_id="11")
    assert info is not None
    assert info["rank_name"] == "Gold II"


def test_omeda_profile_rank() -> None:
    info = rank_info_from_omeda_profile(
        {"rank_title": "Platinum III", "rank_image": "/assets/omeda_ranks/plat.png"},
        base_url="https://omeda.city",
    )
    assert info is not None
    assert info["rank_name"] == "Platinum III"
    assert info["rank_icon"] == "https://omeda.city/assets/omeda_ranks/plat.png"


def test_apply_rank_info_only_fills_missing() -> None:
    player = MatchPlayerLine(
        player_id="p1",
        name="Test",
        team="dusk",
        role="carry",
        kills=0,
        deaths=0,
        assists=0,
        rank_name="Diamond I",
    )
    apply_rank_info(
        player,
        {"rank_name": "Platinum I", "rank_abbrev": "P1", "rank_icon": "hash", "rank_id": "32"},
    )
    assert player.rank_name == "Diamond I"
    assert player.rank_icon == "hash"
