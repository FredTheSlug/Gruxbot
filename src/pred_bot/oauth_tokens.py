"""Persist pred.gg OAuth tokens on disk."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from pred_bot.oauth_pkce import refresh_access_token


class OAuthTokenStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> dict[str, Any] | None:
        if not self._path.is_file():
            return None
        with self._path.open(encoding="utf-8") as f:
            return json.load(f)

    def save(self, tokens: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as f:
            json.dump(tokens, f, indent=2)

    def is_expired(self, tokens: dict[str, Any], *, skew_seconds: int = 60) -> bool:
        expires_at = tokens.get("expires_at")
        if expires_at is None:
            return False
        return float(expires_at) <= time.time() + skew_seconds

    def authorization_header(self, tokens: dict[str, Any]) -> str:
        token_type = tokens.get("token_type") or "Bearer"
        access = tokens["access_token"]
        if token_type.lower() == "bearer":
            return f"Bearer {access}"
        return f"{token_type} {access}"

    async def get_valid_tokens(
        self,
        client: httpx.AsyncClient,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        skew_seconds: int = 60,
    ) -> dict[str, Any] | None:
        tokens = self.load()
        if not tokens:
            return None
        if not self.is_expired(tokens, skew_seconds=skew_seconds):
            return tokens
        refresh = tokens.get("refresh_token")
        if not refresh:
            return tokens
        refreshed = await refresh_access_token(
            client,
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh,
        )
        if tokens.get("refresh_token") and not refreshed.get("refresh_token"):
            refreshed["refresh_token"] = tokens["refresh_token"]
        self.save(refreshed)
        return refreshed

    async def get_authorization_header(
        self,
        client: httpx.AsyncClient,
        *,
        token_url: str,
        client_id: str | None,
        client_secret: str | None,
    ) -> str | None:
        if client_id and client_secret:
            tokens = await self.get_valid_tokens(
                client,
                token_url=token_url,
                client_id=client_id,
                client_secret=client_secret,
            )
        else:
            tokens = self.load()
            if tokens and self.is_expired(tokens):
                return None
        if not tokens:
            return None
        return self.authorization_header(tokens)
