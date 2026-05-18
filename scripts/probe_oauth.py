"""Probe pred.gg OAuth endpoints (run manually)."""
import base64
import hashlib
import secrets
import urllib.parse

import httpx

CLIENT_ID = "REPLACE_ME"
REDIRECT = "http://127.0.0.1:8765/callback"
verifier = secrets.token_urlsafe(64)
challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
state = secrets.token_urlsafe(16)

params = {
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT,
    "response_type": "code",
    "code_challenge": challenge,
    "code_challenge_method": "S256",
    "state": state,
}
url = "https://pred.gg/api/oauth2/authorize?" + urllib.parse.urlencode(params)
print(url)
