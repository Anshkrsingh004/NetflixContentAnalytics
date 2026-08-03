"""Tests for natural-language search (Milestone 11)."""

from __future__ import annotations

import pandas as pd

from src.search import engine


def test_build_document_combines_lowercased_fields():
    row = pd.Series({
        "title": "Space Odyssey", "genres": "Sci-Fi", "description": "In DEEP space",
        "cast": "", "directors": "", "countries": "", "type": "Movie", "rating": "PG",
    })
    doc = engine._build_document(row)
    assert "space odyssey" in doc
    assert "sci-fi" in doc
    assert "in deep space" in doc
    # the title is weighted (appears more than once)
    assert doc.count("space odyssey") >= 2


def test_search_returns_ranked_results(search_engine):
    results = search_engine.search("korean zombie horror", n=5)
    assert not results.empty
    assert len(results) <= 5
    assert results["score"].is_monotonic_decreasing
    assert (results["score"] > 0).all()


def test_search_type_filter(search_engine):
    results = search_engine.search("crime drama", n=8, type_filter="Movie")
    assert (results["type"] == "Movie").all()


def test_search_no_match_returns_empty(search_engine):
    results = search_engine.search("qxzwq zzxqwv nonsenseword", n=5)
    assert results.empty
