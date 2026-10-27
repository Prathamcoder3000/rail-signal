-- ==============================================================================
-- RAIL / SIGNAL — Core Relational Data Model Schema
-- Purpose: Authoritative DDL for core railway datasets (idempotent initialization).
-- Tables: stations, trains, schedules, journey_train, journey_test
-- ==============================================================================

-- 1. STATIONS TABLE
CREATE TABLE IF NOT EXISTS stations (
    station_code TEXT PRIMARY KEY,
    station_name TEXT,
    state TEXT,
    zone TEXT,
    address TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_stations_zone ON stations (zone);
CREATE INDEX IF NOT EXISTS idx_stations_state ON stations (state);

-- 2. TRAINS TABLE
CREATE TABLE IF NOT EXISTS trains (
    train_number TEXT PRIMARY KEY,
    train_name TEXT,
    train_type TEXT,
    zone TEXT,
    from_station_code TEXT,
    from_station_name TEXT,
    to_station_code TEXT,
    to_station_name TEXT,
    departure_time TEXT,
    arrival_time TEXT,
    duration_hours INTEGER,
    duration_minutes INTEGER,
    distance_km INTEGER,
    has_first_ac BOOLEAN,
    has_second_ac BOOLEAN,
    has_third_ac BOOLEAN,
    has_sleeper BOOLEAN,
    has_chair_car BOOLEAN
);

CREATE INDEX IF NOT EXISTS idx_trains_zone ON trains (zone);
CREATE INDEX IF NOT EXISTS idx_trains_train_type ON trains (train_type);
CREATE INDEX IF NOT EXISTS idx_trains_from_station ON trains (from_station_code);
CREATE INDEX IF NOT EXISTS idx_trains_to_station ON trains (to_station_code);

-- 3. SCHEDULES TABLE
CREATE TABLE IF NOT EXISTS schedules (
    schedule_id BIGINT PRIMARY KEY,
    train_number TEXT,
    station_code TEXT,
    station_name TEXT,
    arrival_time TEXT,
    departure_time TEXT,
    day_number INTEGER
);

CREATE INDEX IF NOT EXISTS idx_schedules_train_number ON schedules (train_number);
CREATE INDEX IF NOT EXISTS idx_schedules_station_code ON schedules (station_code);

-- 4. OPERATIONAL JOURNEYS (TRAINING SET)
CREATE TABLE IF NOT EXISTS journey_train (
    journey_id TEXT PRIMARY KEY,
    train_number TEXT,
    train_type TEXT,
    departure_date TEXT,
    year INTEGER,
    month INTEGER,
    day_of_week INTEGER,
    departure_hour INTEGER,
    is_weekend SMALLINT,
    is_night_departure SMALLINT,
    is_peak_hour SMALLINT,
    is_festival_season SMALLINT,
    season TEXT,
    zone TEXT,
    zone_abbr TEXT,
    source_station_category TEXT,
    destination_station_category TEXT,
    distance_km INTEGER,
    num_scheduled_stops INTEGER,
    scheduled_travel_hours DOUBLE PRECISION,
    track_doubled SMALLINT,
    is_hdn_route SMALLINT,
    traction_type TEXT,
    is_electrified SMALLINT,
    psr_count INTEGER,
    is_circular_route SMALLINT,
    is_monsoon_season SMALLINT,
    is_fog_risk SMALLINT,
    fog_risk_score DOUBLE PRECISION,
    zone_fog_index DOUBLE PRECISION,
    zone_congestion_index DOUBLE PRECISION,
    season_severity_score DOUBLE PRECISION,
    loco_age_years DOUBLE PRECISION,
    coach_age_years DOUBLE PRECISION,
    has_lhb_coaches SMALLINT,
    is_rake_shared SMALLINT,
    maintenance_score DOUBLE PRECISION,
    seat_utilisation_pct DOUBLE PRECISION,
    is_overloaded SMALLINT,
    late_incoming_rake SMALLINT,
    is_special_train SMALLINT,
    route_historical_ontime_pct DOUBLE PRECISION,
    primary_delay_cause TEXT,
    delay_minutes INTEGER,
    is_delayed SMALLINT
);

CREATE INDEX IF NOT EXISTS idx_journey_train_train_number ON journey_train (train_number);
CREATE INDEX IF NOT EXISTS idx_journey_train_zone ON journey_train (zone);
CREATE INDEX IF NOT EXISTS idx_journey_train_is_delayed ON journey_train (is_delayed);
CREATE INDEX IF NOT EXISTS idx_journey_train_delay_cause ON journey_train (primary_delay_cause);

-- 5. OPERATIONAL JOURNEYS (TEST/HOLDOUT SET)
CREATE TABLE IF NOT EXISTS journey_test (
    journey_id TEXT PRIMARY KEY,
    train_number TEXT,
    train_type TEXT,
    departure_date TEXT,
    year INTEGER,
    month INTEGER,
    day_of_week INTEGER,
    departure_hour INTEGER,
    is_weekend SMALLINT,
    is_night_departure SMALLINT,
    is_peak_hour SMALLINT,
    is_festival_season SMALLINT,
    season TEXT,
    zone TEXT,
    zone_abbr TEXT,
    source_station_category TEXT,
    destination_station_category TEXT,
    distance_km INTEGER,
    num_scheduled_stops INTEGER,
    scheduled_travel_hours DOUBLE PRECISION,
    track_doubled SMALLINT,
    is_hdn_route SMALLINT,
    traction_type TEXT,
    is_electrified SMALLINT,
    psr_count INTEGER,
    is_circular_route SMALLINT,
    is_monsoon_season SMALLINT,
    is_fog_risk SMALLINT,
    fog_risk_score DOUBLE PRECISION,
    zone_fog_index DOUBLE PRECISION,
    zone_congestion_index DOUBLE PRECISION,
    season_severity_score DOUBLE PRECISION,
    loco_age_years DOUBLE PRECISION,
    coach_age_years DOUBLE PRECISION,
    has_lhb_coaches SMALLINT,
    is_rake_shared SMALLINT,
    maintenance_score DOUBLE PRECISION,
    seat_utilisation_pct DOUBLE PRECISION,
    is_overloaded SMALLINT,
    late_incoming_rake SMALLINT,
    is_special_train SMALLINT,
    route_historical_ontime_pct DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_journey_test_train_number ON journey_test (train_number);
CREATE INDEX IF NOT EXISTS idx_journey_test_zone ON journey_test (zone);
