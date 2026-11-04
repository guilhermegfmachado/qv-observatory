"""Temporary: round 4, EP INTERVENTION structure; GDELT static files."""
import gzip, io, json, re, urllib.request, urllib.error, datetime as dt

UA = {"User-Agent": "qv-observatory/0.2 (research; github.com/guilhermegfmachado/qv-observatory)"}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.headers.get("Content-Type"), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type"), e.read()
    except Exception as e:
        return 0, None, str(e).encode()

st, ct, b = get("https://data.europarl.europa.eu/distribution/doc/CRE-10-2024-07-16_mul.xml")
t = b.decode("utf-8", "replace")
i = t.find("<INTERVENTION")
print("### INTERVENTION 1\n", t[i:i + 2500])
j = t.find("<INTERVENTION", i + 10)
print("### INTERVENTION 2\n", t[j:j + 1200])
print("### LG values", sorted(set(re.findall(r"<LG[^>]*>\s*([^<]*)<", t)))[:40])
print("### CHAPTER head\n", t[t.find("<CHAPTER"):t.find("<CHAPTER") + 600])

now = dt.datetime.utcnow().replace(second=0, microsecond=0) - dt.timedelta(hours=3)
stamp = now.strftime("%Y%m%d%H%M00")
for u in [f"http://data.gdeltproject.org/gdeltv3/webngrams/{stamp}.webngrams.json.gz",
          "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"]:
    st, ct, body = get(u)
    print(f"\n### {u}\n{st} {ct} {len(body)}")
    if st == 200 and u.endswith(".gz"):
        lines = gzip.decompress(body).decode("utf-8", "replace").splitlines()
        print("lines", len(lines))
        for l in lines[:3]:
            print(l[:600])
        langs = {}
        for l in lines:
            try:
                o = json.loads(l)
            except Exception:
                continue
            langs[o.get("lang")] = langs.get(o.get("lang"), 0) + 1
        print("langs", sorted(langs.items(), key=lambda x: -x[1])[:12])
    elif st == 200:
        print(body[:500].decode())
