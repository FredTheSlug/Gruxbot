"""`/item` slash command."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from pred_bot.jsonutil import find_in_list_by_name, first_list_of_dicts, pick_str
from pred_bot.stats_client import StatsAuthRequired

if TYPE_CHECKING:
    from pred_bot.bot import PredBot

log = logging.getLogger(__name__)

MAX_JSON_CHARS = 950


def register(bot: PredBot) -> None:
    @bot.tree.command(name="item", description="Look up item info from Omeda.city")
    @app_commands.describe(item_query="Item name (partial match ok)")
    async def item_cmd(interaction: discord.Interaction, item_query: str) -> None:
        await interaction.response.defer(thinking=True)
        client = bot.http_client
        try:
            items_payload = await bot.stats.get_items(client)
        except StatsAuthRequired:
            await interaction.followup.send(
                "That stats endpoint requires authentication.",
                ephemeral=True,
            )
            return
        except Exception as e:
            log.exception("item list failed")
            await interaction.followup.send(f"Request failed: `{e}`", ephemeral=True)
            return

        items = first_list_of_dicts(items_payload)
        if not items and isinstance(items_payload, dict):
            items = first_list_of_dicts(items_payload.get("items") or items_payload.get("data"))

        match = find_in_list_by_name(items, item_query)
        if not match:
            await interaction.followup.send(f"No item matched `{item_query}`.", ephemeral=True)
            return

        name = pick_str(match, "name", "title", "display_name", "slug") or item_query
        embed = discord.Embed(
            title=name,
            description=f"[Items on Pred.gg]({bot.stats.items_url()})",
        )
        iid = pick_str(match, "id", "item_id")
        if iid:
            embed.add_field(name="ID", value=f"`{iid}`", inline=False)

        chunk = json.dumps(match, indent=2, default=str)
        if len(chunk) > MAX_JSON_CHARS:
            chunk = chunk[: MAX_JSON_CHARS - 20] + "\n… (truncated)"
        embed.add_field(name="Item data (JSON)", value=f"```json\n{chunk}\n```", inline=False)

        await interaction.followup.send(embed=embed)
