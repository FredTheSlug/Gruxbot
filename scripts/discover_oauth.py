"""Discover pred.gg OAuth parameters from site bundles and routes."""
from __future__ import annotations

import json
import re
import sys

import httpx

BASE = "https://pred.gg"


def main() -> None:
    client = httpx.Client(timeout=30, follow_redirects=True)
    html = client.get(f"{BASE}/").text
    scripts = set(re.findall(r"/_app/immutable/[^\"']+\.js", html))
    # SvelteKit may embed more chunks in inline script
    scripts.update(re.findall(r'"(/_app/immutable/[^"]+\.js)"', html))
    print(f"homepage scripts: {len(scripts)}")

    terms = (
        "code_challenge",
        "generateCodeVerifier",
        "access_denied",
        "oauth2/authorize",
        "redirect_uri",
        "redirectUri",
        "PRED_OAUTH",
        "client_secret",
        "scope:",
        'scope="',
        "scope='",
    )
    for rel in sorted(scripts):
        js = client.get(BASE + rel).text
        hits = [t for t in terms if t in js]
        if hits:
            print(f"\n=== {rel} hits={hits} ===")
            for t in hits:
                for m in re.finditer(re.escape(t) + r".{0,120}", js):
                    print(" ", m.group(0)[:140])

    # Route-specific: oauth authorize page chunks from app manifest
    for path in ("/oauth2/authorize", "/gql", "/developers", "/dev", "/api"):
        try:
            r = client.get(BASE + path, follow_redirects=False)
            print(f"\nGET {path} -> {r.status_code} loc={r.headers.get('location', '')[:80]}")
        except Exception as e:
            print(f"GET {path} err {e}")

    # Try well-known oauth metadata
    for path in (
        "/.well-known/oauth-authorization-server",
        "/api/oauth2/.well-known/oauth-authorization-server",
        "/.well-known/openid-configuration",
    ):
        try:
            r = client.get(BASE + path)
            if r.status_code == 200:
                print(f"\n{path}:\n{r.text[:2000]}")
        except Exception:
            pass

    # Search all linked chunk names from any JS we already have
    all_js = ""
    for rel in list(scripts)[:30]:
        all_js += client.get(BASE + rel).text
    more = set(re.findall(r"/_app/immutable/[^\"']+\.js", all_js))
    extra = more - scripts
    if extra:
        print(f"\nextra chunks referenced: {len(extra)}")
        for rel in sorted(extra)[:40]:
            js = client.get(BASE + rel).text
            if "oauth" in js.lower() or "pkce" in js.lower():
                print(" oauth chunk", rel)
                for pat in ("scope", "code_challenge", "redirect_uri"):
                    if pat in js:
                        i = js.find(pat)
                        print(f"  {pat}:", js[i - 80 : i + 120])


if __name__ == "__main__":
    main()
