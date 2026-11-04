"""Write the single JSON file the static site reads."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path

from .analysis import agency, drift, migration


def run(con: sqlite3.Connection, cfg: dict, out_path: Path, synthetic: bool = False) -> dict:
    mig = migration.run(con, cfg)
    stats = con.execute(
        "SELECT domain, lang, COUNT(*) AS n, MIN(date) AS first, MAX(date) AS last"
        " FROM documents GROUP BY domain, lang ORDER BY domain, lang").fetchall()
    data = {
        "meta": {
            "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "synthetic": synthetic,
            "domains": cfg["domains"],
            "corpus": [dict(r) for r in stats],
            "counts": [dict(r) for r in con.execute(
                "SELECT source, domain, lang, COUNT(*) AS days, SUM(hits) AS hits, MIN(date) AS first,"
                " MAX(date) AS last FROM counts GROUP BY source, domain, lang ORDER BY 1, 3")],
            "sources": [r[0] for r in con.execute(
                "SELECT source FROM documents UNION SELECT source FROM counts ORDER BY 1")],
        },
        "migration": mig,
        "drift": drift.run(con, cfg),
        "agency": agency.run(con, cfg),
        "concepts": {k: {"label": c.label, "lexemes": {l: p.pattern for l, p in c.patterns.items()}}
                     for k, c in cfg["_concepts"].items()},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return data
