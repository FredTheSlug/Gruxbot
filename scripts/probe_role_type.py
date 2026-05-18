import httpx

for name in ("Role", "MatchPlayer"):
    r = httpx.post(
        "https://pred.gg/gql",
        json={
            "query": """
            query($n: String!) {
              t: __type(name: $n) {
                kind
                enumValues { name }
                fields { name type { name kind ofType { name } } }
              }
            }
            """,
            "variables": {"n": name},
        },
        timeout=30,
    ).json()
    print(name, r.get("data", {}).get("t"))
