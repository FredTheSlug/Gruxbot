import json

import httpx

GQL = "https://pred.gg/gql"
MID = "9d1794a79dae4c3ca4d32f8d1d8913df"


def gql(query: str, variables: dict | None = None) -> dict:
    body: dict = {"query": query}
    if variables:
        body["variables"] = variables
    return httpx.post(GQL, json=body, headers={"Content-Type": "application/json"}, timeout=30).json()


r = gql(
    """
    {
      mp: __type(name: "MatchPlayer") {
        fields {
          name
          type { kind name ofType { kind name ofType { name } } }
        }
      }
    }
    """
)
for f in r.get("data", {}).get("mp", {}).get("fields", []):
    if f.get("name") == "role":
        print("role field type:", json.dumps(f, indent=2))

r = gql(
    """
    query($id: ID!) {
      match(by: {id: $id}) {
        matchPlayers {
          role
          hero { slug }
        }
      }
    }
    """,
    {"id": MID},
)
print("roles in match:", json.dumps(r, indent=2)[:1500])

# try roles query
for q in [
    "{ roles { id slug data { icon name displayName } } }",
    "{ roles { id slug icon } }",
    """
    {
      carry: role(by: {slug: "carry"}) { slug data { icon } }
    }
    """,
]:
    rr = gql(q)
    if rr.get("errors"):
        print("ERR", q[:40], rr["errors"][0]["message"][:100])
    else:
        print("OK", q[:40], json.dumps(rr.get("data"), indent=2)[:800])
