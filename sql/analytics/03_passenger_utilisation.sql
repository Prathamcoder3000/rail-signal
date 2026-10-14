-- Seat utilisation by train type in the educational dataset.

SELECT
    train_type,
    COUNT(*) AS total_journeys,
    ROUND(AVG(seat_utilisation_pct)::NUMERIC, 2)
        AS avg_seat_utilisation_pct,
    COUNT(*) FILTER (WHERE is_overloaded = 1)
        AS overloaded_journeys
FROM journey_train
GROUP BY train_type
ORDER BY avg_seat_utilisation_pct DESC NULLS LAST;