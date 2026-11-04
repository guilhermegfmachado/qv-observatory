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
python -m observatory ingest eurlex --incremental --lang en   # resume from latest stored date
python -m observatory mentions
python -m observatory oie --dry-run           # always dry-run first: prints request count
python -m observatory oie --limit 2000
python -m observatory oie --batch --limit 2000  # Message Batches API: half price, async
python -m observatory probe eurlex            # check a source's assumptions (also: parlamint DIR,
                                              # creative-europe CSV, model)
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
Each has a probe: `python -m observatory probe <source>` reports what it found and exits non-zero
when the assumption fails.
1. `ingest/parlamint.py`: file layout of the current ParlaMint release on CLARIN.SI
   (`probe parlamint downloads/ParlaMint-PT/` after downloading).
2. `ingest/eurlex.py`: the CELLAR SPARQL query (CDM property names) and rate limits
   (`probe eurlex`; runs at the start of every weekly pipeline).
3. `ingest/creative_europe.py`: column names of the current platform export
   (`probe creative-europe downloads/creative-europe.csv`).
4. `config.oie.model`: `claude-haiku-5-5` is current as of 2026-11 (`probe model`). Current models
   reject `temperature`; extraction depth is set by `oie.effort`. Batch mode is implemented.

## Deploy
- `.github/workflows/ci.yml`: tests on every push and PR.
- `.github/workflows/pipeline.yml`: Mondays 04:17 UTC and on demand. Probes EUR-Lex, ingests new
  documents incrementally, runs mentions, extracts triples in batch mode if the
  `ANTHROPIC_API_KEY` secret is set, exports, refuses to publish if `meta.synthetic`, and deploys
  `site/` to GitHub Pages. The SQLite corpus lives in the Actions cache, never in git; on a cache
  miss the incremental ingest backfills from 2015-01-01.
- ParlaMint and Creative Europe are manual downloads and are not ingested in CI yet.

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
