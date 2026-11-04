"""Open information extraction with the Claude API, restricted to sentences that mention a
tracked concept (keeps cost proportional to signal, not corpus size).

The prompt is pinned by `prompt_version`; changing it requires bumping the version so cached
and stored triples stay comparable. Requires `pip install anthropic` and ANTHROPIC_API_KEY.

Two modes: synchronous requests (default), or `batch=True`, which submits everything through
the Message Batches API at half the price and polls until it ends (usually under an hour).
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from itertools import groupby

from ..text import sentences

PROMPTS = {
    "v1": """You are an open information extraction system. For each numbered sentence, extract
every (subject; relation; object) triple the sentence asserts. Rules:
- Keep the sentence's own language and wording; do not translate or normalise.
- The relation is the verbal phrase as written (include negation and modality: "may foster").
- Do not map anything to an ontology or invent relations that are not stated.
- Subjects and objects are minimal noun phrases.
Return ONLY a JSON object: {"<sentence number>": [["subject","relation","object"], ...], ...}.
Use an empty list when a sentence asserts no relation.

Sentences:
{sentences}""",
}

MAX_TOKENS = 16000
BATCH_POLL_SECONDS = 60
BATCH_MAX_REQUESTS = 100_000


def _key(prompt_version: str, model: str, effort: str, sentence: str) -> str:
    return hashlib.sha1(f"{prompt_version}|{model}|{effort}|{sentence}".encode()).hexdigest()


def _parse(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


def _role(concept_pat, subj: str, obj: str) -> str:
    if concept_pat.search(subj):
        return "subject"
    if concept_pat.search(obj):
        return "object"
    return "other"


def candidates(con: sqlite3.Connection, concepts: dict, max_chars: int, limit: int | None = None):
    """Yield (doc_id, concept_key, matched_lang, sentence) for sentences mentioning a concept,
    skipping documents that already have triples. `limit` is checked at document boundaries, so
    a document is never split across runs."""
    q = """SELECT DISTINCT d.id, d.text, m.concept, m.lang FROM documents d
           JOIN mentions m ON m.doc_id = d.id
           WHERE d.id NOT IN (SELECT DISTINCT doc_id FROM triples)
           ORDER BY d.id, m.concept, m.lang"""
    n = 0
    for _, rows in groupby(con.execute(q), key=lambda r: r["id"]):
        if limit and n >= limit:
            return
        for row in rows:
            pat = concepts[row["concept"]].patterns[row["lang"]]
            for s in sentences(row["text"]):
                if len(s) <= max_chars and pat.search(s):
                    yield row["id"], row["concept"], row["lang"], s
                    n += 1


def _params(model: str, effort: str, prompt_version: str, sents: list[str]) -> dict:
    numbered = "\n".join(f"{j}. {s}" for j, s in enumerate(sents))
    return {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "output_config": {"effort": effort},
        "messages": [{"role": "user", "content": PROMPTS[prompt_version].replace("{sentences}", numbered)}],
    }


def _response_text(msg) -> str | None:
    """Text of a reply, or None when it was refused or cut off (nothing is cached then)."""
    stop = getattr(msg, "stop_reason", "end_turn")
    if stop in ("refusal", "max_tokens"):
        return None
    return "".join(b.text for b in msg.content if b.type == "text")


def _cache(con, keyfn, sents: list[str], text: str | None, label: str) -> None:
    if text is None:
        print(f"  {label}: refused or truncated, will retry next run")
        return
    try:
        parsed = _parse(text)
    except json.JSONDecodeError:
        print(f"  {label}: unparseable response, will retry next run")
        return
    for j, s in enumerate(sents):
        con.execute("INSERT OR REPLACE INTO oie_cache VALUES (?,?)",
                    (keyfn(s), json.dumps(parsed.get(str(j), []), ensure_ascii=False)))
    con.commit()


def _run_sync(client, con, groups, mk_params, keyfn) -> None:
    for gi, sents in enumerate(groups):
        _cache(con, keyfn, sents, _response_text(client.messages.create(**mk_params(sents))),
               f"request {gi}")
        print(f"  {gi + 1}/{len(groups)} requests")


def _run_batch(client, con, groups, mk_params, keyfn) -> None:
    for start in range(0, len(groups), BATCH_MAX_REQUESTS):
        chunk = dict(enumerate(groups[start : start + BATCH_MAX_REQUESTS], start))
        batch = client.messages.batches.create(
            requests=[{"custom_id": f"g{gi}", "params": mk_params(s)} for gi, s in chunk.items()])
        print(f"  batch {batch.id}: {len(chunk)} requests submitted")
        while batch.processing_status != "ended":
            time.sleep(BATCH_POLL_SECONDS)
            batch = client.messages.batches.retrieve(batch.id)
            print(f"  batch {batch.id}: {batch.processing_status},"
                  f" {batch.request_counts.processing} processing")
        for res in client.messages.batches.results(batch.id):  # any order: key by custom_id
            sents = chunk[int(res.custom_id[1:])]
            if res.result.type == "succeeded":
                _cache(con, keyfn, sents, _response_text(res.result.message), res.custom_id)
            else:
                print(f"  {res.custom_id}: {res.result.type}, will retry next run")


def run(con: sqlite3.Connection, cfg: dict, limit: int | None = None, dry_run: bool = False,
        batch: bool = False) -> int:
    ocfg = cfg["oie"]
    model, pv, bs = ocfg["model"], ocfg["prompt_version"], ocfg["batch_size"]
    effort = ocfg.get("effort", "low")
    concepts = cfg["_concepts"]
    items = list(candidates(con, concepts, ocfg["max_sentence_chars"], limit))
    keyfn = lambda s: _key(pv, model, effort, s)  # noqa: E731

    pending = list(dict.fromkeys(
        s for *_, s in items
        if not con.execute("SELECT 1 FROM oie_cache WHERE key=?", (keyfn(s),)).fetchone()))
    groups = [pending[i : i + bs] for i in range(0, len(pending), bs)]
    if dry_run:
        print(f"{len(items)} sentences in {len({i[0] for i in items})} documents;"
              f" {len(pending)} uncached -> {len(groups)} requests"
              f" ({'batch' if batch else 'sync'}, model {model}, effort {effort})")
        return 0

    if groups:
        import anthropic  # imported lazily so the rest of the pipeline runs without it

        client = anthropic.Anthropic()
        mk_params = lambda s: _params(model, effort, pv, s)  # noqa: E731
        (_run_batch if batch else _run_sync)(client, con, groups, mk_params, keyfn)

    return _store(con, concepts, items, keyfn, model, pv)


def _store(con, concepts, items, keyfn, model, pv) -> int:
    """Write triples for documents whose sentences are all cached; others wait for a later run."""
    stored = 0
    for doc_id, rows in groupby(items, key=lambda it: it[0]):
        rows = list(rows)
        cached = [con.execute("SELECT response FROM oie_cache WHERE key=?", (keyfn(r[3]),)).fetchone()
                  for r in rows]
        if not all(cached):
            continue
        for (_, concept, lang, sent), c in zip(rows, cached):
            pat = concepts[concept].patterns[lang]
            for t in json.loads(c["response"]):
                if len(t) != 3 or not all(isinstance(x, str) and x.strip() for x in t):
                    continue
                s, r, o = (x.strip() for x in t)
                con.execute(
                    "INSERT INTO triples (doc_id, concept, sentence, subj, rel, obj, concept_role, model, prompt_version)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (doc_id, concept, sent, s, r, o, _role(pat, s, o), model, pv),
                )
                stored += 1
    con.commit()
    return stored
