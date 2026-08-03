"""Unit tests for the data-quality scoring (Milestone 4 logic)."""

from __future__ import annotations

import pandas as pd
import pytest

from src.analysis import quality


def test_completeness_score_counts_non_null_cells():
    df = pd.DataFrame({"a": [1, None], "b": [1, 2]})  # 3 of 4 cells present
    assert quality.completeness_score(df) == 75.0


def test_duplicate_percentage():
    df = pd.DataFrame({"a": [1, 1, 2, 3]})  # one duplicate row of 4
    assert quality.duplicate_percentage(df) == 25.0
    assert quality.uniqueness_score(df) == 75.0


def test_validity_rules_flags_leaked_duration_in_rating():
    df = pd.DataFrame({
        "type": ["Movie", "TV Show"],
        "rating": ["PG-13", "74 min"],   # second is an invalid (leaked) rating
        "release_year": [2020, 2019],
    })
    rules = quality.validity_rules(df)
    assert rules["type_in_domain"] == 100.0
    assert rules["rating_not_duration"] == 50.0  # 1 of 2 looks like a duration


def test_consistency_score_matches_units_to_type():
    df = pd.DataFrame({
        "type": ["Movie", "TV Show", "Movie"],
        "duration_unit": ["Minutes", "Seasons", "Seasons"],  # last is inconsistent
    })
    assert quality.consistency_score(df) == pytest.approx(66.67, abs=0.01)


def test_consistency_score_na_without_columns():
    assert quality.consistency_score(pd.DataFrame({"type": ["Movie"]})) is None


@pytest.mark.parametrize("score,expected", [
    (99, "A+"), (95, "A"), (91, "A-"), (88, "B"), (80, "C"), (70, "D"), (50, "F"),
])
def test_grade_thresholds(score, expected):
    assert quality.grade(score) == expected


def test_data_quality_score_is_bounded(cleaned_sample):
    score = quality.data_quality_score(cleaned_sample)
    assert 0.0 <= score <= 100.0


def test_assess_returns_expected_keys(cleaned_sample):
    a = quality.assess(cleaned_sample)
    assert set(a) >= {"rows", "columns", "score", "grade", "dimensions"}
    assert a["rows"] == len(cleaned_sample)
