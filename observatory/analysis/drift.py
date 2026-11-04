"""Semantic drift per concept, language and year.

Stdlib baseline: PPMI-weighted collocates in a window around each mention; drift between
consecutive years is 1 - Jaccard overlap of the top-k collocate sets (a simplified version
of Hamilton, Leskovec & Jurafsky's 2016 local-neighbourhood measure). Swap in diachronic
embeddings later without changing the output shape.
"""
from __future__ import annotations

import math
import sqlite3
from collections import Counter, defaultdict

from ..config import LANGS
from ..text import tokens


def run(con: sqlite3.Connection, cfg: dict) -> dict:
    acfg = cfg["analysis"]
    win, top_k, max_df = acfg["drift_window"], acfg["drift_top_k"], acfg["stopword_max_df"]
    concepts = cfg["_concepts"]

    # Token counts per (lang, year) and stopwords per lang.
    freq: dict[tuple[str, str], Counter] = defaultdict(Counter)
    docs_by_lang = defaultdict(list)
    for row in con.execute("SELECT id, lang, date, text FROM documents"):
        toks = tokens(row["text"])
        year = row["date"][:4]
        langs = list(LANGS) if row["lang"] == "mul" else [row["lang"]]
        for lang in langs:
            freq[(lang, year)].update(toks)
            docs_by_lang[lang].append((row["id"], year, toks))
    # Stopwords: tokens present in more than max_df of a language's documents.
    stop = {}
    for lang, docs in docs_by_lang.items():
        df = Counter()
        for _, _, toks in docs:
            df.update(set(toks))
        stop[lang] = {w for w, c in df.items() if c / len(docs) > max_df}

    out = {}
    for key, concept in concepts.items():
        per_lang = {}
        for lang, pat in concept.patterns.items():
            if lang not in docs_by_lang:
                continue
            ctx: dict[str, Counter] = defaultdict(Counter)
            for _, year, toks in docs_by_lang[lang]:
                for i, t in enumerate(toks):
                    if pat.fullmatch(t):
                        for w in toks[max(0, i - win): i] + toks[i + 1: i + 1 + win]:
                            if len(w) > 2 and w not in stop[lang] and not pat.fullmatch(w):
                                ctx[year][w] += 1
            years = sorted(y for y in ctx if sum(ctx[y].values()) >= 20)
            if not years:
                continue
            neigh = {}
            for y in years:
                n_tok = sum(freq[(lang, y)].values())
                c_tot = sum(ctx[y].values())
                scored = []
                for w, c in ctx[y].items():
                    if c < 2:
                        continue
                    pmi = math.log((c * n_tok) / (c_tot * freq[(lang, y)][w]))
                    if pmi > 0:
                        scored.append((w, round(pmi * math.log1p(c), 3)))  # damp rare-word bias
                neigh[y] = sorted(scored, key=lambda x: -x[1])[:top_k]
            drift = []
            for a, b in zip(years, years[1:]):
                sa, sb = {w for w, _ in neigh[a]}, {w for w, _ in neigh[b]}
                if sa and sb:
                    drift.append({"from": a, "to": b, "drift": round(1 - len(sa & sb) / len(sa | sb), 3),
                                  "entered": sorted(sb - sa)[:10], "left": sorted(sa - sb)[:10]})
            per_lang[lang] = {"neighbours": {y: neigh[y][:12] for y in years}, "drift": drift}
        out[key] = per_lang
    return out
