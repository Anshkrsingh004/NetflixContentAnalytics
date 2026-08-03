-- ===========================================================================
-- Business question: Which directors have the most titles on Netflix?
-- Technique: bridge JOIN + GROUP BY with the 'Unknown' sentinel filtered out
--            (about 30% of titles list no director, so leaving it in would
--            drown out every real name).
-- ===========================================================================
SELECT
    d.director_name,
    COUNT(*) AS n_titles
FROM title_directors td
JOIN directors d ON d.director_id = td.director_id
WHERE d.director_name <> 'Unknown'
GROUP BY d.director_name
ORDER BY n_titles DESC
LIMIT 15;
