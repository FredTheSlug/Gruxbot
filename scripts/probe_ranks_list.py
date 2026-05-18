import json
import httpx

GQL = "https://pred.gg/gql"


def gql(query: str) -> dict:
    return httpx.post(GQL, json={"query": query}, headers={"Content-Type": "application/json"}, timeout=30).json()


intro = gql('{ __type(name: "Query") { fields { name } } }')
names = [f["name"] for f in intro["data"]["__type"]["fields"]]
print("rank query fields:", [n for n in names if "rank" in n.lower()])

for q in [
    '{ rating(id: "11") { id name ranks { id name tierName abbreviation } } }',
    '{ rating(by: {id: "11"}) { id name ranks { id name tierName abbreviation } } }',
    """
    query($id: ID!) {
      match(by: {id: $id}) {
        matchPlayers { rating { rank { id name tierName abbreviation } } }
      }
    }
    """,
]:
    variables = {"id": "9d1794a79dae4c3ca4d32f8d1d8913df"} if "match(by" in q else None
    r = gql(q) if variables is None else httpx.post(
        GQL,
        json={"query": q, "variables": variables},
        headers={"Content-Type": "application/json"},
        timeout=30,
    ).json()
    label = q.strip().split("\n")[0][:50]
    if r.get("errors"):
        print(label, "ERR", r["errors"][0]["message"][:120])
    else:
        print(label, json.dumps(r.get("data"), indent=2)[:1200])

r = gql('{ rating(by: {id: "11"}) { ranks { id name abbreviation } } }')
ranks = r["data"]["rating"]["ranks"]
for rid in ("40", "41", "42", "33", "32"):
    hit = next((x for x in ranks if x["id"] == rid), None)
    print(rid, hit)
