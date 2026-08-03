"""Content-based recommendation engine (Milestone 10).

Recommends "titles similar to X" using the **content** of each title — its
description plus its genres, cast, directors, and countries — with no viewership
data (there is none). The pipeline is the classic content-based recipe:

1. **Assemble a metadata "soup"** per title, collapsing multi-word names into
   single tokens (so "Steven Spielberg" is one feature, not "steven" + "spielberg"
   colliding with every other Steven) and **weighting** the fields that define
   similarity most (genres > directors > cast/countries).
2. **Vectorize** the soups with **TF-IDF** — term frequency × inverse document
   frequency down-weights words common to everything and up-weights the
   distinctive ones.
3. **Rank by cosine similarity.** Because TF-IDF rows are L2-normalized, cosine
   similarity is just their dot product, computed **one row at a time** against the
   matrix — so we never materialize the 8,807×8,807 dense similarity matrix
   (~600 MB); each query is a fast sparse mat-vec.

Every recommendation is **explainable**: we show the genres it shares with the
seed, so a suggestion is never a black box.

Run it with:  ``python -m src.recommender.engine``
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from src import config
from src.analysis import sql_analytics
from src.database.connection import get_connection
from src.logger import get_logger

log = get_logger(__name__)

# Field weights: how many times each field's tokens are repeated in the soup.
# Genres dominate similarity; description is free text used once.
FIELD_WEIGHTS = {"genres": 3, "directors": 2, "cast": 1, "countries": 1}

# Seed titles for the sample report (only those present in the catalog are used).
SAMPLE_SEEDS = [
    "Breaking Bad", "Stranger Things", "Narcos", "Black Mirror",
    "The Irishman", "Dangal",
]


# ---------------------------------------------------------------------------
# Corpus assembly
# ---------------------------------------------------------------------------
def load_corpus(conn) -> pd.DataFrame:
    """Rebuild one denormalized row per title (from the normalized bridges).

    Public because the M11 search index reuses this exact corpus (it only builds
    a different *document* representation on top of it).
    """
    titles = pd.read_sql_query(
        "SELECT show_id, title, type, rating, release_year, description FROM titles",
        conn,
    )

    def concat_field(bridge: str, dim: str, id_col: str, name_col: str) -> pd.Series:
        pairs = pd.read_sql_query(
            f"SELECT b.show_id, d.{name_col} AS v "
            f"FROM {bridge} b JOIN {dim} d ON d.{id_col} = b.{id_col}",
            conn,
        )
        return pairs.groupby("show_id")["v"].apply(lambda s: ", ".join(s))

    titles["genres"] = titles["show_id"].map(
        concat_field("title_genres", "genres", "genre_id", "genre_name")).fillna("")
    titles["directors"] = titles["show_id"].map(
        concat_field("title_directors", "directors", "director_id", "director_name")).fillna("")
    titles["cast"] = titles["show_id"].map(
        concat_field("title_cast", "actors", "actor_id", "actor_name")).fillna("")
    titles["countries"] = titles["show_id"].map(
        concat_field("title_countries", "countries", "country_id", "country_name")).fillna("")
    return titles


def _tokenize_names(field: str, weight: int) -> str:
    """Collapse a comma-separated list into repeated single-token names.

    "United States, South Korea" -> "unitedstates southkorea"; the 'Unknown'
    sentinel is dropped. ``weight`` repeats the tokens to boost that field.
    """
    if not field:
        return ""
    tokens: list[str] = []
    for part in field.split(","):
        p = part.strip().lower()
        if not p or p == "unknown":
            continue
        tokens.append(re.sub(r"[^a-z0-9]", "", p))  # one solid token per name
    return " ".join(tokens * weight)


def _build_soup(row: pd.Series) -> str:
    """Combine a title's description and weighted metadata into one document."""
    description = str(row["description"] or "").lower()
    return " ".join([
        description,
        _tokenize_names(row["genres"], FIELD_WEIGHTS["genres"]),
        _tokenize_names(row["directors"], FIELD_WEIGHTS["directors"]),
        _tokenize_names(row["cast"], FIELD_WEIGHTS["cast"]),
        _tokenize_names(row["countries"], FIELD_WEIGHTS["countries"]),
    ])


def _genre_set(field: str) -> set[str]:
    """The set of real genre names for a title (for explainability)."""
    return {g.strip() for g in str(field).split(",") if g.strip() and g.strip() != "Unknown"}


# ---------------------------------------------------------------------------
# The recommender
# ---------------------------------------------------------------------------
class Recommender:
    """A fitted TF-IDF content model over the title catalog.

    Build it once (``from_connection``) and call :meth:`recommend` many times —
    which is exactly how the dashboard will use it (fit once, cache, serve).
    """

    def __init__(self, corpus: pd.DataFrame, vectorizer: TfidfVectorizer, matrix):
        self.corpus = corpus.reset_index(drop=True)
        self.vectorizer = vectorizer
        self.matrix = matrix  # L2-normalized sparse TF-IDF (n_titles x n_features)
        # First index wins for duplicate titles; lookup is case-insensitive.
        self._index: dict[str, int] = {}
        for i, title in enumerate(self.corpus["title"]):
            self._index.setdefault(title.strip().lower(), i)

    @classmethod
    def from_connection(cls, conn) -> "Recommender":
        """Load the corpus, build soups, and fit the TF-IDF matrix."""
        corpus = load_corpus(conn)
        corpus["soup"] = corpus.apply(_build_soup, axis=1)
        vectorizer = TfidfVectorizer(stop_words="english", min_df=2)
        matrix = vectorizer.fit_transform(corpus["soup"])
        log.info("Fitted TF-IDF model: %d titles x %d features", *matrix.shape)
        return cls(corpus, vectorizer, matrix)

    def _resolve(self, title: str) -> int:
        """Find a title's row index (exact case-insensitive, then substring)."""
        key = title.strip().lower()
        if key in self._index:
            return self._index[key]
        mask = self.corpus["title"].str.lower().str.contains(re.escape(key), na=False)
        matches = self.corpus.index[mask]
        if len(matches):
            return int(matches[0])
        raise KeyError(f"Title not found in catalog: {title!r}")

    def _similarities(self, idx: int) -> np.ndarray:
        """Cosine similarity of one title against all titles (dense 1-D array)."""
        # L2-normalized rows -> cosine == dot product. One sparse mat-vec, no
        # giant dense matrix.
        return (self.matrix @ self.matrix[idx].T).toarray().ravel()

    def recommend(
        self, title: str, n: int = 10, *, same_type: bool = False
    ) -> tuple[pd.DataFrame, pd.Series]:
        """Return the top-``n`` most similar titles and the resolved seed row."""
        idx = self._resolve(title)
        sims = self._similarities(idx)
        sims[idx] = -1.0  # never recommend the seed itself
        seed = self.corpus.iloc[idx]
        seed_genres = _genre_set(seed["genres"])

        rows: list[dict] = []
        for j in np.argsort(-sims):
            if sims[j] <= 0:
                break
            cand = self.corpus.iloc[j]
            if same_type and cand["type"] != seed["type"]:
                continue
            shared = seed_genres & _genre_set(cand["genres"])
            rows.append({
                "title": cand["title"],
                "type": cand["type"],
                "release_year": int(cand["release_year"]),
                "similarity": round(float(sims[j]), 3),
                "shared_genres": ", ".join(sorted(shared)),
            })
            if len(rows) >= n:
                break
        return pd.DataFrame(rows), seed


# ---------------------------------------------------------------------------
# Sample report
# ---------------------------------------------------------------------------
def build_report(rec: Recommender, seeds: list[str]) -> str:
    """Assemble a Markdown report of sample recommendations for known titles."""
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sections = [
        "# 🎯 Recommendation Samples — Content-Based Engine",
        "",
        f"- **Generated:** {generated}",
        "- **Source:** `data/database/netflix.db` (normalized SQLite DB, Milestone 5)",
        "",
        "> Auto-generated by `src/recommender/engine.py`. Each title is represented "
        "by a TF-IDF vector over its description + weighted genres, cast, directors, "
        "and countries; recommendations are the nearest titles by cosine "
        "similarity. `Shared genres` shows *why* each was suggested.",
        "",
    ]
    for seed in seeds:
        try:
            recs, seed_row = rec.recommend(seed, n=10)
        except KeyError:
            sections += [f"## {seed}", "", "_Not in the catalog — skipped._", ""]
            log.info("Seed not found, skipped: %s", seed)
            continue
        sections += [
            f"## Because you watched *{seed_row['title']}* "
            f"({seed_row['type']}, {int(seed_row['release_year'])})",
            "",
            f"**Genres:** {seed_row['genres']}",
            "",
            "| # | Title | Type | Year | Similarity | Shared genres |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for i, (_, r) in enumerate(recs.iterrows(), start=1):
            sections.append(
                f"| {i} | {r['title']} | {r['type']} | {r['release_year']} "
                f"| {r['similarity']:.3f} | {r['shared_genres']} |"
            )
        sections.append("")
    return "\n".join(sections)


def save_report(rec: Recommender, seeds: list[str],
                path: Path = config.RECOMMENDATIONS_REPORT) -> Path:
    """Build and write the sample-recommendations report."""
    config.ensure_directories()
    path.write_text(build_report(rec, seeds), encoding="utf-8")
    log.info("Recommendation samples written to %s", path)
    return path


def main() -> None:
    """Ensure the DB exists, fit the model, and write sample recommendations."""
    sql_analytics.ensure_database()
    with get_connection() as conn:
        rec = Recommender.from_connection(conn)

    out = save_report(rec, SAMPLE_SEEDS)

    print("\n=== RECOMMENDATION SAMPLE ===")
    for seed in SAMPLE_SEEDS[:2]:
        try:
            recs, seed_row = rec.recommend(seed, n=5)
        except KeyError:
            print(f"\n{seed}: not in catalog")
            continue
        print(f"\nSimilar to '{seed_row['title']}':")
        for _, r in recs.iterrows():
            print(f"  {r['similarity']:.3f}  {r['title']} ({r['type']}, {r['release_year']})")

    print(f"\n[OK] Recommendation samples saved to: {out}")


if __name__ == "__main__":
    main()
