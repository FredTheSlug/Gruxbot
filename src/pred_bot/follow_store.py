"""SQLite persistence for /follow subscriptions."""

from __future__ import annotations

import time
from dataclasses import dataclass

import aiosqlite


@dataclass(frozen=True)
class FollowRow:
    guild_id: int
    channel_id: int
    user_id: int
    player_id: str
    last_seen_match_id: str | None
    created_at: int


class FollowStore:
    def __init__(self, database_path: str) -> None:
        self._path = database_path

    async def init(self) -> None:
        import os

        parent = os.path.dirname(self._path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS follows (
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    player_id TEXT NOT NULL,
                    last_seen_match_id TEXT,
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, user_id, player_id)
                )
                """
            )
            await db.commit()

    async def add_follow(
        self,
        *,
        guild_id: int,
        channel_id: int,
        user_id: int,
        player_id: str,
        last_seen_match_id: str | None,
    ) -> None:
        now = int(time.time())
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                """
                INSERT INTO follows (guild_id, channel_id, user_id, player_id, last_seen_match_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id, player_id) DO UPDATE SET
                    channel_id = excluded.channel_id,
                    last_seen_match_id = excluded.last_seen_match_id
                """,
                (guild_id, channel_id, user_id, player_id, last_seen_match_id, now),
            )
            await db.commit()

    async def remove_follow(self, *, guild_id: int, user_id: int, player_id: str) -> int:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "DELETE FROM follows WHERE guild_id = ? AND user_id = ? AND player_id = ?",
                (guild_id, user_id, player_id),
            )
            await db.commit()
            return cur.rowcount or 0

    async def list_for_user(self, *, guild_id: int, user_id: int) -> list[FollowRow]:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT guild_id, channel_id, user_id, player_id, last_seen_match_id, created_at
                FROM follows
                WHERE guild_id = ? AND user_id = ?
                ORDER BY player_id
                """,
                (guild_id, user_id),
            )
            rows = await cur.fetchall()
        return [
            FollowRow(
                guild_id=int(r["guild_id"]),
                channel_id=int(r["channel_id"]),
                user_id=int(r["user_id"]),
                player_id=str(r["player_id"]),
                last_seen_match_id=r["last_seen_match_id"],
                created_at=int(r["created_at"]),
            )
            for r in rows
        ]

    async def all_follows(self) -> list[FollowRow]:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT guild_id, channel_id, user_id, player_id, last_seen_match_id, created_at
                FROM follows
                """
            )
            rows = await cur.fetchall()
        return [
            FollowRow(
                guild_id=int(r["guild_id"]),
                channel_id=int(r["channel_id"]),
                user_id=int(r["user_id"]),
                player_id=str(r["player_id"]),
                last_seen_match_id=r["last_seen_match_id"],
                created_at=int(r["created_at"]),
            )
            for r in rows
        ]

    async def update_last_seen(self, *, guild_id: int, user_id: int, player_id: str, last_seen_match_id: str) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                """
                UPDATE follows SET last_seen_match_id = ?
                WHERE guild_id = ? AND user_id = ? AND player_id = ?
                """,
                (last_seen_match_id, guild_id, user_id, player_id),
            )
            await db.commit()
