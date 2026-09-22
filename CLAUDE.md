# Lectic

Setting this up for someone, or installing a knowledge pack for them? Follow [AGENTS.md](AGENTS.md).

Working on the code? [docs/DEVELOPING.md](docs/DEVELOPING.md) is the contributor guide: run the suite with
`python -m unittest discover -s tests` on Python 3.10+, keep storage changes behind `scripts/store.py`, and
never write to the real `~/.lectic` from a test (`tests/support.py` isolates it).
