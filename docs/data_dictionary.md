# 📖 Data Dictionary — Netflix Titles Dataset

**Source file:** `data/raw/netflix_titles.csv`
**Rows:** 8,807 &nbsp;•&nbsp; **Columns:** 12 &nbsp;•&nbsp; **Grain:** one row per Netflix title
**Primary key:** `show_id` (100% unique, no nulls)

> This document describes the **raw** dataset *as received* — including its
> known quality issues. Cleaning decisions that resolve these issues are
> implemented in Milestone 3 (`src/cleaning/`). Statistics below were produced
> by `src/analysis/profiling.py`.

---

## Unit of Analysis
Each row represents a single **Movie** or **TV Show** in Netflix's catalog. The
dataset is a catalog snapshot (titles added up to **September 2021**); it does
**not** contain viewership, ratings-by-users, or revenue — so all analysis is
about *catalog composition and growth*, not popularity.

---

## Column Reference

| # | Column | Raw Type | Missing % | Description | Example | Notes / Quality Issues |
|---|--------|----------|-----------|-------------|---------|------------------------|
| 1 | `show_id` | text | 0% | Unique identifier for each title. **Primary key.** | `s1` | Clean. 8,807 unique values. |
| 2 | `type` | text | 0% | Whether the title is a Movie or a TV Show. | `Movie` | Only 2 values: **Movie (6,131)**, **TV Show (2,676)**. |
| 3 | `title` | text | 0% | Name of the title. | `Blood & Water` | 8,807 unique. Safe secondary label. |
| 4 | `director` | text | **29.91%** | Director(s), comma-separated. | `Kirsten Johnson` | Highest missingness (2,634 nulls). Multi-value: **4,993 distinct directors**. |
| 5 | `cast` | text | 9.37% | Billed cast, comma-separated. | `Ama Qamata, Khosi Ngema` | 825 nulls. Multi-value: **36,439 distinct actors** across 64,126 mentions. |
| 6 | `country` | text | 9.44% | Production country/countries, comma-separated. | `United States, India` | 831 nulls. Multi-value: **122 distinct countries**. US dominates (3,690). |
| 7 | `date_added` | text | 0.11% | Date the title was added to Netflix. | `September 25, 2021` | 10 nulls. Stored as text in `"%B %d, %Y"` format → parse to date in M3. Range: **2008-01-01 → 2021-09-25**. |
| 8 | `release_year` | integer | 0% | Year the title was originally released. | `2020` | Clean integer. Range **1925 → 2021**. Not the same as `date_added`. |
| 9 | `rating` | text | 0.05% | Maturity/content rating (TV/MPAA). | `TV-MA` | **⚠️ Dirty:** 3 rows contain a *duration* (`74 min`, `84 min`, `66 min`) instead of a rating — see below. |
| 10 | `duration` | text | 0.03% | Length: minutes (movies) or seasons (TV). | `90 min` / `2 Seasons` | **Dual-unit & dual-type:** 6,128 in minutes, 2,676 in seasons. 3 nulls (the mis-shifted rows). Needs splitting into a number + unit in M3. |
| 11 | `listed_in` | text | 0% | Genres/categories, comma-separated. | `Dramas, International Movies` | Multi-value: **42 distinct genres** across 19,323 mentions. 514 unique raw combinations. |
| 12 | `description` | text | 0% | Short synopsis. | `As her father nears the end...` | 8,775 unique (near-unique). Feeds the recommendation engine (M10). |

---

## ⚠️ Known Data-Quality Issues (to resolve in Milestone 3)

1. **Rating/duration column leakage (3 rows).**
   Titles `s5542` (*Louis C.K. 2017*), `s5795` (*Louis C.K.: Hilarious*), and
   `s5814` (*Louis C.K.: Live at the Comedy Store*) have their **duration
   value sitting in the `rating` column** (`74 min`, `84 min`, `66 min`) and a
   **null `duration`**. The data is shifted one column over.
   → *Fix:* move the `"… min"` value into `duration`, and set `rating` to a
   valid "unknown" category (`NR`).

2. **`duration` mixes two units and depends on `type`.**
   Movies are measured in **minutes**, TV shows in **seasons**. A single numeric
   column can't represent both.
   → *Fix:* split into `duration_value` (int) + `duration_unit` (`min`/`Season(s)`),
   or derive `duration_minutes` for movies and `num_seasons` for TV shows.

3. **`date_added` is text, not a date.**
   Stored as `"September 25, 2021"` with occasional leading whitespace.
   → *Fix:* strip whitespace and parse with format `"%B %d, %Y"`; derive
   `year_added` / `month_added` for time-series analysis. (All 8,797 non-null
   values parse successfully.)

4. **Multi-value columns** (`director`, `cast`, `country`, `listed_in`).
   Comma-separated lists in a single cell violate first normal form (1NF) and
   can't be grouped/filtered directly.
   → *Fix:* keep the raw column for display, and (in M5) explode into bridge
   tables so we can answer "how many titles per country/genre/actor".

5. **Missing values** concentrated in `director` (29.9%), `country` (9.4%), and
   `cast` (9.4%).
   → *Fix:* fill with an explicit sentinel (e.g. `"Unknown"`) rather than
   dropping rows — dropping would discard ~30% of the catalog. Decision and
   rationale documented in M3.

6. **`rating` also carries a small "unknown" tail** (`NR`, `UR`) — legitimate
   values meaning *Not Rated* / *Unrated*, kept as-is.

---

## Cardinality Highlights
- **Perfectly unique (keys):** `show_id`, `title` (both 8,807).
- **Very low cardinality (great for filters):** `type` (2), `rating` (14 valid),
  `release_year` (74).
- **High cardinality (multi-value):** `cast` (36k+ actors), `director` (~5k),
  `country` (122), `listed_in` (42 genres).

---

## Downstream Usage Map
| Consumer (later milestone) | Columns relied on |
|----------------------------|-------------------|
| Cleaning pipeline (M3) | all — especially `rating`, `duration`, `date_added` |
| SQLite schema (M5) | `show_id` (PK), exploded `country`/`listed_in`/`cast`/`director` |
| KPIs & EDA (M6–M8) | `type`, `release_year`, `date_added`, `country`, `listed_in` |
| Recommendation engine (M10) | `listed_in`, `cast`, `director`, `description`, `type` |
| Dashboard filters (M13) | `type`, `country`, `listed_in`, `director`, `release_year` |
