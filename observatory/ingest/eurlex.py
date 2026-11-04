"""EUR-Lex documents via the Publications Office CELLAR repository.

One SPARQL query per date window lists works with an (X)HTML manifestation in the requested
language and returns the CELLAR item URLs, which are then fetched directly. eur-lex.europa.eu
itself is not used for text: it answers scripted clients with a bot-check page.
Check with `python -m observatory probe eurlex` before a large run (also run weekly in CI),
and keep the request rate low.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import time
import urllib.parse
import urllib.request

from .base import Document

SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
HUMAN_URL = "https://eur-lex.europa.eu/legal-content/{lang}/TXT/?uri=CELEX:{celex}"  # attribution link
UA = "qv-observatory/0.2 (research; github.com/guilhermegfmachado/qv-observatory)"

# ISO 639-1 -> Publications Office language authority code
LANG3 = {"en": "ENG", "fr": "FRA", "nl": "NLD", "pt": "POR", "de": "DEU", "es": "SPA", "it": "ITA"}

# Sector 5 document types: DC communications/reports, PC legislative proposals, JC joint communications
DEFAULT_TYPES = ("DC", "PC", "JC")

QUERY = """
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?celex ?date (GROUP_CONCAT(DISTINCT STR(?item); separator=" ") AS ?items) WHERE {{
  ?work cdm:resource_legal_id_celex ?celex ;
        cdm:work_date_document ?date .
  FILTER(?date >= "{start}"^^xsd:date && ?date < "{end}"^^xsd:date)
  FILTER(REGEX(STR(?celex), "^{sector}[0-9]{{4}}({types})"))
  ?expr cdm:expression_belongs_to_work ?work ;
        cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/{lang3}> .
  ?manif cdm:manifestation_manifests_expression ?expr ;
         cdm:manifestation_type ?type .
  FILTER(STR(?type) IN ("xhtml", "html"))
  ?item cdm:item_belongs_to_manifestation ?manif .
}} GROUP BY ?celex ?date ORDER BY ?date ?celex LIMIT {limit}
"""


def _get(url: str, accept: str = "text/html, application/xhtml+xml") -> str:
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", "replace")


def _strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def _doc_order(url: str) -> int:
    m = re.search(r"DOC_(\d+)$", url)
    return int(m[1]) if m else 0


def list_works(start: str, end: str, lang: str = "en", sector: str = "5",
               types=DEFAULT_TYPES, limit: int = 500) -> list[tuple[str, str, list[str]]]:
    """(celex, date, item URLs) for works dated in [start, end) with HTML in `lang`."""
    q = QUERY.format(start=start, end=end, sector=sector, types="|".join(types),
                     lang3=LANG3[lang], limit=limit)
    url = f"{SPARQL}?{urllib.parse.urlencode({'query': q, 'format': 'application/sparql-results+json'})}"
    rows = json.loads(_get(url, "application/sparql-results+json"))["results"]["bindings"]
    return [(r["celex"]["value"], r["date"]["value"][:10],
             sorted(r["items"]["value"].split(), key=_doc_order)) for r in rows]


def _windows(start: str, end: str, days: int = 90):
    a, z = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    while a < z:
        b = min(a + dt.timedelta(days=days), z)
        yield a.isoformat(), b.isoformat()
        a = b


def read(start: str, end: str, lang: str = "en", sector: str = "5", limit: int = 500, pause: float = 1.0,
         skip: set[str] = frozenset(), types=DEFAULT_TYPES):
    """Yield up to `limit` new documents dated in [start, end), oldest first.
    `skip`: external ids already stored; their text is not fetched again."""
    n = 0
    for a, b in _windows(start, end):
        for celex, date, items in list_works(a, b, lang, sector, types, limit=10_000):
            if n >= limit:
                return
            ext = f"{celex}:{lang}"
            if ext in skip:
                continue
            try:
                parts = [_strip_html(_get(u)) for u in items]
            except Exception as exc:  # noqa: BLE001 - log and continue
                print(f"  skip {celex}: {exc}")
                continue
            finally:
                time.sleep(pause)
            text = "\n".join(p for p in parts if p)
            if len(text) < 200:
                print(f"  skip {celex}: only {len(text)} chars")
                continue
            n += 1
            yield Document(source="eurlex", external_id=ext, domain="policy", lang=lang, date=date,
                           title=celex, url=HUMAN_URL.format(lang=lang.upper(), celex=celex), text=text)
