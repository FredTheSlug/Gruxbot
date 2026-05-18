"""Tests for OAuth PKCE helpers."""

from pred_bot.oauth_pkce import build_authorize_url, generate_pkce


def test_generate_pkce_lengths() -> None:
    pkce = generate_pkce()
    assert len(pkce.verifier) >= 43
    assert len(pkce.challenge) >= 43
    assert pkce.state


def test_build_authorize_url_contains_pkce_params() -> None:
    pkce = generate_pkce()
    url = build_authorize_url(
        client_id="cid",
        redirect_uri="http://127.0.0.1:8765/callback",
        pkce=pkce,
    )
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
    assert "client_id=cid" in url
    assert "state=" in url


def test_build_authorize_url_includes_scope() -> None:
    pkce = generate_pkce()
    url = build_authorize_url(
        client_id="cid",
        redirect_uri="http://127.0.0.1:8765/callback",
        pkce=pkce,
        scope="read",
    )
    assert "scope=read" in url
