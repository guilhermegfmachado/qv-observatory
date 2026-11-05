"""Where and when concepts appear: per-domain usage rates, onsets, first use per language,
and lead/lag between domains by cross-correlation."""
from __future__ import annotations

import math
import sqlite3
from itertools import permutations


def _period(date: str, gran: str) -> str:
    return date[:7] if gran == "month" else date[:4]


def _period_range(first: str, last: str, gran: str) -> list[str]:
    if gran == "year":
        return [str(y) for y in range(int(first), int(last) + 1)]
    y, m = map(int, first.split("-"))
    ly, lm = map(int, last.split("-"))
    out = []
    while (y, m) <= (ly, lm):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _pearson(a: list[float], b: list[float]) -> float | None:
    n = len(a)
    if n < 6:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va == 0 or vb == 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


def best_lag(lead: list, follow: list, max_lag: int, min_pairs: int = 6) -> tuple[int, float, int] | None:
    """(lag, r, pairs) for the lag L >= 0 maximising corr(lead[t], follow[t+L]), using only
    lags with at least `min_pairs` periods where both series have data."""
    best = None
    for lag in range(0, max_lag + 1):
        pairs = [(lead[t], follow[t + lag]) for t in range(len(lead) - lag)
                 if lead[t] is not None and follow[t + lag] is not None]
        if len(pairs) < min_pairs:
            continue
        r = _pearson([p[0] for p in pairs], [p[1] for p in pairs])
        if r is not None and (best is None or r > best[1]):
            best = (lag, r, len(pairs))
    return best


def run(con: sqlite3.Connection, cfg: dict) -> dict:
    acfg = cfg["analysis"]
    gran, min_docs, frac = acfg["series_granularity"], acfg["min_docs_per_period"], acfg["onset_fraction"]
    min_mentions = acfg.get("min_mentions_for_lag", 30)
    min_pairs = acfg.get("min_periods_for_lag", 12)
    max_lag = acfg["max_lag_months"] if gran == "month" else max(1, acfg["max_lag_months"] // 12)
    domains = list(cfg["domains"])

    bounds = con.execute("SELECT MIN(d), MAX(d) FROM (SELECT date AS d FROM documents"
                         " UNION ALL SELECT date FROM counts)").fetchone()
    if not bounds[0]:
        return {"periods": [], "concepts": {}}
    periods = _period_range(_period(bounds[0], gran), _period(bounds[1], gran), gran)
    idx = {p: i for i, p in enumerate(periods)}

    totals = {d: [0] * len(periods) for d in domains}
    for row in con.execute("SELECT domain, date FROM documents"):
        if row["domain"] in totals:
            totals[row["domain"]][idx[_period(row["date"], gran)]] += 1
    # Aggregate sources: the day's total is the same for every concept, so take it once per language.
    for row in con.execute("SELECT domain, date, MAX(total) AS t FROM counts GROUP BY domain, lang, date"):
        if row["domain"] in totals:
            totals[row["domain"]][idx[_period(row["date"], gran)]] += row["t"]

    out = {"granularity": gran, "periods": periods,
           "documents": {d: totals[d] for d in domains}, "concepts": {}}
    for key in cfg["_concepts"]:
        hits = {d: [0] * len(periods) for d in domains}
        for row in con.execute(
            "SELECT DISTINCT d.id, d.domain, d.date FROM documents d JOIN mentions m ON m.doc_id=d.id"
            " WHERE m.concept=?", (key,)):
            if row["domain"] in hits:
                hits[row["domain"]][idx[_period(row["date"], gran)]] += 1
        doc_mentions = sum(sum(v) for v in hits.values())  # documents only, not aggregate counts
        for row in con.execute("SELECT domain, date, SUM(hits) AS h FROM counts WHERE concept=?"
                               " GROUP BY domain, date", (key,)):
            if row["domain"] in hits:
                hits[row["domain"]][idx[_period(row["date"], gran)]] += row["h"]

        series, onsets = {}, {}
        for d in domains:
            rates = [(h / n if n >= min_docs else None) for h, n in zip(hits[d], totals[d])]
            series[d] = [None if r is None else round(r, 4) for r in rates]
            peak = max((r for r in rates if r is not None), default=0)
            onsets[d] = next((periods[i] for i, r in enumerate(rates)
                              if peak > 0 and r is not None and r >= frac * peak), None)

        # A lag is reported only with enough evidence on both sides, and only in the stronger
        # direction of each pair: two directions with similar r mean the data cannot tell them apart.
        hit_totals = {d: sum(hits[d]) for d in domains}
        best_by_pair = {}
        for a, b in permutations(domains, 2):
            if min(hit_totals[a], hit_totals[b]) < min_mentions:
                continue
            res = best_lag(series[a], series[b], max_lag, min_pairs)
            if not res or res[1] < 0.3 or (res[0] == 0 and domains.index(a) > domains.index(b)):
                continue
            pair = frozenset((a, b))
            cand = {"lead": a, "follow": b, "lag": res[0], "r": round(res[1], 3), "periods": res[2]}
            if pair not in best_by_pair or cand["r"] > best_by_pair[pair]["r"]:
                best_by_pair[pair] = cand
        lags = list(best_by_pair.values())
        lags.sort(key=lambda x: -x["r"])

        first_by_lang = [
            {"lang": r["lang"], "date": r["date"], "domain": r["domain"], "title": r["title"]}
            for r in con.execute(
                """SELECT m.lang, d.date, d.domain, d.title FROM mentions m
                   JOIN documents d ON d.id = m.doc_id
                   WHERE m.concept = ? AND d.date = (
                     SELECT MIN(d2.date) FROM mentions m2 JOIN documents d2 ON d2.id = m2.doc_id
                     WHERE m2.concept = m.concept AND m2.lang = m.lang)
                   GROUP BY m.lang ORDER BY d.date""", (key,))
        ]
        out["concepts"][key] = {
            "mentions": doc_mentions,
            "counted_items": {d: sum(hits[d]) for d in domains},
            "series": series, "onsets": onsets, "lags": lags, "first_by_lang": first_by_lang,
        }
    return out
