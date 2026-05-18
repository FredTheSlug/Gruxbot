import json
import httpx

GQL = "https://pred.gg/gql"
MID = "9d1794a79dae4c3ca4d32f8d1d8913df"


def gql(query: str, variables: dict | None = None) -> dict:
    body: dict = {"query": query}
    if variables:
        body["variables"] = variables
    return httpx.post(GQL, json=body, headers={"Content-Type": "application/json"}, timeout=30).json()


print("MatchPlayer rank-like:", [f["name"] for f in gql(
    '{ t: __type(name: "MatchPlayer") { fields { name } } }'
)["data"]["t"]["fields"] if "rank" in f["name"].lower()])

print("Rating fields:", [f["name"] for f in gql(
    '{ t: __type(name: "Rating") { fields { name } } }'
)["data"]["t"]["fields"]])

print("Rank type:", gql('{ t: __type(name: "Rank") { fields { name } } }'))

for q in [
    """
    query($id: ID!) {
      match(by: {id: $id}) {
        matchPlayers {
          player { name }
          rating { points newPoints name group ranks { id name } }
        }
      }
    }
    """,
    """
    query($id: ID!) {
      match(by: {id: $id}) {
        matchPlayers {
          player { name rank { name } }
        }
      }
    }
    """,
]:
    rr = gql(q, {"id": MID})
    if rr.get("errors"):
        print("ERR", rr["errors"][0]["message"])
    else:
        print(json.dumps(rr["data"]["match"]["matchPlayers"][:3], indent=2))
