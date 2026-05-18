"""Build Discord embeds for match notifications (pred.gg-style)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from pred_bot.hero_portraits import portrait_url
from pred_bot.jsonutil import normalize_match_id
from pred_bot.match_detail import MatchDetail, MatchPlayerLine, format_duration, format_match_timestamp

if TYPE_CHECKING:
    from pred_bot.stats_client import StatsClient

EMBED_COLOR = 0x8B9A4B
ROLE_EMOJI = {
    "carry": "🏹",
    "support": "💚",
    "jungle": "🌿",
    "midlane": "⚡",
    "offlane": "🛡️",
}
MAX_PLAYER_EMBEDS = 6


def match_scoreboard_url(stats: StatsClient, match_id: str) -> str:
    base = stats.web_base_url.rstrip("/")
    mid = match_id.replace("-", "")
    return f"{base}/matches/{mid}/statistics"


def _format_vp_change(vp: int | None) -> str:
    if vp is None:
        return "—"
    return f"+{vp}" if vp > 0 else str(vp)


def _format_ps(score: float | None) -> str:
    if score is None:
        return "—"
    return f"{score:.2f} PS"


def _team_players(players: list[MatchPlayerLine], team: str) -> list[MatchPlayerLine]:
    key = team.strip().lower()
    rows = [p for p in players if p.team == key]
    rows.sort(key=lambda p: (p.performance_score or 0), reverse=True)
    return rows


def _player_portrait_url(p: MatchPlayerLine, stats: StatsClient) -> str | None:
    return portrait_url(p.hero_icon, base=stats.web_base_url)


def _player_stat_embed(
    p: MatchPlayerLine,
    stats: StatsClient,
    *,
    title: str | None = None,
    highlight: bool = False,
) -> discord.Embed:
    embed = discord.Embed(color=EMBED_COLOR)
    if title:
        embed.title = title

    name = p.name if p.name else "Unknown"
    if highlight:
        name = f"**{name}**"
    role_icon = ROLE_EMOJI.get(p.role, "▫️")
    vp = _format_vp_change(p.vp_change)
    author = f"{vp} {role_icon} {name}"
    if len(author) > 256:
        author = author[:253] + "..."

    icon_url = _player_portrait_url(p, stats)
    if icon_url:
        embed.set_author(name=author, icon_url=icon_url)
    else:
        embed.set_author(name=author)

    kda = f"{p.kills}/{p.deaths}/{p.assists}"
    ps = _format_ps(p.performance_score)
    desc = f"{kda} · {ps}"
    if p.hero_name:
        desc = f"{p.hero_name} — {desc}"
    embed.description = desc
    return embed


def build_match_embed(
    detail: MatchDetail,
    stats: StatsClient,
    *,
    highlight_player_id: str | None = None,
    title_prefix: str = "",
    compact: bool = False,
) -> tuple[list[discord.Embed], discord.ui.View]:
    """Return summary embed; per-player rows unless compact (scoreboard image used)."""
    match_url = stats.match_url(detail.match_id)
    scoreboard_url = match_scoreboard_url(stats, detail.match_id)

    dawn_kills = detail.team_kills.get("dawn", 0)
    dusk_kills = detail.team_kills.get("dusk", 0)
    dawn_name = detail.team_display_name("dawn")
    dusk_name = detail.team_display_name("dusk")

    embed = discord.Embed(color=EMBED_COLOR, url=match_url)
    embed.description = f"[Click here to view more]({match_url})"

    embed.add_field(
        name="\u200b",
        value=(
            f"**{dusk_name} ({dusk_kills})** vs **{dawn_name} ({dawn_kills})**\n"
            f"{format_duration(detail.duration_seconds)}"
        ),
        inline=True,
    )
    embed.add_field(
        name="\u200b",
        value=f"{detail.region}\n{detail.game_mode}",
        inline=True,
    )

    win_key = detail.winning_team_key()
    win_label = detail.team_display_name(win_key)
    highlight_norm = normalize_match_id(highlight_player_id)

    footer_time = format_match_timestamp(detail.end_time, detail.start_time)
    footer = detail.match_id
    if footer_time:
        footer = f"{detail.match_id} · {footer_time}"
    embed.set_footer(text=footer)

    if title_prefix:
        embed.title = title_prefix

    if highlight_norm:
        for p in detail.players:
            if normalize_match_id(p.player_id) == highlight_norm:
                thumb = _player_portrait_url(p, stats)
                if thumb:
                    embed.set_thumbnail(url=thumb)
                break

    embeds: list[discord.Embed] = [embed]

    if compact:
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Open", style=discord.ButtonStyle.link, url=match_url))
        view.add_item(
            discord.ui.Button(
                label="View Scoreboard", style=discord.ButtonStyle.link, url=scoreboard_url
            )
        )
        return embeds, view

    win_players = _team_players(detail.players, win_key)
    for index, p in enumerate(win_players[:MAX_PLAYER_EMBEDS]):
        hi = highlight_norm is not None and normalize_match_id(p.player_id) == highlight_norm
        section_title = f"{win_label} — Victory" if index == 0 else None
        embeds.append(
            _player_stat_embed(p, stats, title=section_title, highlight=hi)
        )

    if highlight_norm:
        on_winning = any(normalize_match_id(p.player_id) == highlight_norm for p in win_players)
        if not on_winning:
            for p in detail.players:
                if normalize_match_id(p.player_id) == highlight_norm:
                    lose_label = detail.team_display_name(p.team)
                    embeds.append(
                        _player_stat_embed(
                            p,
                            stats,
                            title=f"{lose_label} — followed player",
                            highlight=True,
                        )
                    )
                    break

    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Open", style=discord.ButtonStyle.link, url=match_url))
    view.add_item(
        discord.ui.Button(label="View Scoreboard", style=discord.ButtonStyle.link, url=scoreboard_url)
    )
    return embeds, view
