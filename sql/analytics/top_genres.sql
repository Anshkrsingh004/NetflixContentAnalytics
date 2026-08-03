-- ===========================================================================
-- Business question: What are the most common genres across the catalog?
-- Technique: bridge JOIN + GROUP BY. A title carries several genres, so this
--            counts genre memberships (title-genre links), not distinct titles.
-- ===========================================================================
SELECT
    g.genre_name,
    COUNT(*) AS n_titles
FROM title_genres tg
JOIN genres g ON g.genre_id = tg.genre_id
GROUP BY g.genre_name
ORDER BY n_titles DESC
LIMIT 15;
