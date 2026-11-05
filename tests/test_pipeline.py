"""End-to-end smoke test on the synthetic corpus. Run: python -m unittest discover tests"""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import synthetic  # noqa: E402
from observatory import config, db, export  # noqa: E402
from observatory.analysis import migration  # noqa: E402
from observatory.extract import mentions, oie  # noqa: E402
from observatory.ingest import base, folder  # noqa: E402


def _fake_message(**kw):
    """Makes the first word of every sentence the subject of one triple."""
    assert "temperature" not in kw, "sampling parameters are rejected by current models"
    lines = [l for l in kw["messages"][0]["content"].splitlines() if l[:1].isdigit() and ". " in l]
    out = {l.split(". ", 1)[0]: [[l.split(". ", 1)[1].split()[0], "requires", "investment"]]
           for l in lines}
    block = types.SimpleNamespace(type="text", text=json.dumps(out))
    return types.SimpleNamespace(content=[block], stop_reason="end_turn")


class FakeBatches:
    """Stands in for client.messages.batches: ends immediately, returns results reversed."""

    def __init__(self):
        self.store = {}

    def create(self, requests):
        self.store["b1"] = requests
        return types.SimpleNamespace(id="b1", processing_status="ended")

    def results(self, batch_id):
        for r in reversed(self.store[batch_id]):
            yield types.SimpleNamespace(custom_id=r["custom_id"], result=types.SimpleNamespace(
                type="succeeded", message=_fake_message(**r["params"])))


class FakeClient:
    """Stands in for anthropic.Anthropic."""

    def __init__(self):
        self.messages = types.SimpleNamespace(create=_fake_message, batches=FakeBatches())


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        synthetic.build(cls.tmp / "corpus", per_month=4)
        cls.cfg = config.load()
        cls.con = db.connect(cls.tmp / "t.sqlite")
        base.insert(cls.con, folder.read(cls.tmp / "corpus", "synthetic"))
        mentions.run(cls.con, cls.cfg["_concepts"])

    def test_lexicon_matches_all_languages(self):
        langs = {r[0] for r in self.con.execute(
            "SELECT DISTINCT lang FROM mentions WHERE concept='resilience'")}
        self.assertEqual(langs, {"en", "pt", "nl", "fr"})

    def test_policy_leads_art(self):
        data = export.run(self.con, self.cfg, self.tmp / "o.json", synthetic=True)
        onsets = data["migration"]["concepts"]["resilience"]["onsets"]
        self.assertLess(onsets["policy"], onsets["art"])
        lag = next(l for l in data["migration"]["concepts"]["resilience"]["lags"]
                   if l["lead"] == "policy" and l["follow"] == "art")
        self.assertGreater(lag["lag"], 6)

    def test_drift_detects_vocabulary_shift(self):
        d = export.run(self.con, self.cfg, self.tmp / "o.json")["drift"]["resilience"]["en"]["drift"]
        self.assertTrue(any(step["drift"] > 0.3 for step in d))

    def _oie(self, **kw):
        sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=FakeClient)
        try:
            return oie.run(self.con, self.cfg, **kw)
        finally:
            del sys.modules["anthropic"]

    def test_oie_with_fake_client(self):
        self.assertGreater(self._oie(limit=40), 0)
        roles = {r[0] for r in self.con.execute("SELECT DISTINCT concept_role FROM triples")}
        self.assertIn("subject", roles)

    def test_oie_batch_mode(self):
        before = self.con.execute("SELECT COUNT(DISTINCT doc_id) FROM triples").fetchone()[0]
        self.assertGreater(self._oie(limit=40, batch=True), 0)
        after = self.con.execute("SELECT COUNT(DISTINCT doc_id) FROM triples").fetchone()[0]
        self.assertGreater(after, before)

    def test_gdelt_counts_enter_news_lane(self):
        from observatory.ingest import gdelt
        calls = []

        def fake_timeline(q, a, b):
            calls.append(q)
            return [(a, 50, 1000), (b, 70, 1000)]

        con = db.connect(self.tmp / "g.sqlite")
        self.addCleanup(con.close)
        orig, gdelt.timeline, gdelt.PAUSE = gdelt.timeline, fake_timeline, 0
        try:
            n = gdelt.run(con, self.cfg, langs=("en",), end="2018-06-30")
        finally:
            gdelt.timeline = orig
        self.assertEqual(n, 2 * 2 * len([k for k in self.cfg["concepts"] if "gdelt" in self.cfg["concepts"][k]]))
        self.assertIn("(resilience OR resilient) sourcelang:english", calls)
        mig = migration.run(con, self.cfg)
        series = mig["concepts"]["resilience"]["series"]["news"]
        self.assertEqual(max(v for v in series if v is not None), 0.07)  # 70 of 1000 articles
        self.assertEqual(mig["concepts"]["resilience"]["mentions"], 0)  # counts are not documents

    def test_europarl_parse_groups_speeches_by_language(self):
        from observatory.ingest import europarl
        xml = """<DEBATS><CHAPTER NUMBER="1"><TL-CHAP VL="EN">Item</TL-CHAP>
        <INTERVENTION><ORATEUR PP="NULL" LG="EN" MEPID="1" LIB="A | B"><LG>EN</LG>
        <EMPHAS NAME="B">Chair. –</EMPHAS></ORATEUR><PARA>Resilience matters.</PARA>
        <PARA><EMPHAS NAME="I">(Applause)</EMPHAS></PARA></INTERVENTION>
        <INTERVENTION><ORATEUR LG="FR" MEPID="2"><LG>FR</LG></ORATEUR>
        <PARA>La r&#233;silience compte.</PARA></INTERVENTION></CHAPTER></DEBATS>"""
        self.assertEqual(europarl.parse(xml), {"EN": ["Resilience matters."], "FR": ["La résilience compte."]})

    def test_eurlex_strip_keeps_words_whole(self):
        from observatory.ingest import eurlex
        raw = "<head><title>x</title></head><p>stren<span class='a'>gthening</span> resi\xadlience</p><p>next</p>"
        self.assertEqual(eurlex._strip_html(raw), "strengthening resilience next")

    def test_limit_never_splits_a_document(self):
        items = list(oie.candidates(self.con, self.cfg["_concepts"], 600, limit=3))
        doc = items[-1][0]
        full = [i for i in oie.candidates(self.con, self.cfg["_concepts"], 600) if i[0] == doc]
        self.assertEqual(len([i for i in items if i[0] == doc]), len(full))


if __name__ == "__main__":
    unittest.main()
