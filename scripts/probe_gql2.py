import httpx

GQL = "https://pred.gg/gql"
h = {"Content-Type": "application/json"}


def run(name, query, variables=None):
    body = {"query": query}
    if variables:
        body["variables"] = variables
    r = httpx.post(GQL, json=body, headers=h, timeout=30)
    print("===", name, r.status_code, "===")
    print(r.text[:900])
    print()


uuid = "9ac7a82d-0dab-4ca3-ab4f-0ce1b269cd82"

run(
    "player basic",
    """
    query($uuid: UUID!) {
      player(by: {uuid: $uuid}) {
        name uuid favRegion favRole
        generalStatistic { result { matchesPlayed wins } }
      }
    }
    """,
    {"uuid": uuid},
)

run(
    "leaderboard",
    """
    query {
      leaderboardPaginated(limit: 3, offset: 0) {
        results { player { name uuid } }
      }
    }
    """,
)

run(
    "heroes",
    """
    query {
      heroes { id slug data { name displayName } }
    }
    """,
)

run(
    "items",
    """
    query {
      items { id slug data { name displayName } }
    }
    """,
)

run(
    "hero by slug",
    """
    query {
      hero(by: {slug: "grux"}) { id slug data { name } }
    }
    """,
)

run(
    "item by slug",
    """
    query {
      item(by: {slug: "sages-ring"}) { id slug data { name } }
    }
    """,
)
