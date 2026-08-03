-- ===========================================================================
-- Business question: What is the split between Movies and TV Shows, and what
--                    share of the whole catalog does each type represent?
-- Technique: GROUP BY aggregation combined with a window function,
--            SUM(COUNT(*)) OVER (), to compute each type's percentage of the
--            total without a separate self-join or subquery.
-- ===========================================================================
SELECT
    type,
    COUNT(*)                                            AS n_titles,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)  AS pct_of_catalog
FROM titles
GROUP BY type
ORDER BY n_titles DESC;
