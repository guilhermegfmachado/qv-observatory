"""News and art press from RSS / Atom feeds (titles and summaries only).

Feeds carry only recent items, so the pipeline polls daily and the corpus grows from then on.
Feeds marked `paged` (WordPress) also serve older pages (?paged=2, 3, ...), which backfills
history until a page holds only items already stored.

These texts are copyrighted: they stay in the local corpus for counting, are never quoted on
the site (see analysis/examples.py), and only statistics are published. Full articles are not
fetched.
"""
from __future__ import annotations

import datetime as dt
import html
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from .base import Document

UA = "qv-observatory/0.3 (research; github.com/guilhermegfmachado/qv-observatory)"
_TAG = re.compile(r"<[^>]+>")


def _clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", html.unescape(s or "")))).strip()


def _date(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    try:
        return parsedate_to_datetime(s).date().isoformat()
    except (TypeError, ValueError):
        m = re.match(r"\d{4}-\d{2}-\d{2}", s)
        return m[0] if m else None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse(xml: bytes) -> list[dict]:
    """Items of an RSS 2.0 or Atom feed: {id, url, title, text, date}."""
    root = ET.fromstring(xml)
    out = []
    for el in root.iter():
        if _local(el.tag) not in ("item", "entry"):
            continue
        f: dict[str, str] = {}
        for ch in el:
            name = _local(ch.tag)
            if name == "link":
                f.setdefault("link", ch.get("href") or (ch.text or ""))
            elif name in ("title", "guid", "id", "pubDate", "published", "updated", "date",
                          "description", "summary", "encoded", "content"):
                f.setdefault(name, ch.text or "")
        date = _date(f.get("pubDate") or f.get("published") or f.get("date") or f.get("updated"))
        title = _clean(f.get("title"))
        body = _clean(f.get("description") or f.get("summary") or f.get("encoded") or f.get("content"))
        if body.startswith(title):
            body = body[len(title):].strip()
        url = (f.get("link") or "").strip()
        ident = (f.get("guid") or f.get("id") or url or title).strip()
        if date and title:
            out.append({"id": ident, "url": url, "title": title, "date": date,
                        "text": f"{title}. {body}".strip() if body else title})
    return out


def fetch(url: str) -> list[dict] | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, */*"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return parse(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []           # past the last page of a paged feed
        print(f"  {url}: HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, ET.ParseError) as e:
        print(f"  {url}: {e}")
    return None


def _page_url(url: str, n: int) -> str:
    return url if n == 1 else f"{url}{'&' if '?' in url else '?'}paged={n}"


def read(feeds: list[dict], skip: set[str] = frozenset(), max_pages: int = 30, pause: float = 1.5,
         today: str | None = None):
    """Yield documents from every feed. `skip`: document ids already stored."""
    today = today or dt.date.today().isoformat()
    seen = set(skip)
    for feed in feeds:
        name, pages = feed["name"], (max_pages if feed.get("paged") else 1)
        new = 0
        for n in range(1, pages + 1):
            items = fetch(_page_url(feed["url"], n))
            if n > 1:
                time.sleep(pause)
            if not items:
                break
            fresh = 0
            for it in items:
                doc = Document(source=f"rss:{name}", external_id=it["id"], domain=feed["domain"],
                               lang=feed["lang"], date=it["date"], title=it["title"][:300],
                               url=it["url"], text=it["text"])
                if doc.id in seen or it["date"] > today:
                    continue
                seen.add(doc.id)
                fresh += 1
                yield doc
            new += fresh
            if n > 1 and fresh == 0:
                break           # reached what earlier runs already stored
        print(f"  {name}: {new} new items")
