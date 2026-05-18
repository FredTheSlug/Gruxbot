"""Unified Predecessor stats API: pred.gg GraphQL with optional omeda.city REST fallback."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from pred_bot.jsonutil import normalize_match_id
from pred_bot.match_detail import MatchDetail, MatchPlayerLine, parse_match_payload
from pred_bot.omeda_client import OmedaAuthRequired, OmedaClient
from pred_bot.player_rank import (
    apply_rank_info,
    pick_rank_from_player_ratings,
    rank_info_from_omeda_profile,
)
from pred_bot.pred_client import PredAuthRequired, PredGqlClient

log = logging.getLogger(__name__)

# Backwards-compatible alias for command handlers
StatsAuthRequired = PredAuthRequired


class StatsClient:
    """Facade used by the Discord bot."""

    def __init__(
        self,
        *,
        pred: PredGqlClient,
        omeda: OmedaClient | None,
        use_omeda_fallback: bool = True,
        web_base_url: str = "https://pred.gg",
        omeda_base_url: str = "https://omeda.city",
    ) -> None:
        self._pred = pred
        self._omeda = omeda
        self._use_omeda_fallback = use_omeda_fallback and omeda is not None
        self.web_base_url = web_base_url.rstrip("/")
        self.omeda_base_url = (
            omeda._base_url.rstrip("/") if omeda is not None else omeda_base_url.rstrip("/")
        )
        self._hero_icons_by_id: dict[str, str] = {}
        self._hero_icons_by_slug: dict[str, str] = {}
        self._hero_icons_loaded = False
        self._ranks_by_id: dict[str, dict[str, str]] = {}
        self._ranks_loaded = False
        self._season_rating_id: str | None = None
        self._player_rank_cache: dict[str, dict[str, str]] = {}

    def player_url(self, player_id: str) -> str:
        return f"{self.web_base_url}/players/{player_id}"

    def match_url(self, match_id: str) -> str:
        return f"{self.web_base_url}/matches/{match_id}"

    def heroes_url(self) -> str:
        return f"{self.web_base_url}/heroes"

    def items_url(self) -> str:
        return f"{self.web_base_url}/items"

    async def search_players(
        self,
        client: httpx.AsyncClient,
        *,
        name: str,
        page: int = 0,
        include_inactive: int = 0,
        include_unranked: int = 0,
    ) -> Any:
        try:
            return await self._pred.search_players(
                client, name=name, offset=page * 12, limit=12
            )
        except PredAuthRequired:
            if not self._use_omeda_fallback:
                raise
            log.debug("playersPaginated forbidden; falling back to omeda.city REST")
            return await self._omeda.search_players(  # type: ignore[union-attr]
                client,
                name=name,
                page=page,
                include_inactive=include_inactive,
                include_unranked=include_unranked,
            )

    async def get_player(self, client: httpx.AsyncClient, player_id: str) -> Any:
        try:
            profile = await self._pred.get_player(client, player_id)
            if profile:
                return profile
        except PredAuthRequired:
            if not self._use_omeda_fallback:
                raise
        if self._use_omeda_fallback:
            return await self._omeda.get_player(client, player_id)  # type: ignore[union-attr]
        return {}

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
        try:
            return await self._pred.get_player_matches(
                client,
                player_id,
                offset=page * per_page,
                limit=per_page,
            )
        except PredAuthRequired:
            if not self._use_omeda_fallback:
                raise
            log.debug("matchesPaginated forbidden; falling back to omeda.city REST")
            return await self._omeda.get_player_matches(  # type: ignore[union-attr]
                client,
                player_id,
                page=page,
                per_page=per_page,
                time_frame=time_frame,
                hero_id=hero_id,
                role=role,
                player_name=player_name,
                game_mode=game_mode,
            )

    async def get_heroes(self, client: httpx.AsyncClient) -> Any:
        return await self._pred.get_heroes(client)

    async def get_hero_statistics(
        self,
        client: httpx.AsyncClient,
        *,
        hero_ids: list[str] | None = None,
        time_frame: str | None = None,
        hero_slug: str | None = None,
    ) -> Any:
        if hero_slug or hero_ids:
            slug = hero_slug
            if not slug and hero_ids:
                # best-effort: omeda used numeric ids; pred uses slugs in /hero command
                pass
            data = await self._pred.get_hero_statistics(client, hero_slug=slug)
            if data:
                return data
        if self._use_omeda_fallback and hero_ids:
            try:
                return await self._omeda.get_hero_statistics(  # type: ignore[union-attr]
                    client, hero_ids=hero_ids, time_frame=time_frame
                )
            except OmedaAuthRequired:
                pass
        return {}

    async def get_items(self, client: httpx.AsyncClient) -> Any:
        return await self._pred.get_items(client)

    async def get_match(self, client: httpx.AsyncClient, match_id: str) -> MatchDetail | dict[str, Any]:
        raw: Any = {}
        try:
            raw = await self._pred.get_match(client, match_id)
        except PredAuthRequired:
            if not self._use_omeda_fallback:
                raise
        if (not raw or not raw.get("matchPlayers")) and self._use_omeda_fallback:
            raw = await self._omeda.get_match(client, match_id)  # type: ignore[union-attr]
        parsed = parse_match_payload(raw)
        if parsed:
            await self._enrich_hero_icons(client, parsed)
            await self._enrich_player_ranks(client, parsed)
            await self._enrich_rank_from_pred(client, match_id, parsed)
            await self._enrich_ranks_from_profiles(client, parsed)
            if self._use_omeda_fallback:
                await self._merge_omeda_performance(client, match_id, parsed)
            return parsed
        return raw if isinstance(raw, dict) else {}

    async def _ensure_hero_icons(self, client: httpx.AsyncClient) -> None:
        if self._hero_icons_loaded:
            return
        self._hero_icons_loaded = True
        try:
            heroes = await self._pred.get_heroes(client)
        except Exception:
            return
        if not isinstance(heroes, list):
            return
        for hero in heroes:
            if not isinstance(hero, dict):
                continue
            icon = hero.get("icon")
            if not icon:
                continue
            hero_id = hero.get("id")
            slug = hero.get("slug")
            if hero_id is not None:
                self._hero_icons_by_id[str(hero_id)] = str(icon)
            if slug:
                self._hero_icons_by_slug[str(slug).lower()] = str(icon)

    async def _enrich_hero_icons(self, client: httpx.AsyncClient, detail: MatchDetail) -> None:
        if all(p.hero_icon for p in detail.players):
            return
        await self._ensure_hero_icons(client)
        for player in detail.players:
            if player.hero_icon:
                continue
            if player.hero_id:
                icon = self._hero_icons_by_id.get(str(player.hero_id))
                if icon:
                    player.hero_icon = icon
                    continue
            if player.hero_slug:
                icon = self._hero_icons_by_slug.get(player.hero_slug.lower())
                if icon:
                    player.hero_icon = icon

    async def _ensure_rank_table(self, client: httpx.AsyncClient) -> None:
        if self._ranks_loaded:
            return
        self._ranks_loaded = True
        try:
            ranks = await self._pred.get_rating_ranks(client)
        except Exception:
            return
        for rank in ranks:
            rank_id = rank.get("id")
            if rank_id is None:
                continue
            self._ranks_by_id[str(rank_id)] = {
                "name": str(rank.get("name") or ""),
                "abbreviation": str(rank.get("abbreviation") or ""),
                "icon": str(rank.get("icon") or ""),
            }

    async def _enrich_player_ranks(self, client: httpx.AsyncClient, detail: MatchDetail) -> None:
        if not detail.players:
            return
        if all(p.rank_icon for p in detail.players):
            return
        await self._ensure_rank_table(client)
        for player in detail.players:
            row = self._ranks_by_id.get(str(player.rank_id or ""))
            if not row:
                continue
            if not player.rank_name:
                player.rank_name = row.get("name") or None
            if not player.rank_abbrev:
                player.rank_abbrev = row.get("abbreviation") or None
            if not player.rank_icon:
                player.rank_icon = row.get("icon") or None

    async def _enrich_rank_from_pred(
        self,
        client: httpx.AsyncClient,
        match_id: str,
        detail: MatchDetail,
    ) -> None:
        """Fill rank name/icon from pred.gg when the primary payload omitted them."""
        if all(p.rank_icon for p in detail.players):
            return
        try:
            raw = await self._pred.get_match(client, match_id)
        except Exception:
            return
        pred_detail = parse_match_payload(raw)
        if not pred_detail:
            return
        by_id = {
            normalize_match_id(p.player_id): p
            for p in pred_detail.players
            if p.player_id
        }
        for player in detail.players:
            key = normalize_match_id(player.player_id)
            if not key:
                continue
            src = by_id.get(key)
            if not src:
                continue
            if not player.rank_name:
                player.rank_name = src.rank_name
            if not player.rank_abbrev:
                player.rank_abbrev = src.rank_abbrev
            if not player.rank_icon:
                player.rank_icon = src.rank_icon
            if not player.rank_id:
                player.rank_id = src.rank_id

    async def _current_season_rating_id(self, client: httpx.AsyncClient) -> str | None:
        if self._season_rating_id:
            return self._season_rating_id
        try:
            seasons = await self._pred.list_ratings(client)
        except Exception:
            return None
        ids: list[int] = []
        for season in seasons:
            try:
                ids.append(int(season.get("id") or 0))
            except (TypeError, ValueError):
                continue
        if ids:
            self._season_rating_id = str(max(ids))
        return self._season_rating_id

    async def _fetch_player_rank_info(
        self,
        client: httpx.AsyncClient,
        player_id: str,
    ) -> dict[str, str] | None:
        season_id = await self._current_season_rating_id(client)
        try:
            ratings = await self._pred.get_player_ratings(client, player_id)
            info = pick_rank_from_player_ratings(ratings, preferred_season_id=season_id)
            if info:
                return info
        except Exception:
            log.debug("pred player ratings failed for %s", player_id[:8], exc_info=True)
        if self._use_omeda_fallback:
            try:
                profile = await self._omeda.get_player(client, player_id)  # type: ignore[union-attr]
                if isinstance(profile, dict):
                    return rank_info_from_omeda_profile(profile, base_url=self.omeda_base_url)
            except Exception:
                log.debug("omeda player rank failed for %s", player_id[:8], exc_info=True)
        return None

    async def _enrich_ranks_from_profiles(
        self,
        client: httpx.AsyncClient,
        detail: MatchDetail,
    ) -> None:
        """Fill rank from player profile when the match row has no ranked rating (e.g. casual modes)."""
        for player in detail.players:
            if player.rank_name or player.rank_icon:
                continue
            key = normalize_match_id(player.player_id)
            if not key:
                continue
            cached = self._player_rank_cache.get(key)
            if cached:
                apply_rank_info(player, cached)
                continue
            info = await self._fetch_player_rank_info(client, player.player_id)
            if info:
                self._player_rank_cache[key] = info
                apply_rank_info(player, info)

    async def _merge_omeda_performance(
        self,
        client: httpx.AsyncClient,
        match_id: str,
        detail: MatchDetail,
    ) -> None:
        """Fill omeda-only stats when pred.gg GraphQL omits them."""
        try:
            omeda_raw = await self._omeda.get_match(client, match_id)  # type: ignore[union-attr]
        except Exception:
            return
        omeda = parse_match_payload(omeda_raw)
        if not omeda:
            return
        by_id_ps = {
            normalize_match_id(p.player_id): p.performance_score
            for p in omeda.players
            if p.player_id and p.performance_score is not None
        }
        by_id_cs = {
            normalize_match_id(p.player_id): p.cs
            for p in omeda.players
            if p.player_id and p.cs is not None
        }
        by_id_rank = {
            normalize_match_id(p.player_id): (p.rank_name, p.rank_abbrev, p.rank_icon)
            for p in omeda.players
            if p.player_id and (p.rank_name or p.rank_abbrev or p.rank_icon)
        }
        for p in detail.players:
            key = normalize_match_id(p.player_id)
            if key and key in by_id_ps:
                p.performance_score = by_id_ps[key]
            if p.cs is None and key and key in by_id_cs:
                p.cs = by_id_cs[key]
            if key and key in by_id_rank:
                name, abbrev, icon = by_id_rank[key]
                if not p.rank_name:
                    p.rank_name = name
                if not p.rank_abbrev:
                    p.rank_abbrev = abbrev
                if not p.rank_icon:
                    p.rank_icon = icon
