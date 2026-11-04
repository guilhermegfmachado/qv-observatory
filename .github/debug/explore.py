"""Temporary: second round on EP API, GDELT pacing, ParlaMint links."""
import json, re, time, urllib.parse, urllib.request, urllib.error

UA = {"User-Agent": "qv-observatory/0.2 (research; github.com/guilhermegfmachado/qv-observatory)"}

def get(url, headers=None, method="GET"):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, r.geturl(), r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, url, e.headers, e.read()
    except Exception as e:
        return 0, url, {}, str(e).encode()

def show(label, url, headers=None, n=3000):
    st, u, hd, body = get(url, headers)
    print(f"\n### {label}\n{st} {hd.get('Content-Type') if hd else None} {len(body)} {u}\n{body[:n].decode('utf-8','replace')}")
    return st, body

LD = {"Accept": "application/ld+json"}
E = "https://data.europarl.europa.eu/api/v2/"
st, b = show("EP speeches 1 full", E + "speeches?" + urllib.parse.urlencode({"format": "application/ld+json", "limit": "1", "offset": "200"}), LD, 6000)
show("EP speech by id", E + "speeches/MTG-PL-2024-01-17-OTH-32020000?format=application%2Fld%2Bjson", LD, 4000)
st, b = show("EP CRE doc", E + "plenary-session-documents/CRE-10-2024-07-16?format=application%2Fld%2Bjson", LD, 5000)
urls = sorted(set(re.findall(rb'https?://[^"\s]+', b)))
print("URLs in CRE doc:", [u.decode() for u in urls][:40])
for u in urls:
    us = u.decode()
    if any(x in us for x in (".xml", ".html", ".pdf", ".docx", "download", "/doc/")) and "europarl.europa.eu/doceo" not in us:
        st2, _, hd2, body2 = get(us)
        print("  try", st2, hd2.get("Content-Type") if hd2 else None, len(body2), us)

G = "https://api.gdeltproject.org/api/v2/doc/doc?"
for label, params in [
    ("GDELT 3mo en", {"query": "resilience sourcelang:english", "mode": "timelinevolraw", "format": "json", "timespan": "3months", "timelinesmooth": "0"}),
    ("GDELT 2017 en", {"query": "resilience sourcelang:english", "mode": "timelinevolraw", "format": "json", "startdatetime": "20170101000000", "enddatetime": "20170301000000"}),
    ("GDELT 2y en", {"query": "resilience sourcelang:english", "mode": "timelinevolraw", "format": "json", "startdatetime": "20240101000000", "enddatetime": "20241231000000"}),
    ("GDELT OR pt", {"query": "(resiliência OR resiliente) sourcelang:portuguese", "mode": "timelinevolraw", "format": "json", "timespan": "1month"}),
]:
    time.sleep(7)
    st, body = show(label, G + urllib.parse.urlencode(params), n=600)
    if st == 200 and body.strip():
        try:
            d = json.loads(body)
            for s in d.get("timeline", []):
                pts = s.get("data", [])
                print("  series", s.get("series"), len(pts), "points; first", pts[:1], "last", pts[-1:])
        except Exception as e:
            print("  parse error", e)

st, b = get("https://www.clarin.si/repository/xmlui/handle/11356/1912")[0:4:3] if False else (None, None)
st, u, hd, body = get("https://www.clarin.si/repository/xmlui/handle/11356/1912")
t = body.decode("utf-8", "replace")
title = re.search(r"<title>(.*?)</title>", t, re.S)
print("\n### ParlaMint handle title:", title and title[1].strip())
links = sorted(set(re.findall(r'href="([^"]*ParlaMint-(?:PT|NL|FR|BE|GB)[^"]*)"', t)))
print("links:", links[:30])
for l in links:
    if l.endswith(".tgz") and ".txt" in l:
        full = urllib.parse.urljoin("https://www.clarin.si", l)
        st, _, hd, _ = get(full, method="HEAD")
        print("  HEAD", st, hd.get("Content-Length") if hd else None, full)
