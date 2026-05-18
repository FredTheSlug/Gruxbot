import httpx
import re

html = httpx.get("https://pred.gg/", timeout=30).text
scripts = set(re.findall(r"/_app/immutable/[^\"']+\.js", html))
print("scripts", len(scripts))
for rel in sorted(scripts):
    js = httpx.get("https://pred.gg" + rel, timeout=20).text
    if "code_challenge" in js or "generateCodeVerifier" in js or "access_denied" in js:
        print("FOUND", rel)
        for term in ("scope", "access_denied", "code_challenge", "redirect_uri"):
            if term in js:
                i = js.find(term)
                print(term, js[i - 100 : i + 200])
