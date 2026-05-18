import httpx
import re

# SvelteKit data endpoint?
pid = "9ac7a82d-0dab-4ca3-ab4f-0ce1b269cd82"
paths = [
    f"/players/{pid}/__data.json",
    f"/players/{pid}.json",
    f"/api/players/{pid}",
    f"/api/player/{pid}",
    "/api/graphql",
]
for p in paths:
    r = httpx.get("https://pred.gg" + p, timeout=15, headers={"Accept": "application/json"})
    ct = r.headers.get("content-type", "")
    print("GET", p, r.status_code, ct[:40], r.text[:120].replace("\n", " "))

# omeda redirect?
for base in ["https://omeda.city", "https://www.omeda.city"]:
    try:
        r = httpx.get(f"{base}/players/{pid}.json", timeout=15, follow_redirects=False)
        print("omeda", base, r.status_code, r.headers.get("location"))
    except Exception as e:
        print("omeda err", e)

# search all js for http urls containing pred or graph
html = httpx.get("https://pred.gg/", timeout=30).text
scripts = re.findall(r'href="(/_app/immutable/[^"]+\.js)"', html)
all_urls = set()
for s in scripts:
    js = httpx.get("https://pred.gg" + s, timeout=30).text
    all_urls.update(re.findall(r"https://[a-zA-Z0-9._/-]{8,80}", js))
for u in sorted(all_urls):
    print("url", u)
