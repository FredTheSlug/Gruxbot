"""Tests for configuration helpers."""

from pred_bot.config import _normalize_bearer


def test_normalize_bearer_adds_prefix() -> None:
    assert _normalize_bearer("abc123") == "Bearer abc123"


def test_normalize_bearer_keeps_existing() -> None:
    assert _normalize_bearer("Bearer xyz") == "Bearer xyz"


def test_normalize_bearer_empty() -> None:
    assert _normalize_bearer(None) is None
    assert _normalize_bearer("  ") is None
