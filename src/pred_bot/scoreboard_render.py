"""Render a match scoreboard PNG from normalized match data."""

from __future__ import annotations

import asyncio
import io
import logging
import os
from typing import TYPE_CHECKING

import httpx
from PIL import Image, ImageDraw, ImageFont

from pred_bot.hero_portraits import portrait_url
from pred_bot.jsonutil import normalize_match_id
from pred_bot.match_detail import MatchDetail, MatchPlayerLine, format_duration
from pred_bot.role_icons import normalize_role, prepare_role_icon, render_role_icon, role_icon_url

if TYPE_CHECKING:
    from pred_bot.stats_client import StatsClient

log = logging.getLogger(__name__)

WIDTH = 960
HEADER_H = 100
ROW_H = 68
ROW_GAP = 6
PADDING = 20
COL_GAP = 24
PORTRAIT = 48
ROLE_ICON_SIZE = 24
RANK_BADGE_H = 34
RANK_BADGE_MAX_W = 52
ROW_RADIUS = 8
IMAGE_FETCH_TIMEOUT = 60.0
ASSET_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; pred-bot/1.0; +https://pred.gg)",
    "Accept": "image/png,image/webp,image/*,*/*",
    "Referer": "https://pred.gg/",
}

BG_TOP = (16, 18, 13)
BG_BOTTOM = (24, 26, 19)
PANEL_WIN = (40, 46, 30)
PANEL_LOSE = (34, 32, 28)
PANEL_BORDER_WIN = (72, 82, 52)
PANEL_BORDER_LOSE = (58, 52, 48)
HEADER_PANEL = (28, 30, 22)
ACCENT = (168, 186, 98)
TEXT = (240, 242, 232)
MUTED = (148, 154, 132)
HIGHLIGHT = (232, 198, 88)
HIGHLIGHT_GLOW = (232, 198, 88, 45)
PLACEHOLDER = (58, 62, 50)
DIVIDER = (52, 56, 44)

TIER_COLORS: dict[str, tuple[int, int, int]] = {
    "bronze": (196, 128, 72),
    "silver": (188, 194, 204),
    "gold": (228, 188, 64),
    "platinum": (88, 205, 215),
    "diamond": (168, 128, 255),
    "paragon": (255, 158, 68),
}


def _load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        os.environ.get("SCOREBOARD_FONT_PATH"),
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for path in candidates:
        if path and os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _rgba(color: tuple[int, int, int], alpha: int = 255) -> tuple[int, int, int, int]:
    return color + (alpha,)


def _vertical_gradient(size: tuple[int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img.convert("RGBA")


def _team_rows(players: list[MatchPlayerLine], team: str) -> list[MatchPlayerLine]:
    key = team.strip().lower()
    rows = [p for p in players if p.team == key]
    rows.sort(key=lambda p: (p.performance_score or 0), reverse=True)
    return rows[:5]


def _player_key(p: MatchPlayerLine) -> str:
    return normalize_match_id(p.player_id) or p.name


def _format_cs(cs: int | None) -> str:
    if cs is None:
        return "—"
    return str(cs)


def _format_rank_label(player: MatchPlayerLine) -> str:
    if player.rank_name:
        return player.rank_name[:14]
    if player.rank_abbrev:
        return player.rank_abbrev
    return ""


def _tier_color(rank_label: str) -> tuple[int, int, int]:
    lower = rank_label.lower()
    for tier, color in TIER_COLORS.items():
        if tier in lower:
            return color
    return MUTED[:3]


def _circle_portrait(img: Image.Image, size: int) -> Image.Image:
    img = img.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def _placeholder(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), PLACEHOLDER + (255,))
    draw = ImageDraw.Draw(img)
    draw.ellipse((2, 2, size - 3, size - 3), fill=(78, 82, 68, 255))
    return img


def _lookup_rank_image(
    rank_icons: dict[str, Image.Image],
    player: MatchPlayerLine,
    key: str,
) -> Image.Image | None:
    if player.rank_icon and player.rank_icon in rank_icons:
        return rank_icons[player.rank_icon]
    return rank_icons.get(key)


async def _fetch_images_by_url(
    client: httpx.AsyncClient,
    url_to_keys: dict[str, set[str]],
) -> dict[str, Image.Image]:
    images: dict[str, Image.Image] = {}
    by_url: dict[str, Image.Image] = {}

    async def one(url: str) -> None:
        try:
            resp = await client.get(url, timeout=IMAGE_FETCH_TIMEOUT, headers=ASSET_HEADERS)
            resp.raise_for_status()
            by_url[url] = Image.open(io.BytesIO(resp.content)).copy()
        except Exception:
            log.warning("scoreboard image fetch failed %s", url, exc_info=True)

    await asyncio.gather(*(one(url) for url in url_to_keys))
    for url, keys in url_to_keys.items():
        img = by_url.get(url)
        if img is None:
            continue
        for key in keys:
            images[key] = img
    return images


async def fetch_portraits(
    client: httpx.AsyncClient,
    players: list[MatchPlayerLine],
    *,
    base_url: str,
) -> dict[str, Image.Image]:
    url_to_keys: dict[str, set[str]] = {}
    for player in players:
        url = portrait_url(player.hero_icon, base=base_url)
        if url:
            url_to_keys.setdefault(url, set()).add(_player_key(player))
    return await _fetch_images_by_url(client, url_to_keys)


async def fetch_role_icons(
    client: httpx.AsyncClient,
    players: list[MatchPlayerLine],
    *,
    base_url: str,
) -> dict[str, Image.Image]:
    url_to_keys: dict[str, set[str]] = {}
    for player in players:
        slug = normalize_role(player.role)
        url = role_icon_url(player.role, base=base_url)
        if url:
            url_to_keys.setdefault(url, set()).add(slug)
    return await _fetch_images_by_url(client, url_to_keys)


async def fetch_rank_icons(
    client: httpx.AsyncClient,
    players: list[MatchPlayerLine],
    *,
    base_url: str,
) -> dict[str, Image.Image]:
    url_to_keys: dict[str, set[str]] = {}
    for player in players:
        url = portrait_url(player.rank_icon, base=base_url)
        if not url:
            continue
        keys = url_to_keys.setdefault(url, set())
        keys.add(_player_key(player))
        if player.rank_icon:
            keys.add(player.rank_icon)
    return await _fetch_images_by_url(client, url_to_keys)


def _prepare_rank_badge(img: Image.Image) -> Image.Image:
    badge = img.convert("RGBA")
    bbox = badge.split()[3].getbbox()
    if bbox:
        badge = badge.crop(bbox)
    width, height = badge.size
    if height <= 0:
        return badge
    scale = RANK_BADGE_H / height
    new_w = max(1, int(width * scale))
    if new_w > RANK_BADGE_MAX_W:
        scale = RANK_BADGE_MAX_W / width
        new_w = RANK_BADGE_MAX_W
    new_h = max(1, int(height * scale))
    return badge.resize((new_w, new_h), Image.Resampling.LANCZOS)


def _fallback_rank_badge(player: MatchPlayerLine) -> Image.Image:
    label = (player.rank_abbrev or (player.rank_name or "?")[:3]).upper()[:3]
    size = RANK_BADGE_H
    color = _tier_color(player.rank_name or player.rank_abbrev or "")
    badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(badge)
    draw.ellipse((1, 1, size - 2, size - 2), fill=color + (255,))
    draw.ellipse((3, 3, size - 4, size - 4), outline=(255, 255, 255, 160), width=2)
    font = _load_font(12, bold=True)
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((size - tw) // 2, (size - th) // 2 - 1), label, fill=(22, 24, 18, 255), font=font)
    return badge


def _resolve_rank_badge(
    player: MatchPlayerLine,
    key: str,
    rank_icons: dict[str, Image.Image],
) -> Image.Image | None:
    if not (player.rank_icon or player.rank_name or player.rank_abbrev):
        return None
    raw = _lookup_rank_image(rank_icons, player, key)
    if raw is not None:
        return _prepare_rank_badge(raw)
    return _fallback_rank_badge(player)


def _resolve_role_icon(
    role: str,
    role_icons: dict[str, Image.Image],
    *,
    size: int,
) -> Image.Image:
    slug = normalize_role(role)
    raw = role_icons.get(slug)
    if raw is not None:
        return prepare_role_icon(raw, size, role=role)
    return render_role_icon(role, size)


def render_scoreboard_png(
    detail: MatchDetail,
    *,
    portraits: dict[str, Image.Image] | None = None,
    rank_icons: dict[str, Image.Image] | None = None,
    role_icons: dict[str, Image.Image] | None = None,
    highlight_player_id: str | None = None,
) -> bytes:
    portraits = portraits or {}
    rank_icons = rank_icons or {}
    role_icons = role_icons or {}
    highlight_norm = normalize_match_id(highlight_player_id)

    dusk_rows = _team_rows(detail.players, "dusk")
    dawn_rows = _team_rows(detail.players, "dawn")
    row_count = max(len(dusk_rows), len(dawn_rows), 1)
    body_h = row_count * (ROW_H + ROW_GAP) - ROW_GAP
    height = HEADER_H + PADDING + body_h + PADDING

    img = _vertical_gradient((WIDTH, height))
    draw = ImageDraw.Draw(img)
    title_font = _load_font(24, bold=True)
    header_font = _load_font(14)
    row_font = _load_font(15)
    small_font = _load_font(13)
    label_font = _load_font(13, bold=True)

    dusk_k = detail.team_kills.get("dusk", 0)
    dawn_k = detail.team_kills.get("dawn", 0)
    win_key = detail.winning_team_key()

    draw.rectangle((0, 0, WIDTH, HEADER_H), fill=_rgba(HEADER_PANEL))
    draw.line([(PADDING, HEADER_H - 1), (WIDTH - PADDING, HEADER_H - 1)], fill=_rgba(ACCENT, 120), width=2)

    dusk_name = detail.team_display_name("dusk")
    dawn_name = detail.team_display_name("dawn")
    dusk_title = f"{dusk_name}  ({dusk_k})"
    draw.text((PADDING, 20), dusk_title, fill=TEXT, font=title_font)
    dawn_title = f"{dawn_name}  ({dawn_k})"
    dawn_w = draw.textlength(dawn_title, font=title_font)
    draw.text((WIDTH - PADDING - dawn_w, 20), dawn_title, fill=TEXT, font=title_font)

    meta = f"{format_duration(detail.duration_seconds)}  ·  {detail.game_mode}"
    meta_w = draw.textlength(meta, font=header_font)
    draw.text(((WIDTH - meta_w) // 2, 62), meta, fill=MUTED, font=header_font)

    col_w = (WIDTH - PADDING * 2 - COL_GAP) // 2
    y0 = HEADER_H + PADDING
    mid_x = PADDING + col_w + COL_GAP // 2
    draw.line([(mid_x, y0 - 8), (mid_x, y0 + body_h)], fill=_rgba(DIVIDER, 160), width=1)

    def draw_team_column(
        x: int,
        team_key: str,
        rows: list[MatchPlayerLine],
    ) -> None:
        is_winner = team_key == win_key
        label = detail.team_display_name(team_key)
        if is_winner:
            label = f"{label}  ·  Victory"
        draw.text((x, y0 - 20), label, fill=_rgba(ACCENT) if is_winner else MUTED, font=label_font)

        for index, player in enumerate(rows):
            y = y0 + index * (ROW_H + ROW_GAP)
            hi = highlight_norm is not None and normalize_match_id(player.player_id) == highlight_norm
            row_box = (x, y, x + col_w, y + ROW_H)
            fill = PANEL_WIN if is_winner else PANEL_LOSE
            border = PANEL_BORDER_WIN if is_winner else PANEL_BORDER_LOSE
            draw.rounded_rectangle(row_box, radius=ROW_RADIUS, fill=_rgba(fill))
            draw.rounded_rectangle(row_box, radius=ROW_RADIUS, outline=_rgba(border), width=1)
            if hi:
                glow = Image.new("RGBA", (col_w, ROW_H), (0, 0, 0, 0))
                gdraw = ImageDraw.Draw(glow)
                gdraw.rounded_rectangle((0, 0, 3, ROW_H), radius=2, fill=HIGHLIGHT_GLOW)
                img.paste(glow, (x, y), glow)

            key = _player_key(player)
            portrait_raw = portraits.get(key)
            portrait = _circle_portrait(portrait_raw, PORTRAIT) if portrait_raw else _placeholder(PORTRAIT)
            px = x + 12
            py = y + (ROW_H - PORTRAIT) // 2
            img.paste(portrait, (px, py), portrait)

            name = (player.name or "Unknown")[:18]
            rank_label = _format_rank_label(player)
            kda = f"{player.kills}/{player.deaths}/{player.assists}"
            cs = _format_cs(player.cs)

            text_x = px + PORTRAIT + 12
            name_color = HIGHLIGHT if hi else TEXT
            draw.text((text_x, y + 12), name, fill=name_color, font=row_font)

            role_icon = _resolve_role_icon(player.role, role_icons, size=ROLE_ICON_SIZE)
            stats_y = y + 36
            img.paste(role_icon, (text_x, stats_y), role_icon)
            stats_text = f"{kda}  ·  {cs} CS"
            draw.text((text_x + ROLE_ICON_SIZE + 8, stats_y + 2), stats_text, fill=MUTED, font=small_font)

            right_x = x + col_w - 12
            rank_badge = _resolve_rank_badge(player, key, rank_icons)
            if rank_badge is not None:
                right_x -= rank_badge.width
                rank_y = y + (ROW_H - rank_badge.height) // 2
                img.paste(rank_badge, (right_x, rank_y), rank_badge)
                right_x -= 10

            if rank_label:
                rank_color = _tier_color(rank_label)
                rank_w = draw.textlength(rank_label, font=small_font)
                right_x -= rank_w
                draw.text((right_x, y + 14), rank_label, fill=_rgba(rank_color), font=small_font)

    draw_team_column(PADDING, "dusk", dusk_rows)
    draw_team_column(PADDING + col_w + COL_GAP, "dawn", dawn_rows)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


async def render_scoreboard_for_match(
    client: httpx.AsyncClient,
    detail: MatchDetail,
    stats: StatsClient,
    *,
    highlight_player_id: str | None = None,
) -> bytes | None:
    try:
        with_icons = sum(1 for p in detail.players if p.rank_icon)
        portraits, rank_icons, role_icons = await asyncio.gather(
            fetch_portraits(client, detail.players, base_url=stats.web_base_url),
            fetch_rank_icons(client, detail.players, base_url=stats.web_base_url),
            fetch_role_icons(client, detail.players, base_url=stats.web_base_url),
        )
        fetched = sum(
            1 for p in detail.players if _lookup_rank_image(rank_icons, p, _player_key(p)) is not None
        )
        role_slugs = {normalize_role(p.role) for p in detail.players if p.role}
        log.info(
            "scoreboard match=%s rank icons: %s with hash, %s fetched; role icons: %s roles, %s fetched",
            detail.match_id[:8],
            with_icons,
            fetched,
            len(role_slugs),
            len(role_icons),
        )
        return render_scoreboard_png(
            detail,
            portraits=portraits,
            rank_icons=rank_icons,
            role_icons=role_icons,
            highlight_player_id=highlight_player_id,
        )
    except Exception:
        log.exception("scoreboard render failed match=%s", detail.match_id)
        return None
