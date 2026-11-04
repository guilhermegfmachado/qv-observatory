"""CLI: python -m observatory <command>"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import config, db, export
from .extract import mentions, oie
from .ingest import base, creative_europe, eurlex, folder, parlamint


def main(argv=None):
    ap = argparse.ArgumentParser(prog="observatory")
    ap.add_argument("--config", type=Path)
    ap.add_argument("--db", type=Path, help="override db_path")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ing = sub.add_parser("ingest", help="load documents")
    ing.add_argument("source", choices=["folder", "parlamint", "creative-europe", "eurlex"])
    ing.add_argument("path", nargs="?", help="folder / ParlaMint dir / Creative Europe CSV")
    ing.add_argument("--lang", default="en")
    ing.add_argument("--start", help="eurlex: YYYY-MM-DD")
    ing.add_argument("--end", help="eurlex: YYYY-MM-DD")
    ing.add_argument("--limit", type=int, default=500)

    men = sub.add_parser("mentions", help="scan documents for concept lexemes")
    men.add_argument("--rebuild", action="store_true")

    ex = sub.add_parser("oie", help="extract triples with the Claude API")
    ex.add_argument("--limit", type=int, help="max sentences this run")
    ex.add_argument("--dry-run", action="store_true", help="count sentences and requests only")

    exp = sub.add_parser("export", help="run analyses and write the site JSON")
    exp.add_argument("--synthetic", action="store_true", help="flag output as test data")
    exp.add_argument("--out", type=Path)

    sub.add_parser("status", help="corpus summary")

    args = ap.parse_args(argv)
    cfg = config.load(args.config)
    con = db.connect(args.db or config.resolve(cfg, cfg["project"]["db_path"]))

    if args.cmd == "ingest":
        if args.source == "eurlex":
            docs = eurlex.read(args.start, args.end, lang=args.lang, limit=args.limit)
        elif args.source == "folder":
            docs = folder.read(Path(args.path))
        elif args.source == "parlamint":
            docs = parlamint.read(Path(args.path))
        else:
            docs = creative_europe.read(Path(args.path), lang=args.lang)
        ins, skip = base.insert(con, docs)
        print(f"inserted {ins}, already present {skip}")
    elif args.cmd == "mentions":
        print(f"scanned {mentions.run(con, cfg['_concepts'], args.rebuild)} documents")
    elif args.cmd == "oie":
        print(f"stored {oie.run(con, cfg, args.limit, args.dry_run)} triples")
    elif args.cmd == "export":
        out = args.out or config.resolve(cfg, cfg["project"]["site_data"])
        export.run(con, cfg, out, synthetic=args.synthetic)
        print(f"wrote {out}")
    elif args.cmd == "status":
        for r in con.execute("SELECT domain, lang, COUNT(*), MIN(date), MAX(date) FROM documents"
                             " GROUP BY domain, lang ORDER BY domain, lang"):
            print("\t".join(str(x) for x in r))
        print("triples:", con.execute("SELECT COUNT(*) FROM triples").fetchone()[0])


if __name__ == "__main__":
    main()
