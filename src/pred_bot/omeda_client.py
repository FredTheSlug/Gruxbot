"""Async client for Omeda.city public JSON endpoints."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)


class OmedaAuthRequired(Exception):
    """Raised when Omeda returns 403 (likely requires authentication)."""


class OmedaClient:
    def __init__(
        self,
        base_url: str,
        *,
        user_agent: str = "GruxBotPredBot/1.0",
        max_concurrency: int = 5,
        max_retries: int = 3,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"User-Agent": user_agent, "Accept": "application/json"}
        self._max_retries = max(1, max_retries)
        self._sem = asyncio.Semaphore(max(1, max_concurrency))

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
        last_exc: BaseException | None = None
        async with self._sem:
            for attempt in range(self._max_retries):
                try:
                    resp = await client.get(url, headers=self._headers, params=params)
                    if resp.status_code == 403:
                        raise OmedaAuthRequired(f"Omeda endpoint requires auth: {url}")
                    if resp.status_code >= 500:
                        log.warning("Omeda server error %s %s (attempt %s)", resp.status_code, url, attempt + 1)
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                    resp.raise_for_status()
                    return resp.json()
                except (httpx.TimeoutException, httpx.TransportError) as e:
                    last_exc = e
                    log.warning("Omeda request failed %s: %s (attempt %s)", url, e, attempt + 1)
                    await asyncio.sleep(0.5 * (2**attempt))
                except OmedaAuthRequired:
                    raise
                except httpx.HTTPStatusError as e:
                    if e.response is not None and e.response.status_code >= 500:
                        last_exc = e
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                    raise
        if last_exc:
            raise last_exc
        raise RuntimeError(f"Omeda request exhausted retries: {url}")

    async def search_players(
        self,
        client: httpx.AsyncClient,
        *,
        name: str,
        page: int = 0,
        include_inactive: int = 0,
        include_unranked: int = 0,
    ) -> Any:
        return await self._get_json(
            client,
            "/players.json",
            params={
                "page": page,
                "filter[name]": name,
                "filter[include_inactive]": include_inactive,
                "filter[include_unranked]": include_unranked,
            },
        )

    async def get_player(self, client: httpx.AsyncClient, player_id: str) -> Any:
        return await self._get_json(client, f"/players/{player_id}.json")

    async def get_player_matches(
        self,
        client: httpx.AsyncClient,
        player_id: str,
        *,
        page: int = 0,
        per_page: int = 25,
        time_frame: str | None = None,
        hero_id: str | None = None,
        role: str | None = None,
        player_name: str | None = None,
        game_mode: str | None = None,
    ) -> Any:
        params: dict[str, Any] = {"page": page, "per_page": min(per_page, 100)}
        if time_frame:
            params["time_frame"] = time_frame
        if hero_id:
            params["filter[hero_id]"] = hero_id
        if role:
            params["filter[role]"] = role
        if player_name:
            params["filter[player_name]"] = player_name
        if game_mode:
            params["filter[game_mode]"] = game_mode
        return await self._get_json(client, f"/players/{player_id}/matches.json", params=params)

    async def get_heroes(self, client: httpx.AsyncClient) -> Any:
        return await self._get_json(client, "/heroes.json")

    async def get_hero_statistics(
        self,
        client: httpx.AsyncClient,
        *,
        hero_ids: list[str] | None = None,
        time_frame: str | None = None,
    ) -> Any:
        params: dict[str, Any] = {}
        if time_frame:
            params["time_frame"] = time_frame
        if hero_ids and len(hero_ids) == 1:
            params["filter[hero_id]"] = hero_ids[0]
        return await self._get_json(client, "/dashboard/hero_statistics.json", params=params or None)

    async def get_items(self, client: httpx.AsyncClient) -> Any:
        return await self._get_json(client, "/items.json")

    async def get_match(self, client: httpx.AsyncClient, match_id: str) -> Any:
        return await self._get_json(client, f"/matches/{match_id}.json")

    async def get_matches_feed(
        self,
        client: httpx.AsyncClient,
        *,
        cursor: str | None = None,
        per_page: int = 25,
        timestamp: int | None = None,
    ) -> Any:
        params: dict[str, Any] = {"per_page": min(per_page, 100)}
        if cursor:
            params["cursor"] = cursor
        if timestamp is not None:
            params["timestamp"] = timestamp
        return await self._get_json(client, "/matches.json", params=params)
