"""`/lastmatch` — preview rich match embeds for testing."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from pred_bot.jsonutil import get_match_ids_newest_first, looks_like_player_id, pick_str
from pred_bot.match_detail import MatchDetail
from pred_bot.match_message import build_match_message
from pred_bot.stats_client import StatsAuthRequired

if TYPE_CHECKING:
    from pred_bot.bot import PredBot

log = logging.getLogger(__name__)


def register(bot: PredBot) -> None:
    @bot.tree.command(
        name="lastmatch",
        description="Show the rich match card for a player's latest game (testing)",
    )
    @app_commands.describe(
        player_id="Predecessor player UUID",
        match_id="Optional match id (defaults to latest on their profile)",
        public="Post in the channel instead of only you (default false)",
    )
    async def lastmatch_cmd(
        interaction: discord.Interaction,
        player_id: str,
        match_id: str | None = None,
        public: bool = False,
    ) -> None:
        await interaction.response.defer(thinking=True, ephemeral=not public)
        pid = player_id.strip()
        if not looks_like_player_id(pid):
            await interaction.followup.send(
                "Please provide a valid player UUID (from their pred.gg profile URL).",
                ephemeral=True,
            )
            return

        client = bot.http_client
        mid = match_id.strip() if match_id else None

        try:
            if not mid:
                matches_payload = await bot.stats.get_player_matches(
                    client, pid, page=0, per_page=1
                )
                ids = get_match_ids_newest_first(matches_payload)
                if not ids:
                    await interaction.followup.send(
                        f"No matches found for `{pid}`.",
                        ephemeral=True,
                    )
                    return
                mid = ids[0]

            detail = await bot.stats.get_match(client, mid)
        except StatsAuthRequired:
            await interaction.followup.send(
                "Could not load matches (pred.gg auth required and omeda fallback disabled).",
                ephemeral=True,
            )
            return
        except Exception as e:
            log.exception("lastmatch failed")
            await interaction.followup.send(f"Could not load match: `{e}`", ephemeral=True)
            return

        if not isinstance(detail, MatchDetail):
            await interaction.followup.send(
                "Match data could not be parsed into a card (API shape unexpected).",
                ephemeral=True,
            )
            return

        player_label = pid
        try:
            profile = await bot.stats.get_player(client, pid)
            if isinstance(profile, dict):
                player_label = pick_str(profile, "display_name", "name", "username") or player_label
        except Exception:
            pass

        embeds, view, scoreboard_file = await build_match_message(
            client,
            detail,
            bot.stats,
            highlight_player_id=pid,
            title_prefix=f"Latest match — {player_label}",
            scoreboard_image=bot.config.scoreboard_image_enabled,
        )
        await interaction.followup.send(embeds=embeds, view=view, file=scoreboard_file)
