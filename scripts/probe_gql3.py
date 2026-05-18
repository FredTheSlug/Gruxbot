import httpx

GQL = "https://pred.gg/gql"
h = {"Content-Type": "application/json"}


def run(name, query, variables=None):
    body = {"query": query}
    if variables:
        body["variables"] = variables
    r = httpx.post(GQL, json=body, headers=h, timeout=30)
    print("===", name, "===")
    print(r.text[:1200])
    print()


uuid = "9ac7a82d-0dab-4ca3-ab4f-0ce1b269cd82"

run(
    "player generalStatistic",
    """
    query($uuid: UUID!) {
      player(by: {uuid: $uuid}) {
        name uuid
        generalStatistic {
          result {
            matchesPlayed
          }
        }
      }
    }
    """,
    {"uuid": uuid},
)

run(
    "players list",
    """
    query { players { name uuid } }
    """,
)

run(
    "backend",
    """
    query { backend { __typename } }
    """,
)

# ratings for leaderboard
run(
    "ratings",
    """
    query { ratings { id name } }
    """,
)

run(
    "leaderboard with rating",
    """
    query {
      ratings { id name }
    }
    """,
)

# Try match list via application or connectionInfo
run("connectionInfo", "query { connectionInfo { __typename } }")

# omeda still?
import httpx as hx

pid = uuid
r = hx.get(f"https://omeda.city/players/{pid}/matches.json", params={"page": 0, "per_page": 3}, timeout=30)
print("=== omeda matches ===", r.status_code, r.text[:400])
