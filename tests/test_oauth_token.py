"""Tests for OAuth token exchange client authentication."""

from __future__ import annotations

import base64
import json
import time

import httpx
import pytest
from pytest_httpx import HTTPXMock

from pred_bot.oauth_pkce import exchange_code_for_tokens
from pred_bot.oauth_tokens import OAuthTokenStore


@pytest.mark.asyncio
async def test_exchange_sends_secret_in_body(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        json={
            "access_token": "at",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "rt",
        }
    )

    async with httpx.AsyncClient() as client:
        tokens = await exchange_code_for_tokens(
            client,
            token_url="https://pred.gg/api/oauth2/token",
            client_id="cid",
            client_secret="sec",
            redirect_uri="http://127.0.0.1:8765/callback",
            code="authcode",
            code_verifier="v" * 43,
            scope="read",
        )

    assert tokens["access_token"] == "at"
    request = httpx_mock.get_requests()[0]
    assert "Authorization" not in request.headers
    body = request.content.decode()
    assert "client_secret=sec" in body
    assert "client_id=cid" in body
    assert "scope=read" in body


@pytest.mark.asyncio
async def test_exchange_falls_back_to_basic_without_client_id_in_body(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(status_code=401, json={"error": "invalid_client"})
    httpx_mock.add_response(
        json={
            "access_token": "at2",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
    )

    async with httpx.AsyncClient() as client:
        tokens = await exchange_code_for_tokens(
            client,
            token_url="https://pred.gg/api/oauth2/token",
            client_id="cid",
            client_secret="sec",
            redirect_uri="http://127.0.0.1:8765/callback",
            code="authcode",
            code_verifier="v" * 43,
        )

    assert tokens["access_token"] == "at2"
    assert len(httpx_mock.get_requests()) == 2
    second = httpx_mock.get_requests()[1]
    assert second.headers["Authorization"] == "Basic " + base64.b64encode(b"cid:sec").decode()
    assert "client_id" not in second.content.decode()


@pytest.mark.asyncio
async def test_authorization_header_without_client_credentials(tmp_path) -> None:
    token_path = tmp_path / "oauth_tokens.json"
    token_path.write_text(
        json.dumps(
            {
                "access_token": "valid-at",
                "token_type": "Bearer",
                "expires_at": time.time() + 3600,
            }
        ),
        encoding="utf-8",
    )
    store = OAuthTokenStore(token_path)

    async with httpx.AsyncClient() as client:
        header = await store.get_authorization_header(
            client,
            token_url="https://pred.gg/api/oauth2/token",
            client_id=None,
            client_secret=None,
        )

    assert header == "Bearer valid-at"
