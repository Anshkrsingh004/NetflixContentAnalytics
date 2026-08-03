-- ===========================================================================
-- Business question: Has the average movie runtime changed across decades?
-- Technique: a filtered AVG aggregate (Movies measured in Minutes only),
--            grouped by release decade, with HAVING to drop thinly-populated
--            early decades that would give a noisy average.
-- ===========================================================================
SELECT
    (release_year / 10) * 10        AS decade,
    COUNT(*)                        AS n_movies,
    ROUND(AVG(duration_value), 1)   AS avg_runtime_min
FROM titles
WHERE type = 'Movie' AND duration_unit = 'Minutes'
GROUP BY decade
HAVING COUNT(*) >= 10
ORDER BY decade;
