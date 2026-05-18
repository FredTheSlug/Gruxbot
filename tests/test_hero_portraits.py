"""Tests for hero portrait URLs."""

from __future__ import annotations

from pred_bot.hero_portraits import portrait_url


def test_portrait_url_from_hash() -> None:
    assert portrait_url("2c827fcff5a02da5") == "https://pred.gg/assets/2c827fcff5a02da5.png"


def test_portrait_url_keeps_full_url() -> None:
    url = "https://cdn.example.com/hero.png"
    assert portrait_url(url) == url


def test_portrait_url_custom_base() -> None:
    assert (
        portrait_url("abc123", base="https://staging.pred.gg")
        == "https://staging.pred.gg/assets/abc123.png"
    )
