import httpx
import json

GQL = "https://pred.gg/gql"
h = {"Content-Type": "application/json"}


def gql(query):
    return httpx.post(GQL, json={"query": query}, headers=h, timeout=30).json()


print(gql("""
query {
  leaderboardPaginated(ratingId: "11", limit: 5, offset: 0, filter: {playerName: "Heygan"}) {
    results {
      peakRanking
      player { name uuid }
    }
  }
}
"""))

# Get current rating id from ratings - use latest split
ratings = gql("query { ratings { id name } }")
print("ratings", ratings)
