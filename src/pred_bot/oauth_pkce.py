"""OAuth 2.0 authorization code + PKCE helpers for pred.gg."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_AUTHORIZE_URL = "https://pred.gg/api/oauth2/authorize"
DEFAULT_TOKEN_URL = "https://pred.gg/api/oauth2/token"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/callback"

_FORM_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded",
}


@dataclass(frozen=True)
class PkcePair:
    verifier: str
    challenge: str
    state: str


def generate_pkce() -> PkcePair:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    state = secrets.token_urlsafe(24)
    return PkcePair(verifier=verifier, challenge=challenge, state=state)


def build_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    pkce: PkcePair,
    authorize_url: str = DEFAULT_AUTHORIZE_URL,
    scope: str | None = None,
) -> str:
    params: dict[str, str] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "code_challenge": pkce.challenge,
        "code_challenge_method": "S256",
        "state": pkce.state,
    }
    if scope:
        params["scope"] = scope
    return f"{authorize_url}?{urllib.parse.urlencode(params)}"


def _basic_auth_header(client_id: str, client_secret: str) -> dict[str, str]:
    token = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _token_error_body(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text


def _raise_token_http_error(resp: httpx.Response) -> None:
    body = _token_error_body(resp)
    hint = ""
    if resp.status_code == 401 and isinstance(body, dict) and body.get("error") == "invalid_client":
        hint = (
            " Check PRED_OAUTH_CLIENT_ID and PRED_OAUTH_CLIENT_SECRET in your environment "
            "(copy again from the dev portal; no extra quotes or spaces)."
        )
    elif isinstance(body, dict) and body.get("error") == "invalid_grant":
        hint = " Run `python -m pred_bot.auth` again to get a fresh authorization code."
    elif isinstance(body, dict) and body.get("error") == "invalid_request":
        hint = (
            " Check redirect URI matches authorize step, and re-run auth for a fresh code."
        )
    raise RuntimeError(f"Token endpoint returned {resp.status_code}: {body}.{hint}")


async def _post_token(
    client: httpx.AsyncClient,
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    data: dict[str, str],
) -> dict[str, Any]:
    """POST /token; pred.gg expects client_id + client_secret in the form body."""
    payload = dict(data)
    payload["client_secret"] = client_secret
    resp = await client.post(token_url, data=payload, headers=_FORM_HEADERS)
    if resp.is_success:
        body = resp.json()
        if isinstance(body, dict) and body.get("error"):
            raise RuntimeError(f"Token error: {body}")
        return _parse_token_response(body)
    if resp.status_code == 401:
        # Some OAuth servers accept Basic auth without client_id in the body.
        basic_payload = {k: v for k, v in data.items() if k != "client_id"}
        resp = await client.post(
            token_url,
            data=basic_payload,
            headers={**_FORM_HEADERS, **_basic_auth_header(client_id, client_secret)},
        )
        if resp.is_success:
            body = resp.json()
            if isinstance(body, dict) and body.get("error"):
                raise RuntimeError(f"Token error: {body}")
            return _parse_token_response(body)
    _raise_token_http_error(resp)


def _parse_token_response(payload: dict[str, Any]) -> dict[str, Any]:
    access = payload.get("access_token")
    if not access:
        raise RuntimeError(f"Token response missing access_token: {payload}")
    expires_in = payload.get("expires_in")
    expires_at: float | None = None
    if expires_in is not None:
        expires_at = time.time() + float(expires_in)
    return {
        "access_token": access,
        "refresh_token": payload.get("refresh_token"),
        "token_type": payload.get("token_type") or "Bearer",
        "expires_at": expires_at,
        "scope": payload.get("scope"),
    }


async def exchange_code_for_tokens(
    client: httpx.AsyncClient,
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
    scope: str | None = None,
) -> dict[str, Any]:
    data: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }
    if scope:
        data["scope"] = scope
    return await _post_token(
        client,
        token_url=token_url,
        client_id=client_id,
        client_secret=client_secret,
        data=data,
    )


async def refresh_access_token(
    client: httpx.AsyncClient,
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> dict[str, Any]:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    return await _post_token(
        client,
        token_url=token_url,
        client_id=client_id,
        client_secret=client_secret,
        data=data,
    )


def exchange_code_for_tokens_sync(
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
    scope: str | None = None,
) -> dict[str, Any]:
    data: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }
    if scope:
        data["scope"] = scope
    with httpx.Client(timeout=30.0) as client:
        return _sync_post_token(
            client,
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            data=data,
        )


def _sync_post_token(
    client: httpx.Client,
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    data: dict[str, str],
) -> dict[str, Any]:
    payload = dict(data)
    payload["client_secret"] = client_secret
    resp = client.post(token_url, data=payload, headers=_FORM_HEADERS)
    if resp.is_success:
        body = resp.json()
        if isinstance(body, dict) and body.get("error"):
            raise RuntimeError(f"Token error: {body}")
        return _parse_token_response(body)
    if resp.status_code == 401:
        basic_payload = {k: v for k, v in data.items() if k != "client_id"}
        resp = client.post(
            token_url,
            data=basic_payload,
            headers={**_FORM_HEADERS, **_basic_auth_header(client_id, client_secret)},
        )
        if resp.is_success:
            body = resp.json()
            if isinstance(body, dict) and body.get("error"):
                raise RuntimeError(f"Token error: {body}")
            return _parse_token_response(body)
    _raise_token_http_error(resp)
