import httpx

GQL = "https://pred.gg/gql"
h = {"Content-Type": "application/json"}


def gql(query, variables=None):
    body = {"query": query}
    if variables:
        body["variables"] = variables
    return httpx.post(GQL, json=body, headers=h, timeout=30).json()


# leaderboardPaginated schema guess from error
for rating_id in ["11", "5"]:
    q = """
    query($ratingId: Query!, $limit: Int, $offset: Int, $search: String) {
      leaderboardPaginated(ratingId: $ratingId, limit: $limit, offset: $offset, filter: {search: $search}) {
        results {
          player { name uuid }
        }
      }
    }
    """
    # ratingId type might be ID not Query - introspect
    pass

# introspect leaderboardPaginated
intro = gql("""
{
  __type(name: "Query") {
    fields(includeDeprecated: true) {
      name
      args { name type { kind name ofType { name kind } } }
    }
  }
}
""")
for f in intro.get("data", {}).get("__type", {}).get("fields", []):
    if f["name"] in ("leaderboardPaginated", "player", "playersPaginated"):
        print(f["name"], f.get("args"))

# introspect Player type
intro2 = gql("{ __type(name: \"Player\") { fields { name } } }")
print("Player fields:", [x["name"] for x in intro2.get("data", {}).get("__type", {}).get("fields", [])])

# Try leaderboard with ID type
q = """
query {
  leaderboardPaginated(ratingId: "11", limit: 5, offset: 0) {
    results {
      rank
      player { name uuid }
    }
  }
}
"""
print(gql(q))
