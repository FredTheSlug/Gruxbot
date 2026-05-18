"""Introspect pred.gg match GraphQL for rich embed fields."""
import json
import httpx

GQL = "https://pred.gg/gql"
h = {"Content-Type": "application/json", "Accept": "application/json"}


def gql(query: str, variables: dict | None = None) -> dict:
    body: dict = {"query": query}
    if variables:
        body["variables"] = variables
    return httpx.post(GQL, json=body, headers=h, timeout=30).json()


# Full introspection for Match and MatchPlayer
q = """
{
  matchType: __type(name: "Match") {
    fields { name type { kind name ofType { kind name ofType { name } } } }
  }
  mpType: __type(name: "MatchPlayer") {
    fields { name type { kind name ofType { kind name ofType { name } } } }
  }
}
"""
print(json.dumps(gql(q), indent=2)[:12000])

mid = "9d1794a79dae4c3ca4d32f8d1d8913df"
# minimal then expand
for fields in [
    "id uuid gameMode startTime endTime region duration",
    "id uuid gameMode startTime endTime region duration matchPlayers { player { name uuid } }",
]:
    r = gql(
        f'query($id: ID!) {{ match(by: {{id: $id}}) {{ {fields} }} }}',
        {"id": mid},
    )
    print("\n--- fields:", fields[:60], "---")
    if r.get("errors"):
        print("ERR", r["errors"][0].get("message"))
    else:
        print(json.dumps(r.get("data"), indent=2)[:4000])
