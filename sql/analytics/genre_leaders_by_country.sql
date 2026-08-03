-- ===========================================================================
-- Business question: For each of the biggest content-producing countries, what
--                    is its single most common genre?
-- Technique: the classic "top-N-per-group" problem. A CTE counts (country,
--            genre) pairs across two chained bridge joins; a second CTE applies
--            RANK() OVER (PARTITION BY country ORDER BY n DESC) so each country
--            is ranked independently; the outer query keeps only rank 1.
-- ===========================================================================
WITH country_genre_counts AS (
    SELECT
        c.country_name,
        g.genre_name,
        COUNT(*) AS n_titles
    FROM title_countries tc
    JOIN countries c     ON c.country_id = tc.country_id
    JOIN title_genres tg ON tg.show_id   = tc.show_id
    JOIN genres g        ON g.genre_id   = tg.genre_id
    WHERE c.country_name <> 'Unknown'
    GROUP BY c.country_name, g.genre_name
),
ranked AS (
    SELECT
        country_name,
        genre_name,
        n_titles,
        RANK() OVER (PARTITION BY country_name ORDER BY n_titles DESC) AS rnk,
        SUM(n_titles) OVER (PARTITION BY country_name)                 AS country_total
    FROM country_genre_counts
)
SELECT
    country_name,
    genre_name AS top_genre,
    n_titles
FROM ranked
WHERE rnk = 1
ORDER BY country_total DESC
LIMIT 15;
