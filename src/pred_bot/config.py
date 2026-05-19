"""Environment-backed configuration."""

from __future__ import annotations

import os
from pathlib import Path

# pred-bot/ (package lives in pred-bot/src/pred_bot/)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _normalize_bearer(value: str | None) -> str | None:
    if not value:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if trimmed.lower().startswith("bearer "):
        return trimmed
    return f"Bearer {trimmed}"


class Config:
    discord_token: str
    omeda_base_url: str
    follow_poll_seconds: int
    database_path: str
    guild_id: int | None
    http_max_concurrency: int
    http_max_retries: int

    def __init__(self) -> None:
        self.discord_token = os.environ["DISCORD_BOT_TOKEN"]
        self.pred_gql_url = os.environ.get("PRED_GQL_URL", "https://pred.gg/gql").rstrip("/")
        self.pred_gql_authorization = _normalize_bearer(
            os.environ.get("PRED_GQL_AUTHORIZATION")
        )
        self.pred_gql_build_authorization = _normalize_bearer(
            os.environ.get("PRED_GQL_BUILD_AUTHORIZATION")
        )
        raw_client_id = os.environ.get("PRED_OAUTH_CLIENT_ID")
        raw_client_secret = os.environ.get("PRED_OAUTH_CLIENT_SECRET")
        self.pred_oauth_client_id = raw_client_id.strip() if raw_client_id else None
        self.pred_oauth_client_secret = raw_client_secret.strip() if raw_client_secret else None
        self.pred_oauth_redirect_uri = os.environ.get(
            "PRED_OAUTH_REDIRECT_URI", "http://127.0.0.1:8765/callback"
        )
        self.pred_oauth_authorize_url = os.environ.get(
            "PRED_OAUTH_AUTHORIZE_URL", "https://pred.gg/api/oauth2/authorize"
        ).rstrip("/")
        self.pred_oauth_token_url = os.environ.get(
            "PRED_OAUTH_TOKEN_URL", "https://pred.gg/api/oauth2/token"
        ).rstrip("/")
        self.pred_oauth_scope = os.environ.get("PRED_OAUTH_SCOPE", "read")
        oauth_path = Path(os.environ.get("OAUTH_TOKEN_PATH", "data/oauth_tokens.json"))
        if not oauth_path.is_absolute():
            oauth_path = _PROJECT_ROOT / oauth_path
        self.oauth_token_path = str(oauth_path)
        self.stats_web_base_url = os.environ.get("STATS_WEB_BASE_URL", "https://pred.gg").rstrip("/")
        self.omeda_base_url = os.environ.get("OMEDA_BASE_URL", "https://omeda.city").rstrip("/")
        self.use_omeda_fallback = os.environ.get("STATS_USE_OMEDA_FALLBACK", "true").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        self.follow_poll_seconds = int(os.environ.get("FOLLOW_POLL_SECONDS", "120"))
        db_path = Path(os.environ.get("DATABASE_PATH", "data/follows.sqlite3"))
        if not db_path.is_absolute():
            db_path = _PROJECT_ROOT / db_path
        self.database_path = str(db_path)
        gid = os.environ.get("GUILD_ID")
        self.guild_id = int(gid) if gid else None
        self.http_max_concurrency = int(os.environ.get("HTTP_MAX_CONCURRENCY", "5"))
        self.http_max_retries = int(os.environ.get("HTTP_MAX_RETRIES", "3"))
        self.follow_poll_debug = os.environ.get("FOLLOW_POLL_DEBUG", "").strip().lower() in ("1", "true", "yes")
        self.scoreboard_image_enabled = os.environ.get(
            "SCOREBOARD_IMAGE_ENABLED", "true"
        ).strip().lower() in ("1", "true", "yes")
