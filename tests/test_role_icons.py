"""Tests for role icon URLs and rendering."""

from __future__ import annotations

import io

import httpx
from PIL import Image

from pred_bot.role_icons import normalize_role, prepare_role_icon, render_role_icon, role_icon_url


def test_role_icon_urls() -> None:
    assert role_icon_url("OFFLANE") == "https://pred.gg/images/icons/roles/offlane.png"
    assert role_icon_url("mid", base="https://pred.gg") == "https://pred.gg/images/icons/roles/midlane.png"
    assert role_icon_url("NONE") is None


def test_prepare_role_icon_resizes_full_canvas() -> None:
    resp = httpx.get(
        "https://pred.gg/images/icons/roles/offlane.png",
        timeout=30,
        headers={"User-Agent": "pred-bot-test"},
    )
    resp.raise_for_status()
    raw = Image.open(io.BytesIO(resp.content))
    prepared = prepare_role_icon(raw, 24, role="offlane")
    assert prepared.size == (24, 24)
    assert max(prepared.split()[3].getdata()) == 255


def test_render_role_icons_for_all_roles() -> None:
    for role in ("carry", "offlane", "midlane", "jungle", "support"):
        img = render_role_icon(role, 20)
        assert img.size == (20, 20)
        alpha = img.split()[3]
        assert max(alpha.getdata()) > 200


def test_role_aliases() -> None:
    assert normalize_role("MID") == "midlane"
    assert normalize_role("off_lane") == "offlane"
    img = render_role_icon("MID", 18)
    assert img.size == (18, 18)
