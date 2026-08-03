"""Tests for the content-based recommender (Milestone 10)."""

from __future__ import annotations

from src.recommender import engine


def test_tokenize_names_collapses_and_weights():
    assert engine._tokenize_names("Steven Spielberg, Ang Lee", 1) == "stevenspielberg anglee"
    # weight repeats the tokens
    assert engine._tokenize_names("Dramas", 3) == "dramas dramas dramas"
    # the 'Unknown' sentinel is dropped
    assert engine._tokenize_names("Unknown", 1) == ""
    assert engine._tokenize_names("", 2) == ""


def test_genre_set_drops_unknown_and_blanks():
    assert engine._genre_set("Dramas, Unknown,  ") == {"Dramas"}


def test_recommend_returns_ranked_neighbors(recommender):
    recs, seed = recommender.recommend("Breaking Bad", n=5)
    assert len(recs) == 5
    assert seed["title"] == "Breaking Bad"
    # the seed itself is never recommended
    assert "Breaking Bad" not in set(recs["title"])
    # similarity is sorted high -> low and in [0, 1]
    assert recs["similarity"].is_monotonic_decreasing
    assert recs["similarity"].between(0, 1).all()


def test_recommend_shared_genres_are_a_subset_of_seed(recommender):
    recs, seed = recommender.recommend("Breaking Bad", n=5)
    seed_genres = engine._genre_set(seed["genres"])
    top_shared = engine._genre_set(recs.iloc[0]["shared_genres"])
    assert top_shared <= seed_genres


def test_same_type_filter(recommender):
    recs, _ = recommender.recommend("Breaking Bad", n=5, same_type=True)
    assert (recs["type"] == "TV Show").all()
