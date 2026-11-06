"""SQLite storage. One file, no server."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id      TEXT PRIMARY KEY,     -- sha1 of source + external id
    source  TEXT NOT NULL,        -- parlamint | eurlex | creative_europe | folder:<name>
    domain  TEXT NOT NULL,        -- policy | parliament | news | art
    lang    TEXT NOT NULL,        -- ISO 639-1, or 'mul'
    date    TEXT NOT NULL,        -- YYYY-MM-DD
    country TEXT,
    title   TEXT,
    url     TEXT,
    text    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_docs_domain_date ON documents(domain, date);

CREATE TABLE IF NOT EXISTS mentions (
    doc_id  TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    concept TEXT NOT NULL,
    lang    TEXT NOT NULL,        -- language whose pattern matched
    count   INTEGER NOT NULL,
    PRIMARY KEY (doc_id, concept, lang)
);

CREATE TABLE IF NOT EXISTS triples (
    id             INTEGER PRIMARY KEY,
    doc_id         TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    concept        TEXT NOT NULL,
    sentence       TEXT NOT NULL,
    subj           TEXT NOT NULL,
    rel            TEXT NOT NULL,
    obj            TEXT NOT NULL,
    concept_role   TEXT NOT NULL,  -- subject | object | other
    model          TEXT NOT NULL,
    prompt_version TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_triples_concept ON triples(concept);

-- Aggregate sources (GDELT): per-day matching items and the total they are a share of.
CREATE TABLE IF NOT EXISTS counts (
    source  TEXT NOT NULL,        -- gdelt
    domain  TEXT NOT NULL,
    concept TEXT NOT NULL,
    lang    TEXT NOT NULL,
    date    TEXT NOT NULL,        -- YYYY-MM-DD
    hits    INTEGER NOT NULL,
    total   INTEGER NOT NULL,
    PRIMARY KEY (source, concept, lang, date)
);

-- How far back each paged feed has been read, so backfill continues across runs.
CREATE TABLE IF NOT EXISTS feed_state (
    name          TEXT PRIMARY KEY,
    deepest_page  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS oie_cache (
    key      TEXT PRIMARY KEY,     -- sha1(prompt_version + model + sentence)
    response TEXT NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    return con
