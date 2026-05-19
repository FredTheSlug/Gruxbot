"""GraphQL client for pred.gg (https://pred.gg/gql)."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from pred_bot.oauth_tokens import OAuthTokenStore

log = logging.getLogger(__name__)

CURRENT_SEASON_RATING_ID = "11"


class PredAuthRequired(Exception):
    """Raised when pred.gg GraphQL returns Forbidden on a field."""


class PredGqlClient:
    def __init__(
        self,
        gql_url: str = "https://pred.gg/gql",
        *,
        user_agent: str = "GruxBotPredBot/1.0",
        authorization: str | None = None,
        oauth_store: OAuthTokenStore | None = None,
        oauth_client_id: str | None = None,
        oauth_client_secret: str | None = None,
        oauth_token_url: str = "https://pred.gg/api/oauth2/token",
        max_concurrency: int = 5,
        max_retries: int = 3,
    ) -> None:
        self._gql_url = gql_url.rstrip("/")
        self._base_headers: dict[str, str] = {
            "User-Agent": user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self._static_authorization = authorization
        self._oauth_store = oauth_store
        self._oauth_client_id = oauth_client_id
        self._oauth_client_secret = oauth_client_secret
        self._oauth_token_url = oauth_token_url.rstrip("/")
        self._max_retries = max(1, max_retries)
        self._sem = asyncio.Semaphore(max(1, max_concurrency))
        self._versions: list[dict[str, Any]] | None = None
        self._paragon_rank_ids: list[str] | None = None

    async def _request_headers(self, client: httpx.AsyncClient) -> dict[str, str]:
        headers = dict(self._base_headers)
        auth = self._static_authorization
        if (
            not auth
            and self._oauth_store
            and self._oauth_client_id
            and self._oauth_client_secret
        ):
            auth = await self._oauth_store.get_authorization_header(
                client,
                token_url=self._oauth_token_url,
                client_id=self._oauth_client_id,
                client_secret=self._oauth_client_secret,
            )
        if auth:
            headers["Authorization"] = auth
        return headers

    async def execute(
        self,
        client: httpx.AsyncClient,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"query": query}
        if variables:
            body["variables"] = variables
        last_exc: BaseException | None = None
        async with self._sem:
            for attempt in range(self._max_retries):
                try:
                    headers = await self._request_headers(client)
                    resp = await client.post(self._gql_url, headers=headers, json=body)
                    if resp.status_code == 403:
                        raise PredAuthRequired(f"pred.gg GraphQL forbidden: {self._gql_url}")
                    if resp.status_code >= 500:
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                    resp.raise_for_status()
                    payload = resp.json()
                    if payload.get("errors"):
                        for err in payload["errors"]:
                            if err.get("message") == "Forbidden":
                                raise PredAuthRequired(str(err))
                        log.warning("GraphQL errors: %s", payload["errors"][:2])
                    return payload
                except (httpx.TimeoutException, httpx.TransportError) as e:
                    last_exc = e
                    await asyncio.sleep(0.5 * (2**attempt))
                except PredAuthRequired:
                    raise
                except httpx.HTTPStatusError as e:
                    if e.response is not None and e.response.status_code >= 500:
                        last_exc = e
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                    raise
        if last_exc:
            raise last_exc
        raise RuntimeError("pred.gg GraphQL request exhausted retries")

    @staticmethod
    def _forbidden_in_payload(payload: dict[str, Any], path_prefix: list[str]) -> bool:
        for err in payload.get("errors") or []:
            if err.get("message") != "Forbidden":
                continue
            path = err.get("path") or []
            if not path_prefix:
                return True
            if path[: len(path_prefix)] == path_prefix:
                return True
        return False

    async def search_players(
        self,
        client: httpx.AsyncClient,
        *,
        name: str,
        offset: int = 0,
        limit: int = 12,
    ) -> Any:
        payload = await self.execute(
            client,
            """
            query SearchPlayers($query: String!, $offset: Int, $limit: Int) {
              playersPaginated(filter: {search: $query}, limit: $limit, offset: $offset) {
                results {
                  name
                  uuid
                }
              }
            }
            """,
            {"query": name, "offset": offset, "limit": limit},
        )
        if self._forbidden_in_payload(payload, ["playersPaginated"]):
            raise PredAuthRequired("playersPaginated requires auth")
        results = (payload.get("data") or {}).get("playersPaginated", {}).get("results") or []
        return [{"id": r.get("uuid"), "display_name": r.get("name"), "name": r.get("name")} for r in results]

    async def get_player(self, client: httpx.AsyncClient, player_id: str) -> Any:
        payload = await self.execute(
            client,
            """
            query PlayerProfile($uuid: UUID!) {
              player(by: {uuid: $uuid}) {
                name
                uuid
                favRegion
                favRole
              }
            }
            """,
            {"uuid": player_id},
        )
        player = (payload.get("data") or {}).get("player")
        if not player:
            return {}
        return {
            "id": player.get("uuid"),
            "display_name": player.get("name"),
            "name": player.get("name"),
            "region": player.get("favRegion"),
            "fav_role": player.get("favRole"),
        }

    async def get_player_ratings(self, client: httpx.AsyncClient, player_id: str) -> list[dict[str, Any]]:
        payload = await self.execute(
            client,
            """
            query PlayerRatings($uuid: UUID!) {
              player(by: {uuid: $uuid}) {
                ratings {
                  id
                  points
                  unranked
                  rank { id name abbreviation icon tierName }
                  rating { id name }
                }
              }
            }
            """,
            {"uuid": player_id},
        )
        player = (payload.get("data") or {}).get("player") or {}
        ratings = player.get("ratings") or []
        return [r for r in ratings if isinstance(r, dict)]

    async def list_ratings(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        payload = await self.execute(
            client,
            """
            query Ratings {
              ratings { id name }
            }
            """,
        )
        ratings = (payload.get("data") or {}).get("ratings") or []
        return [r for r in ratings if isinstance(r, dict)]

    async def get_player_matches(
        self,
        client: httpx.AsyncClient,
        player_id: str,
        *,
        offset: int = 0,
        limit: int = 25,
    ) -> Any:
        payload = await self.execute(
            client,
            """
            query PlayerMatches($uuid: UUID!, $offset: Int!, $limit: Int!) {
              player(by: {uuid: $uuid}) {
                matchesPaginated(offset: $offset, limit: $limit) {
                  results {
                    match {
                      id
                      uuid
                      gameMode
                      startTime
                      endTime
                    }
                  }
                }
              }
            }
            """,
            {"uuid": player_id, "offset": offset, "limit": min(limit, 100)},
        )
        if self._forbidden_in_payload(payload, ["player", "matchesPaginated"]):
            raise PredAuthRequired("matchesPaginated requires auth")
        player = (payload.get("data") or {}).get("player") or {}
        results = (player.get("matchesPaginated") or {}).get("results") or []
        matches = []
        for row in results:
            m = row.get("match") or row
            mid = m.get("uuid") or m.get("id")
            mode = m.get("gameMode")
            matches.append(
                {
                    "id": mid,
                    "uuid": mid,
                    "start_time": m.get("startTime"),
                    "end_time": m.get("endTime"),
                    "game_mode": mode.lower() if isinstance(mode, str) else mode,
                }
            )
        return {"matches": matches}

    async def get_heroes(self, client: httpx.AsyncClient) -> Any:
        payload = await self.execute(
            client,
            """
            query Heroes {
              heroes {
                id
                slug
                data {
                  name
                  displayName
                  icon
                }
              }
            }
            """,
        )
        heroes = (payload.get("data") or {}).get("heroes") or []
        out = []
        for h in heroes:
            data = h.get("data") or {}
            out.append(
                {
                    "id": h.get("id"),
                    "slug": h.get("slug"),
                    "name": data.get("displayName") or data.get("name"),
                    "display_name": data.get("displayName") or data.get("name"),
                    "icon": data.get("icon"),
                }
            )
        return out

    async def get_items(self, client: httpx.AsyncClient) -> Any:
        payload = await self.execute(
            client,
            """
            query Items {
              items {
                id
                slug
                data {
                  name
                  displayName
                  icon
                }
              }
            }
            """,
        )
        items = (payload.get("data") or {}).get("items") or []
        out = []
        for it in items:
            data = it.get("data") or {}
            out.append(
                {
                    "id": it.get("id"),
                    "slug": it.get("slug"),
                    "name": data.get("displayName") or data.get("name"),
                    "display_name": data.get("displayName") or data.get("name"),
                }
            )
        return out

    async def get_rating_ranks(
        self,
        client: httpx.AsyncClient,
        rating_id: str = "11",
    ) -> list[dict[str, Any]]:
        payload = await self.execute(
            client,
            """
            query($id: ID!) {
              rating(by: {id: $id}) {
                ranks { id name abbreviation icon tierName }
              }
            }
            """,
            {"id": rating_id},
        )
        rating = (payload.get("data") or {}).get("rating") or {}
        ranks = rating.get("ranks") or []
        return [r for r in ranks if isinstance(r, dict)]

    async def get_game_versions(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        if self._versions is not None:
            return self._versions
        payload = await self.execute(
            client,
            """
            query Versions {
              versions { id name }
            }
            """,
        )
        versions = (payload.get("data") or {}).get("versions") or []
        self._versions = [v for v in versions if isinstance(v, dict) and v.get("id") is not None]
        return self._versions

    async def get_current_version_ids(self, client: httpx.AsyncClient) -> list[str]:
        versions = await self.get_game_versions(client)
        if not versions:
            return []
        latest = max(versions, key=lambda v: int(v["id"]))
        return [str(latest["id"])]

    async def get_paragon_rank_ids(
        self,
        client: httpx.AsyncClient,
        *,
        rating_id: str = CURRENT_SEASON_RATING_ID,
    ) -> list[str]:
        if self._paragon_rank_ids is not None:
            return list(self._paragon_rank_ids)
        ranks = await self.get_rating_ranks(client, rating_id=rating_id)
        ids = [
            str(r["id"])
            for r in ranks
            if isinstance(r, dict)
            and r.get("id") is not None
            and str(r.get("tierName") or "").strip().lower() == "paragon"
        ]
        self._paragon_rank_ids = ids
        return list(ids)

    _HERO_CORE_BUILD_QUERY = """
        query HeroBuildData($slug: String!, $filter: HeroCoreBuildFilterInput, $limit: Int!) {
          hero(by: { slug: $slug }) {
            slug
            data {
              displayName
              icon
            }
            coreBuild(filter: $filter, limit: $limit) {
              results {
                matchesPlayedBuildOrder
                matchesWonBuildOrder
                core1Item {
                  id
                  data {
                    displayName
                    icon
                    smallIcon
                    item { slug }
                  }
                }
                core2Item {
                  id
                  data {
                    displayName
                    icon
                    smallIcon
                    item { slug }
                  }
                }
                core3Item {
                  id
                  data {
                    displayName
                    icon
                    smallIcon
                    item { slug }
                  }
                }
                crests: items(slot: CREST, limit: 3) {
                  matchesPlayedBuildOrder
                  matchesWonBuildOrder
                  item {
                    id
                    data {
                      displayName
                      icon
                      smallIcon
                      item { slug }
                    }
                  }
                }
              }
            }
          }
        }
    """

    async def get_hero_core_build(
        self,
        client: httpx.AsyncClient,
        *,
        hero_slug: str,
        role: str,
        limit: int = 1,
    ) -> dict[str, Any]:
        role_enum = role.strip().upper().replace("-", "")
        paragon_ids = await self.get_paragon_rank_ids(client)
        if not paragon_ids:
            log.warning("no Paragon rank ids found for rating %s", CURRENT_SEASON_RATING_ID)
        version_ids = await self.get_current_version_ids(client)
        if not version_ids:
            log.warning("no game versions returned from pred.gg")

        build_filter: dict[str, Any] = {
            "gameModes": ["RANKED"],
            "roles": [role_enum],
            "ranks": paragon_ids,
            "versions": version_ids,
        }
        payload = await self.execute(
            client,
            self._HERO_CORE_BUILD_QUERY,
            {
                "slug": hero_slug.strip().lower(),
                "limit": limit,
                "filter": build_filter,
            },
        )
        if self._forbidden_in_payload(payload, ["hero", "coreBuild"]):
            raise PredAuthRequired("hero.coreBuild requires auth")
        hero = (payload.get("data") or {}).get("hero") or {}
        core = hero.get("coreBuild") or {}
        results = core.get("results") or []
        return {
            "hero": hero,
            "results": [r for r in results if isinstance(r, dict)],
            "filter": build_filter,
            "paragon_rank_ids": paragon_ids,
            "version_ids": version_ids,
        }

    async def get_match(self, client: httpx.AsyncClient, match_id: str) -> Any:
        payload = await self.execute(
            client,
            """
            query MatchDetail($id: ID!) {
              match(by: {id: $id}) {
                id
                uuid
                duration
                gameMode
                startTime
                endTime
                region
                winningTeam
                matchPlayers {
                  team
                  kills
                  deaths
                  assists
                  minionsKilled
                  role
                  hero { id slug data { displayName icon } }
                  heroData { displayName icon }
                  player { name uuid }
                  rating { points newPoints rank { id name abbreviation tierName icon } }
                }
              }
            }
            """,
            {"id": match_id.replace("-", "")},
        )
        m = (payload.get("data") or {}).get("match") or {}
        if not m:
            return {}
        return m

    async def get_hero_statistics(
        self,
        client: httpx.AsyncClient,
        *,
        hero_ids: list[str] | None = None,
        hero_slug: str | None = None,
    ) -> Any:
        if hero_slug:
            payload = await self.execute(
                client,
                """
                query HeroDetail($slug: String!) {
                  hero(by: {slug: $slug}) {
                    id
                    slug
                    data {
                      name
                      displayName
                    }
                  }
                }
                """,
                {"slug": hero_slug},
            )
            return payload.get("data") or {}
        return {}
