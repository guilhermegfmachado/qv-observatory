# QV Observatory — instructions for Claude Code

## What this is
A real-time genealogy of concepts across European discourse. It tracks when concepts
(resilience, community, care, sustainability, inclusion, decolonial, polycrisis…) appear in
four domains (EU policy, parliaments, news, art discourse), in which language first, how
long one domain takes to follow another, how their collocates drift, and how often an
abstract concept becomes the grammatical agent of a sentence. It is the machine-reading
counterpart to QV's book *Os Últimos Textos Humanos*: the machine reads Europe, QV writes back.

## Layout
- `config/observatory.toml` — domains, analysis parameters, concept lexicons (regex per language).
- `observatory/ingest/` — one module per source; each yields `Document`s (see `base.py`).
- `observatory/extract/mentions.py` — lexicon matching (stdlib, re-runnable with `--rebuild`).
- `observatory/extract/oie.py` — open information extraction with the Claude API, only on
  sentences that mention a concept. Prompt pinned by `prompt_version`, responses cached.
- `observatory/analysis/` — `migration` (rates, onsets, lead/lag), `drift` (collocate change),
  `agency` (share of triples with the concept as subject).
- `observatory/export.py` → `site/data/observatory.json` → `site/index.html` (static, no build step).
- `tests/` — `synthetic.py` builds a seeded fake corpus; `test_pipeline.py` runs end to end.

## Commands
```
python -m unittest discover tests            # must pass before any commit
python -m observatory ingest folder corpus/   # <domain>/<lang>/<YYYY-MM-DD>__slug.txt
python -m observatory ingest parlamint downloads/ParlaMint-PT/
python -m observatory ingest creative-europe downloads/creative-europe.csv
python -m observatory ingest eurlex --start 2015-01-01 --end 2026-01-01 --lang en
python -m observatory mentions
python -m observatory oie --dry-run           # always dry-run first: prints request count
python -m observatory oie --limit 2000
python -m observatory export
cd site && python -m http.server              # preview
```

## Rules
- Core pipeline stays stdlib-only. Heavy dependencies (spaCy, Stanza, sentence-transformers)
  go behind optional imports, like `anthropic` in `oie.py`.
- Never change an OIE prompt in place: add a new `prompt_version` key.
- Never commit corpora, the SQLite file or API keys. Commit `site/data/observatory.json` only
  when it comes from real data, never with `meta.synthetic = true` on the public branch.
- Respect source terms: ParlaMint and Wikidata are openly licensed; EUR-Lex reuse is permitted
  with attribution; news and festival texts are copyrighted — store them locally for analysis,
  publish only derived statistics and short phrases, never full texts.
- Persons: publish no data about private individuals (GDPR). Institutions and public roles only.
- Report numbers with their denominators; flag periods below `min_docs_per_period`.

## Unverified — check before relying on them
1. `ingest/parlamint.py`: file layout of the current ParlaMint release on CLARIN.SI.
2. `ingest/eurlex.py`: the CELLAR SPARQL query (CDM property names) and rate limits.
3. `ingest/creative_europe.py`: column names of the current platform export.
4. `config.oie.model`: current model string at docs.claude.com; consider the Batch API for cost.

## Roadmap
- v0.2 Sources: GDELT GKG (news themes), CC-News (multilingual news text), e-flux announcements
  (the International Art English corpus, Rule & Levine 2012), festival and biennial texts.
- v0.2 Ontology-gap index: for each concept, compare relations asserted in OIE triples with the
  properties Wikidata records for the matching item; publish the share left unrecognised.
- v0.3 Diachronic embeddings (multilingual sentence-transformers, aligned per year) replacing the
  PPMI baseline in `drift.py`; cross-lingual alignment of the same concept across languages.
- v0.3 Lemmatisation (Stanza) so lexicons can use lemmas instead of regex stems.
- v0.4 Forecast: which concepts are rising in policy but not yet in art (expected arrival from lag).
- v0.4 Site: per-concept dossier pages for QV articles; Portuguese, Dutch and French interface.
- Deploy: GitHub Pages from `site/`, weekly GitHub Action that ingests, extracts and exports.
