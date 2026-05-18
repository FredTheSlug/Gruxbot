import re

import httpx

BASE = "https://pred.gg"
html = httpx.get(f"{BASE}/", timeout=20, headers={"User-Agent": "Mozilla/5.0"}).text
scripts = re.findall(r"/_app/immutable/[^\"']+\.js", html)
print("bundles", len(scripts))
found: set[str] = set()
for s in scripts:
    js = httpx.get(BASE + s, timeout=30).text
    for m in re.findall(r"/assets/[a-zA-Z0-9_./-]+\.(?:png|svg|webp)", js):
        if "role" in m.lower() or "lane" in m.lower() or "jungle" in m.lower() or "carry" in m.lower():
            found.add(m)
    for m in re.findall(r"[a-f0-9]{12,20}", js):
        if m in ("82f82fede2ff80be",):
            continue
found_sorted = sorted(found)
print("asset paths", found_sorted[:30])

for s in scripts[:12]:
    js = httpx.get(BASE + s, timeout=30).text
    if "CARRY" in js and ("icon" in js.lower() or "role" in js.lower()):
        for needle in ("roleIcon", "RoleIcon", "ROLE_", "roles/", "getRole", "role.icon"):
            if needle in js:
                i = js.find(needle)
                print(s[-24:], needle, repr(js[i : i + 120]))

# brute common patterns
roles = ["carry", "support", "jungle", "midlane", "offlane", "CARRY", "OFFLANE"]
patterns = []
for r in roles:
    patterns.extend(
        [
            f"/assets/roles/{r}.png",
            f"/assets/roles/{r.lower()}.png",
            f"/assets/role_{r.lower()}.png",
            f"/assets/{r.lower()}_role.png",
            f"/images/roles/{r.lower()}.png",
        ]
    )

for p in patterns:
    resp = httpx.get(BASE + p, timeout=10)
    ct = resp.headers.get("content-type", "")
    if resp.status_code == 200 and "image" in ct:
        print("HIT", p, len(resp.content))

# GraphQL __type Role enum values
import json

GQL = f"{BASE}/gql"
r = httpx.post(
    GQL,
    json={"query": '{ t: __type(name: "Role") { enumValues { name } } }'},
    timeout=30,
).json()
print("Role enum:", r)
