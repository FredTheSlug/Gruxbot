"""`/player` slash command."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from pred_bot.jsonutil import (
    extract_player_id_from_search,
    extract_player_rows_from_search,
    get_match_ids_newest_first,
    looks_like_player_id,
    pick_str,
)
from pred_bot.stats_client import StatsAuthRequired

if TYPE_CHECKING:
    from pred_bot.bot import PredBot

log = logging.getLogger(__name__)


def register(bot: PredBot) -> None:
    @bot.tree.command(name="player", description="Look up a Predecessor player (Omeda.city)")
    @app_commands.describe(
        query="Player name or player UUID",
        recent="How many recent matches to list (1–25)",
    )
    async def player_cmd(
        interaction: discord.Interaction,
        query: str,
        recent: app_commands.Range[int, 1, 25] = 5,
    ) -> None:
        await interaction.response.defer(thinking=True)
        client = bot.http_client
        try:
            player_id: str | None = None
            if looks_like_player_id(query):
                player_id = query.strip()
            else:
                search = await bot.stats.search_players(client, name=query.strip(), page=0)
                player_id = extract_player_id_from_search(search)
                if not player_id:
                    rows = extract_player_rows_from_search(search)
                    hint = ""
                    if len(rows) > 1:
                        names = [pick_str(r, "name", "username", "display_name") for r in rows[:5]]
                        hint = " Close matches: " + ", ".join(n for n in names if n) + "."
                    await interaction.followup.send(
                        f"No player found for `{query}`. Try a different spelling or paste the UUID from Omeda.city.{hint}",
                        ephemeral=True,
                    )
                    return

            profile = await bot.stats.get_player(client, player_id)
            matches_payload = await bot.stats.get_player_matches(
                client,
                player_id,
                page=0,
                per_page=recent,
            )
        except StatsAuthRequired:
            await interaction.followup.send(
                "That stats endpoint requires authentication. Set `PRED_GQL_AUTHORIZATION` or enable "
                "`STATS_USE_OMEDA_FALLBACK=true` (default).",
                ephemeral=True,
            )
            return
        except Exception as e:
            log.exception("player command failed")
            await interaction.followup.send(f"Request failed: `{e}`", ephemeral=True)
            return

        if isinstance(profile, dict):
            name = pick_str(profile, "name", "username", "display_name") or player_id
            rank = pick_str(profile, "rank", "rank_name", "tier")
            mmr = pick_str(profile, "mmr", "elo")
        else:
            name = player_id
            rank = None
            mmr = None

        desc_parts = [f"**ID:** `{player_id}`", f"[Profile on Pred.gg]({bot.stats.player_url(player_id)})"]
        if rank:
            desc_parts.append(f"**Rank:** {rank}")
        if mmr:
            desc_parts.append(f"**MMR:** {mmr}")

        embed = discord.Embed(title=name, description="\n".join(desc_parts))

        mids = get_match_ids_newest_first(matches_payload)[: int(recent)]
        if mids:
            lines = [f"[{m}]({bot.stats.match_url(m)})" for m in mids]
            field_val = "\n".join(lines)
            if len(field_val) > 1000:
                field_val = field_val[:997] + "..."
            embed.add_field(name="Recent matches", value=field_val, inline=False)
        else:
            embed.add_field(name="Recent matches", value="No matches returned.", inline=False)

        await interaction.followup.send(embed=embed)
