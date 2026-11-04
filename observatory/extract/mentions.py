"""Lexicon-based concept mentions: cheap, transparent, re-runnable."""
from __future__ import annotations

import sqlite3


def run(con: sqlite3.Connection, concepts: dict, rebuild: bool = False) -> int:
    """Scan documents not yet scanned (or all, with rebuild). Returns documents scanned."""
    con.execute("CREATE TABLE IF NOT EXISTS _scanned (doc_id TEXT PRIMARY KEY)")
    if rebuild:
        con.execute("DELETE FROM mentions")
        con.execute("DELETE FROM _scanned")
    docs = con.execute(
        "SELECT id, lang, text FROM documents WHERE id NOT IN (SELECT doc_id FROM _scanned)"
    ).fetchall()
    rows = []
    for doc in docs:
        for c in concepts.values():
            for lang, pat in c.pattern_for(doc["lang"]):
                k = len(pat.findall(doc["text"]))
                if k:
                    rows.append((doc["id"], c.key, lang, k))
    con.executemany("INSERT OR REPLACE INTO mentions VALUES (?,?,?,?)", rows)
    con.executemany("INSERT OR IGNORE INTO _scanned VALUES (?)", [(d["id"],) for d in docs])
    con.commit()
    return len(docs)
