"""Close reading for the site: example sentences and co-occurring concepts.

Example sentences come only from sources whose reuse is permitted with attribution (EUR-Lex,
European Parliament). Copyrighted sources (news and art feeds) are never quoted.
"""
from __future__ import annotations

import re
import sqlite3

from ..text import sentences

QUOTABLE = ("eurlex", "europarl")
_GOOD = re.compile(r"^[A-ZÀ-Ö\"'“«(]")   # starts like a sentence
_NOISY = re.compile(r"\d[\d.,/()-]{3,}|\bCOM\(|\bSWD\(|\bOJ [LC]\b|https?://|\.{3,}|_{3,}")


def _pick(text: str, pat: re.Pattern) -> str | None:
    for s in sentences(text):
        words = len(s.split())
        if 12 <= words <= 45 and 80 <= len(s) <= 300 and _GOOD.match(s) and not _NOISY.search(s) \
                and pat.search(s) and s.rstrip()[-1:] in ".!?":
            return s
    return None


def examples(con: sqlite3.Connection, cfg: dict, per_domain: int = 3, lang: str = "en") -> dict:
    """For each concept: up to `per_domain` sentences per quotable domain, spread over the years
    (earliest, middle, latest year with a usable sentence)."""
    out = {}
    q_marks = ",".join("?" * len(QUOTABLE))
    for key, concept in cfg["_concepts"].items():
        pat = concept.patterns.get(lang)
        if pat is None:
            continue
        found = []
        for (domain,) in con.execute(f"SELECT DISTINCT domain FROM documents WHERE source IN ({q_marks})", QUOTABLE):
            years = [r[0] for r in con.execute(
                f"""SELECT DISTINCT substr(d.date,1,4) FROM documents d JOIN mentions m ON m.doc_id=d.id
                    WHERE m.concept=? AND d.lang=? AND d.domain=? AND d.source IN ({q_marks}) ORDER BY 1""",
                (key, lang, domain, *QUOTABLE))]
            if not years:
                continue
            picks = sorted({years[0], years[len(years) // 2], years[-1]})[:per_domain]
            for year in picks:
                for row in con.execute(
                        f"""SELECT d.date, d.title, d.url, d.text FROM documents d JOIN mentions m ON m.doc_id=d.id
                            WHERE m.concept=? AND d.lang=? AND d.domain=? AND d.source IN ({q_marks})
                              AND d.date LIKE ? ORDER BY m.count DESC, d.date LIMIT 25""",
                        (key, lang, domain, *QUOTABLE, f"{year}%")):
                    s = _pick(row["text"], pat)
                    if s:
                        found.append({"domain": domain, "date": row["date"], "source": row["title"],
                                      "url": row["url"], "text": s})
                        break
        out[key] = found
    return out


def cooccurrence(con: sqlite3.Connection, cfg: dict) -> dict:
    """For each concept A: of the documents that use A, the share that also use each other concept B."""
    totals = dict(con.execute("SELECT concept, COUNT(DISTINCT doc_id) FROM mentions GROUP BY concept"))
    out = {k: [] for k in cfg["_concepts"]}
    for a, b, n in con.execute(
            """SELECT a.concept, b.concept, COUNT(DISTINCT a.doc_id) FROM mentions a
               JOIN mentions b ON a.doc_id = b.doc_id AND a.concept <> b.concept
               GROUP BY a.concept, b.concept"""):
        if a in out and totals.get(a):
            out[a].append({"with": b, "share": round(n / totals[a], 3), "documents": n})
    for a in out:
        out[a].sort(key=lambda x: -x["share"])
    return out
