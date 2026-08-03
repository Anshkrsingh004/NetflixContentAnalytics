-- ===========================================================================
-- Business question: Which actors appear in the most titles?
-- Technique: bridge JOIN + GROUP BY on the largest dimension (~36k actors),
--            with the 'Unknown' sentinel (titles with no listed cast) removed.
-- ===========================================================================
SELECT
    a.actor_name,
    COUNT(*) AS n_titles
FROM title_cast tc
JOIN actors a ON a.actor_id = tc.actor_id
WHERE a.actor_name <> 'Unknown'
GROUP BY a.actor_name
ORDER BY n_titles DESC
LIMIT 15;
