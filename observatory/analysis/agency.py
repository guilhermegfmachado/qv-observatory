"""Reification index from OIE triples: how often an abstract concept is the grammatical
agent of a relation ("resilience enables...", "a comunidade exige...") rather than its object.
A rising agency share is a measurable trace of a concept hardening into an actor."""
from __future__ import annotations

import sqlite3
from collections import Counter


def run(con: sqlite3.Connection, cfg: dict) -> dict:
    out = {}
    for key in cfg["_concepts"]:
        rows = con.execute(
            "SELECT t.rel, t.concept_role, d.domain, substr(d.date,1,4) AS year FROM triples t"
            " JOIN documents d ON d.id = t.doc_id WHERE t.concept = ?", (key,)).fetchall()
        if not rows:
            continue
        by_domain, by_year = {}, {}
        for group, field in ((by_domain, "domain"), (by_year, "year")):
            counts = Counter((r[field], r["concept_role"]) for r in rows)
            for g in {r[field] for r in rows}:
                n = sum(counts[(g, role)] for role in ("subject", "object", "other"))
                group[g] = {"triples": n, "agency": round(counts[(g, "subject")] / n, 3)}
        rels = Counter(r["rel"].lower() for r in rows if r["concept_role"] == "subject")
        out[key] = {"triples": len(rows), "by_domain": by_domain, "by_year": dict(sorted(by_year.items())),
                    "agent_relations": rels.most_common(15)}
    return out
