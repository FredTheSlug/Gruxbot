import httpx
import re

html = httpx.get("https://pred.gg/", timeout=30).text
scripts = re.findall(r'href="(/_app/immutable/[^"]+\.js)"', html)
for rel in scripts:
    js = httpx.get("https://pred.gg" + rel, timeout=20).text
    if "redirectUri" in js and "generateCodeVerifier" in js:
        print("FILE", rel, "len", len(js))
        for m in re.finditer(r'scope[=:]["\']([^"\']+)["\']', js):
            print(" scope literal", m.group(1))
        i = js.find("generateCodeVerifier")
        print(js[i - 800 : i + 1500])
