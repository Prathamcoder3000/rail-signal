# RAIL / SIGNAL — Pipeline Execution Monitoring & Audit Guide

## 1. Overview

RAIL / SIGNAL implements authoritative, non-destructive pipeline execution tracking and monitoring.
Every monitored pipeline run is persisted in PostgreSQL in the `pipeline_runs` table, providing granular stage-by-stage outcomes, timestamps, record tallies, and audit diagnostics.

### Storage Architecture
1. **Authoritative Store (PostgreSQL):** Table `pipeline_runs` in database `rail_signal`.
2. **Redundant Filesystem Audit Log:** `data/processed/pipeline_runs.jsonl` (append-only JSONL event stream).

---

## 2. PostgreSQL Schema: `pipeline_runs`

The DDL definition is versioned in `sql/schema/01_pipeline_runs.sql`. Table and index creation are completely idempotent (`CREATE TABLE IF NOT EXISTS`).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `run_id` | `VARCHAR(64)` | `PRIMARY KEY` | Concurrency-safe unique run ID (e.g. `run_YYYYMMDD_HHMMSS_hex8`). |
| `pipeline_name` | `VARCHAR(128)` | `NOT NULL` | Human-readable name of the executing pipeline. |
| `run_type` | `VARCHAR(32)` | `NOT NULL DEFAULT 'VALIDATION'` | Execution category: `VALIDATION` or `FULL_ETL`. |
| `trigger_type` | `VARCHAR(32)` | `NOT NULL DEFAULT 'MANUAL_API'` | Invocation source: `CLI`, `MANUAL_API`, or `SCHEDULED`. |
| `status` | `VARCHAR(32)` | `NOT NULL CHECK IN (...)` | Overall status: `PENDING`, `RUNNING`, `SUCCESS`, or `FAILED`. |
| `start_time` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Execution commencement timestamp (UTC). |
| `finish_time` | `TIMESTAMPTZ` | `NULL` | Completion or termination timestamp (UTC). |
| `duration_seconds`| `NUMERIC(10, 3)` | `NULL` | Wall-clock execution duration in seconds. |
| `records_processed`| `BIGINT` | `NOT NULL DEFAULT 0` | Total records evaluated across all stages. |
| `records_accepted` | `BIGINT` | `NOT NULL DEFAULT 0` | Valid records accepted. |
| `records_quarantined`| `BIGINT` | `NOT NULL DEFAULT 0` | Records isolated in quarantine logs. |
| `current_stage` | `VARCHAR(128)` | `NULL` | Currently running stage (cleared when run finishes). |
| `failed_stage` | `VARCHAR(128)` | `NULL` | The specific stage where an unhandled failure occurred. |
| `error_summary` | `TEXT` | `NULL` | Sanitized error diagnostic summary. Credentials stripped. |
| `stage_details` | `JSONB` | `NOT NULL DEFAULT '[]'` | Ordered array of stage outcome objects. |
| `metadata` | `JSONB` | `NOT NULL DEFAULT '{}'` | Additional execution parameters, trigger context, and runtime flags. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Record creation timestamp. |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Record last modification timestamp. |

### Indexes
- `idx_pipeline_runs_created_at` on `(created_at DESC)` for fast paginated history retrieval.
- `idx_pipeline_runs_status` on `(status)` for filtering by execution state.
- `idx_pipeline_runs_pipeline_name` on `(pipeline_name)`.
- `idx_pipeline_runs_run_type` on `(run_type)`.

---

## 3. Pipeline Status Definitions

| Status | Meaning | Guarantees |
|---|---|---|
| `RUNNING` | The pipeline or stage is actively executing. | Monitored by `PipelineExecutionTracker`. Upon any handled or unhandled exception, tracker context guarantees automatic transition to `FAILED` so runs are never stranded. |
| `SUCCESS` | All declared stages finished without errors and verified expected prerequisites. | `duration_seconds` and `finish_time` populated; final audit event emitted. |
| `FAILED` | An execution error occurred. | `failed_stage` and `error_summary` are populated; credentials and passwords are strictly stripped. |
| `PENDING` | Reserved for queued or scheduled background executions prior to startup. | Transitioned to `RUNNING` upon start. |

---

## 4. Validation-Only vs. Full ETL Distinction

To satisfy academic safety requirements and guarantee zero data loss, the platform strictly separates validation runs from complete data loads:

### 1. Validation Run (`run_type = 'VALIDATION'`)
- **Default and safe.** Can be triggered freely via API (`POST /api/pipeline/run`) or CLI.
- **Stages:**
  1. `01_environment_and_config`: Verifies `.env` presence, configuration settings, and paths.
  2. `02_raw_datasets_verification`: Confirms 5 raw datasets exist (`stations.json`, `trains.json`, `schedules.json`, `ir_train.csv`, `ir_test.csv`) and checks file sizes.
  3. `03_database_connectivity_and_integrity`: Connects to PostgreSQL, checks baseline table counts (verifies 2,283,664 rows).
  4. `04_storage_artifacts_verification`: Verifies Parquet files in `data/processed/` and checks `quality_report.json`.
- **Data Protection:** Does NOT insert, delete, or modify any database table or raw dataset.

### 2. Full ETL Run (`run_type = 'FULL_ETL'`)
- Re-reads raw sources, applies schema transformation, generates new Parquet files, and reloads tables.
- **Restricted in Phase 1:** `POST /api/pipeline/run` with `mode="full_etl"` returns `HTTP 400 Bad Request` to safeguard existing 2,283,664 PostgreSQL records from accidental overwrite.

---

## 5. API Endpoints Reference

### A. List Execution History
`GET /api/pipeline/history?page=1&page_size=10&status=SUCCESS`

**Response (HTTP 200):**
```json
{
  "items": [
    {
      "run_id": "run_20261027_123133_1d2b05c6",
      "pipeline_name": "RAIL / SIGNAL Validation Pipeline",
      "run_type": "VALIDATION",
      "trigger_type": "MANUAL_API",
      "status": "SUCCESS",
      "start_time": "2026-10-27T12:31:33.118095Z",
      "finish_time": "2026-10-27T12:31:34.907554Z",
      "duration_seconds": 1.789,
      "records_processed": 2283664,
      "records_accepted": 2283664,
      "records_quarantined": 0,
      "current_stage": null,
      "failed_stage": null,
      "error_summary": null,
      "stage_count": 4,
      "created_at": "2026-10-27T12:31:33.118095Z"
    }
  ],
  "total": 19,
  "page": 1,
  "page_size": 10,
  "total_pages": 2,
  "stats": {
    "total_runs": 19,
    "successful_runs": 13,
    "failed_runs": 6,
    "running_runs": 0,
    "latest_run_status": "SUCCESS",
    "latest_run_timestamp": "2026-10-27T12:48:17.919262Z",
    "latest_run_duration_seconds": 3.358
  }
}
```

### B. Get Run Details
`GET /api/pipeline/history/{run_id}`

**Response (HTTP 200):**
```json
{
  "run_id": "run_20261027_123133_1d2b05c6",
  "pipeline_name": "RAIL / SIGNAL Validation Pipeline",
  "run_type": "VALIDATION",
  "trigger_type": "MANUAL_API",
  "status": "SUCCESS",
  "start_time": "2026-10-27T12:31:33.118095Z",
  "finish_time": "2026-10-27T12:31:34.907554Z",
  "duration_seconds": 1.789,
  "records_processed": 2283664,
  "records_accepted": 2283664,
  "records_quarantined": 0,
  "current_stage": null,
  "failed_stage": null,
  "error_summary": null,
  "stage_count": 4,
  "created_at": "2026-10-27T12:31:33.118095Z",
  "stage_details": [
    {
      "stage_name": "01_environment_and_config",
      "status": "SUCCESS",
      "started_at": "2026-10-27T12:31:33.128786Z",
      "ended_at": "2026-10-27T12:31:33.134967Z",
      "duration_seconds": 0.006,
      "records_processed": 0,
      "records_accepted": 0,
      "records_quarantined": 0,
      "details": {
        "env_file_present": true,
        "postgres_host": "localhost",
        "postgres_port": 5432,
        "postgres_db": "rail_signal",
        "app_version": "0.3.0"
      },
      "error": null
    },
    {
      "stage_name": "02_raw_datasets_verification",
      "status": "SUCCESS",
      "started_at": "2026-10-27T12:31:33.136711Z",
      "ended_at": "2026-10-27T12:31:33.141332Z",
      "duration_seconds": 0.005,
      "records_processed": 0,
      "records_accepted": 0,
      "records_quarantined": 0,
      "details": {
        "verified_datasets": {
          "stations": {"path": "data/raw/datameet/stations.json", "size_bytes": 1864683},
          "trains": {"path": "data/raw/datameet/trains.json", "size_bytes": 14768598},
          "schedules": {"path": "data/raw/datameet/schedules.json", "size_bytes": 82174280},
          "journey_train": {"path": "data/raw/operational_journeys/ir_train.csv", "size_bytes": 337159362},
          "journey_test": {"path": "data/raw/operational_journeys/ir_test.csv", "size_bytes": 76010466}
        },
        "all_present": true
      },
      "error": null
    },
    {
      "stage_name": "03_database_connectivity_and_integrity",
      "status": "SUCCESS",
      "started_at": "2026-10-27T12:31:33.143050Z",
      "ended_at": "2026-10-27T12:31:34.895475Z",
      "duration_seconds": 1.752,
      "records_processed": 2283664,
      "records_accepted": 2283664,
      "records_quarantined": 0,
      "details": {
        "database": "rail_signal",
        "table_counts": {
          "stations": 8988,
          "trains": 5207,
          "schedules": 394469,
          "journey_train": 1500000,
          "journey_test": 375000
        },
        "total_rows_verified": 2283664,
        "expected_baseline": 2283664,
        "matches_baseline": true
      },
      "error": null
    },
    {
      "stage_name": "04_storage_artifacts_verification",
      "status": "SUCCESS",
      "started_at": "2026-10-27T12:31:34.899789Z",
      "ended_at": "2026-10-27T12:31:34.905750Z",
      "duration_seconds": 0.006,
      "records_processed": 0,
      "records_accepted": 0,
      "records_quarantined": 0,
      "details": {
        "stations": {"path": "data/processed/stations.parquet", "size_bytes": 387041},
        "trains": {"path": "data/processed/trains.parquet", "size_bytes": 188611},
        "schedules": {"path": "data/processed/schedules.parquet", "size_bytes": 5381805},
        "journey_train": {"path": "data/processed/journey_train.parquet", "size_bytes": 49561864},
        "journey_test": {"path": "data/processed/journey_test.parquet", "size_bytes": 11752071},
        "quality_report_exists": true
      },
      "error": null
    }
  ],
  "metadata": {}
}
```

### C. Trigger Safe Validation Run
`POST /api/pipeline/run`

**Request Body:**
```json
{
  "mode": "validation"
}
```

**Response (HTTP 200):**
```json
{
  "run_id": "run_20261027_123133_1d2b05c6",
  "pipeline_name": "RAIL / SIGNAL Validation Pipeline",
  "run_type": "VALIDATION",
  "status": "SUCCESS",
  "message": "Validation pipeline executed successfully. Verified environment config, 5 raw datasets, 2,283,664 PostgreSQL records, and processed Parquet storage artifacts.",
  "duration_seconds": 1.789,
  "summary": {
    "run_id": "run_20261027_123133_1d2b05c6",
    "pipeline_name": "RAIL / SIGNAL Validation Pipeline",
    "run_type": "VALIDATION",
    "trigger_type": "MANUAL_API",
    "status": "SUCCESS",
    "start_time": "2026-10-27T12:31:33.118095Z",
    "finish_time": "2026-10-27T12:31:34.907554Z",
    "duration_seconds": 1.789,
    "records_processed": 2283664,
    "records_accepted": 2283664,
    "records_quarantined": 0,
    "current_stage": null,
    "failed_stage": null,
    "error_summary": null,
    "stage_count": 4,
    "created_at": "2026-10-27T12:31:33.118095Z"
  }
}
```

---

---

## 6. Frontend Integration & UI Architecture (Phase 2)

Phase 2 connects the Next.js frontend to the authoritative PostgreSQL pipeline monitoring endpoints:

### Features & User Workflows:
1. **Real-Time Aggregate KPI Cards:**
   - Populated from `stats` in `GET /api/pipeline/history`.
   - Displays database-wide metrics: Total Recorded Runs, Successful Runs, Failed Runs, and Latest Execution Status & Duration.
2. **Interactive Pipeline Validation Trigger:**
   - Prominently placed in the page header: **"Run Pipeline Validation"**.
   - Disabled with a spinner during execution to prevent duplicate triggers.
   - Invokes `POST /api/pipeline/run` with `{"mode": "validation"}`.
   - Displays a dismissible success banner with the generated run ID, execution duration, and an "Inspect Telemetry Details →" button.
   - Automatically refreshes the execution history table upon completion.
3. **Execution History Audit Trail Table:**
   - Displays real records from PostgreSQL `pipeline_runs`.
   - Columns: Run ID, Pipeline / Mode, Trigger Type, Status Badge (SUCCESS/FAILED/RUNNING), Started At, Duration, Telemetry (records & stage count), Error Summary, and "Inspect" Action.
   - Features status filter pills (`All Runs`, `SUCCESS`, `FAILED`) and manual refresh button.
   - Server-side pagination controls (`Previous`, `Page X of Y`, `Next`).
4. **Execution Telemetry Detail Drawer (`PipelineDetailDrawer`):**
   - Slide-over drawer accessible by clicking any table row or "Inspect" button.
   - Retrieves telemetry via `GET /api/pipeline/history/{run_id}`.
   - Displays overall duration, record counts, and timestamps.
   - Renders stage-by-stage cards with durations, parameters (e.g. database row counts, verified file sizes), and formatted error diagnostics if failed.

---

## 7. How to Test Locally

### Running Automated Test Suite
Execute the dedicated monitoring test suite:
```powershell
python -m pytest tests/test_pipeline_monitoring.py -v
```

Execute all 66 tests across the entire repository:
```powershell
python -m pytest -v
```

### Running Frontend Validation
In `frontend/`:
```powershell
pnpm exec tsc --noEmit
pnpm build
```

### End-to-End Verification
1. Start the FastAPI backend:
   ```powershell
   python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
   ```
2. Start the Next.js frontend:
   ```powershell
   cd frontend
   pnpm start
   ```
3. Navigate to [http://localhost:3000](http://localhost:3000) and click **Data Pipeline** in the sidebar.
4. Click **Run Pipeline Validation** to trigger live execution and inspect the resulting telemetry drawer.
