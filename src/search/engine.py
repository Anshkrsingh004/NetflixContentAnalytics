"""Natural-language catalog search (Milestone 11).

Free-text search over the catalog — type "dark psychological thriller" or
"korean zombie horror" and get the most relevant titles. It reuses the retrieval
architecture from the Milestone 10 recommender (TF-IDF + cosine similarity) and
its **corpus loader**, but builds a *different document representation* on
purpose:

- The **recommender** collapses multi-word names into single tokens
  (``stevenspielberg``) — right for item-to-item similarity.
- **Search** keeps everything as **natural language words** (genres, cast,
  countries, description), because a user's query is natural language — so
  "crime", "thriller", "korea" must match the readable text, not a glued token.
  It also uses **1–2-gram** features and **sublinear TF** so relevance is robust
  to document length.

A query is transformed into the same TF-IDF space and ranked by cosine similarity
against every title's searchable document. This is the standard **vector-space
model** of information retrieval.

Run it with:  ``python -m src.search.engine``
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from src import config
from src.analysis import sql_analytics
from src.database.connection import get_connection
from src.logger import get_logger
from src.recommender.engine import load_corpus

log = get_logger(__name__)

# Fields that make up each title's searchable document, and how many times each
# is repeated (title/genres carry the most weight for relevance).
DOCUMENT_FIELDS = {
    "title": 3, "genres": 2, "description": 1,
    "cast": 1, "directors": 1, "countries": 1, "type": 1, "rating": 1,
}

# Example queries for the sample report.
SAMPLE_QUERIES = [
    "dark psychological thriller",
    "space adventure with aliens",
    "romantic comedy in high school",
    "true crime documentary serial killer",
    "korean zombie horror",
    "world war two history",
]


def _build_document(row: pd.Series) -> str:
    """Combine a title's natural-language fields into one searchable document."""
    parts: list[str] = []
    for field, weight in DOCUMENT_FIELDS.items():
        value = str(row.get(field) or "").replace(",", " ").lower()
        if value and value != "unknown":
            parts.extend([value] * weight)
    return " ".join(parts)


class SearchEngine:
    """A fitted TF-IDF search index over the catalog.

    Build once (``from_connection``) and call :meth:`search` per query — the same
    fit-once/serve-many pattern the dashboard will cache.
    """

    def __init__(self, corpus: pd.DataFrame, vectorizer: TfidfVectorizer, matrix):
        self.corpus = corpus.reset_index(drop=True)
        self.vectorizer = vectorizer
        self.matrix = matrix  # L2-normalized sparse TF-IDF (n_titles x n_features)

    @classmethod
    def from_connection(cls, conn) -> "SearchEngine":
        """Load the shared corpus, build documents, and fit the TF-IDF index."""
        corpus = load_corpus(conn)
        documents = corpus.apply(_build_document, axis=1)
        vectorizer = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 2), min_df=2, sublinear_tf=True,
        )
        matrix = vectorizer.fit_transform(documents)
        log.info("Fitted search index: %d titles x %d features", *matrix.shape)
        return cls(corpus, vectorizer, matrix)

    def search(
        self, query: str, n: int = 10, *, type_filter: str | None = None
    ) -> pd.DataFrame:
        """Return the ``n`` most relevant titles for a free-text ``query``."""
        q_vec = self.vectorizer.transform([query.lower()])
        # Both sides L2-normalized -> cosine similarity is a single mat-vec.
        scores = (self.matrix @ q_vec.T).toarray().ravel()

        rows: list[dict] = []
        for i in np.argsort(-scores):
            if scores[i] <= 0:
                break  # no remaining term overlap
            title = self.corpus.iloc[i]
            if type_filter and title["type"] != type_filter:
                continue
            rows.append({
                "title": title["title"],
                "type": title["type"],
                "release_year": int(title["release_year"]),
                "genres": title["genres"],
                "score": round(float(scores[i]), 3),
            })
            if len(rows) >= n:
                break
        return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Sample report
# ---------------------------------------------------------------------------
def build_report(engine: SearchEngine, queries: list[str]) -> str:
    """Assemble a Markdown report of sample search results."""
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sections = [
        "# 🔎 Natural-Language Search — Sample Queries",
        "",
        f"- **Generated:** {generated}",
        "- **Source:** `data/database/netflix.db` (normalized SQLite DB, Milestone 5)",
        "",
        "> Auto-generated by `src/search/engine.py`. Each title is indexed as a "
        "TF-IDF vector over its title, genres, description, cast, directors, and "
        "countries; a free-text query is projected into the same space and titles "
        "are ranked by cosine similarity (the vector-space retrieval model).",
        "",
    ]
    for query in queries:
        results = engine.search(query, n=8)
        sections += [f'## Query: "{query}"', ""]
        if results.empty:
            sections += ["_No matching titles._", ""]
            continue
        sections += [
            "| # | Title | Type | Year | Score | Genres |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for i, (_, r) in enumerate(results.iterrows(), start=1):
            sections.append(
                f"| {i} | {r['title']} | {r['type']} | {r['release_year']} "
                f"| {r['score']:.3f} | {r['genres']} |"
            )
        sections.append("")
    return "\n".join(sections)


def save_report(engine: SearchEngine, queries: list[str],
                path: Path = config.SEARCH_REPORT) -> Path:
    """Build and write the sample-search report."""
    config.ensure_directories()
    path.write_text(build_report(engine, queries), encoding="utf-8")
    log.info("Search samples written to %s", path)
    return path


def main() -> None:
    """Ensure the DB exists, fit the index, and write sample search results."""
    sql_analytics.ensure_database()
    with get_connection() as conn:
        engine = SearchEngine.from_connection(conn)

    out = save_report(engine, SAMPLE_QUERIES)

    print("\n=== SEARCH SAMPLE ===")
    for query in SAMPLE_QUERIES[:2]:
        print(f'\nQuery: "{query}"')
        for _, r in engine.search(query, n=5).iterrows():
            print(f"  {r['score']:.3f}  {r['title']} ({r['type']}, {r['release_year']})")

    print(f"\n[OK] Search samples saved to: {out}")


if __name__ == "__main__":
    main()
