"""European Parliament plenary debates (verbatim reports, CRE) from the EP Open Data Portal.

The API lists sittings (plenary-session-documents of type CRE_PLENARY); each sitting's
multilingual XML is downloaded from data.europarl.europa.eu/distribution. Every speech
(INTERVENTION) carries the speaker's language (ORATEUR LG), so one sitting becomes one
document per language, holding the speeches given in that language. Speaker names are not
stored. europarl.europa.eu/doceo is not used: it refuses scripted clients.
"""
from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from .base import Document

API = "https://data.europarl.europa.eu/api/v2/plenary-session-documents"
BASE = "https://data.europarl.europa.eu/"
HUMAN_URL = "https://www.europarl.europa.eu/doceo/document/{id}_EN.html"  # attribution link
UA = "qv-observatory/0.2 (research; github.com/guilhermegfmachado/qv-observatory)"
ID_RE = re.compile(r"^CRE-(\d+)-(\d{4}-\d{2}-\d{2})$")
LANGS = {"EN": "en", "FR": "fr", "NL": "nl", "PT": "pt", "DE": "de", "ES": "es", "IT": "it"}

_INTERVENTION = re.compile(r"<INTERVENTION\b.*?</INTERVENTION\s*>", re.S)
_SPEAKER_LANG = re.compile(r'<ORATEUR\b[^>]*\bLG="([A-Z]{2})"')
_PARA = re.compile(r"<PARA\b[^>]*>(.*?)</PARA\s*>", re.S)
_STAGE = re.compile(r"^\(.*\)$")  # "(Applause)", "(The sitting was suspended)"


def _get(url: str, accept: str) -> bytes:
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def list_sittings(page: int = 500) -> list[tuple[str, str]]:
    """All (sitting id, date) for plenary verbatim reports, oldest first."""
    out, offset = {}, 0
    while True:
        q = urllib.parse.urlencode({"work-type": "CRE_PLENARY", "format": "application/ld+json",
                                    "limit": page, "offset": offset})
        data = json.loads(_get(f"{API}?{q}", "application/ld+json")).get("data", [])
        for d in data:
            m = ID_RE.match(d.get("identifier", ""))
            if m:
                out[d["identifier"]] = m[2]
        if len(data) < page:
            break
        offset += page
    return sorted(out.items(), key=lambda kv: (kv[1], kv[0]))


def xml_url(sid: str) -> str | None:
    """URL of the sitting's multilingual XML as the API lists it, or None if not published yet."""
    q = urllib.parse.urlencode({"format": "application/ld+json"})
    data = json.loads(_get(f"{API}/{sid}?{q}", "application/ld+json")).get("data", [])
    for work in data:
        for expr in work.get("is_realized_by", []):
            for man in expr.get("is_embodied_by", []):
                if str(man.get("format", "")).endswith("/XML") and man.get("is_exemplified_by"):
                    return urllib.parse.urljoin(BASE, man["is_exemplified_by"])
    return None


def parse(xml: str) -> dict[str, list[str]]:
    """Speech paragraphs per speaker language: {"EN": [...], "FR": [...]}."""
    by_lang: dict[str, list[str]] = {}
    for iv in _INTERVENTION.findall(xml):
        m = _SPEAKER_LANG.search(iv)
        if not m:
            continue
        for raw in _PARA.findall(iv):
            text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()
            if text and not _STAGE.match(text):
                by_lang.setdefault(m[1], []).append(text)
    return by_lang


def _fetch_sitting(sid: str):
    try:
        url = xml_url(sid)
        if not url:
            return None, "no XML published yet"
        return _get(url, "*/*").decode("utf-8", "replace"), None
    except Exception as exc:  # noqa: BLE001 - reported by the caller
        return None, exc


def read(start: str = "2014-01-01", limit: int = 100, workers: int = 4, skip: set[str] = frozenset()):
    """Yield documents for up to `limit` sittings dated >= start that are not yet stored,
    fetched `workers` at a time. `skip`: sitting ids already stored."""
    todo = [(sid, date) for sid, date in list_sittings() if date >= start and sid not in skip][:limit]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for (sid, date), (xml, err) in zip(todo, pool.map(_fetch_sitting, [s for s, _ in todo])):
            if xml is None:
                print(f"  skip {sid}: {err}")
                continue
            for lg, paras in parse(xml).items():
                lang = LANGS.get(lg)
                if not lang or sum(map(len, paras)) < 200:
                    continue
                yield Document(source="europarl", external_id=f"{sid}:{lang}", domain="parliament",
                               lang=lang, date=date, country="EU", title=sid,
                               url=HUMAN_URL.format(id=sid), text="\n".join(paras))
