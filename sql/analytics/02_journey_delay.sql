-- Delay statistics from the educational training dataset.
-- These are not real-time railway performance figures.

SELECT
    COUNT(*) AS total_journeys,
    COUNT(*) FILTER (WHERE is_delayed = 1) AS delayed_journeys,
    COUNT(*) FILTER (WHERE is_delayed = 0) AS on_time_journeys,
    ROUND(
        (
            100.0 * COUNT(*) FILTER (WHERE is_delayed = 1)
            / NULLIF(COUNT(*), 0)
        )::NUMERIC,
        2
    ) AS delay_percentage,
    ROUND(AVG(delay_minutes)::NUMERIC, 2) AS avg_delay_minutes
FROM journey_train;