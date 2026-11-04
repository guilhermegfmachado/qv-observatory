"""Temporary: check candidate parliament and news APIs from CI."""
import json, re, urllib.parse, urllib.request, urllib.error

UA = {"User-Agent": "qv-observatory/0.2 (research; github.com/guilhermegfmachado/qv-observatory)"}

def get(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.geturl(), r.headers.get("Content-Type"), r.read()
    except urllib.error.HTTPError as e:
        return e.code, url, e.headers.get("Content-Type"), e.read()
    except Exception as e:
        return 0, url, None, str(e).encode()

def show(label, url, headers=None, n=700):
    st, u, ct, body = get(url, headers)
    print(f"\n### {label}\n{st} {ct} {len(body)} {u}\n{body[:n].decode('utf-8','replace')}")
    return st, body

G = "https://api.gdeltproject.org/api/v2/doc/doc?"
show("GDELT timelinevolraw 3mo en", G + urllib.parse.urlencode({"query": "resilience sourcelang:english", "mode": "timelinevolraw", "format": "json", "timespan": "3months"}), n=500)
show("GDELT timelinevolraw 2017 en", G + urllib.parse.urlencode({"query": "resilience sourcelang:english", "mode": "timelinevolraw", "format": "json", "startdatetime": "20170101000000", "enddatetime": "20170301000000"}), n=500)
show("GDELT timelinevolraw pt", G + urllib.parse.urlencode({"query": "resiliência sourcelang:portuguese", "mode": "timelinevolraw", "format": "json", "timespan": "1month", "timelinesmooth": "0"}), n=500)
show("GDELT artlist fr", G + urllib.parse.urlencode({"query": "résilience sourcelang:french", "mode": "artlist", "format": "json", "maxrecords": "3", "timespan": "1week"}), n=600)

E = "https://data.europarl.europa.eu/api/v2/"
show("EP speeches", E + "speeches?" + urllib.parse.urlencode({"format": "application/ld+json", "limit": "3", "offset": "0"}), {"Accept": "application/ld+json"})
show("EP meetings 2025", E + "meetings?" + urllib.parse.urlencode({"year": "2025", "format": "application/ld+json", "limit": "3"}), {"Accept": "application/ld+json"})
show("EP plenary-session-documents", E + "plenary-session-documents?" + urllib.parse.urlencode({"format": "application/ld+json", "limit": "3"}), {"Accept": "application/ld+json"})
st, body = show("doceo CRE html", "https://www.europarl.europa.eu/doceo/document/CRE-10-2025-01-20_EN.html", n=300)
if st == 200:
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body.decode("utf-8", "replace")))
    print("doceo text chars:", len(t), t[2000:2400])
show("doceo CRE xml", "https://www.europarl.europa.eu/doceo/document/CRE-10-2025-01-20_EN.xml", n=300)
show("CLARIN ParlaMint handle", "https://www.clarin.si/repository/xmlui/handle/11356/1912", n=200)
