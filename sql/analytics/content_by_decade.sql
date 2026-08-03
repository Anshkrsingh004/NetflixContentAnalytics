-- ===========================================================================
-- Business question: How many Movies vs TV Shows were released in each decade?
-- Technique: derive a decade dimension with integer math on release_year, then
--            use conditional aggregation (CASE inside SUM) to pivot the `type`
--            rows into side-by-side movie / TV-show columns.
-- ===========================================================================
SELECT
    (release_year / 10) * 10                             AS decade,
    SUM(CASE WHEN type = 'Movie'   THEN 1 ELSE 0 END)    AS movies,
    SUM(CASE WHEN type = 'TV Show' THEN 1 ELSE 0 END)    AS tv_shows,
    COUNT(*)                                             AS total
FROM titles
GROUP BY decade
ORDER BY decade;
