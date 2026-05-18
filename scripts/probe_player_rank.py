import json

import httpx

GQL = "https://pred.gg/gql"
MID = "9d1794a79dae4c3ca4d32f8d1d8913df"
PID = "41a5b34d-915c-4651-ac0e-0376fd23424c"  # Seabass


def gql(query: str, variables: dict | None = None) -> dict:
    body: dict = {"query": query}
    if variables:
        body["variables"] = variables
    return httpx.post(GQL, json=body, headers={"Content-Type": "application/json"}, timeout=30).json()


intro = gql('{ t: __type(name: "Player") { fields { name } } }')
print("Player fields:", [f["name"] for f in intro["data"]["t"]["fields"] if "rank" in f["name"].lower() or "rating" in f["name"].lower()])

print(
    "PlayerRating fields:",
    gql('{ t: __type(name: "PlayerRating") { fields { name } } }')["data"]["t"]["fields"],
)

for qname, q in [
    (
        "player ratings",
        """
        query($uuid: UUID!) {
          player(by: {uuid: $uuid}) {
            name
            ratings { id points rank { id name abbreviation icon } rating { id name } }
          }
        }
        """,
    ),
    (
        "player rating",
        """
        query($uuid: UUID!) {
          player(by: {uuid: $uuid}) {
            name
            rating { id name rank { id name abbreviation icon } points }
          }
        }
        """,
    ),
    (
        "player peakRanking",
        """
        query($uuid: UUID!) {
          player(by: {uuid: $uuid}) {
            name
            peakRanking { id name }
          }
        }
        """,
    ),
]:
    r = gql(q, {"uuid": PID})
    if r.get("errors"):
        print(qname, "ERR", r["errors"][0]["message"][:120])
    else:
        print(qname, json.dumps(r.get("data"), indent=2)[:2000])

# unranked / non-ranked match sample - find a TEAM_VS or casual match
r = gql(
    """
    query($id: ID!) {
      match(by: {id: $id}) {
        gameMode
        matchPlayers {
          player { uuid name }
          rating { points newPoints rank { id name icon } }
        }
      }
    }
    """,
    {"id": MID},
)
print("ranked sample mode", r.get("data", {}).get("match", {}).get("gameMode"))
print(json.dumps(r["data"]["match"]["matchPlayers"][6], indent=2))
