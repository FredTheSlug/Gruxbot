import httpx
import re

# pull node list from app chunk
app = httpx.get("https://pred.gg/_app/immutable/entry/app.30qqjOPa.js", timeout=30).text
nodes = re.findall(r"\.\./nodes/([^\"]+\.js)", app)
chunks = re.findall(r"\.\./chunks/([^\"]+\.js)", app)
print("nodes", len(set(nodes)), "chunks", len(set(chunks)))

needles = ["graphql", "playersPaginated", "matchesPaginated", "player(", "gql", "fetch(", "POST", "query "]
for rel in list(set(nodes))[:40] + list(set(chunks))[:60]:
    url = "https://pred.gg/_app/immutable/nodes/" + rel if rel in nodes else "https://pred.gg/_app/immutable/chunks/" + rel
    try:
        js = httpx.get(url, timeout=20).text
    except Exception:
        continue
    low = js.lower()
    if any(n.lower() in low for n in needles):
        for n in needles:
            if n.lower() in low:
                i = low.index(n.lower())
                print("===", rel, n, "===")
                print(js[max(0, i - 80) : i + 200])
                break
