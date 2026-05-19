"""Check pred.gg auth: which GraphQL fields work. Run: python -m pred_bot.auth_status"""

from __future__ import annotations

import asyncio
import logging

import httpx

from pred_bot.config import Config
from pred_bot.logging import setup_logging
from pred_bot.oauth_tokens import OAuthTokenStore
from pred_bot.pred_client import PredAuthRequired, PredGqlClient

log = logging.getLogger(__name__)


async def run_status() -> int:
    config = Config()
    store = OAuthTokenStore(config.oauth_token_path)
    tokens = store.load()
    pred = PredGqlClient(
        config.pred_gql_url,
        authorization=config.pred_gql_authorization,
        build_authorization=config.pred_gql_build_authorization,
        oauth_store=store if tokens else None,
        oauth_client_id=config.pred_oauth_client_id,
        oauth_client_secret=config.pred_oauth_client_secret,
        oauth_token_url=config.pred_oauth_token_url,
    )

    print("OAuth token file:", config.oauth_token_path, "present" if tokens else "missing")
    if tokens:
        print("  refresh_token:", bool(tokens.get("refresh_token")))
        print("  scope field:", repr(tokens.get("scope")))
    print("PRED_GQL_AUTHORIZATION:", "set" if config.pred_gql_authorization else "not set")
    print("PRED_GQL_BUILD_AUTHORIZATION:", "set" if config.pred_gql_build_authorization else "not set")
    print()

    async with httpx.AsyncClient(timeout=30) as client:
        headers = await pred._request_headers(client)
        print("Default Authorization:", "yes" if headers.get("Authorization") else "no")

        try:
            await pred.execute(client, "{ heroes { slug } }")
            print("heroes: OK")
        except Exception as exc:
            print("heroes:", exc)

        try:
            await pred.execute(
                client,
                'query { playersPaginated(filter: {search: "a"}, limit: 1, offset: 0) { results { name } } }',
            )
            print("playersPaginated: OK")
        except PredAuthRequired:
            print("playersPaginated: Forbidden")
        except Exception as exc:
            print("playersPaginated:", exc)

        try:
            raw = await pred.get_hero_core_build(client, hero_slug="neon", role="MIDLANE")
            n = len(raw.get("results") or [])
            print(f"hero.coreBuild (neon mid): OK ({n} result(s))")
            return 0
        except PredAuthRequired as exc:
            print("hero.coreBuild: Forbidden")
            print()
            print(str(exc))
            return 1
        except Exception as exc:
            print("hero.coreBuild:", exc)
            return 1


def main() -> None:
    setup_logging()
    raise SystemExit(asyncio.run(run_status()))


if __name__ == "__main__":
    main()
