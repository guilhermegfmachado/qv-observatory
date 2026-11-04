"""ParlaMint (CLARIN.SI) plain-text distribution.

Download per-country archives from https://www.clarin.si/repository (search "ParlaMint").
Each sitting comes as a .txt file of "<utterance-id>\t<text>" lines, usually alongside
"-meta.tsv" files. One sitting becomes one document. VERIFY the file layout of the
release you download before a full run; adjust FILE_RE if needed.
"""
from __future__ import annotations

import re
from pathlib import Path

from .base import Document

FILE_RE = re.compile(r"ParlaMint-(?P<cc>[A-Z]{2}(?:-[A-Z]{2})?)_(?P<date>\d{4}-\d{2}-\d{2})")

# Main language per parliament. Multilingual parliaments are 'mul' (all lexicons applied).
COUNTRY_LANG = {
    "AT": "de", "BE": "mul", "BG": "bg", "CZ": "cs", "DK": "da", "EE": "et", "ES": "es",
    "ES-CT": "mul", "ES-GA": "mul", "ES-PV": "mul", "FI": "fi", "FR": "fr", "GB": "en",
    "GR": "el", "HR": "hr", "HU": "hu", "IS": "is", "IT": "it", "LV": "lv", "NL": "nl",
    "NO": "no", "PL": "pl", "PT": "pt", "RS": "sr", "SE": "sv", "SI": "sl", "TR": "tr",
    "UA": "mul", "BA": "bs",
}


def read(root: Path):
    for path in sorted(Path(root).rglob("ParlaMint-*.txt")):
        m = FILE_RE.search(path.name)
        if not m:
            continue
        utterances = []
        for line in path.read_text(encoding="utf-8").splitlines():
            _, _, text = line.partition("\t")
            if text.strip():
                utterances.append(text.strip())
        if not utterances:
            continue
        cc = m["cc"]
        yield Document(
            source="parlamint",
            external_id=path.stem,
            domain="parliament",
            lang=COUNTRY_LANG.get(cc, "mul"),
            date=m["date"],
            country=cc,
            title=path.stem,
            text="\n".join(utterances),
        )
