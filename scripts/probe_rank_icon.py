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
    query($id: ID!) {
      match(by: {id: $id}) {
        matchPlayers {
          player { name }
          rating { rank { id name icon abbreviation } }
        }
      }
    }
    """,
    {"id": MID},
)
players = r["data"]["match"]["matchPlayers"]
print(json.dumps(players[:3], indent=2))

icon = players[0]["rating"]["rank"]["icon"]
for url in (
    f"https://pred.gg/assets/{icon}.png",
    f"https://pred.gg/assets/{icon}",
    f"https://pred.gg/images/ranks/{icon}.png",
):
    resp = httpx.get(url, timeout=15)
    print(url, resp.status_code, resp.headers.get("content-type"), len(resp.content))
