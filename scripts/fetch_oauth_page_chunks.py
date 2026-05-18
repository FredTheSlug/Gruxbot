"""Download JS chunks from pred.gg /oauth2/authorize page."""
import re
import httpx

BASE = "https://pred.gg"
html = httpx.get(f"{BASE}/oauth2/authorize", timeout=30).text
print("html len", len(html))
scripts = set(re.findall(r"/_app/immutable/[^\"']+\.js", html))
print("scripts", len(scripts))
for rel in sorted(scripts):
    js = httpx.get(BASE + rel, timeout=30).text
    low = js.lower()
    if any(k in low for k in ("code_challenge", "scope", "access_denied", "client_id", "redirect")):
        print("\n===", rel, "===")
        for term in ("scope", "code_challenge", "access_denied", "redirect_uri", "redirectUri", "client_id"):
            if term.lower() in low:
                i = low.find(term.lower())
                print(term, js[max(0, i - 100) : i + 200])
