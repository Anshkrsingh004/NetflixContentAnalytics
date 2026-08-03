# Deployment

The dashboard deploys to **Streamlit Community Cloud** — free, and it builds
straight from this GitHub repository.

## Why it "just works" on a fresh clone

The generated artifacts (the cleaned CSV and the SQLite database) are **not**
committed — they're rebuilt on demand. Only the **raw** dataset
(`data/raw/netflix_titles.csv`) ships in the repo. On first run the app calls
`ensure_database()`, which:

1. runs the cleaning pipeline to produce `data/processed/netflix_clean.csv`, then
2. applies the schema and ETL to build `data/database/netflix.db`.

So a cloud instance that clones the repo has everything it needs — there is **no
data upload step**. (Verified locally by deleting both artifacts and confirming
they rebuild to 8,807 titles.)

## One-time deploy steps (Streamlit Community Cloud)

1. Go to **[share.streamlit.io](https://share.streamlit.io)** and sign in with
   GitHub; authorize access to the repository.
2. Click **Create app → Deploy a public app from GitHub**.
3. Fill in:
   - **Repository:** `Anshkrsingh004/NetflixContentAnalytics`
   - **Branch:** `main`
   - **Main file path:** `src/dashboard/app.py`
4. Open **Advanced settings** and set **Python version = 3.12** (matches
   `requirements.txt`). The repo also pins this via a **`.python-version`** file,
   which the cloud's `uv`-based build reads — important because a newer default
   (e.g. Python 3.14) has no prebuilt wheels for the pinned packages and would try
   to compile Pillow/pandas from source and fail.
5. Click **Deploy**. The first load installs dependencies and builds the database
   (a few seconds); subsequent loads are instant thanks to Streamlit's caching.
6. Copy the resulting URL (e.g. `https://<app-name>.streamlit.app`) into the
   **Live Demo** line of the README.

Pushing to `main` afterwards triggers an **automatic redeploy**.

## Continuous integration

`.github/workflows/ci.yml` runs the full `pytest` suite on every push and pull
request to `main` (Python 3.12, dependencies from `requirements.txt`). Because the
tests build the database from the committed raw CSV, CI needs no extra data setup.
The status badge in the README reflects the latest run.

## Resource notes

- The free tier allows ~1 GB RAM; this app is light — a single SQLite file plus
  two small TF-IDF matrices — and stays well within it.
- Everything Streamlit needs is configured in-repo:
  `requirements.txt` (dependencies) and `.streamlit/config.toml` (theme).
- **`requirements.txt` is deliberately lean** — only the five packages the running
  app imports (`streamlit`, `pandas`, `numpy`, `plotly`, `scikit-learn`). The
  dev-only extras (matplotlib, Jupyter, pytest) live in `requirements-dev.txt`,
  which Streamlit Cloud does **not** install, so builds stay fast. If a deploy
  hangs in the build ("in the oven"), a bloated requirements file is the usual
  cause.
