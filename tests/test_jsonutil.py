"""Tests for JSON helpers."""

from __future__ import annotations

from pred_bot.jsonutil import (
    extract_player_id_from_search,
    find_new_matches_since,
    get_match_ids_in_order,
    get_match_ids_newest_first,
    looks_like_player_id,
    normalize_match_id,
    row_matches_id,
)


def test_looks_like_player_id() -> None:
    assert looks_like_player_id("26a541c0-6c09-4beb-b787-bfd86bc96b4b")
    assert not looks_like_player_id("not-a-uuid")


def test_extract_player_id_from_search_list() -> None:
    payload = [{"id": "abc", "name": "x"}]
    assert extract_player_id_from_search(payload) == "abc"


def test_extract_player_id_nested() -> None:
    payload = {"results": [{"player_id": "p1"}]}
    assert extract_player_id_from_search(payload) == "p1"


def test_get_match_ids_in_order() -> None:
    payload = [{"id": "m1", "x": 1}, {"match_id": "m2"}]
    assert get_match_ids_in_order(payload) == ["m1", "m2"]


def test_normalize_match_id() -> None:
    assert normalize_match_id("ABC") == "abc"
    assert normalize_match_id(None) is None


def test_get_match_ids_newest_first_sorts_by_time() -> None:
    payload = {
        "matches": [
            {"id": "older", "start_time": "2026-05-01T10:00:00.000Z"},
            {"id": "newest", "start_time": "2026-05-10T10:00:00.000Z"},
            {"id": "mid", "start_time": "2026-05-05T10:00:00.000Z"},
        ]
    }
    assert get_match_ids_newest_first(payload) == ["newest", "mid", "older"]


def test_row_matches_id_across_uuid_and_id_fields() -> None:
    row = {"id": "abc-123", "uuid": "ABC-123"}
    assert row_matches_id(row, "abc-123")
    assert row_matches_id(row, "ABC-123")


def test_find_new_matches_since_rebaseline_when_last_seen_missing() -> None:
    payload = {
        "matches": [
            {"id": "m-new", "start_time": "2026-05-10T10:00:00.000Z"},
            {"id": "m-old", "start_time": "2026-05-01T10:00:00.000Z"},
        ]
    }
    scan = find_new_matches_since(payload, "m-unknown")
    assert scan.status == "rebaseline"
    assert scan.new_match_ids == ()
    assert scan.newest_match_id == "m-new"


def test_find_new_matches_since_only_newer_than_last_seen() -> None:
    payload = {
        "matches": [
            {"id": "m3", "start_time": "2026-05-12T10:00:00.000Z"},
            {"id": "m2", "start_time": "2026-05-11T10:00:00.000Z"},
            {"id": "m1", "start_time": "2026-05-10T10:00:00.000Z"},
        ]
    }
    scan = find_new_matches_since(payload, "m1")
    assert scan.status == "new"
    assert scan.new_match_ids == ("m2", "m3")
