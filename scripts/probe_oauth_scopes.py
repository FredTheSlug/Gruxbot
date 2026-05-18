"""Search pred.gg frontend for OAuth scope strings."""
import httpx
import re

html = httpx.get("https://pred.gg/", timeout=30).text
scripts = re.findall(r'href="(/_app/immutable/[^"]+\.js)"', html)
needles = ("oauth", "scope", "authorize", "access_denied", "client_id", "pkce", "code_challenge")
for rel in scripts:
    url = "https://pred.gg" + rel
    try:
        js = httpx.get(url, timeout=20).text
    except Exception:
        continue
    low = js.lower()
    if "oauth2" in low or "scope" in low and "authorize" in low:
        for n in needles:
            if n in low:
                i = low.find(n)
                print("===", rel, n, "===")
                print(js[max(0, i - 120) : i + 200])
                print()
