-- ===========================================================================
-- Business question: How is the catalog distributed across maturity ratings
--                    (TV-MA, PG-13, ...), and which ratings dominate?
-- Technique: GROUP BY with a window SUM(COUNT(*)) OVER () for percentage share.
--            NULL ratings are excluded so percentages describe rated titles.
-- ===========================================================================
SELECT
    rating,
    COUNT(*)                                            AS n_titles,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)  AS pct_of_catalog
FROM titles
WHERE rating IS NOT NULL
GROUP BY rating
ORDER BY n_titles DESC;
