"""Tests for Omeda.city HTTP client."""

from __future__ import annotations

import httpx
import pytest
from pytest_httpx import HTTPXMock

from pred_bot.omeda_client import OmedaClient, OmedaAuthRequired


@pytest.mark.asyncio
async def test_get_player_403_raises(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(status_code=403)
    omeda = OmedaClient("https://omeda.city")
    async with httpx.AsyncClient() as client:
        with pytest.raises(OmedaAuthRequired):
            await omeda.get_player(client, "00000000-0000-0000-0000-000000000001")


@pytest.mark.asyncio
async def test_search_players_query_params(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json={"results": []})
    omeda = OmedaClient("https://omeda.city")
    async with httpx.AsyncClient() as client:
        await omeda.search_players(client, name="Grux", page=3, include_inactive=1, include_unranked=0)
    assert len(httpx_mock.get_requests()) == 1
    req = httpx_mock.get_requests()[0]
    assert str(req.url).startswith("https://omeda.city/players.json")
    q = dict(req.url.params)
    assert q["page"] == "3"
    assert q["filter[name]"] == "Grux"
    assert q["filter[include_inactive]"] == "1"
    assert q["filter[include_unranked]"] == "0"


@pytest.mark.asyncio
async def test_get_json_returns_payload(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json={"id": "x", "name": "Test"})
    omeda = OmedaClient("https://omeda.city")
    async with httpx.AsyncClient() as client:
        data = await omeda.get_player(client, "00000000-0000-0000-0000-000000000002")
    assert data == {"id": "x", "name": "Test"}
