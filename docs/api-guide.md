# FastAPI Backend API Reference — RAIL / SIGNAL

The **RAIL / SIGNAL** backend exposes RESTful endpoints for railway infrastructure reference data, journey delay analytics, passenger utilisation distributions, and data quality pipeline audits.

---

## 1. Starting the API Server

From the project root directory:

```powershell
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive OpenAPI documentation is automatically available at:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 2. API Endpoints

### 2.1 System & Health

#### `GET /api/health`
Checks application health, version, database connectivity, and table row counts.

**Response Example (`200 OK`):**
```json
{
  "status": "healthy",
  "version": "0.3.0",
  "timestamp": "2026-10-18T14:00:00Z",
  "database": {
    "connected": true,
    "database": "rail_signal",
    "status": "ready"
  },
  "counts": {
    "stations": 8988,
    "trains": 5207,
    "schedules": 394469,
    "journey_train": 1500000,
    "journey_test": 375000
  }
}
```

---

### 2.2 Dashboard Overview

#### `GET /api/overview`
Consolidated operational metrics, delay distributions, category profiles, and dataset freshness.

**Response Example (`200 OK`):**
```json
{
  "kpis": {
    "stations_processed": 8988,
    "trains_processed": 5207,
    "schedules_accepted": 394469,
    "journey_records": 1875000,
    "total_records": 2283664
  },
  "delay_summary": {
    "total_journeys": 1500000,
    "on_time_journeys": 421671,
    "delayed_journeys": 1078329,
    "on_time_percentage": 28.11,
    "delay_percentage": 71.89,
    "avg_delay_minutes": 97.73,
    "provenance_note": "Educational simulation model data from Kaggle IR Predict Train Delay; not real-time telemetry."
  },
  "train_category_profile": [
    {
      "train_type": "PASS",
      "total_trains": 2459,
      "avg_distance_km": 157.98,
      "avg_duration_hours": 4.82
    },
    {
      "train_type": "EXP",
      "total_trains": 1287,
      "avg_distance_km": 947.68,
      "avg_duration_hours": 19.90
    }
  ],
  "passenger_utilisation_summary": {
    "avg_utilisation_pct": 71.60,
    "total_journeys_represented": 1875000,
    "overloaded_journeys": 0,
    "provenance_note": "Simulated occupancy parameter from educational modeling dataset; does not reflect CRIS physical passenger counts."
  },
  "data_freshness": "2026-10-14T14:17:47.813716+00:00"
}
```

---

### 2.3 Trains & Schedules

#### `GET /api/trains`
Searches, filters, and paginates official train reference records.

**Query Parameters:**
- `query` (optional string): Search term matched against `train_number` or `train_name`.
- `train_type` (optional string): Filter by category (e.g. `PASS`, `EXP`, `SF`, `RAJ`, `SHTB`, `DRNT`).
- `zone` (optional string): Filter by administrative zone (e.g. `NR`, `WR`, `CR`).
- `page` (integer, default `1`): 1-indexed page number.
- `page_size` (integer, default `10`, max `100`): Items per page.

**Response Example (`200 OK`):**
```json
{
  "items": [
    {
      "train_number": "12951",
      "train_name": "Mumbai Rajdhani",
      "train_type": "RAJ",
      "zone": "WR",
      "from_station_code": "MMCT",
      "from_station_name": "Mumbai Central",
      "to_station_code": "NDLS",
      "to_station_name": "New Delhi",
      "departure_time": "17:00:00",
      "arrival_time": "08:32:00",
      "duration_hours": 15,
      "duration_minutes": 32,
      "distance_km": 1384,
      "has_first_ac": true,
      "has_second_ac": true,
      "has_third_ac": true,
      "has_sleeper": false,
      "has_chair_car": false,
      "formatted_duration": "15h 32m"
    }
  ],
  "total": 5207,
  "page": 1,
  "page_size": 10,
  "total_pages": 521,
  "available_train_types": ["DEL", "DEMU", "DRNT", "EXP", "GR", "HYD", "JSHTB", "KLKT", "MAIL", "MEMU", "PASS", "RAJ", "SF", "SHTB", "SKR", "TOY"]
}
```

#### `GET /api/trains/{train_number}`
Returns details for a single train including its complete sequence of scheduled stops.

---

### 2.4 Analytics

#### `GET /api/analytics/train-performance`
Category-level and overall route distance and scheduled duration metrics.

#### `GET /api/analytics/delays`
Summary of on-time versus delayed journeys and average delay minutes. Explicitly flagged as synthetic educational modeling data.

#### `GET /api/analytics/passenger-flow`
Seat utilisation averages and four-band distribution across 1.5 million journeys:
- `0–50%`: 10.9% (163,544 records)
- `50–75%`: 42.3% (635,075 records)
- `75–100%`: 46.8% (701,381 records)
- `100%+`: 0.0% (0 records)

---

### 2.5 Data Quality & Pipeline Status

#### `GET /api/data-quality`
Summary of accepted versus quarantined records per dataset and rejection reasons from `quality_report.json`.

#### `GET /api/pipeline/status`
Details on pipeline execution status, 7 workflow stages, and Parquet output specifications.

---

## 3. Running API Tests

Automated tests for all endpoints and error cases:

```powershell
python -m pytest tests/test_api.py -v
```
