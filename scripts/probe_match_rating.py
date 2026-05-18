import json
import httpx

GQL = "https://pred.gg/gql"
MID = "9d1794a79dae4c3ca4d32f8d1d8913df"


def gql(query: str, variables: dict | None = None) -> dict:
    body: dict = {"query": query}
    if variables:
        body["variables"] = variables
    return httpx.post(GQL, json=body, headers={"Content-Type": "application/json"}, timeout=30).json()


for type_name in ("MatchPlayerRating", "Rating", "PlayerRating"):
    r = gql(f'{{ t: __type(name: "{type_name}") {{ name fields {{ name type {{ name kind ofType {{ name }} }} }} }} }} }}')
    t = r.get("data", {}).get("t")
    if t:
        print(type_name, [f["name"] for f in t["fields"]])

rr = gql(
    """
    query($id: ID!) {
      match(by: {id: $id}) {
        matchPlayers {
          player { name }
          rating {
            points
            newPoints
            ranks { id name tierName abbreviation tierIdx divisionIdx }
          }
        }
      }
    }
    """,
    {"id": MID},
)
print(json.dumps(rr, indent=2)[:6000])
