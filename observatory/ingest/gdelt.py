"""News volume from the GDELT DOC 2.0 API (no article text: counts only).

For each concept and language, `timelinevolraw` returns per-day counts of matching articles
("value") and of all articles GDELT monitored in that language ("norm"), from 2017 onward.
These go to the `counts` table and enter the news lane as hits / total.

GDELT asks for at most one request every 5 seconds; shared CI addresses still get throttled
at times, so requests are paced and retried with backoff. Query terms come from the
`gdelt` table of each concept in config/observatory.toml (GDELT has no wildcards).
"""
from __future__ import annotations

import datetime as dt
import json
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.gdeltproject.org/api/v2/doc/doc"
UA = "qv-observatory/0.2 (research; github.com/guilhermegfmachado/qv-observatory)"
SOURCELANG = {"en": "english", "fr": "french", "nl": "dutch", "pt": "portuguese",
              "de": "german", "es": "spanish", "it": "italian"}
START = "2017-01-01"  # DOC API coverage begins in 2017
PAUSE = 6.0
BACKOFF = (20, 60, 120, 240)


def build_query(terms: str, lang: str) -> str:
    parts = [t.strip() for t in terms.split(" OR ") if t.strip()]
    parts = [f'"{t}"' if " " in t else t for t in parts]
    body = parts[0] if len(parts) == 1 else "(" + " OR ".join(parts) + ")"
    return f"{body} sourcelang:{SOURCELANG[lang]}"


def _get(params: dict) -> dict | None:
    url = f"{API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for wait in (*BACKOFF, None):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                body = r.read().decode("utf-8", "replace").strip()
            return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            if e.code != 429 or wait is None:
                print(f"  gdelt HTTP {e.code}")
                return None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if wait is None:
                print(f"  gdelt error: {e}")
                return None
        time.sleep(wait)
    return None


def timeline(query: str, start: str, end: str) -> list[tuple[str, int, int]] | None:
    """[(YYYY-MM-DD, hits, total)] for [start, end]; None if the request failed."""
    d = _get({"query": query, "mode": "timelinevolraw", "format": "json", "timelinesmooth": "0",
              "startdatetime": start.replace("-", "") + "000000",
              "enddatetime": end.replace("-", "") + "235959"})
    if d is None:
        return None
    out = []
    for series in d.get("timeline", []):
        for p in series.get("data", []):
            day = p["date"][:8]
            out.append((f"{day[:4]}-{day[4:6]}-{day[6:]}", int(p["value"]), int(p.get("norm", 0))))
    return out


def _years(start: str, end: str):
    a, z = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    while a <= z:
        b = min(dt.date(a.year, 12, 31), z)
        yield a.isoformat(), b.isoformat()
        a = b + dt.timedelta(days=1)


def run(con, cfg: dict, langs=("en", "fr", "nl", "pt"), end: str | None = None) -> int:
    """Fetch new days for every concept x language, resuming from the latest stored day.
    Stops a (concept, language) at its first failed request so no gap is left behind."""
    end = end or dt.date.today().isoformat()
    stored, first = 0, True
    for key, spec in cfg.get("concepts", {}).items():
        terms = spec.get("gdelt", {})
        for lang in langs:
            if lang not in terms:
                continue
            q = build_query(terms[lang], lang)
            last = con.execute("SELECT MAX(date) FROM counts WHERE source='gdelt' AND concept=? AND lang=?",
                               (key, lang)).fetchone()[0]
            for a, b in _years(last or START, end):
                if not first:
                    time.sleep(PAUSE)
                first = False
                rows = timeline(q, a, b)
                if rows is None:
                    # Throttling applies to the whole address, so further requests would only
                    # burn the time budget. Stop here; the next run resumes from this point.
                    print(f"  {key}/{lang} {a}..{b}: failed after retries; stopping, resumes next run")
                    return stored
                con.executemany(
                    "INSERT OR REPLACE INTO counts VALUES ('gdelt','news',?,?,?,?,?)",
                    [(key, lang, d, h, t) for d, h, t in rows if t > 0])
                con.commit()
                stored += len(rows)
                print(f"  {key}/{lang} {a}..{b}: {len(rows)} days, {sum(r[1] for r in rows)} matching articles")
    return stored
