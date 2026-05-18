import re
import httpx

BASE = "https://pred.gg"
start = httpx.get(f"{BASE}/_app/immutable/entry/start.DITls1kt.js", timeout=30).text
chunks = set(re.findall(r"/_app/immutable/chunks/[A-Za-z0-9_-]+\.js", start))
# also from app entry
app = httpx.get(f"{BASE}/_app/immutable/entry/app.30qqjOPa.js", timeout=30).text
chunks.update(re.findall(r"/_app/immutable/chunks/[A-Za-z0-9_-]+\.js", app))
print("chunks to scan", len(chunks))
found = []
for rel in sorted(chunks):
    js = httpx.get(BASE + rel, timeout=30).text
    if "code_challenge" in js or "generateCodeVerifier" in js:
        found.append(rel)
        print("PKCE", rel)
        i = js.find("code_challenge") if "code_challenge" in js else js.find("generateCodeVerifier")
        print(js[max(0, i - 200) : i + 400])
    if "api/oauth2" in js:
        print("oauth api", rel)
        for m in re.finditer(r".{0,40}api/oauth2.{0,80}", js):
            print(" ", m.group(0)[:120])
print("pkce files", found)
