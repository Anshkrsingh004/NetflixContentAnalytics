-- ===========================================================================
-- Business question: Which countries produce the most titles in the catalog?
-- Technique: resolve the title-to-country many-to-many through the bridge
--            table, then GROUP BY + ORDER BY + LIMIT. The 'Unknown' sentinel
--            (from titles with no listed country) is filtered out.
-- ===========================================================================
SELECT
    c.country_name,
    COUNT(*) AS n_titles
FROM title_countries tc
JOIN countries c ON c.country_id = tc.country_id
WHERE c.country_name <> 'Unknown'
GROUP BY c.country_name
ORDER BY n_titles DESC
LIMIT 15;
