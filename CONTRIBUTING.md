# Contributing

Thanks for your interest in the Netflix Content Analytics Platform. This is a
portfolio project, but it's built like a real one — so contributions and the
conventions below are welcome and expected.

## Getting set up

```bash
python -m venv .venv
# Windows:  .\.venv\Scripts\Activate.ps1
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
pytest                      # confirm a green baseline (67 tests)
```

The database and cleaned dataset are generated artifacts (git-ignored). Any entry
point that needs them will build them from the committed raw CSV on first run, so
there is no manual setup step.

## Project conventions

These mirror how the codebase is already written — please keep them consistent:

- **Central config.** Every path and project-wide constant lives in
  `src/config.py`. Never hard-code a file location elsewhere.
- **Logging, not `print()`.** Modules obtain a logger via
  `get_logger(__name__)`; `print()` is only for a script's user-facing CLI output.
- **Small, pure functions.** Transformations take a value and return a new one
  without mutating the input (the cleaning pipeline relies on this).
- **Reuse the layers below.** Build on the existing SQL/KPI/chart/corpus layers
  rather than re-deriving their results — there should be one source of truth for
  each computed value.
- **Docstrings.** Every module and public function has a docstring explaining the
  *why*, not just the *what*.

## Tests

- Add or update tests for any new logic. Pure logic gets a **unit test** on a
  small synthetic input; anything touching the database or a model gets an
  **integration test** (see `tests/`).
- For code whose exact output isn't fixed (e.g. the recommender), assert
  **invariants** rather than specific values.
- Keep the suite fast and deterministic — no network calls.

```bash
pytest              # run everything
pytest tests/test_cleaning.py -v
```

## Commits & pull requests

- Use clear, conventional commit messages: `feat(scope): …`, `fix(scope): …`,
  `test: …`, `docs: …`, `chore: …`.
- Keep a PR focused on one change; describe what and why, and confirm `pytest`
  passes.

## Data source

The dataset is the public *Netflix Movies and TV Shows* catalog from Kaggle. Please
don't commit large regenerated artifacts (cleaned CSVs, the SQLite DB) — they're
git-ignored on purpose.
