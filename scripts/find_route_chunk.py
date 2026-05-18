import re
import httpx

BASE = "https://pred.gg"
# Download all JS referenced from homepage + start + app
seen = set()
queue = [
    "/_app/immutable/entry/start.DITls1kt.js",
    "/_app/immutable/entry/app.30qqjOPa.js",
]
while queue:
    rel = queue.pop()
    if rel in seen:
        continue
    seen.add(rel)
    js = httpx.get(BASE + rel, timeout=30).text
    for m in re.finditer(r"/_app/immutable/[^\"'\s]+\.js", js):
        n = m.group(0)
        if n not in seen:
            queue.append(n)
    if "oauth2" in js and ("authorize" in js or "code_challenge" in js):
        if "oauth2/authorize" in js or "code_challenge" in js:
            print("INTEREST", rel, "size", len(js))
            for pat in ("oauth2", "code_challenge", "scope", "access_denied", "redirect_uri"):
                if pat in js:
                    for m in re.finditer(rf".{{0,50}}{re.escape(pat)}.{{0,80}}", js):
                        s = m.group(0)
                        if "discord" not in s and "ad_storage" not in s:
                            print(" ", s[:130])

print("total js files", len(seen))
