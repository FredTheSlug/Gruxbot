"""Discord match notification: embeds + optional scoreboard image attachment."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import discord
import httpx

from pred_bot.match_detail import MatchDetail
from pred_bot.match_embed import build_match_embed
from pred_bot.scoreboard_render import render_scoreboard_for_match

if TYPE_CHECKING:
    from pred_bot.stats_client import StatsClient


async def build_match_message(
    client: httpx.AsyncClient,
    detail: MatchDetail,
    stats: StatsClient,
    *,
    highlight_player_id: str | None = None,
    title_prefix: str = "",
    scoreboard_image: bool = True,
) -> tuple[list[discord.Embed], discord.ui.View | None, discord.File | None]:
    """Build embeds and an optional scoreboard PNG attached to the summary embed."""
    compact = scoreboard_image
    embeds, view = build_match_embed(
        detail,
        stats,
        highlight_player_id=highlight_player_id,
        title_prefix=title_prefix,
        compact=compact,
    )
    if not scoreboard_image:
        return embeds, view, None

    png = await render_scoreboard_for_match(
        client,
        detail,
        stats,
        highlight_player_id=highlight_player_id,
    )
    if not png:
        embeds, view = build_match_embed(
            detail,
            stats,
            highlight_player_id=highlight_player_id,
            title_prefix=title_prefix,
            compact=False,
        )
        return embeds, view, None

    file = discord.File(io.BytesIO(png), filename="scoreboard.png")
    embeds[0].set_image(url="attachment://scoreboard.png")
    return embeds, view, file
