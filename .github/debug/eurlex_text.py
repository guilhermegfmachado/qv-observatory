"""Temporary: try ways of fetching EUR-Lex full text from CI."""
import json, re, urllib.parse, urllib.request, urllib.error

UA = {"User-Agent": "qv-observatory/0.2 (research; github.com/guilhermegfmachado/qv-observatory)"}
SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"

def get(url, headers=None, method="GET"):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.geturl(), r.headers.get("Content-Type"), r.read()
    except urllib.error.HTTPError as e:
        return e.code, url, e.headers.get("Content-Type"), e.read()

def sparql(q):
    url = f"{SPARQL}?{urllib.parse.urlencode({'query': q, 'format': 'application/sparql-results+json'})}"
    return json.loads(get(url, {"Accept": "application/sparql-results+json"})[3])["results"]["bindings"]

for celex in ["52026DC0446", "52023DC0062"]:
    print("=====", celex)
    # A: content negotiation on the CELEX resource URI
    for acc in ["application/xhtml+xml", "text/html", "application/xhtml+xml, text/html;q=0.9"]:
        st, u, ct, body = get(f"https://publications.europa.eu/resource/celex/{celex}",
                              {"Accept": acc, "Accept-Language": "eng"})
        print("A", acc, st, ct, len(body), u)
        if st == 300:
            print("   300 body:", body[:600])
    # B: SPARQL for manifestations of the English expression
    q = f"""PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT ?manif ?type ?item WHERE {{
  ?work cdm:resource_legal_id_celex "{celex}"^^<http://www.w3.org/2001/XMLSchema#string> .
  ?expr cdm:expression_belongs_to_work ?work ;
        cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> .
  ?manif cdm:manifestation_manifests_expression ?expr ;
         cdm:manifestation_type ?type .
  OPTIONAL {{ ?item cdm:item_belongs_to_manifestation ?manif }}
}} LIMIT 20"""
    try:
        rows = sparql(q)
    except Exception as e:
        rows = []; print("B error", e)
    print("B rows", len(rows))
    for r in rows:
        print("  ", r["type"]["value"], r["manif"]["value"], r.get("item", {}).get("value"))
    for r in rows:
        if r["type"]["value"] in ("xhtml", "html") and "item" in r:
            st, u, ct, body = get(r["item"]["value"])
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body.decode("utf-8", "replace")))
            print("B fetch", st, ct, len(text), text[:200])
            break
