# Contributing

Domain Atlas is a small local-first project. Keep changes focused, preserve
source provenance, and avoid adding live-provider calls to deterministic tests.

1. Create a focused branch and update the relevant SDD iteration spec when the
   behavior changes.
2. Run `uv sync --extra dev`, then `uv run python scripts/regression.py --fast`
   and the regression layers affected by the change.
3. Never commit `.env`, runtime `data/`, uploads, provider keys, or user
   projects. Use `.env.example` for new configuration names.
4. Treat public writable deployment as a separate security concern. Do not
   weaken source-provenance, SSRF, upload, or provider-cost boundaries merely
   to make a demo easier to use.
