"""Tests for the central configuration module (Milestone 1)."""

from __future__ import annotations

from src import config


def test_project_root_and_raw_dataset_resolve():
    assert config.PROJECT_ROOT.is_dir()
    assert (config.PROJECT_ROOT / "src").is_dir()
    assert config.RAW_DATASET.exists(), "raw dataset should ship with the repo"


def test_paths_are_anchored_under_project_root():
    for path in (config.DATABASE_PATH, config.CLEAN_DATASET, config.LOG_FILE,
                 config.SQL_ANALYTICS_DIR, config.FIGURES_DIR):
        assert str(path).startswith(str(config.PROJECT_ROOT))


def test_ensure_directories_is_idempotent():
    config.ensure_directories()
    config.ensure_directories()  # second call must not raise
    for directory in config._REQUIRED_DIRS:
        assert directory.is_dir()
