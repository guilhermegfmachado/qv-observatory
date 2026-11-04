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

The demo writes synthetic data to `site/data/observatory.json` (not tracked in git). The public
site is built from real EUR-Lex data by the weekly `pipeline` workflow and served on GitHub Pages;
see CLAUDE.md. Triple extraction needs `pip install anthropic` and
`ANTHROPIC_API_KEY`.
