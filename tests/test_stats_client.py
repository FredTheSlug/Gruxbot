"""Tests for pred.gg + omeda fallback stats client."""

from __future__ import annotations

import httpx
import pytest
from pytest_httpx import HTTPXMock

from pred_bot.omeda_client import OmedaClient
from pred_bot.pred_client import PredGqlClient
from pred_bot.stats_client import StatsClient


@pytest.mark.asyncio
async def test_search_falls_back_to_omeda_on_forbidden(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://pred.gg/gql",
        json={
            "data": None,
            "errors": [{"message": "Forbidden", "path": ["playersPaginated"]}],
        },
    )
    httpx_mock.add_response(
        url="https://omeda.city/players.json?filter%5Binclude_inactive%5D=0&filter%5Binclude_unranked%5D=0&filter%5Bname%5D=Grux&page=0",
        json=[{"id": "abc", "display_name": "Grux"}],
    )
    stats = StatsClient(
        pred=PredGqlClient("https://pred.gg/gql"),
        omeda=OmedaClient("https://omeda.city"),
        use_omeda_fallback=True,
    )
    async with httpx.AsyncClient() as client:
        result = await stats.search_players(client, name="Grux", page=0)
    assert isinstance(result, list)
    assert result[0]["id"] == "abc"


@pytest.mark.asyncio
async def test_get_heroes_from_pred(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://pred.gg/gql",
        json={
            "data": {
                "heroes": [
                    {"id": "8", "slug": "grux", "data": {"name": "Grux", "displayName": "Grux"}},
                ]
            }
        },
    )
    stats = StatsClient(
        pred=PredGqlClient("https://pred.gg/gql"),
        omeda=None,
        use_omeda_fallback=False,
    )
    async with httpx.AsyncClient() as client:
        heroes = await stats.get_heroes(client)
    assert heroes[0]["slug"] == "grux"
    assert heroes[0]["name"] == "Grux"
