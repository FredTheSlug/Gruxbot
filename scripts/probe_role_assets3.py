import json

import httpx

GQL = "https://pred.gg/gql"
r = httpx.post(
    GQL,
    json={
        "query": """
        {
          __type(name: "Query") {
            fields { name }
          }
        }
        """
    },
    timeout=30,
).json()
names = [f["name"] for f in r["data"]["__type"]["fields"]]
print([n for n in names if "role" in n.lower() or "lane" in n.lower()])

# match with roleData?
mid = "9d1794a79dae4c3ca4d32f8d1d8913df"
for fields in [
    "role roleData { icon displayName }",
    "role hero { slug }",
]:
    q = f'query($id: ID!) {{ match(by: {{id: $id}}) {{ matchPlayers {{ {fields} }} }} }}'
    rr = httpx.post(GQL, json={"query": q, "variables": {"id": mid}}, timeout=30).json()
    if rr.get("errors"):
        print(fields, rr["errors"][0]["message"][:100])
    else:
        print(fields, json.dumps(rr["data"]["match"]["matchPlayers"][0], indent=2))
