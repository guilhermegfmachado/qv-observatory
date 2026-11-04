# QV Observatory

Tracks how concepts travel through European discourse: when *resilience*, *care* or
*polycrisis* surface in EU policy, parliaments, news and art writing, in which language
first, how long art takes to catch up, and how their company changes over time.

Quick start (Python 3.11+):

    python -m unittest discover tests
    python tests/synthetic.py /tmp/demo/corpus
    python -m observatory --db /tmp/demo/demo.sqlite ingest folder /tmp/demo/corpus
    python -m observatory --db /tmp/demo/demo.sqlite mentions
    python -m observatory --db /tmp/demo/demo.sqlite export --synthetic
    cd site && python -m http.server 8000    # open http://localhost:8000

The bundled `site/data/observatory.json` is synthetic test data. Replace it by ingesting
real sources (see CLAUDE.md). Triple extraction needs `pip install anthropic` and
`ANTHROPIC_API_KEY`.
