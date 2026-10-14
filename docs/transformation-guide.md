# Data Transformation and Parquet Storage Guide — RAIL / SIGNAL

This document outlines the architecture, data cleaning rules, Parquet storage strategies, and quality reporting for **Phase 2, Step 3** (`backend/pipeline/transformation.py`).

---

## 1. Overview & Architectural Principles

The transformation layer sits between raw ingestion and downstream storage/analytics. It converts semi-structured JSON and raw CSV records into standardized, schema-enforced, column-oriented Parquet files.

### Key Tenets:
1. **Source Immutability:** Raw source files under `data/raw/` are strictly read-only and never modified or overwritten.
2. **Schema Alignment:** Output tables strictly match the fields, constraints, and data types documented in [`docs/data-dictionary.md`](file:///d:/DE%20project/RAIL-SIGNAL/docs/data-dictionary.md).
3. **No Silent Data Loss (Quarantine Audit):** Any record that fails primary key constraints, coordinate boundaries, required field presence, or value ranges is segregated into `data/processed/quarantine/<dataset>_quarantine.json` alongside the specific rejection reason.
4. **Legitimate Journey Endpoint Normalization:** Literal `'None'`, `'null'`, and empty strings in timetable arrival/departure fields represent origin departure and terminus arrival endpoints. They are cleanly normalized to null (`None`) without triggering validation or quarantine rejections.
5. **Memory Safety & Streaming:** The 1.5-million-row journey dataset is streamed incrementally in configurable chunks using `stream_csv_to_parquet` and PyArrow's `ParquetWriter`, avoiding RAM exhaustion.
6. **Atomic Parquet Writes:** Tables are written to temporary files (`<filename>.tmp.<pid>`), verified for row count integrity, and atomically replaced at the target destination.

---

## 2. Parquet Output Artifacts

All processed datasets are saved under `data/processed/` with snappy compression:

| Artifact | Source Ingestion | Primary Key / IDs | Schema Highlights |
| :--- | :--- | :--- | :--- |
| `stations.parquet` | `data/raw/datameet/stations.json` | `station_code` (VARCHAR, uppercase) | Standardized names, zones, states, coordinates bounded to `[-180, 180]` and `[-90, 90]`. |
| `trains.parquet` | `data/raw/datameet/trains.json` | `train_number` (VARCHAR, string) | Preserves leading zeros (`'04601'`), origin/dest codes, durations, coach class booleans (`has_first_ac`, etc.). |
| `schedules.parquet` | `data/raw/datameet/schedules.json` | `schedule_id` (INT64) | Normalized `arrival_time` / `departure_time` (null for endpoints), positive `day_number`, string train and station codes. |
| `journey_train.parquet` | `data/raw/operational_journeys/ir_train.csv` | `journey_id` (VARCHAR) | Binary target `is_delayed` $\in \{0, 1\}$, non-negative distance/travel hours, seat utilisation $\in [0, 100]$. |
| `journey_test.parquet` | `data/raw/operational_journeys/ir_test.csv` | `journey_id` (VARCHAR) | Contains approved features only. **Guaranteed zero presence of target or delay outcome columns.** |

---

## 3. Cleaning & Quarantine Rules

| Dataset | Required Fields | Quarantine Conditions | Warning Conditions |
| :--- | :--- | :--- | :--- |
| **Stations** | `station_code`, `station_name` | - Empty code or name<br>- Duplicate `station_code`<br>- Coordinates out of bounds | Missing optional attributes (`state`, `zone`, `address`) |
| **Trains** | `train_number`, `train_name` | - Empty number or name<br>- Duplicate `train_number`<br>- Negative distance or duration | Unmatched origin/destination station references |
| **Schedules** | `schedule_id`, `train_number`, `station_code`, `day_number` | - Missing or invalid `schedule_id`<br>- Duplicate `schedule_id`<br>- Empty train number or station code<br>- `day_number < 1` | Unmatched train number or station code references |
| **Journeys (Train)** | `journey_id`, `is_delayed` | - Missing or duplicate `journey_id`<br>- Target `is_delayed` not 0 or 1<br>- Negative distance<br>- Seat utilisation outside `[0, 100]` | Inbound rake delays, high density corridor indicators |
| **Journeys (Test)** | `journey_id` | - Missing or duplicate `journey_id`<br>- Negative distance<br>- Seat utilisation outside `[0, 100]` | Leakage columns stripped if present |

---

## 4. Execution & Testing

### Running Unit Tests (In-Memory Fixtures)
To verify transformation, atomic writing, chunked streaming, and quarantine tracking without reading production files:

```powershell
python -m pytest tests/test_transformation.py -v
```

To run the complete Phase 2 test suite (40 tests):

```powershell
python -m pytest tests/test_ingestion.py tests/test_validation.py tests/test_transformation.py -v
```

### Executing the Production Transformation Pipeline
To run transformation and write Parquet outputs to `data/processed/`:

```python
from backend.pipeline.transformation import execute_transformation_pipeline

report = execute_transformation_pipeline(
    raw_dir="data/raw",
    processed_dir="data/processed",
    chunk_size=50000,
)
print("Pipeline run completed. Success:", report.pipeline_success)
```

The execution produces:
- `data/processed/*.parquet`
- `data/processed/quarantine/*_quarantine.json`
- `data/processed/quality_report.json`
