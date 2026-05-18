"""Probe pred.gg token endpoint auth style (invalid code — inspect error body)."""
import base64
import httpx

TOKEN = "https://pred.gg/api/oauth2/token"
cid = "invalid"
secret = "invalid"
base = {
    "grant_type": "authorization_code",
    "code": "invalidcode",
    "redirect_uri": "http://127.0.0.1:8765/callback",
    "code_verifier": "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG",
    "scope": "read",
    "client_id": cid,
}
basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
hdr = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}

variants = [
    ("secret_in_body", base | {"client_secret": secret}, {}),
    ("basic_no_body_secret", base, {"Authorization": f"Basic {basic}"}),
    ("basic_no_client_id_in_body", {k: v for k, v in base.items() if k != "client_id"}, {"Authorization": f"Basic {basic}"}),
]

for name, data, extra in variants:
    r = httpx.post(TOKEN, data=data, headers={**hdr, **extra}, timeout=20)
    print(name, r.status_code, r.text[:250])
