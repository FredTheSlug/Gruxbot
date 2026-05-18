import httpx
import json

GQL = "https://pred.gg/gql"
h = {"Content-Type": "application/json"}


def gql(query):
    return httpx.post(GQL, json={"query": query}, headers=h, timeout=30).json()


for t in ["LeaderboardFilterInput", "PlayerRating", "MatchPlayer"]:
    r = gql(f'{{ __type(name: "{t}") {{ inputFields {{ name type {{ name kind ofType {{ name }} }} }} fields {{ name type {{ name kind ofType {{ name ofType {{ name }} }} }} }} }} }}')
    print(t, json.dumps(r, indent=2)[:1500])
    print("---")

mid = "32dc1e65-3275-49c3-b8f1-24f8371d2ea1"
print(gql(f"""
{{
  match(by: {{id: "{mid}"}}) {{
    id uuid gameMode startTime endTime
    matchPlayers {{
      player {{ uuid name }}
    }}
  }}
}}
"""))
