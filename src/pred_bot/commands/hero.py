"""`/hero` slash command."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands

from pred_bot.jsonutil import find_in_list_by_name, first_list_of_dicts, pick_str
from pred_bot.stats_client import StatsAuthRequired

if TYPE_CHECKING:
    from pred_bot.bot import PredBot

log = logging.getLogger(__name__)

MAX_JSON_CHARS = 950


def register(bot: PredBot) -> None:
    @bot.tree.command(name="hero", description="Look up hero info from Omeda.city")
    @app_commands.describe(hero_query="Hero name (partial match ok)")
    async def hero_cmd(interaction: discord.Interaction, hero_query: str) -> None:
        await interaction.response.defer(thinking=True)
        client = bot.http_client
        try:
            heroes_payload = await bot.stats.get_heroes(client)
        except StatsAuthRequired:
            await interaction.followup.send(
                "That stats endpoint requires authentication.",
                ephemeral=True,
            )
            return
        except Exception as e:
            log.exception("hero list failed")
            await interaction.followup.send(f"Request failed: `{e}`", ephemeral=True)
            return

        heroes = first_list_of_dicts(heroes_payload)
        if not heroes and isinstance(heroes_payload, dict):
            heroes = first_list_of_dicts(heroes_payload.get("heroes") or heroes_payload.get("data"))

        match = find_in_list_by_name(heroes, hero_query)
        if not match:
            await interaction.followup.send(f"No hero matched `{hero_query}`.", ephemeral=True)
            return

        hero_name = pick_str(match, "name", "title", "display_name", "slug") or hero_query
        hero_id = pick_str(match, "id", "hero_id")
        hero_slug = pick_str(match, "slug")

        stats: Any | None = None
        try:
            stats = await bot.stats.get_hero_statistics(
                client,
                hero_ids=[hero_id] if hero_id else None,
                hero_slug=hero_slug,
            )
        except StatsAuthRequired:
            stats = None
        except Exception:
            log.debug("hero statistics optional fetch failed", exc_info=True)
            stats = None

        embed = discord.Embed(
            title=hero_name,
            description=f"[Heroes on Pred.gg]({bot.stats.heroes_url()})",
        )
        if hero_id:
            embed.add_field(name="ID", value=f"`{hero_id}`", inline=False)

        if stats is not None:
            chunk = json.dumps(stats, indent=2, default=str)
            if len(chunk) > MAX_JSON_CHARS:
                chunk = chunk[: MAX_JSON_CHARS - 20] + "\n… (truncated)"
            embed.add_field(name="Hero statistics (JSON)", value=f"```json\n{chunk}\n```", inline=False)
        else:
            chunk = json.dumps(match, indent=2, default=str)
            if len(chunk) > MAX_JSON_CHARS:
                chunk = chunk[: MAX_JSON_CHARS - 20] + "\n… (truncated)"
            embed.add_field(name="Hero data (JSON)", value=f"```json\n{chunk}\n```", inline=False)

        await interaction.followup.send(embed=embed)
