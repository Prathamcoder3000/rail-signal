# Data Dictionary - RAIL / SIGNAL

This data dictionary outlines the entities, attributes, data types, constraints, and lineage across the verified raw sources and the planned processed datasets in the platform.

> **Status Notice:**
> - Raw JSON/CSV files under `data/raw/` are **verified and present**.
> - Parquet files under `data/processed/` and PostgreSQL database tables are **planned design artifacts for Phase 2 and Phase 3** and have not yet been generated.

---

## 1. Physical Railway Infrastructure & Timetables (DataMeet) - Real-World Reference Data

### 1.1 `stations` (Raw: `stations.json` | Planned Parquet & Table: `stations`)
Source: `data/raw/datameet/stations.json` (GeoJSON FeatureCollection: 8,990 features, verified 8,990 unique station codes)

| Field Name | Type | Constraints | Description | Raw Source Key |
| :--- | :--- | :--- | :--- | :--- |
| `station_code` | VARCHAR(10) | PRIMARY KEY, NOT NULL | Unique IRCTC/CRIS alphabetical station code (e.g. NDLS, CSTM) | `properties.code` |
| `station_name` | VARCHAR(150) | NOT NULL | Official station name | `properties.name` |
| `state` | VARCHAR(100) | NULLABLE | Indian State / Union Territory | `properties.state` |
| `zone` | VARCHAR(20) | NULLABLE | Railway administrative zone (e.g. NR, WR, CR, SR) | `properties.zone` |
| `address` | TEXT | NULLABLE | Locality and city address details | `properties.address` |
| `latitude` | NUMERIC(10, 6)| NULLABLE | WGS84 GPS Latitude coordinate | `geometry.coordinates[1]` |
| `longitude` | NUMERIC(10, 6)| NULLABLE | WGS84 GPS Longitude coordinate | `geometry.coordinates[0]` |

### 1.2 `trains` (Raw: `trains.json` | Planned Parquet & Table: `trains`)
Source: `data/raw/datameet/trains.json` (GeoJSON FeatureCollection: 5,208 features, verified 5,208 unique train numbers)

| Field Name | Type | Constraints | Description | Raw Source Key |
| :--- | :--- | :--- | :--- | :--- |
| `train_number` | VARCHAR(10) | PRIMARY KEY, NOT NULL | Standard 5-digit Indian Railways train identifier | `properties.number` |
| `train_name` | VARCHAR(150) | NOT NULL | Official train name | `properties.name` |
| `train_type` | VARCHAR(50) | NULLABLE | Train class category (e.g. EXP, SF, DEMU, PASS) | `properties.type` |
| `zone` | VARCHAR(20) | NULLABLE | Operating administrative zone | `properties.zone` |
| `from_station_code` | VARCHAR(10)| FOREIGN KEY | Origin station code | `properties.from_station_code` |
| `from_station_name` | VARCHAR(150)| NULLABLE | Origin station name | `properties.from_station_name` |
| `to_station_code` | VARCHAR(10)| FOREIGN KEY | Destination station code | `properties.to_station_code` |
| `to_station_name` | VARCHAR(150)| NULLABLE | Destination station name | `properties.to_station_name` |
| `departure_time` | VARCHAR(10) | NULLABLE | Scheduled origin departure time (HH:MM:SS) | `properties.departure` |
| `arrival_time` | VARCHAR(10) | NULLABLE | Scheduled destination arrival time (HH:MM:SS) | `properties.arrival` |
| `duration_hours` | INTEGER | NULLABLE | Journey duration (hours component) | `properties.duration_h` |
| `duration_minutes` | INTEGER | NULLABLE | Journey duration (minutes component) | `properties.duration_m` |
| `distance_km` | INTEGER | NULLABLE | Total scheduled route distance in kilometers | `properties.distance` |
| `has_first_ac` | BOOLEAN | NOT NULL | Accommodates 1A coach | `properties.first_ac > 0` |
| `has_second_ac` | BOOLEAN | NOT NULL | Accommodates 2A coach | `properties.second_ac > 0` |
| `has_third_ac` | BOOLEAN | NOT NULL | Accommodates 3A coach | `properties.third_ac > 0` |
| `has_sleeper` | BOOLEAN | NOT NULL | Accommodates SL coach | `properties.sleeper > 0` |
| `has_chair_car` | BOOLEAN | NOT NULL | Accommodates CC coach | `properties.chair_car > 0` |

### 1.3 `schedules` (Raw: `schedules.json` | Planned Parquet & Table: `schedules`)
Source: `data/raw/datameet/schedules.json` (JSON Array: 417,080 records, verified 417,080 unique IDs)

| Field Name | Type | Constraints | Description | Raw Source Key |
| :--- | :--- | :--- | :--- | :--- |
| `schedule_id` | BIGINT | PRIMARY KEY | Unique stop sequence identifier | `id` |
| `train_number` | VARCHAR(10) | NOT NULL, INDEX | Train 5-digit identifier | `train_number` |
| `station_code` | VARCHAR(10) | NOT NULL, INDEX | Stop station identifier | `station_code` |
| `station_name` | VARCHAR(150) | NULLABLE | Stop station name | `station_name` |
| `arrival_time` | VARCHAR(10) | NULLABLE | Scheduled stop arrival time ('None' for origin departure) | `arrival` |
| `departure_time` | VARCHAR(10) | NULLABLE | Scheduled stop departure time ('None' for terminus arrival) | `departure` |
| `day_number` | INTEGER | NOT NULL | Day of journey (1, 2, 3...) | `day` |

---

## 2. Operational Journey Performance (Kaggle Dataset) - Synthetic Modeling Features

### 2.1 `journey_performance` (Raw: `ir_train.csv` / `ir_test.csv` | Planned Parquet & Table)
Source: `data/raw/operational_journeys/ir_train.csv` (1,500,000 data rows) and `ir_test.csv` (375,000 data rows).

> **DATA PROVENANCE & TARGET LEAKAGE NOTICE:**
> - Metrics including `seat_utilisation_pct`, `is_overloaded`, and `is_delayed` are educational simulation parameters designed for machine learning modeling experiments. They do not constitute actual real-time physical railway sensor telemetry.
> - **Target Leakage Fields:** `primary_delay_cause` and `delay_minutes` exist ONLY in `ir_train.csv` and represent destination outcomes. They are strictly prohibited from being used as model input features.

| Field Name | Type | Constraints | Description | Source Field | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `journey_id` | VARCHAR(64) | PRIMARY KEY | Unique operational journey run ID | `journey_id` | Feature |
| `train_number` | VARCHAR(10) | NULLABLE, INDEX | Associated train identifier | `train_number` | Feature |
| `departure_date`| DATE | NOT NULL, INDEX | Departure date of the journey | `departure_date` | Feature |
| `zone` | VARCHAR(20) | NULLABLE, INDEX | Operating administrative zone | `zone` | Feature |
| `scheduled_travel_hours` | NUMERIC(6, 2) | NULLABLE | Scheduled travel duration | `scheduled_travel_hours` | Feature |
| `num_scheduled_stops` | INTEGER | NULLABLE | Count of scheduled intermediate halts | `num_scheduled_stops` | Feature |
| `is_delayed` | BOOLEAN | NOT NULL | Binary classification target (1 = >15 min delay) [Synthetic] | `is_delayed` | Target |
| `seat_utilisation_pct` | NUMERIC(5, 2) | NULLABLE | Simulated passenger occupancy % [Synthetic] | `seat_utilisation_pct` | Feature (Synthetic) |
| `is_overloaded` | BOOLEAN | NOT NULL | Simulated passenger capacity exceeded [Synthetic]| `is_overloaded` | Feature (Synthetic) |
| `late_incoming_rake` | BOOLEAN | NULLABLE | Inbound rake delay indicator | `late_incoming_rake` | Feature |
| `is_hdn_route` | BOOLEAN | NULLABLE | High Density Network route indicator | `is_hdn_route` | Feature |
| `track_doubled` | BOOLEAN | NULLABLE | Double tracked corridor indicator | `track_doubled` | Feature |
| `primary_delay_cause` | VARCHAR(100) | NULLABLE | Categorical root cause of delay [Train Only] | `primary_delay_cause` | **Target Leakage - Do Not Use as Feature** |
| `delay_minutes` | INTEGER | NULLABLE | Delay in minutes at destination [Train Only] | `delay_minutes` | **Target Leakage - Do Not Use as Feature** |

---

## 3. Data Engineering Audit & Quality Metastore (Planned Phase 3 Entities)

### 3.1 `pipeline_runs` (Planned Design)
Tracks automated ETL pipeline executions for full observability.

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `run_id` | VARCHAR(64) | PRIMARY KEY | UUID identifying pipeline execution |
| `pipeline_name` | VARCHAR(100) | NOT NULL | Target pipeline (e.g. `rail_signal_core_etl`) |
| `status` | VARCHAR(20) | NOT NULL | `STARTED`, `SUCCESS`, `FAILED` |
| `start_time` | TIMESTAMP WITH TIME ZONE | NOT NULL | Pipeline trigger timestamp |
| `end_time` | TIMESTAMP WITH TIME ZONE | NULLABLE | Pipeline termination timestamp |
| `input_records` | BIGINT | NOT NULL | Total records ingested across sources |
| `output_records` | BIGINT | NOT NULL | Total valid records persisted to Parquet/DB |
| `rejected_records` | BIGINT | NOT NULL | Total invalid records caught by validation rules |
| `error_summary` | TEXT | NULLABLE | Structured error message or traceback |

### 3.2 `data_quality_results` (Planned Design)
Records granular schema and business rule validation audit checks.

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `check_id` | VARCHAR(64) | PRIMARY KEY | UUID identifying audit check result |
| `run_id` | VARCHAR(64) | FOREIGN KEY | Associated pipeline run |
| `entity_name` | VARCHAR(100) | NOT NULL | Target table/file (e.g. `stations`, `trains`, `schedules`)|
| `check_type` | VARCHAR(50) | NOT NULL | `NULL_CHECK`, `SCHEMA_VALIDATION`, `DUPLICATE_CHECK`, `REFERENTIAL_INTEGRITY` |
| `status` | VARCHAR(20) | NOT NULL | `PASSED`, `WARNING`, `FAILED` |
| `records_checked` | BIGINT | NOT NULL | Total rows evaluated |
| `failed_records` | BIGINT | NOT NULL | Rows failing criteria |
| `details` | JSONB / TEXT | NULLABLE | Rule details and sample failing keys |
| `created_at` | TIMESTAMP WITH TIME ZONE | NOT NULL | Evaluation timestamp |
