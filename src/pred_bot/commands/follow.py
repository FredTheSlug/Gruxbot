"""`/follow`, `/unfollow`, `/following` slash commands."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from pred_bot.follow_notify import process_follow_row
from pred_bot.jsonutil import get_match_ids_newest_first, looks_like_player_id
from pred_bot.stats_client import StatsAuthRequired

if TYPE_CHECKING:
    from pred_bot.bot import PredBot

log = logging.getLogger(__name__)


def register(bot: PredBot) -> None:
    @bot.tree.command(name="follow", description="Get notified in this channel when a player finishes a match")
    @app_commands.describe(player_id="Omeda / Predecessor player UUID")
    async def follow_cmd(interaction: discord.Interaction, player_id: str) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        pid = player_id.strip()
        if not looks_like_player_id(pid):
            await interaction.followup.send("Please provide a valid player UUID (from the player profile URL on Omeda.city).", ephemeral=True)
            return
        if interaction.guild is None:
            await interaction.followup.send("Follow only works in a server channel.", ephemeral=True)
            return
        client = bot.http_client
        try:
            await bot.stats.get_player(client, pid)
            matches_payload = await bot.stats.get_player_matches(client, pid, page=0, per_page=1)
        except StatsAuthRequired:
            await interaction.followup.send(
                "Could not load match history (pred.gg auth required and omeda fallback disabled).",
                ephemeral=True,
            )
            return
        except Exception as e:
            log.exception("follow verify failed")
            await interaction.followup.send(f"Could not verify player: `{e}`", ephemeral=True)
            return

        ids = get_match_ids_newest_first(matches_payload)
        last_seen = ids[0] if ids else None
        channel_id = interaction.channel_id
        if channel_id is None:
            await interaction.followup.send("Could not determine channel.", ephemeral=True)
            return
        await bot.follow_store.add_follow(
            guild_id=interaction.guild.id,
            channel_id=channel_id,
            user_id=interaction.user.id,
            player_id=pid,
            last_seen_match_id=last_seen,
        )
        baseline = f"`{last_seen[:8]}…`" if last_seen else "none"
        await interaction.followup.send(
            f"Watching player `{pid}` in <#{interaction.channel_id}>.\n"
            f"Baseline match (won't notify for this one): {baseline}\n"
            f"Poll interval: {bot.config.follow_poll_seconds}s. "
            f"Use `/followcheck` to force-check now.",
            ephemeral=True,
        )

    @bot.tree.command(name="unfollow", description="Stop following a player")
    @app_commands.describe(player_id="Omeda / Predecessor player UUID")
    async def unfollow_cmd(interaction: discord.Interaction, player_id: str) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        if interaction.guild is None:
            await interaction.followup.send("This command only works in a server.", ephemeral=True)
            return
        n = await bot.follow_store.remove_follow(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            player_id=player_id.strip(),
        )
        if n:
            await interaction.followup.send(f"Removed follow for `{player_id.strip()}`.", ephemeral=True)
        else:
            await interaction.followup.send("No follow found for that player.", ephemeral=True)

    @bot.tree.command(name="following", description="List players you are following in this server")
    async def following_cmd(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        if interaction.guild is None:
            await interaction.followup.send("This command only works in a server.", ephemeral=True)
            return
        rows = await bot.follow_store.list_for_user(guild_id=interaction.guild.id, user_id=interaction.user.id)
        if not rows:
            await interaction.followup.send("You are not following anyone here.", ephemeral=True)
            return
        lines = [
            f"<#{r.channel_id}> — `{r.player_id}` (last seen `{ (r.last_seen_match_id or 'none')[:8]}…`)"
            for r in rows
        ]
        await interaction.followup.send("**Following:**\n" + "\n".join(lines), ephemeral=True)

    @bot.tree.command(
        name="followcheck",
        description="Check followed players now and post any missed match notifications",
    )
    @app_commands.describe(
        player_id="Optional: only check this player UUID (must already be followed)",
    )
    async def followcheck_cmd(
        interaction: discord.Interaction,
        player_id: str | None = None,
    ) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        if interaction.guild is None:
            await interaction.followup.send("This command only works in a server.", ephemeral=True)
            return
        rows = await bot.follow_store.list_for_user(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
        )
        if player_id:
            pid = player_id.strip()
            rows = [r for r in rows if r.player_id == pid]
            if not rows:
                await interaction.followup.send(
                    f"You are not following `{pid}` in this server.",
                    ephemeral=True,
                )
                return
        if not rows:
            await interaction.followup.send("You have no follows here. Use `/follow` first.", ephemeral=True)
            return

        client = bot.http_client
        lines: list[str] = []
        for row in rows:
            result = await process_follow_row(bot, client, row)
            if result.status == "notified":
                lines.append(
                    f"**Posted** {result.new_match_count} match(es) for `{result.player_id[:8]}…` "
                    f"in <#{row.channel_id}>."
                )
            elif result.status == "unchanged":
                lines.append(
                    f"No new matches for `{result.player_id[:8]}…` "
                    f"(newest `{ (result.newest_match_id or '')[:8]}…`)."
                )
            elif result.status == "no_channel":
                lines.append(
                    f"**Cannot reach channel** <#{row.channel_id}> for `{result.player_id[:8]}…` — "
                    f"check bot permissions or use a text channel."
                )
            elif result.status == "send_forbidden":
                lines.append(
                    f"**Cannot send** in <#{row.channel_id}> — grant Send Messages + Embed Links."
                )
            else:
                lines.append(f"`{result.player_id[:8]}…`: {result.status} — {result.detail}")

        await interaction.followup.send("\n".join(lines), ephemeral=True)
