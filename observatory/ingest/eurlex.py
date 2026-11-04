"""EUR-Lex via the Publications Office CELLAR SPARQL endpoint, then HTML full text.

Check with `python -m observatory probe eurlex` before a large run (also run weekly in CI), and keep the
request rate low. Fetches one language manifestation per document.
"""
from __future__ import annotations

import html
import json
import re
import time
import urllib.parse
import urllib.request

from .base import Document

SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
TEXT_URL = "https://eur-lex.europa.eu/legal-content/{lang}/TXT/HTML/?uri=CELEX:{celex}"

QUERY = """
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT DISTINCT ?celex ?date WHERE {{
  ?work cdm:resource_legal_id_celex ?celex ;
        cdm:work_date_document ?date .
  FILTER(?date >= "{start}"^^xsd:date && ?date < "{end}"^^xsd:date)
  FILTER(STRSTARTS(STR(?celex), "{sector}"))
}} ORDER BY ?date ?celex LIMIT {limit}
"""


def _get(url: str, accept: str = "text/html") -> str:
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "qv-observatory/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def _strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def read(start: str, end: str, lang: str = "en", sector: str = "5", limit: int = 500, pause: float = 1.0,
         skip: set[str] = frozenset()):
    """sector '5' = preparatory acts (communications, proposals); '3' = legislation.
    `skip`: external ids already stored; their text is not fetched again."""
    q = QUERY.format(start=start, end=end, sector=sector, limit=limit)
    url = f"{SPARQL}?{urllib.parse.urlencode({'query': q, 'format': 'application/sparql-results+json'})}"
    rows = json.loads(_get(url, "application/sparql-results+json"))["results"]["bindings"]
    for row in rows:
        celex, date = row["celex"]["value"], row["date"]["value"][:10]
        if f"{celex}:{lang}" in skip:
            continue
        text_url = TEXT_URL.format(lang=lang.upper(), celex=celex)
        try:
            text = _strip_html(_get(text_url))
        except Exception as exc:  # noqa: BLE001 - log and continue
            print(f"  skip {celex}: {exc}")
            continue
        time.sleep(pause)
        if len(text) < 200:
            continue
        yield Document(source="eurlex", external_id=f"{celex}:{lang}", domain="policy",
                       lang=lang, date=date, title=celex, url=text_url, text=text)
