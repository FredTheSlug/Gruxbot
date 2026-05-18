import json
import httpx

GQL = "https://pred.gg/gql"
h = {"Content-Type": "application/json"}


def gql(q: str, variables: dict | None = None) -> dict:
    body: dict = {"query": q}
    if variables:
        body["variables"] = variables
    return httpx.post(GQL, json=body, headers=h, timeout=30).json()


print(
    json.dumps(
        gql(
            """
            {
              matchPlayerType: __type(name: "MatchPlayer") {
                fields { name }
              }
            }
            """
        ),
        indent=2,
    )[:2000]
)

mid = "9d1794a79dae4c3ca4d32f8d1d8913df"
r = gql(
    """
    query($id: ID!) {
      match(by: {id: $id}) {
        matchPlayers {
          role
          hero { slug data { displayName icon } }
          heroData { displayName icon }
        }
      }
    }
    """,
    {"id": mid},
)
print(json.dumps(r, indent=2)[:4000])

for icon in ("2c827fcff5a02da5",):
    url = f"https://pred.gg/assets/{icon}.png"
    resp = httpx.get(url, timeout=15)
    print("asset", url, resp.status_code, resp.headers.get("content-type"), len(resp.content))
