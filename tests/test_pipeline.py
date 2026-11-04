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
from observatory.extract import mentions, oie  # noqa: E402
from observatory.ingest import base, folder  # noqa: E402


class FakeClient:
    """Stands in for anthropic.Anthropic: makes 'resilience' the subject of every sentence."""

    class messages:  # noqa: N801
        @staticmethod
        def create(**kw):
            lines = [l for l in kw["messages"][0]["content"].splitlines() if l[:1].isdigit() and ". " in l]
            out = {l.split(". ", 1)[0]: [[l.split(". ", 1)[1].split()[0], "requires", "investment"]]
                   for l in lines}
            block = types.SimpleNamespace(type="text", text=json.dumps(out))
            return types.SimpleNamespace(content=[block])


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

    def test_oie_with_fake_client(self):
        sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=lambda: FakeClient)
        try:
            n = oie.run(self.con, self.cfg, limit=40)
        finally:
            del sys.modules["anthropic"]
        self.assertGreater(n, 0)
        roles = {r[0] for r in self.con.execute("SELECT DISTINCT concept_role FROM triples")}
        self.assertIn("subject", roles)


if __name__ == "__main__":
    unittest.main()
