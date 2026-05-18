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
        fields { name }
      }
    }
    """
)
fields = sorted(f["name"] for f in r["data"]["mp"]["fields"])
print("all fields:", fields)
for kw in ("cs", "creep", "minion", "farm", "score", "performance"):
    print(kw, [f for f in fields if kw in f.lower()])

rr = gql(
    """
    query($id: ID!) {
      match(by: {id: $id}) {
        matchPlayers {
          player { name }
          laneMinionsKilled
          minionsKilled
          neutralMinionsKilled
          neutralMinionsEnemyJungle
          neutralMinionsTeamJungle
        }
      }
    }
    """,
    {"id": MID},
)
print(json.dumps(rr, indent=2)[:4000])
