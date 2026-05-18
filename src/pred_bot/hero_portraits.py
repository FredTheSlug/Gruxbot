"""pred.gg hero portrait asset URLs."""

from __future__ import annotations


def portrait_url(icon: str | None, *, base: str = "https://pred.gg") -> str | None:
    """Build a CDN URL for a hero icon hash from GraphQL."""
    if not icon:
        return None
    raw = icon.strip()
    if not raw:
        return None
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    root = base.rstrip("/")
    if raw.startswith("/"):
        return f"{root}{raw}"
    if "/" in raw:
        return f"{root}/{raw.lstrip('/')}"
    name = raw if raw.endswith(".png") else f"{raw}.png"
    return f"{root}/assets/{name}"
