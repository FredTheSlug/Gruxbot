"""One-time browser login for pred.gg OAuth2 (PKCE). Run: python -m pred_bot.auth"""

from __future__ import annotations

import logging
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event
from urllib.parse import parse_qs, urlparse

from pred_bot.config import Config
from pred_bot.logging import setup_logging
from pred_bot.oauth_pkce import (
    build_authorize_url,
    exchange_code_for_tokens_sync,
    generate_pkce,
)
from pred_bot.oauth_tokens import OAuthTokenStore

log = logging.getLogger(__name__)


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    result_code: str | None = None
    result_state: str | None = None
    result_error: str | None = None
    result_error_description: str | None = None
    done: Event

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not parsed.path.rstrip("/").endswith("/callback"):
            self.send_response(404)
            self.end_headers()
            return
        qs = parse_qs(parsed.query)
        if qs.get("error"):
            _OAuthCallbackHandler.result_error = qs["error"][0]
        if qs.get("error_description"):
            _OAuthCallbackHandler.result_error_description = qs["error_description"][0]
        if qs.get("code"):
            _OAuthCallbackHandler.result_code = qs["code"][0]
        if qs.get("state"):
            _OAuthCallbackHandler.result_state = qs["state"][0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if _OAuthCallbackHandler.result_error:
            desc = _OAuthCallbackHandler.result_error_description or ""
            body = (
                f"<h1>Login failed</h1>"
                f"<p><strong>{_OAuthCallbackHandler.result_error}</strong></p>"
                f"<p>{desc}</p>"
                "<p>See the terminal for troubleshooting steps.</p>"
            )
        else:
            body = "<h1>Success</h1><p>You can close this tab and return to the terminal.</p>"
        self.wfile.write(body.encode("utf-8"))
        _OAuthCallbackHandler.done.set()


def _print_oauth_denied_help(*, redirect_uri: str, scope: str | None) -> None:
    print("\nOAuth access_denied — pred.gg refused authorization before issuing a code.")
    print("Your redirect URI is accepted (otherwise you would not reach this callback).")
    print("\nMost common causes:")
    print("  • Not signed in to pred.gg (Steam / Discord / Twitch / Epic) in this browser")
    print("  • Clicked Deny on the app consent screen, or closed the tab mid-login")
    print("  • OAuth app not approved yet for your pred.gg account (ask the pred.gg dev)")
    print("\nChecklist:")
    print("  1. Open https://pred.gg/login — sign in with the account you play Predecessor on.")
    print("  2. Run auth again. You should see an app consent page (not only the login page).")
    print("     Choose Allow / Authorize (not Deny).")
    print(f"  3. In the dev portal, redirect URI must be exactly:\n       {redirect_uri}")
    print("     (not http://localhost, not missing :8765 or /callback)")
    if scope:
        print(f"  4. Scope in use: {scope!r} — ask the pred.gg dev if this is correct.")
    else:
        print(
            '  4. Set scope to read (default):  $env:PRED_OAUTH_SCOPE="read"'
        )
    print("  5. Ask the dev (forums: c0re42 on Discord) to confirm your app is enabled for your account.")
    print("  6. Confirm client id/secret are from the same app as that redirect URI.\n")


def run_login() -> None:
    setup_logging()
    config = Config()
    if not config.pred_oauth_client_id or not config.pred_oauth_client_secret:
        raise SystemExit(
            "Set PRED_OAUTH_CLIENT_ID and PRED_OAUTH_CLIENT_SECRET in the environment first."
        )

    _OAuthCallbackHandler.result_code = None
    _OAuthCallbackHandler.result_state = None
    _OAuthCallbackHandler.result_error = None
    _OAuthCallbackHandler.result_error_description = None

    pkce = generate_pkce()
    url = build_authorize_url(
        client_id=config.pred_oauth_client_id,
        redirect_uri=config.pred_oauth_redirect_uri,
        pkce=pkce,
        authorize_url=config.pred_oauth_authorize_url,
        scope=config.pred_oauth_scope,
    )

    print("\nRegister this redirect URI in your pred.gg application if you have not already:")
    print(f"  {config.pred_oauth_redirect_uri}")
    if config.pred_oauth_scope:
        print(f"OAuth scope: {config.pred_oauth_scope}")
    else:
        print("OAuth scope: read (default)")
    print("\nStep 1 — pred.gg account (required):")
    print("  Open https://pred.gg/login and sign in (Steam, Discord, Twitch, or Epic).")
    print("  Use the same browser profile you will use for Step 2.")
    try:
        input("\nPress Enter after you are signed in on pred.gg (or Ctrl+C to cancel)… ")
    except KeyboardInterrupt:
        raise SystemExit("\nCancelled.") from None

    print("\nStep 2 — authorize this bot app:")
    print("Opening browser for OAuth consent…")
    print(f"If it does not open, visit:\n\n  {url}\n")
    print("You should see a consent screen for your application. Click Allow / Authorize.\n")

    webbrowser.open(url)

    host = urlparse(config.pred_oauth_redirect_uri).hostname or "127.0.0.1"
    port = urlparse(config.pred_oauth_redirect_uri).port or 8765
    _OAuthCallbackHandler.done = Event()
    server = HTTPServer((host, port), _OAuthCallbackHandler)
    print(f"Waiting for callback on {config.pred_oauth_redirect_uri} …")
    while not _OAuthCallbackHandler.done.is_set():
        server.handle_request()

    if _OAuthCallbackHandler.result_error:
        err = _OAuthCallbackHandler.result_error
        desc = _OAuthCallbackHandler.result_error_description
        if err == "access_denied":
            _print_oauth_denied_help(
                redirect_uri=config.pred_oauth_redirect_uri,
                scope=config.pred_oauth_scope,
            )
        msg = f"OAuth error: {err}"
        if desc:
            msg += f" — {desc}"
        raise SystemExit(msg)
    if not _OAuthCallbackHandler.result_code:
        raise SystemExit("No authorization code received.")
    if _OAuthCallbackHandler.result_state != pkce.state:
        raise SystemExit("OAuth state mismatch (possible CSRF). Try again.")

    try:
        tokens = exchange_code_for_tokens_sync(
            token_url=config.pred_oauth_token_url,
            client_id=config.pred_oauth_client_id,
            client_secret=config.pred_oauth_client_secret,
            redirect_uri=config.pred_oauth_redirect_uri,
            code=_OAuthCallbackHandler.result_code,
            code_verifier=pkce.verifier,
            scope=config.pred_oauth_scope,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    store = OAuthTokenStore(config.oauth_token_path)
    store.save(tokens)
    print(f"\nSaved tokens to {config.oauth_token_path}")
    print("Start the bot with the same env vars; it will refresh tokens automatically.\n")


def main() -> None:
    run_login()


if __name__ == "__main__":
    main()
