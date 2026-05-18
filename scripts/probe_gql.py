import httpx

GQL = "https://pred.gg/gql"
h = {"Content-Type": "application/json"}

q1 = {
    "query": """
    query {
      playersPaginated(filter: {search: "Heygan"}, limit: 3, offset: 0) {
        results { name uuid }
      }
    }
    """
}
r = httpx.post(GQL, json=q1, headers=h, timeout=30)
print("search", r.status_code, r.text[:500])

uuid = "9ac7a82d-0dab-4ca3-ab4f-0ce1b269cd82"
q2 = {
    "query": """
    query($uuid: UUID!) {
      player(by: {uuid: $uuid}) {
        name
        uuid
        matchesPaginated(limit: 3, offset: 0) {
          results {
            match {
              id
              uuid
              gameMode
              startTime
              endTime
            }
          }
        }
      }
    }
    """,
    "variables": {"uuid": uuid},
}
r = httpx.post(GQL, json=q2, headers=h, timeout=30)
print("matches", r.status_code, r.text[:1200])

q3 = {
    "query": """
    query($id: ID!) {
      match(by: {id: $id}) {
        id
        uuid
        gameMode
      }
    }
    """,
    "variables": {"id": "32dc1e65-3275-49c3-b8f1-24f8371d2ea1"},
}
r = httpx.post(GQL, json=q3, headers=h, timeout=30)
print("match by id", r.status_code, r.text[:500])

# introspection partial
q4 = {"query": "{ __type(name: \"Query\") { fields { name } } }"}
r = httpx.post(GQL, json=q4, headers=h, timeout=30)
print("query fields", r.status_code, r.text[:2000])
