"""Shared document model and insertion."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VALID_DOMAINS = {"policy", "parliament", "news", "art"}


@dataclass
class Document:
    source: str
    external_id: str
    domain: str
    lang: str
    date: str
    text: str
    title: str = ""
    url: str = ""
    country: str = ""

    @property
    def id(self) -> str:
        return hashlib.sha1(f"{self.source}|{self.external_id}".encode()).hexdigest()

    def validate(self) -> None:
        if self.domain not in VALID_DOMAINS:
            raise ValueError(f"unknown domain {self.domain!r} for {self.external_id}")
        if not DATE_RE.match(self.date):
            raise ValueError(f"bad date {self.date!r} for {self.external_id}")
        if not self.text.strip():
            raise ValueError(f"empty text for {self.external_id}")


def insert(con: sqlite3.Connection, docs) -> tuple[int, int]:
    """Insert documents, skipping ones already present. Returns (inserted, skipped)."""
    inserted = skipped = 0
    for d in docs:
        d.validate()
        cur = con.execute(
            "INSERT OR IGNORE INTO documents (id, source, domain, lang, date, country, title, url, text)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (d.id, d.source, d.domain, d.lang, d.date, d.country, d.title, d.url, d.text),
        )
        if cur.rowcount:
            inserted += 1
        else:
            skipped += 1
    con.commit()
    return inserted, skipped
