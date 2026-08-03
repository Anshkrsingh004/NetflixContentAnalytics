-- ===========================================================================
-- Business question: When a title is added to Netflix, how "fresh" is it — how
--                    many years pass between a title's release and its addition?
-- Technique: a CTE computes the per-title gap (year_added - release_year), then
--            CASE buckets classify each title so we can read the distribution
--            of content freshness at a glance.
-- ===========================================================================
WITH freshness AS (
    SELECT
        show_id,
        year_added - release_year AS years_to_add
    FROM titles
    WHERE year_added IS NOT NULL
)
SELECT
    CASE
        WHEN years_to_add <= 1  THEN '0-1 yr (new release)'
        WHEN years_to_add <= 3  THEN '2-3 yrs'
        WHEN years_to_add <= 10 THEN '4-10 yrs'
        ELSE '10+ yrs (catalog / classic)'
    END                                                 AS freshness_bucket,
    COUNT(*)                                            AS n_titles,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)  AS pct_of_catalog
FROM freshness
GROUP BY freshness_bucket
ORDER BY MIN(years_to_add);
