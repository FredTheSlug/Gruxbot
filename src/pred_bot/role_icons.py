"""Role icons for scoreboard rows (pred.gg CDN + drawn fallback)."""

from __future__ import annotations

from PIL import Image, ImageDraw

ROLE_KEYS = ("carry", "offlane", "midlane", "jungle", "support", "fill", "none")

# Role colors for drawn fallback badges
ROLE_COLORS: dict[str, tuple[int, int, int]] = {
    "carry": (196, 88, 72),
    "offlane": (196, 142, 58),
    "midlane": (108, 148, 220),
    "jungle": (92, 168, 108),
    "support": (168, 118, 196),
    "fill": (130, 136, 115),
    "none": (100, 104, 92),
}

_ICON_CACHE: dict[tuple[str, int], Image.Image] = {}


def normalize_role(role: str) -> str:
    key = role.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    aliases = {
        "adc": "carry",
        "mid": "midlane",
        "midlane": "midlane",
        "solo": "offlane",
    }
    return aliases.get(key, key)


def role_icon_url(role: str, *, base: str = "https://pred.gg") -> str | None:
    """pred.gg static role icons, e.g. /images/icons/roles/offlane.png."""
    slug = normalize_role(role)
    if slug in ("none", ""):
        return None
    return f"{base.rstrip('/')}/images/icons/roles/{slug}.png"


def prepare_role_icon(img: Image.Image, size: int, *, role: str = "") -> Image.Image:
    """Resize pred.gg role PNG for scoreboard paste (full canvas, no crop)."""
    badge = img.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)

    # pred.gg assets are white-only; add a subtle role-tinted plate so icons read on dark rows
    slug = normalize_role(role)
    plate_color = ROLE_COLORS.get(slug, ROLE_COLORS["none"])
    plate = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(plate)
    radius = max(3, size // 4)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=plate_color + (200,))
    plate.alpha_composite(badge)
    return plate


def _draw_carry(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fg: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    draw.polygon([(cx, y0 + 1), (x1 - 2, cy), (cx, y1 - 1), (x0 + 2, cy)], fill=fg)


def _draw_offlane(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fg: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    draw.polygon(
        [(x0 + 3, y0 + 2), (x1 - 3, y0 + 2), (x1 - 1, y1 - 2), (x0 + 1, y1 - 2)],
        fill=fg,
    )


def _draw_midlane(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fg: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    draw.polygon([(cx, y0 + 1), (x1 - 2, cy), (cx, y1 - 1), (x0 + 2, cy)], fill=fg)
    draw.line([(x0 + 3, y1 - 2), (x1 - 3, y0 + 2)], fill=fg, width=2)


def _draw_jungle(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fg: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    draw.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=fg)
    draw.line([(x0 + 2, cy), (x1 - 2, cy)], fill=fg, width=2)
    draw.line([(cx, y0 + 2), (cx, y1 - 2)], fill=fg, width=2)


def _draw_support(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fg: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    draw.rectangle((x0 + 3, cy - 1, x1 - 3, cy + 1), fill=fg)
    draw.rectangle((cx - 1, y0 + 3, cx + 1, y1 - 3), fill=fg)


def _draw_fill(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fg: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), outline=fg, width=2)


_DRAWERS = {
    "carry": _draw_carry,
    "offlane": _draw_offlane,
    "midlane": _draw_midlane,
    "jungle": _draw_jungle,
    "support": _draw_support,
    "fill": _draw_fill,
    "none": _draw_fill,
}


def render_role_icon(role: str, size: int = 20) -> Image.Image:
    """Return a small RGBA role badge (drawn fallback when CDN fetch fails)."""
    cache_key = (normalize_role(role), size)
    cached = _ICON_CACHE.get(cache_key)
    if cached is not None:
        return cached

    key = normalize_role(role)
    bg = ROLE_COLORS.get(key, ROLE_COLORS["none"])
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = max(1, size // 10)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=max(3, size // 4), fill=bg + (255,))
    inner = (pad + 1, pad + 1, size - pad - 2, size - pad - 2)
    fg: tuple[int, int, int, int] = (248, 250, 240, 255)
    drawer = _DRAWERS.get(key, _draw_fill)
    drawer(draw, inner, fg)
    _ICON_CACHE[cache_key] = img
    return img
