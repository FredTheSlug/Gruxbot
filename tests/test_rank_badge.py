"""Tests for rank badge image prep."""

from __future__ import annotations

import io

import httpx
from PIL import Image

from pred_bot.scoreboard_render import RANK_BADGE_H, _fallback_rank_badge, _prepare_rank_badge
from pred_bot.match_detail import MatchPlayerLine


def test_prepare_rank_badge_crops_large_canvas() -> None:
    """Simulate pred.gg rank asset: huge transparent canvas, small opaque badge."""
    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    badge = Image.new("RGBA", (80, 80), (200, 180, 80, 255))
    canvas.paste(badge, (216, 216))
    out = _prepare_rank_badge(canvas)
    assert out.height == RANK_BADGE_H
    assert out.width > 10
    alpha = out.split()[3]
    assert alpha.getbbox() is not None
    avg_alpha = sum(alpha.getdata()) / (out.width * out.height)
    assert avg_alpha > 100


def test_fallback_rank_badge_has_opaque_pixels() -> None:
    player = MatchPlayerLine(
        player_id="p1",
        name="Test",
        team="dusk",
        role="support",
        kills=0,
        deaths=0,
        assists=0,
        rank_name="Platinum I",
        rank_abbrev="P1",
    )
    badge = _fallback_rank_badge(player)
    alpha = badge.split()[3]
    assert max(alpha.getdata()) > 200


def test_live_pred_rank_asset_visible_after_crop() -> None:
    url = "https://pred.gg/assets/82f82fede2ff80be.png"
    resp = httpx.get(url, timeout=60)
    resp.raise_for_status()
    raw = Image.open(io.BytesIO(resp.content))
    small_sq = raw.convert("RGBA").resize((26, 26), Image.Resampling.LANCZOS)
    cropped = _prepare_rank_badge(raw)
    sq_alpha = sum(small_sq.split()[3].getdata()) / (26 * 26)
    crop_alpha = sum(cropped.split()[3].getdata()) / (cropped.width * cropped.height)
    assert abs(cropped.height - RANK_BADGE_H) <= 1
    assert crop_alpha > sq_alpha
    assert cropped.width >= 20
