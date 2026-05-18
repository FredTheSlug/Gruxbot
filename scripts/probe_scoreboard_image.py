"""Probe pred.gg for scoreboard screenshot sources."""
import json
import re

import httpx

GQL = "https://pred.gg/gql"
MID = "9d1794a79dae4c3ca4d32f8d1d8913df"


def main() -> None:
    q = """
    {
      matchType: __type(name: "Match") {
        fields { name }
      }
    }
    """
    r = httpx.post(GQL, json={"query": q}, timeout=30).json()
    fields = [f["name"] for f in r.get("data", {}).get("matchType", {}).get("fields", [])]
    print("Match fields:", fields)
    print(
        "image-like:",
        [f for f in fields if re.search(r"image|share|screenshot|card|render", f, re.I)],
    )

    url = f"https://pred.gg/matches/{MID}/statistics"
    html = httpx.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"}).text
    print("html len", len(html))
    for pat in ("og:image", "scoreboard", "screenshot", ".png", "__NEXT_DATA__"):
        print(pat, "->", bool(re.search(pat, html, re.I)))

    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        data = json.loads(m.group(1))
        print("__NEXT_DATA__ keys", data.keys())
        blob = json.dumps(data)[:8000]
        for kw in ("scoreboard", "screenshot", "ogImage", "share", "image"):
            if kw.lower() in blob.lower():
                print("found kw in next data:", kw)

    # try graphql share fields if any
    for field in fields:
        if re.search(r"image|share|screenshot|card", field, re.I):
            try:
                rr = httpx.post(
                    GQL,
                    json={
                        "query": f'query($id: ID!) {{ match(by: {{id: $id}}) {{ {field} }} }}',
                        "variables": {"id": MID},
                    },
                    timeout=30,
                ).json()
                print(field, json.dumps(rr)[:500])
            except Exception as e:
                print(field, e)


if __name__ == "__main__":
    main()
