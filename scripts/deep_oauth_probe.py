"""Search pred.gg bundles for OAuth/PKCE parameters."""
import httpx
import re

html = httpx.get("https://pred.gg/", timeout=30).text
scripts = re.findall(r'href="(/_app/immutable/[^"]+\.js)"', html)
for rel in scripts:
    js = httpx.get("https://pred.gg" + rel, timeout=20).text
    if "oauth" not in js.lower() and "pkce" not in js.lower():
        continue
    if "authorize" not in js.lower() and "code_challenge" not in js.lower():
        continue
    print(f"\n=== {rel} len={len(js)} ===")
    for m in re.finditer(r".{0,80}scope.{0,80}", js, re.I):
        s = m.group(0)
        if "discord" not in s.lower() and "css" not in s.lower():
            print(" scope ctx:", s[:160])
