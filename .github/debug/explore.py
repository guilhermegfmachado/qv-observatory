"""Temporary: round 3, EP plenary verbatim XML on data.europarl.europa.eu."""
import json, re, urllib.parse, urllib.request, urllib.error
from collections import Counter

UA = {"User-Agent": "qv-observatory/0.2 (research; github.com/guilhermegfmachado/qv-observatory)"}

def get(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.geturl(), r.headers.get("Content-Type"), r.read()
    except urllib.error.HTTPError as e:
        return e.code, url, e.headers.get("Content-Type"), e.read()
    except Exception as e:
        return 0, url, None, str(e).encode()

for u in ["https://data.europarl.europa.eu/distribution/doc/CRE-10-2024-07-16_mul.xml",
          "https://data.europarl.europa.eu/api/v2/distribution/doc/CRE-10-2024-07-16_mul.xml"]:
    st, url, ct, body = get(u)
    print(f"\n### {u}\n{st} {ct} {len(body)} {url}")
    if st == 200:
        t = body.decode("utf-8", "replace")
        print(t[:1500])
        tags = Counter(re.findall(r"<([A-Za-z][\w.-]*)", t))
        print("TAGS", tags.most_common(40))
        print("LANG ATTRS", Counter(re.findall(r'(?:xml:)?lang(?:uage)?="([^"]+)"', t)).most_common(30))
        i = t.find("resilien")
        print("SNIPPET", t[max(0, i - 1500):i + 300] if i > 0 else t[20000:22000])
        break

st, url, ct, body = get("https://data.europarl.europa.eu/api/v2/plenary-session-documents?" + urllib.parse.urlencode(
    {"year": "2025", "work-type": "CRE_PLENARY", "format": "application/ld+json", "limit": "5"}), {"Accept": "application/ld+json"})
print("\n### list year=2025", st, len(body), body[:800].decode("utf-8", "replace"))
st, url, ct, body = get("https://data.europarl.europa.eu/api/v2/plenary-session-documents?" + urllib.parse.urlencode(
    {"format": "application/ld+json", "limit": "5", "offset": "2000"}), {"Accept": "application/ld+json"})
print("\n### list offset=2000", st, len(body), body[:800].decode("utf-8", "replace"))
