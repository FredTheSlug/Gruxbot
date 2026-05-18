"""One-off probe for pred.gg API hosts (dev only)."""
import re
import httpx

html = httpx.get("https://pred.gg/", timeout=30).text
scripts = re.findall(r'href="(/_app/immutable/[^"]+\.js)"', html)
print("scripts", len(scripts))
patterns = [
    "graphql",
    "playersPaginated",
    "matchesPaginated",
    "player(",
    "/api/",
    "api.pred",
    "omeda",
    "PUBLIC",
    "VITE_",
]
for s in scripts:
    url = "https://pred.gg" + s
    js = httpx.get(url, timeout=30).text
    for pat in patterns:
        if pat.lower() in js.lower():
            i = js.lower().index(pat.lower())
            print("HIT", pat, "in", s)
            print(js[max(0, i - 100) : i + 200])
            print("---")

# try common graphql hosts
queries = [
    ("https://pred.gg/graphql", {"query": "{ __typename }"}),
    ("https://gql.pred.gg/graphql", {"query": "{ __typename }"}),
    ("https://gql.pred.gg/", {"query": "{ __typename }"}),
    ("https://api.pred.gg/graphql", {"query": "{ __typename }"}),
    ("https://data.pred.gg/graphql", {"query": "{ __typename }"}),
    ("https://stats.pred.gg/graphql", {"query": "{ __typename }"}),
]
for url, body in queries:
    try:
        r = httpx.post(url, json=body, timeout=15)
        print("POST", url, r.status_code, r.text[:300].replace("\n", " "))
    except Exception as e:
        print("POST", url, "ERR", e)

# forum mentioned playersPaginated
q = {
    "query": """
    query {
      playersPaginated(filter: {search: ""}, limit: 3, offset: 0) {
        results { id name }
      }
    }
    """
}
for url in [
    "https://pred.gg/graphql",
    "https://gql.pred.gg/graphql",
    "https://backend.pred.gg/graphql",
]:
    try:
        r = httpx.post(url, json=q, timeout=15, headers={"Content-Type": "application/json"})
        print("playersPaginated", url, r.status_code, r.text[:400])
    except Exception as e:
        print("playersPaginated", url, "ERR", e)
