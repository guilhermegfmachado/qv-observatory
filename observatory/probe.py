"""Check the pipeline's assumptions about live sources before a full run.

Each probe prints what it found and returns True when the assumption holds. Probes that need
the network (eurlex, model) are cheap: a handful of requests.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import urllib.parse
from collections import Counter
from pathlib import Path

from .ingest import creative_europe, eurlex, parlamint


def probe_eurlex(lang: str = "en", days: int = 60) -> bool:
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    q = eurlex.QUERY.format(start=start, end=end, sector="5", limit=3)
    url = f"{eurlex.SPARQL}?{urllib.parse.urlencode({'query': q, 'format': 'application/sparql-results+json'})}"
    try:
        rows = json.loads(eurlex._get(url, "application/sparql-results+json"))["results"]["bindings"]
    except Exception as exc:  # noqa: BLE001
        print(f"eurlex: SPARQL query failed: {exc}")
        return False
    print(f"eurlex: SPARQL returned {len(rows)} rows for {start}..{end}")
    if not rows:
        print("eurlex: no rows; CDM property names or the date filter may have changed")
        return False
    for row in rows:
        celex = row["celex"]["value"]
        text_url = eurlex.TEXT_URL.format(lang=lang.upper(), celex=celex)
        try:
            text = eurlex._strip_html(eurlex._get(text_url))
        except Exception as exc:  # noqa: BLE001
            print(f"eurlex: {celex}: text fetch failed: {exc}")
            continue
        print(f"eurlex: {celex} ({row['date']['value'][:10]}): {len(text)} chars of text")
        if len(text) >= 200:
            return True
    print("eurlex: no usable full text among the sample")
    return False


def probe_parlamint(root: Path) -> bool:
    files = [p for p in Path(root).rglob("ParlaMint-*.txt") if p.is_file()]
    matched = [p for p in files if parlamint.FILE_RE.search(p.name)]
    print(f"parlamint: {len(files)} .txt files, {len(matched)} match FILE_RE")
    for p in sorted(set(files) - set(matched))[:5]:
        print(f"  unmatched: {p.name}")
    if not matched:
        return False
    sample = matched[0]
    lines = sample.read_text(encoding="utf-8").splitlines()
    tabbed = sum("\t" in l for l in lines)
    print(f"parlamint: {sample.name}: {tabbed}/{len(lines)} lines are '<id>\\t<text>'")
    ccs = Counter(parlamint.FILE_RE.search(p.name)["cc"] for p in matched)
    unknown = sorted(cc for cc in ccs if cc not in parlamint.COUNTRY_LANG)
    print(f"parlamint: countries {dict(ccs)}" + (f"; no language mapped for {unknown}" if unknown else ""))
    return tabbed > 0.9 * max(len(lines), 1)


def probe_creative_europe(csv_path: Path) -> bool:
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        first = next(reader, {})
    print(f"creative-europe: {len(headers)} columns: {headers}")
    ok = True
    for field, names in creative_europe.COLUMNS.items():
        hit = next((n for n in names if n in headers), None)
        print(f"  {field:8} -> {hit or 'MISSING'}")
        if field in ("summary", "date") and not hit:
            ok = False
    if first:
        date = creative_europe._pick(first, creative_europe.COLUMNS["date"])
        print(f"  first row date {date!r} -> {creative_europe._iso(date)!r}")
        ok = ok and bool(creative_europe._iso(date))
    return ok


def probe_model(model: str) -> bool:
    try:
        import anthropic
    except ImportError:
        print("model: pip install anthropic to probe the model")
        return False
    try:
        m = anthropic.Anthropic().models.retrieve(model)
    except Exception as exc:  # noqa: BLE001
        print(f"model: {model}: {exc}")
        return False
    print(f"model: {m.id} ({m.display_name}) is available")
    return True
