"""Central configuration for the Netflix Content Analytics Platform.

Every path and project-wide constant lives here so that no other module ever
hard-codes a file location. Paths are built with :mod:`pathlib` and anchored to
the repository root, which makes the code portable across operating systems
(Windows/macOS/Linux) and independent of the current working directory — a
notebook, a test, and the Streamlit app all resolve to the same files.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Core project paths
# ---------------------------------------------------------------------------
# This file lives at <root>/src/config.py, so the project root is two parents
# up. Using ``resolve()`` turns it into an absolute path with no ".." parts.
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]

# Data directories
DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_DATA_DIR: Path = DATA_DIR / "raw"
PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
DATABASE_DIR: Path = DATA_DIR / "database"

# Other top-level directories
NOTEBOOKS_DIR: Path = PROJECT_ROOT / "notebooks"
SQL_DIR: Path = PROJECT_ROOT / "sql"
ASSETS_DIR: Path = PROJECT_ROOT / "assets"
LOGS_DIR: Path = PROJECT_ROOT / "logs"
REPORTS_DIR: Path = PROJECT_ROOT / "reports"  # generated analytical reports

# ---------------------------------------------------------------------------
# Key files (created in later milestones — defined now so every module agrees
# on where they will live)
# ---------------------------------------------------------------------------
RAW_DATASET: Path = RAW_DATA_DIR / "netflix_titles.csv"          # source data
CLEAN_DATASET: Path = PROCESSED_DATA_DIR / "netflix_clean.csv"   # Milestone 3
DATABASE_PATH: Path = DATABASE_DIR / "netflix.db"               # Milestone 5

# Generated reports
DATA_PROFILE_REPORT: Path = REPORTS_DIR / "data_profile.md"     # Milestone 2
DATA_QUALITY_REPORT: Path = REPORTS_DIR / "data_quality_report.md"  # Milestone 4

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE: Path = LOGS_DIR / "netflix_analytics.log"
LOG_LEVEL: str = "INFO"

# Directories that must exist for the pipeline to run end-to-end.
_REQUIRED_DIRS: list[Path] = [
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    DATABASE_DIR,
    LOGS_DIR,
    REPORTS_DIR,
]


def ensure_directories() -> None:
    """Create every required project directory if it does not already exist.

    Safe to call repeatedly: ``mkdir(exist_ok=True)`` is idempotent. Call this
    at the start of any script that writes output so the run never fails just
    because a folder is missing (e.g. on a fresh clone).
    """
    for directory in _REQUIRED_DIRS:
        directory.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    # Quick manual check: print the resolved configuration.
    ensure_directories()
    print("Netflix Content Analytics - resolved configuration")
    print(f"  PROJECT_ROOT   : {PROJECT_ROOT}")
    print(f"  RAW_DATASET    : {RAW_DATASET}  (exists={RAW_DATASET.exists()})")
    print(f"  CLEAN_DATASET  : {CLEAN_DATASET}")
    print(f"  DATABASE_PATH  : {DATABASE_PATH}")
    print(f"  LOG_FILE       : {LOG_FILE}")
