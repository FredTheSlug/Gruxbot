"""Exhaustive probe for pred.gg role icon assets."""
import json
import re

import httpx

BASE = "https://pred.gg"
GQL = f"{BASE}/gql"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def gql(query: str, variables: dict | None = None) -> dict:
    body: dict = {"query": query}
    if variables:
        body["variables"] = variables
    return httpx.post(GQL, json=body, headers=HEADERS, timeout=30).json()


# 1) All Query fields with role/lane
r = gql("{ __type(name: \"Query\") { fields { name } } }")
queries = [f["name"] for f in r.get("data", {}).get("__type", {}).get("fields", [])]
print("Query fields (role*):", [q for q in queries if "role" in q.lower() or "lane" in q.lower()])

# 2) All types with Role in name
r2 = gql("{ __schema { types { name } } }")
types = [t["name"] for t in r2["data"]["__schema"]["types"] if "role" in t["name"].lower()]
print("Types with role:", types)
for tn in types[:8]:
    tr = gql(f'{{ t: __type(name: "{tn}") {{ fields {{ name type {{ name kind ofType {{ name }} }} }} }} }}')
    fields = tr.get("data", {}).get("t", {}).get("fields") or []
    icon_fields = [f["name"] for f in fields if "icon" in f["name"].lower() or "image" in f["name"].lower()]
    if icon_fields:
        print(f"  {tn} icon fields:", icon_fields)

# 3) MatchPlayer all fields
mp = gql('{ mp: __type(name: "MatchPlayer") { fields { name } } }')
print("MatchPlayer fields:", [f["name"] for f in mp["data"]["mp"]["fields"]])

# 4) Search JS bundles for role-related asset paths
html = httpx.get(BASE, timeout=20, headers={"User-Agent": "Mozilla/5.0"}).text
scripts = re.findall(r"/_app/immutable/[^\"']+\.js", html)
patterns: set[str] = set()
for s in scripts:
    try:
        js = httpx.get(BASE + s, timeout=25).text
    except Exception:
        continue
    for m in re.findall(r'["\']([^"\']*(?:role|Role|CARRY|JUNGLE)[^"\']*\.(?:png|svg|webp))["\']', js):
        if len(m) < 120:
            patterns.add(m)
    for m in re.findall(r"/assets/[a-zA-Z0-9_./-]{4,80}", js):
        if re.search(r"role|lane|carry|jungle|support|offlane|mid", m, re.I):
            patterns.add(m)
    if "roleIcon" in js or "RoleIcon" in js or "roles/" in js:
        for needle in ("roleIcon", "RoleIcon", "roles/", "ROLE_ICONS", "role_icon"):
            if needle in js:
                i = js.find(needle)
                print("JS hit", s[-28:], needle, repr(js[i : i + 100]))

print("JS asset patterns:", sorted(patterns)[:25])

# 5) Brute paths
candidates = []
for role in ("carry", "offlane", "midlane", "mid", "jungle", "support", "fill"):
    for prefix in ("/assets/", "/assets/roles/", "/images/roles/", "/images/game/roles/"):
        candidates.append(f"{prefix}{role}.png")
        candidates.append(f"{prefix}{role}.webp")
        candidates.append(f"{prefix}{role.upper()}.png")

hits = []
for path in candidates:
    resp = httpx.get(BASE + path, timeout=8)
    ct = resp.headers.get("content-type", "")
    if resp.status_code == 200 and "image" in ct and len(resp.content) > 500:
        hits.append((path, len(resp.content), ct))

print("HTTP image hits:", hits)
