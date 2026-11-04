"""Creative Europe Project Results platform exports.

Export search results from https://ec.europa.eu/programmes/creative-europe/projects as
spreadsheet, save as CSV (UTF-8). Column names differ between exports: map them in COLUMNS
or pass your own mapping. Project summaries are mostly English, so lang defaults to 'en'.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from .base import Document

COLUMNS = {
    "id": ("Project Number", "Project Identifier", "Project number"),
    "title": ("Project Title", "Project title"),
    "summary": ("Project Summary", "Project summary", "Summary"),
    "date": ("Start Date", "Start date", "Project start date"),
    "country": ("Coordinator's country", "Coordinator country", "Coordinating organisation country"),
    "url": ("Project Url", "Project URL", "Website"),
}


def _pick(row: dict, names) -> str:
    for n in names:
        if row.get(n):
            return row[n].strip()
    return ""


def _iso(date: str) -> str:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", date) or None
    if m:
        return m.group(0)
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", date)  # dd/mm/yyyy
    if m:
        return f"{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}"
    return ""


def read(csv_path: Path, lang: str = "en"):
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            summary, date = _pick(row, COLUMNS["summary"]), _iso(_pick(row, COLUMNS["date"]))
            if not summary or not date:
                continue
            yield Document(
                source="creative_europe",
                external_id=_pick(row, COLUMNS["id"]) or _pick(row, COLUMNS["title"]),
                domain="policy",
                lang=lang,
                date=date,
                country=_pick(row, COLUMNS["country"]),
                title=_pick(row, COLUMNS["title"]),
                url=_pick(row, COLUMNS["url"]),
                text=summary,
            )
