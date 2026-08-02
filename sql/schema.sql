-- ===========================================================================
-- Netflix Content Analytics Platform — normalized SQLite schema (Milestone 5)
-- ---------------------------------------------------------------------------
-- Design: a single `titles` entity table holds one row per Netflix title.
-- The four multi-value attributes (genre, country, director, cast) each get a
-- dimension table of distinct values plus a bridge (junction) table that
-- resolves the many-to-many relationship. This satisfies Third Normal Form:
-- every non-key attribute depends on the key, and repeating groups are removed.
--
-- Re-runnable: drops existing objects first so the loader can rebuild cleanly.
-- ===========================================================================

PRAGMA foreign_keys = ON;

-- Drop in dependency order (bridges first, then dimensions, then titles) -----
DROP TABLE IF EXISTS title_genres;
DROP TABLE IF EXISTS title_countries;
DROP TABLE IF EXISTS title_directors;
DROP TABLE IF EXISTS title_cast;
DROP TABLE IF EXISTS genres;
DROP TABLE IF EXISTS countries;
DROP TABLE IF EXISTS directors;
DROP TABLE IF EXISTS actors;
DROP TABLE IF EXISTS titles;

-- ---------------------------------------------------------------------------
-- Entity table: one row per title (the grain of the whole database)
-- ---------------------------------------------------------------------------
CREATE TABLE titles (
    show_id        TEXT    PRIMARY KEY,
    type           TEXT    NOT NULL CHECK (type IN ('Movie', 'TV Show')),
    title          TEXT    NOT NULL,
    date_added     TEXT,                 -- ISO 'YYYY-MM-DD' or NULL
    year_added     INTEGER,
    month_added    INTEGER,
    release_year   INTEGER NOT NULL,
    rating         TEXT,
    duration_value INTEGER,
    duration_unit  TEXT    CHECK (duration_unit IN ('Minutes', 'Seasons')),
    description    TEXT
);

-- ---------------------------------------------------------------------------
-- Dimension tables: distinct values for each multi-value attribute
-- (INTEGER PRIMARY KEY is an alias for SQLite's auto-incrementing rowid)
-- ---------------------------------------------------------------------------
CREATE TABLE genres (
    genre_id   INTEGER PRIMARY KEY,
    genre_name TEXT NOT NULL UNIQUE
);

CREATE TABLE countries (
    country_id   INTEGER PRIMARY KEY,
    country_name TEXT NOT NULL UNIQUE
);

CREATE TABLE directors (
    director_id   INTEGER PRIMARY KEY,
    director_name TEXT NOT NULL UNIQUE
);

CREATE TABLE actors (
    actor_id   INTEGER PRIMARY KEY,
    actor_name TEXT NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------------
-- Bridge (junction) tables: resolve the many-to-many relationships.
-- Composite primary key prevents duplicate links; FKs enforce integrity.
-- ---------------------------------------------------------------------------
CREATE TABLE title_genres (
    show_id  TEXT    NOT NULL REFERENCES titles(show_id) ON DELETE CASCADE,
    genre_id INTEGER NOT NULL REFERENCES genres(genre_id) ON DELETE CASCADE,
    PRIMARY KEY (show_id, genre_id)
);

CREATE TABLE title_countries (
    show_id    TEXT    NOT NULL REFERENCES titles(show_id) ON DELETE CASCADE,
    country_id INTEGER NOT NULL REFERENCES countries(country_id) ON DELETE CASCADE,
    PRIMARY KEY (show_id, country_id)
);

CREATE TABLE title_directors (
    show_id     TEXT    NOT NULL REFERENCES titles(show_id) ON DELETE CASCADE,
    director_id INTEGER NOT NULL REFERENCES directors(director_id) ON DELETE CASCADE,
    PRIMARY KEY (show_id, director_id)
);

CREATE TABLE title_cast (
    show_id  TEXT    NOT NULL REFERENCES titles(show_id) ON DELETE CASCADE,
    actor_id INTEGER NOT NULL REFERENCES actors(actor_id) ON DELETE CASCADE,
    PRIMARY KEY (show_id, actor_id)
);

-- ---------------------------------------------------------------------------
-- Indexes: speed up the common filters (type/year) and every bridge join.
-- The show_id side of each bridge is already covered by its composite PK.
-- ---------------------------------------------------------------------------
CREATE INDEX idx_titles_type          ON titles(type);
CREATE INDEX idx_titles_release_year  ON titles(release_year);
CREATE INDEX idx_titles_year_added    ON titles(year_added);
CREATE INDEX idx_title_genres_genre       ON title_genres(genre_id);
CREATE INDEX idx_title_countries_country  ON title_countries(country_id);
CREATE INDEX idx_title_directors_director ON title_directors(director_id);
CREATE INDEX idx_title_cast_actor         ON title_cast(actor_id);
