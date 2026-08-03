"""Unit tests for the data-cleaning pipeline (Milestone 3 logic)."""

from __future__ import annotations

import pandas as pd
import pytest

from src.cleaning import cleaners
from src.cleaning.validation import DataValidationError, validate_clean_data


def test_strip_whitespace_trims_and_blanks_to_na():
    df = pd.DataFrame({"title": ["  Alpha  ", "   ", "Beta"]})
    out = cleaners.strip_whitespace(df)
    assert out["title"].tolist()[0] == "Alpha"
    assert pd.isna(out["title"].tolist()[1])   # "   " -> NA
    # input not mutated (pure function)
    assert df["title"].tolist()[0] == "  Alpha  "


def test_remove_duplicates_drops_repeated_show_id():
    df = pd.DataFrame({"show_id": ["a", "a", "b"], "title": ["x", "y", "z"]})
    out = cleaners.remove_duplicates(df)
    assert out["show_id"].tolist() == ["a", "b"]  # keeps first 'a'


def test_normalize_list_string_removes_empty_and_leading_tokens():
    assert cleaners._normalize_list_string(", South Korea") == "South Korea"
    assert cleaners._normalize_list_string("A,  , B") == "A, B"
    assert pd.isna(cleaners._normalize_list_string(", ,"))


def test_fix_rating_duration_leakage():
    df = pd.DataFrame({
        "rating": ["74 min", "PG-13"],
        "duration": [pd.NA, "90 min"],
    })
    out = cleaners.fix_rating_duration_leakage(df)
    assert out.loc[0, "duration"] == "74 min"
    assert out.loc[0, "rating"] == cleaners.DEFAULT_RATING  # "NR"
    assert out.loc[1, "rating"] == "PG-13"                  # untouched


def test_split_duration_handles_both_units():
    df = pd.DataFrame({"duration": ["90 min", "2 Seasons", "1 Season"]})
    out = cleaners.split_duration(df)
    assert out["duration_value"].tolist() == [90, 2, 1]
    assert out["duration_unit"].tolist() == ["Minutes", "Seasons", "Seasons"]
    assert str(out["duration_value"].dtype) == "Int64"


def test_clean_rating_fills_na_with_nr():
    df = pd.DataFrame({"rating": ["PG", pd.NA]})
    out = cleaners.clean_rating(df)
    assert out["rating"].tolist() == ["PG", "NR"]


def test_parse_date_added_extracts_parts_and_coerces_bad_dates():
    df = pd.DataFrame({"date_added": ["September 25, 2021", "not a date"]})
    out = cleaners.parse_date_added(df)
    assert out.loc[0, "year_added"] == 2021
    assert out.loc[0, "month_added"] == 9
    assert pd.isna(out.loc[1, "date_added"])
    assert pd.isna(out.loc[1, "year_added"])


def test_fill_missing_values_uses_sentinel():
    df = pd.DataFrame({
        "director": ["D", pd.NA], "cast": [pd.NA, "C"], "country": ["US", pd.NA],
    })
    out = cleaners.fill_missing_values(df)
    assert out["director"].tolist() == ["D", "Unknown"]
    assert out["cast"].tolist() == ["Unknown", "C"]


def test_add_primary_values_takes_first_token():
    df = pd.DataFrame({
        "country": ["United States, India", pd.NA],
        "listed_in": ["Dramas, Comedies", "Documentaries"],
    })
    out = cleaners.add_primary_values(df)
    assert out["primary_country"].tolist() == ["United States", "Unknown"]
    assert out["primary_genre"].tolist() == ["Dramas", "Documentaries"]


# --- Pipeline + validation (integration over the synthetic sample) ---------
def test_pipeline_produces_valid_clean_frame(cleaned_sample):
    df = cleaned_sample
    # the duplicate show_id (s1) was collapsed
    assert df["show_id"].is_unique
    assert len(df) == 5
    # derived columns exist
    for col in ("duration_value", "duration_unit", "year_added",
                "primary_country", "primary_genre"):
        assert col in df.columns
    # the leaked row was repaired: Gamma now has a numeric duration and NR rating
    gamma = df[df["title"] == "Gamma"].iloc[0]
    assert gamma["duration_value"] == 74
    assert gamma["duration_unit"] == "Minutes"
    assert gamma["rating"] == "NR"
    # nulls filled
    assert (df["director"] != "").all() and df["director"].notna().all()
    assert "Unknown" in df["country"].tolist()


def test_validate_clean_data_passes_on_clean_sample(cleaned_sample):
    results = validate_clean_data(cleaned_sample)
    # every critical check passed (function would have raised otherwise)
    assert results["show_id_unique"]
    assert results["type_values_valid"]
    assert results["duration_unit_valid"]


def test_validate_clean_data_raises_on_duplicate_key(cleaned_sample):
    broken = pd.concat([cleaned_sample, cleaned_sample.iloc[[0]]], ignore_index=True)
    with pytest.raises(DataValidationError):
        validate_clean_data(broken)
