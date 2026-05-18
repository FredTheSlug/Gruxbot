"""Probe which token request fields pred.gg rejects (fake code/client)."""
import base64
import httpx

TOKEN = "https://pred.gg/api/oauth2/token"
REDIRECT = "http://127.0.0.1:8765/callback"
VERIFIER = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_-"
HDR = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}

# Use invalid client — we compare error messages / status
cid, secret = "invalid", "invalid"
basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()


def post(label: str, data: dict, *, extra_hdr: dict | None = None) -> None:
    h = dict(HDR)
    if extra_hdr:
        h.update(extra_hdr)
    r = httpx.post(TOKEN, data=data, headers=h, timeout=20)
    print(f"{label:40} {r.status_code} {r.text[:120]}")


full = {
    "grant_type": "authorization_code",
    "code": "fakecode",
    "redirect_uri": REDIRECT,
    "client_id": cid,
    "code_verifier": VERIFIER,
    "scope": "read",
}

post("body secret", {**full, "client_secret": secret})
post("basic no secret in body", full, extra_hdr={"Authorization": f"Basic {basic}"})
post("basic no client_id in body", {k: v for k, v in full.items() if k != "client_id"}, extra_hdr={"Authorization": f"Basic {basic}"})
no_scope = {k: v for k, v in full.items() if k != "scope"}
no_scope["client_secret"] = secret
post("body secret no scope", no_scope)
no_verifier = {k: v for k, v in full.items() if k != "code_verifier"}
no_verifier["client_secret"] = secret
post("body secret no verifier", no_verifier)
post("body secret short verifier", {**full, "client_secret": secret, "code_verifier": "short"})
