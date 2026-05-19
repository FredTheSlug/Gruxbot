"""`/build` slash command — popular core items and crests from pred.gg."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from pred_bot.hero_build import (
    BuildRecommendation,
    format_item_line,
    parse_core_build_response,
    role_display_name,
    role_to_graphql_enum,
)
from pred_bot.hero_portraits import portrait_url
from pred_bot.jsonutil import find_in_list_by_name, first_list_of_dicts, pick_str
from pred_bot.stats_client import StatsAuthRequired

if TYPE_CHECKING:
    from pred_bot.bot import PredBot
    from pred_bot.stats_client import StatsClient

log = logging.getLogger(__name__)

ROLE_CHOICES = [
    app_commands.Choice(name="Carry", value="carry"),
    app_commands.Choice(name="Offlane", value="offlane"),
    app_commands.Choice(name="Midlane", value="midlane"),
    app_commands.Choice(name="Jungle", value="jungle"),
    app_commands.Choice(name="Support", value="support"),
]


def build_recommendation_embed(
    rec: BuildRecommendation,
    *,
    stats: StatsClient,
    build_url: str,
) -> discord.Embed:
    role_label = role_display_name(rec.role)
    embed = discord.Embed(
        title=f"{rec.hero_name} — {role_label}",
        description=f"[View on pred.gg]({build_url})",
    )
    embed.set_footer(text="Ranked · Paragon · current patch")

    thumb = portrait_url(rec.hero_icon, base=stats.web_base_url)
    if thumb:
        embed.set_thumbnail(url=thumb)

    if rec.sample_size is not None:
        embed.add_field(name="Sample", value=f"{rec.sample_size} matches (top build)", inline=False)

    for index, item in enumerate(rec.core_items[:3], start=1):
        embed.add_field(name=f"Core {index}", value=format_item_line(item), inline=False)

    if not rec.core_items:
        embed.add_field(name="Core items", value="No data", inline=False)

    for index, crest in enumerate(rec.crests[:3], start=1):
        embed.add_field(name=f"Crest {index}", value=format_item_line(crest), inline=True)

    if not rec.crests:
        embed.add_field(name="Crests", value="No data", inline=False)

    return embed


def register(bot: PredBot) -> None:
    @bot.tree.command(
        name="build",
        description="Top core items and crests for a hero and role (Ranked · Paragon)",
    )
    @app_commands.describe(
        hero="Hero name (partial match ok)",
        role="Lane / role",
    )
    @app_commands.choices(role=ROLE_CHOICES)
    async def build_cmd(
        interaction: discord.Interaction,
        hero: str,
        role: app_commands.Choice[str],
    ) -> None:
        await interaction.response.defer(thinking=True)
        client = bot.http_client
        role_value = role_to_graphql_enum(role.value)

        try:
            heroes_payload = await bot.stats.get_heroes(client)
        except StatsAuthRequired:
            await interaction.followup.send(
                "Hero list requires pred.gg authentication. Check OAuth tokens and `.env`.",
                ephemeral=True,
            )
            return
        except Exception as e:
            log.exception("build: hero list failed")
            await interaction.followup.send(f"Request failed: `{e}`", ephemeral=True)
            return

        heroes = first_list_of_dicts(heroes_payload)
        if not heroes and isinstance(heroes_payload, dict):
            heroes = first_list_of_dicts(heroes_payload.get("heroes") or heroes_payload.get("data"))

        match = find_in_list_by_name(heroes, hero)
        if not match:
            await interaction.followup.send(f"No hero matched `{hero}`.", ephemeral=True)
            return

        hero_name = pick_str(match, "name", "title", "display_name", "slug") or hero
        hero_slug = pick_str(match, "slug")
        if not hero_slug:
            await interaction.followup.send("Could not resolve hero slug.", ephemeral=True)
            return

        try:
            raw = await bot.stats.get_hero_core_build(
                client,
                hero_slug=hero_slug,
                role=role_value,
            )
        except StatsAuthRequired as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        except Exception as e:
            log.exception("build: coreBuild failed hero=%s role=%s", hero_slug, role_value)
            await interaction.followup.send(f"Request failed: `{e}`", ephemeral=True)
            return

        rec = parse_core_build_response(raw, hero_slug=hero_slug, role=role_value, hero_name=hero_name)
        if rec is None or (not rec.core_items and not rec.crests):
            await interaction.followup.send(
                f"No build data for **{hero_name}** as **{role_display_name(role_value)}** "
                f"(Ranked · Paragon · current patch).",
                ephemeral=True,
            )
            return

        paragon_ids = raw.get("paragon_rank_ids")
        if not isinstance(paragon_ids, list):
            paragon_ids = None
        build_url = bot.stats.hero_build_url(
            hero_slug,
            role_value,
            paragon_rank_ids=paragon_ids,
        )
        embed = build_recommendation_embed(rec, stats=bot.stats, build_url=build_url)
        await interaction.followup.send(embed=embed)
