-- ===========================================================================
-- Business question: How has the catalog grown over time — how many titles
--                    were added each year, and what is the cumulative total?
-- Technique: a running total via SUM(COUNT(*)) OVER (ORDER BY year_added).
--            The window's default frame accumulates every prior group's count.
-- ===========================================================================
SELECT
    year_added,
    COUNT(*)                                    AS titles_added,
    SUM(COUNT(*)) OVER (ORDER BY year_added)     AS cumulative_titles
FROM titles
WHERE year_added IS NOT NULL
GROUP BY year_added
ORDER BY year_added;
