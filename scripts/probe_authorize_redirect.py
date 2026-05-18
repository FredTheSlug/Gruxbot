"""Trace redirects from pred.gg OAuth authorize (no secrets)."""
import base64
import hashlib
import secrets
import sys
import urllib.parse

import httpx

CLIENT_ID = sys.argv[1] if len(sys.argv) > 1 else "test"
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
print("GET", url[:120], "...")

with httpx.Client(follow_redirects=False, timeout=30) as client:
    r = client.get(url)
    hop = 0
    while hop < 15:
        hop += 1
        print(f"\n--- hop {hop} {r.status_code} ---")
        print("url:", str(r.url)[:200])
        loc = r.headers.get("location")
        if loc:
            print("location:", loc[:300])
        ct = r.headers.get("content-type", "")
        if "text/html" in ct:
            text = r.text
            # consent / error hints
            for needle in (
                "access_denied",
                "denied",
                "Authorize",
                "Allow",
                "scope",
                "consent",
                "login",
                "error",
            ):
                if needle.lower() in text.lower():
                    idx = text.lower().find(needle.lower())
                    snippet = text[max(0, idx - 60) : idx + 120].replace("\n", " ")
                    print(f"  found {needle!r}: ...{snippet}...")
        if r.status_code not in (301, 302, 303, 307, 308) or not loc:
            if r.status_code >= 400:
                print("body:", r.text[:500])
            break
        r = client.get(loc if loc.startswith("http") else str(r.url.join(loc)))
