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


def _doc_langs(lang: str) -> list[str]:
    return list(LANGS) if lang == "mul" else [lang]


def run(con: sqlite3.Connection, cfg: dict) -> dict:
    """Two streaming passes over the corpus, so memory grows with vocabulary, not corpus size:
    (1) token frequencies per (language, year) and document frequencies per language;
    (2) context windows around mentions, read only from documents that mention a concept."""
    acfg = cfg["analysis"]
    win, top_k, max_df = acfg["drift_window"], acfg["drift_top_k"], acfg["stopword_max_df"]
    concepts = cfg["_concepts"]

    freq: dict[tuple[str, str], Counter] = defaultdict(Counter)
    df: dict[str, Counter] = defaultdict(Counter)
    n_docs: Counter = Counter()
    for row in con.execute("SELECT lang, date, text FROM documents"):
        toks = tokens(row["text"])
        uniq = set(toks)
        for lang in _doc_langs(row["lang"]):
            freq[(lang, row["date"][:4])].update(toks)
            df[lang].update(uniq)
            n_docs[lang] += 1
    # Stopwords: tokens present in more than max_df of a language's documents.
    stop = {lang: {w for w, c in d.items() if c / n_docs[lang] > max_df} for lang, d in df.items()}
    del df

    # ctx[(concept, lang)][year] -> collocate counts
    ctx: dict[tuple[str, str], dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    forms: dict[tuple[str, str], Counter] = defaultdict(Counter)  # surface forms actually used
    for row in con.execute("SELECT lang, date, text FROM documents"
                           " WHERE id IN (SELECT DISTINCT doc_id FROM mentions)"):
        toks = tokens(row["text"])
        year = row["date"][:4]
        for lang in _doc_langs(row["lang"]):
            for key, concept in concepts.items():
                pat = concept.patterns.get(lang)
                if pat is None:
                    continue
                for i, t in enumerate(toks):
                    if pat.fullmatch(t):
                        forms[(key, lang)][t] += 1
                        for w in toks[max(0, i - win): i] + toks[i + 1: i + 1 + win]:
                            if len(w) > 2 and w not in stop[lang] and not pat.fullmatch(w):
                                ctx[(key, lang)][year][w] += 1

    out = {}
    for key, concept in concepts.items():
        per_lang = {}
        for lang in concept.patterns:
            c_by_year = ctx.get((key, lang), {})
            years = sorted(y for y in c_by_year if sum(c_by_year[y].values()) >= 20)
            if not years:
                continue
            neigh = {}
            for y in years:
                n_tok = sum(freq[(lang, y)].values())
                c_tot = sum(c_by_year[y].values())
                scored = []
                for w, c in c_by_year[y].items():
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
            per_lang[lang] = {"neighbours": {y: neigh[y][:12] for y in years}, "drift": drift,
                              "forms": forms[(key, lang)].most_common(6)}
        out[key] = per_lang
    return out
