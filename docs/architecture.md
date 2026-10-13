# RAIL / SIGNAL System Architecture

```
                  +----------------------------------------------+
                  |               RAW DATA SOURCES               |
                  |  - DataMeet GeoJSON (Stations, Trains)       |
                  |  - DataMeet Schedules (Timetables)           |
                  |  - Journey Performance Records (Kaggle/Sim)  |
                  +----------------------------------------------+
                                         |
                                         v
                  +----------------------------------------------+
                  |       MODULAR DATA PIPELINE (Python)         |
                  |  1. Extraction & Source Auditing             |
                  |  2. Schema & Range Validation                |
                  |  3. Deduplication & Clean Transformation     |
                  |  4. Key Integrity & Referential Check        |
                  +----------------------------------------------+
                                   |            \
                 Processed Parquet |             \ Data Quality Logs
                                   v              v
                  +-----------------------+     +--------------------------+
                  |  STORAGE LAYER        |     | PIPELINE OBSERVABILITY   |
                  |  - data/processed/    |     | - pipeline_runs          |
                  |    (*.parquet)        |     | - data_quality_results   |
                  |  - PostgreSQL         |     +--------------------------+
                  |    Relational Tables  |                  |
                  +-----------------------+                  |
                             \                               /
                              \                             /
                               v                           v
                  +----------------------------------------------+
                  |             FASTAPI BACKEND SERVICE          |
                  |  - /api/health                               |
                  |  - /api/overview                             |
                  |  - /api/trains & /api/train-performance      |
                  |  - /api/passenger-utilisation (with badge)   |
                  |  - /api/pipeline-runs & /api/data-quality    |
                  +----------------------------------------------+
                                         |
                                         | REST / JSON
                                         v
                  +----------------------------------------------+
                  |          VITE + REACT DASHBOARD              |
                  |  - Dark Charcoal / Warm Ivory / Signal Lime  |
                  |  - Overview, Train Performance, Passenger    |
                  |    Flow, Pipeline History, Data Quality      |
                  +----------------------------------------------+
```

## Core Architectural Decisions

1. **Storage Decoupling:**
   - Raw source records in GeoJSON/JSON are ingested immutably without in-place modification.
   - Parquet format (`snappy` compressed) provides column-oriented analytical efficiency and compact local storage.
   - PostgreSQL provides indexed relational querying for the FastAPI backend and analytical SQL aggregates.

2. **Data Lineage and Provenance Integrity:**
   - Real infrastructure coordinates and timetable records (DataMeet) are kept structurally distinct from synthetic educational modeling metrics (occupancy, simulated delay flags).
   - In the API and dashboard, simulated attributes are flagged explicitly so users and stakeholders have complete visibility over metric origins.

3. **Data Quality & Observability First:**
   - Every ETL execution creates an audited `run_id` in `pipeline_runs`.
   - Granular checks (unmatched foreign keys, null checks, duplicate rates) write directly to `data_quality_results` to feed the Data Quality dashboard page directly.
