# Pipeline Ingestion Guide — RAIL / SIGNAL

This document outlines the architecture, operation, and verification of the **Data Ingestion Layer** (`backend/pipeline/ingestion.py`).

---

## 1. Overview & Architectural Principles

The ingestion layer is the foundational entry point of the RAIL / SIGNAL pipeline. Its purpose is to load raw data files safely and efficiently without altering or overwriting source records.

### Key Tenets:
1. **Source Immutability:** All raw data files in `data/raw/` are treated as read-only.
2. **Identifier Preservation:** Identifiers like `train_number` (e.g. `'04601'`) and `station_code` (e.g. `'NDLS'`) are strictly loaded as strings. Leading zeros and uppercase formatting are guaranteed.
3. **Memory Safety & Streaming:** Very large datasets such as `ir_train.csv` (1.5 million rows, 322 MB) support chunked generator reading via `read_journey_csv_chunks`, preventing memory spikes.
4. **Standardized Ingestion Metadata:** Every extraction call returns an `IngestionMetadata` dataclass tracking source path, format, record counts, detected schema columns, file sizes, and status/error details.

---

## 2. Ingestion Module Reference

Module location: `backend/pipeline/ingestion.py`

### 2.1 Functions Available

| Function | Source File | Input Structure | Output |
| :--- | :--- | :--- | :--- |
| `read_stations_geojson(file_path)` | `data/raw/datameet/stations.json` | GeoJSON `FeatureCollection` | Flattened records (with `longitude`, `latitude`) + `IngestionMetadata` |
| `read_trains_geojson(file_path)` | `data/raw/datameet/trains.json` | GeoJSON `FeatureCollection` | Feature properties list (preserving string train numbers) + `IngestionMetadata` |
| `read_schedules_json(file_path, limit)` | `data/raw/datameet/schedules.json` | JSON Array | Stop schedule records (string codes & train numbers) + `IngestionMetadata` |
| `read_journey_csv_chunks(file_path, chunk_size, max_chunks)` | `data/raw/operational_journeys/ir_train.csv` / `ir_test.csv` | Delimited CSV | Generator yielding `pd.DataFrame` chunks + `IngestionMetadata` on completion |
| `read_journey_train_csv(file_path, nrows)` | `data/raw/operational_journeys/ir_train.csv` | CSV | `pd.DataFrame` (preserving string IDs) + `IngestionMetadata` |
| `read_journey_test_csv(file_path, nrows)` | `data/raw/operational_journeys/ir_test.csv` | CSV | `pd.DataFrame` (preserving string IDs) + `IngestionMetadata` |
| `read_sample_submission_csv(file_path, nrows)` | `data/raw/operational_journeys/ir_sample_submission.csv` | CSV | `pd.DataFrame` (columns: `journey_id`, `is_delayed`) + `IngestionMetadata` |
| `read_data_dictionary_csv(file_path)` | `data/raw/operational_journeys/ir_data_dictionary.csv` | CSV | `pd.DataFrame` (columns: `column`, `type`, `description`) + `IngestionMetadata` |

---

## 3. How to Run the Tests

Ingestion unit tests use small isolated fixtures generated dynamically by pytest, avoiding reliance on or mutation of the production datasets:

```powershell
python -m pytest tests/test_ingestion.py -v
```

All 8 tests verify:
- GeoJSON Point and LineString FeatureCollection parsing.
- Schedules array reading and record limiting.
- String preservation of leading zeros and uppercase codes.
- Chunked CSV generation.
- Missing file errors (`FileNotFoundError`).
- Corrupt/invalid JSON structure handling.
