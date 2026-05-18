import httpx

GQL = "https://pred.gg/gql"
h = {"Content-Type": "application/json"}


def gql(query, variables=None):
    body = {"query": query}
    if variables:
        body["variables"] = variables
    return httpx.post(GQL, json=body, headers=h, timeout=30).json()


print(gql("""
query {
  leaderboardPaginated(ratingId: "11", limit: 5, offset: 0, filter: {search: "Heygan"}) {
    results {
      position
      player { name uuid }
    }
  }
}
"""))

# Match type fields
intro = gql("{ __type(name: \"Match\") { fields { name } } }")
print("Match fields:", [x["name"] for x in intro.get("data", {}).get("__type", {}).get("fields", [])[:30]])

mid = "32dc1e65-3275-49c3-b8f1-24f8371d2ea1"
print(gql("""
query($id: ID!) {
  match(by: {id: $id}) {
    id uuid gameMode startTime endTime region
    players { player { uuid name } hero { slug } }
  }
}
""", {"id": mid}))
