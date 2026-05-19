"""Test which pred.gg GraphQL fields work with current oauth_tokens.json."""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from pred_bot.oauth_tokens import OAuthTokenStore
from pred_bot.pred_client import PredGqlClient, PredAuthRequired


async def main() -> None:
    token_path = Path(__file__).resolve().parents[1] / "data" / "oauth_tokens.json"
    store = OAuthTokenStore(token_path)
    tokens = store.load()
    if not tokens:
        print("No tokens at", token_path)
        return
    print("refresh_token:", bool(tokens.get("refresh_token")))
    print("scope field:", repr(tokens.get("scope")))

    pred = PredGqlClient(oauth_store=store)
    tests: list[tuple[str, str, dict | None]] = [
        ("heroes (public)", "{ heroes { slug } }", None),
        (
            "playersPaginated",
            'query { playersPaginated(filter: {search: "a"}, limit: 1, offset: 0) { results { name } } }',
            None,
        ),
        (
            "hero.coreBuild (neon mid)",
            pred._HERO_CORE_BUILD_QUERY,
            {
                "slug": "neon",
                "limit": 1,
                "filter": {
                    "gameModes": ["RANKED"],
                    "roles": ["MIDLANE"],
                    "ranks": ["36"],
                    "versions": ["144"],
                },
            },
        ),
    ]
    async with httpx.AsyncClient(timeout=30) as client:
        headers = await pred._request_headers(client)
        print("Authorization header:", "yes" if headers.get("Authorization") else "no")
        for name, query, variables in tests:
            try:
                payload = await pred.execute(client, query, variables)
                data = payload.get("data")
                print(f"{name}: OK (data={'yes' if data else 'null'})")
            except PredAuthRequired:
                print(f"{name}: Forbidden")
            except Exception as exc:
                print(f"{name}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
