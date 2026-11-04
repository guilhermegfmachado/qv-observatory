"""Minimal language-agnostic text utilities (stdlib only)."""
from __future__ import annotations

import re

_SENT_RE = re.compile(r"(?<=[.!?…])\s+(?=[\"'«“(]?[A-ZÀ-ÖØ-Þ0-9])")
_TOKEN_RE = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*", re.UNICODE)


def sentences(text: str) -> list[str]:
    out = []
    for block in text.split("\n"):
        out.extend(s.strip() for s in _SENT_RE.split(block) if s.strip())
    return out


def tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]
