"""Shared logic for detecting and posting /follow match notifications."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import discord
import httpx

from pred_bot.follow_store import FollowRow
from pred_bot.jsonutil import find_new_matches_since, pick_str
from pred_bot.match_detail import MatchDetail
from pred_bot.match_message import build_match_message
from pred_bot.stats_client import StatsAuthRequired

if TYPE_CHECKING:
    from pred_bot.bot import PredBot

log = logging.getLogger(__name__)

MAX_NOTIFY_PER_TICK = 5

FollowStatus = Literal[
    "no_matches",
    "unchanged",
    "notified",
    "no_channel",
    "send_forbidden",
    "send_error",
    "api_auth",
    "api_error",
]


@dataclass(frozen=True)
class FollowNotifyResult:
    status: FollowStatus
    player_id: str
    newest_match_id: str | None = None
    last_seen_match_id: str | None = None
    new_match_count: int = 0
    detail: str = ""


async def resolve_follow_channel(bot: PredBot, row: FollowRow) -> discord.abc.Messageable | None:
    """Always fetch channel from Discord API (cache is unreliable for guild channels)."""
    try:
        ch = await bot.fetch_channel(row.channel_id)
    except discord.NotFound:
        log.warning("Follow channel %s not found (deleted?)", row.channel_id)
        return None
    except discord.Forbidden:
        log.warning(
            "Bot cannot access channel %s — re-invite with View Channel + Send Messages",
            row.channel_id,
        )
        return None
    except discord.HTTPException as e:
        log.warning("Discord error fetching channel %s: %s", row.channel_id, e)
        return None
    if isinstance(ch, discord.abc.Messageable):
        return ch
    log.warning(
        "Channel %s is type %s (not messageable — use a text channel)",
        row.channel_id,
        type(ch).__name__,
    )
    return None


async def process_follow_row(
    bot: PredBot,
    client: httpx.AsyncClient,
    row: FollowRow,
) -> FollowNotifyResult:
    """Poll stats API for new matches and post to Discord when the newest id changed."""
    try:
        payload = await bot.stats.get_player_matches(
            client,
            row.player_id,
            page=0,
            per_page=100,
        )
    except StatsAuthRequired:
        return FollowNotifyResult(
            status="api_auth",
            player_id=row.player_id,
            detail="pred.gg GraphQL requires auth (set PRED_GQL_AUTHORIZATION or enable omeda fallback)",
        )
    except Exception as e:
        log.exception("Follow API failed player=%s", row.player_id)
        return FollowNotifyResult(
            status="api_error",
            player_id=row.player_id,
            detail=str(e),
        )

    scan = find_new_matches_since(payload, row.last_seen_match_id)

    if scan.status == "no_matches":
        return FollowNotifyResult(
            status="no_matches",
            player_id=row.player_id,
            last_seen_match_id=row.last_seen_match_id,
        )

    if scan.status == "init":
        if scan.newest_match_id:
            await bot.follow_store.update_last_seen(
                guild_id=row.guild_id,
                user_id=row.user_id,
                player_id=row.player_id,
                last_seen_match_id=scan.newest_match_id,
            )
        return FollowNotifyResult(
            status="unchanged",
            player_id=row.player_id,
            newest_match_id=scan.newest_match_id,
            detail="initialized baseline (no notification)",
        )

    if scan.status == "rebaseline":
        if scan.newest_match_id:
            log.info(
                "Follow rebaseline player=%s (last_seen %s not in current API page); no repost",
                row.player_id[:8],
                (row.last_seen_match_id or "")[:8],
            )
            await bot.follow_store.update_last_seen(
                guild_id=row.guild_id,
                user_id=row.user_id,
                player_id=row.player_id,
                last_seen_match_id=scan.newest_match_id,
            )
        return FollowNotifyResult(
            status="unchanged",
            player_id=row.player_id,
            newest_match_id=scan.newest_match_id,
            detail="rebaselined after API/history change (no notification)",
        )

    if scan.status == "unchanged":
        return FollowNotifyResult(
            status="unchanged",
            player_id=row.player_id,
            newest_match_id=scan.newest_match_id,
            last_seen_match_id=row.last_seen_match_id,
        )

    to_post = list(scan.new_match_ids)[:MAX_NOTIFY_PER_TICK]
    ch = await resolve_follow_channel(bot, row)
    if ch is None:
        return FollowNotifyResult(
            status="no_channel",
            player_id=row.player_id,
            newest_match_id=scan.newest_match_id,
            new_match_count=len(to_post),
            detail=f"channel_id={row.channel_id}",
        )

    player_label = row.player_id
    try:
        profile = await bot.stats.get_player(client, row.player_id)
        if isinstance(profile, dict):
            player_label = pick_str(profile, "display_name", "name", "username") or player_label
    except Exception:
        pass

    log.info(
        "Follow notify: %s new match(es) for %s -> channel %s",
        len(to_post),
        player_label,
        row.channel_id,
    )

    last_posted: str | None = None
    for mid in to_post:
        try:
            detail = await bot.stats.get_match(client, mid)
        except Exception:
            detail = None
        title = f"New match — {player_label}"
        if isinstance(detail, MatchDetail):
            embeds, view, scoreboard_file = await build_match_message(
                client,
                detail,
                bot.stats,
                highlight_player_id=row.player_id,
                title_prefix=title,
                scoreboard_image=bot.config.scoreboard_image_enabled,
            )
        else:
            scoreboard_file = None
            url = bot.stats.match_url(mid)
            embeds = [
                discord.Embed(
                    title=title,
                    description=f"[View on Pred.gg]({url})\n`{mid}`",
                    url=url,
                )
            ]
            view = None
        try:
            await ch.send(embeds=embeds, view=view, file=scoreboard_file)
        except discord.Forbidden:
            return FollowNotifyResult(
                status="send_forbidden",
                player_id=row.player_id,
                newest_match_id=scan.newest_match_id,
                new_match_count=len(to_post),
                detail=f"channel_id={row.channel_id}",
            )
        except discord.HTTPException as e:
            return FollowNotifyResult(
                status="send_error",
                player_id=row.player_id,
                newest_match_id=scan.newest_match_id,
                new_match_count=len(to_post),
                detail=str(e),
            )
        last_posted = mid

    if last_posted:
        await bot.follow_store.update_last_seen(
            guild_id=row.guild_id,
            user_id=row.user_id,
            player_id=row.player_id,
            last_seen_match_id=last_posted,
        )
    return FollowNotifyResult(
        status="notified",
        player_id=row.player_id,
        newest_match_id=scan.newest_match_id,
        last_seen_match_id=row.last_seen_match_id,
        new_match_count=len(to_post),
    )
