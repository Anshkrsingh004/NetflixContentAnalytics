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
   `requirements.txt`).
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
