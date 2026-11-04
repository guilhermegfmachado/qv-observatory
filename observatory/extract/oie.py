"""Open information extraction with the Claude API, restricted to sentences that mention a
tracked concept (keeps cost proportional to signal, not corpus size).

The prompt is pinned by `prompt_version`; changing it requires bumping the version so cached
and stored triples stay comparable. Requires `pip install anthropic` and ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3

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


def _key(prompt_version: str, model: str, sentence: str) -> str:
    return hashlib.sha1(f"{prompt_version}|{model}|{sentence}".encode()).hexdigest()


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
    skipping documents that already have triples."""
    q = """SELECT DISTINCT d.id, d.text, m.concept, m.lang FROM documents d
           JOIN mentions m ON m.doc_id = d.id
           WHERE d.id NOT IN (SELECT DISTINCT doc_id FROM triples)"""
    n = 0
    for row in con.execute(q):
        pat = concepts[row["concept"]].patterns[row["lang"]]
        for s in sentences(row["text"]):
            if len(s) <= max_chars and pat.search(s):
                yield row["id"], row["concept"], row["lang"], s
                n += 1
                if limit and n >= limit:
                    return


def run(con: sqlite3.Connection, cfg: dict, limit: int | None = None, dry_run: bool = False) -> int:
    ocfg = cfg["oie"]
    model, pv, bs = ocfg["model"], ocfg["prompt_version"], ocfg["batch_size"]
    concepts = cfg["_concepts"]
    items = list(candidates(con, concepts, ocfg["max_sentence_chars"], limit))
    if dry_run:
        print(f"{len(items)} sentences would be sent ({-(-len(items) // bs)} requests, model {model})")
        return 0

    import anthropic  # imported lazily so the rest of the pipeline runs without it

    client = anthropic.Anthropic()
    stored = 0
    for i in range(0, len(items), bs):
        batch = items[i : i + bs]
        uncached = [it for it in batch if not con.execute(
            "SELECT 1 FROM oie_cache WHERE key=?", (_key(pv, model, it[3]),)).fetchone()]
        if uncached:
            numbered = "\n".join(f"{j}. {it[3]}" for j, it in enumerate(uncached))
            msg = client.messages.create(
                model=model, max_tokens=4000, temperature=0,
                messages=[{"role": "user", "content": PROMPTS[pv].replace("{sentences}", numbered)}],
            )
            text = "".join(b.text for b in msg.content if b.type == "text")
            try:
                parsed = _parse(text)
            except json.JSONDecodeError:
                print(f"  batch {i // bs}: unparseable response, skipped")
                continue
            for j, it in enumerate(uncached):
                con.execute("INSERT OR REPLACE INTO oie_cache VALUES (?,?)",
                            (_key(pv, model, it[3]), json.dumps(parsed.get(str(j), []), ensure_ascii=False)))
        for doc_id, concept, lang, sent in batch:
            row = con.execute("SELECT response FROM oie_cache WHERE key=?", (_key(pv, model, sent),)).fetchone()
            if not row:
                continue
            pat = concepts[concept].patterns[lang]
            for t in json.loads(row["response"]):
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
        print(f"  {min(i + bs, len(items))}/{len(items)} sentences, {stored} triples")
    return stored
