import json
import httpx

GQL = "https://pred.gg/gql"
h = {"Content-Type": "application/json"}


def gql(query: str, variables: dict | None = None) -> dict:
    body: dict = {"query": query}
    if variables:
        body["variables"] = variables
    return httpx.post(GQL, json=body, headers=h, timeout=30).json()


print("Rank fields", gql('{ __type(name: "Rank") { fields { name } } }'))

mid = "9d1794a79dae4c3ca4d32f8d1d8913df"
r = gql(
    """
    query($id: ID!) {
      match(by: {id: $id}) {
        id uuid duration gameMode region startTime endTime winningTeam
        matchPlayers {
          team
          kills
          deaths
          assists
          role
          hero { slug data { displayName } }
          player { name uuid }
          rating { points newPoints rank { id name } }
        }
      }
    }
    """,
    {"id": mid},
)
print(json.dumps(r, indent=2)[:16000])
