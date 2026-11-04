"""Load config/observatory.toml and compile concept lexicons."""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGS = ("en", "pt", "nl", "fr", "de", "es", "it")


@dataclass(frozen=True)
class Concept:
    key: str
    label: str
    patterns: dict[str, re.Pattern]  # lang -> compiled regex

    def pattern_for(self, lang: str) -> list[tuple[str, re.Pattern]]:
        if lang == "mul":
            return list(self.patterns.items())
        return [(lang, self.patterns[lang])] if lang in self.patterns else []


def load(path: Path | None = None) -> dict:
    path = path or ROOT / "config" / "observatory.toml"
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    cfg["_concepts"] = {
        key: Concept(
            key=key,
            label=spec.get("label", key),
            patterns={
                lang: re.compile(rf"(?<!\w)(?:{spec[lang]})(?!\w)", re.IGNORECASE | re.UNICODE)
                for lang in LANGS
                if lang in spec
            },
        )
        for key, spec in cfg.get("concepts", {}).items()
    }
    return cfg


def resolve(cfg: dict, rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else ROOT / p
