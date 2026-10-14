-- Train performance by train type.
-- Source: educational journey-independent train reference dataset.

SELECT
    train_type,
    COUNT(*) AS total_trains,
    ROUND(AVG(distance_km)::NUMERIC, 2) AS avg_distance_km,
    ROUND(
        AVG(duration_hours + duration_minutes / 60.0)::NUMERIC,
        2
    ) AS avg_duration_hours
FROM trains
WHERE train_type IS NOT NULL
GROUP BY train_type
ORDER BY total_trains DESC;