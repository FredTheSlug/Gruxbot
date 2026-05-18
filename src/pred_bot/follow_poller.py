"""Background polling for /follow notifications."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from pred_bot.follow_notify import process_follow_row, resolve_follow_channel

if TYPE_CHECKING:
    from pred_bot.bot import PredBot

log = logging.getLogger(__name__)


class FollowPoller:
    def __init__(self, bot: PredBot) -> None:
        self._bot = bot
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run(), name="follow-poller")

    async def validate_channels_on_startup(self) -> None:
        rows = await self._bot.follow_store.all_follows()
        if not rows:
            log.info("No /follow subscriptions loaded")
            return
        log.info("Checking %s /follow channel(s)…", len(rows))
        ok = 0
        for row in rows:
            ch = await resolve_follow_channel(self._bot, row)
            if ch is not None:
                name = getattr(ch, "name", str(row.channel_id))
                log.info(
                    "Follow OK: #%s (%s) player=%s last_seen=%s",
                    name,
                    row.channel_id,
                    row.player_id[:8],
                    (row.last_seen_match_id or "none")[:8],
                )
                ok += 1
            else:
                log.warning(
                    "Follow FAIL: cannot post to channel %s for player %s",
                    row.channel_id,
                    row.player_id,
                )
        log.info("Follow channel check: %s/%s reachable", ok, len(rows))

    async def _run(self) -> None:
        await self._bot.wait_until_ready()
        await self.validate_channels_on_startup()
        while not self._bot.is_closed():
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Follow poller tick failed")
            await asyncio.sleep(self._bot.config.follow_poll_seconds)

    async def _tick(self) -> None:
        client = self._bot.http_client
        rows = await self._bot.follow_store.all_follows()
        for row in rows:
            try:
                result = await process_follow_row(self._bot, client, row)
                if result.status == "unchanged" and self._bot.config.follow_poll_debug:
                    log.debug(
                        "Follow unchanged player=%s newest=%s",
                        result.player_id[:8],
                        (result.newest_match_id or "")[:8],
                    )
                elif result.status not in ("unchanged", "notified"):
                    log.warning(
                        "Follow %s player=%s: %s",
                        result.status,
                        result.player_id[:8],
                        result.detail,
                    )
            except Exception:
                log.exception("Follow processing failed player=%s", row.player_id)
