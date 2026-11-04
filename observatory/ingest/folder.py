"""Generic ingester for texts you collect yourself (news, festival and curatorial texts).

Layout:  <root>/<domain>/<lang>/<YYYY-MM-DD>__<slug>.txt
Optional first line "# Title" and second line "url: https://..." are read as metadata.
"""
from __future__ import annotations

from pathlib import Path

from .base import Document


def read(root: Path, name: str | None = None):
    root = Path(root)
    source = f"folder:{name or root.name}"
    for path in sorted(root.glob("*/*/*.txt")):
        domain, lang = path.parent.parent.name, path.parent.name
        date, _, slug = path.stem.partition("__")
        lines = path.read_text(encoding="utf-8").splitlines()
        title = url = ""
        if lines and lines[0].startswith("# "):
            title = lines.pop(0)[2:].strip()
        if lines and lines[0].lower().startswith("url:"):
            url = lines.pop(0)[4:].strip()
        yield Document(
            source=source,
            external_id=str(path.relative_to(root)),
            domain=domain,
            lang=lang,
            date=date,
            title=title or slug.replace("-", " "),
            url=url,
            text="\n".join(lines),
        )
