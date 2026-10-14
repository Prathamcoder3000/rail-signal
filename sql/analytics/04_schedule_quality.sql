-- Completeness overview of accepted schedule records.

SELECT
    COUNT(*) AS total_schedule_records,
    COUNT(*) FILTER (WHERE day_number IS NULL)
        AS missing_day_records,
    COUNT(*) FILTER (WHERE arrival_time IS NULL)
        AS missing_arrival_records,
    COUNT(*) FILTER (WHERE departure_time IS NULL)
        AS missing_departure_records,
    COUNT(DISTINCT train_number) AS distinct_trains,
    COUNT(DISTINCT station_code) AS distinct_stations
FROM schedules;