# 🚆 RAIL / SIGNAL
### Railway Operations & Passenger Flow Data Engineering Platform

RAIL / SIGNAL is an end-to-end data engineering platform designed to process railway-related datasets, validate data quality, store structured information in PostgreSQL, and expose analytical insights through a high-performance FastAPI backend and a Next.js 16 operations dashboard.

The system demonstrates a complete data engineering lifecycle: from raw GeoJSON/CSV ingestion, schema validation, and quarantine auditing to columnar Parquet persistence, PostgreSQL relational loading, and dynamic frontend visualisations.

> **Project status:** **Phases 1–5 Complete & Integrated.** End-to-end pipeline, PostgreSQL database, FastAPI REST service, and Next.js dashboard fully verified.

---

## 🎯 Project Objectives

- **Modular ETL Pipeline:** Ingest, validate, and transform large railway datasets with zero silent row loss.
- **Data Quality & Quarantine:** Segregate invalid records into dedicated audit logs (`data/processed/quarantine/`) without fabricating values.
- **Columnar Storage:** Store clean analytical datasets in compressed Parquet format (`data/processed/`).
- **Relational Analytics:** Load 2,283,664 verified records into PostgreSQL (`rail_signal`) and execute analytical SQL aggregates.
- **RESTful API:** Expose verified metrics, train searches, delay analytics, and data-quality reports via FastAPI with automatic OpenAPI documentation.
- **Interactive Dashboard:** Display metrics on a responsive Next.js 16 / React 19 dashboard adhering to the approved visual identity (dark charcoal, warm ivory, signal-lime accent, railway-blue charts).

---

## 🛠️ Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| **Data Processing** | Python 3.14, Pandas, PyArrow | Ingestion, validation, transformation, and Parquet storage |
| **Database** | PostgreSQL 18, psycopg2 | Relational storage, indexing, and SQL analytical queries |
| **Backend API** | FastAPI, Pydantic v2, Uvicorn | REST API, connection pooling, and request/response validation |
| **Frontend** | Next.js 16 (Turbopack), React 19, TypeScript | Server and client UI components, routing, and state |
| **Styling & Charts** | Tailwind CSS 4, Recharts, Lucide Icons | Responsive railway operations interface and visualisations |
| **Testing & Quality** | Pytest, TypeScript (`tsc --noEmit`) | Automated unit, schema, integration, and build testing |
| **Version Control** | Git & GitHub | Source tracking and branch management |

---

## 🏗️ System Architecture

```text
RAIL / SIGNAL
     |
     v
Raw Railway Datasets (DataMeet GeoJSON + Kaggle Operational CSVs)
     |
     v
Data Ingestion Layer (backend/pipeline/ingestion.py)
     |
     v
Data Validation Layer (backend/pipeline/validation.py)
     |
     +---> Quarantine Store (data/processed/quarantine/)
     v
Data Transformation & Parquet Layer (backend/pipeline/transformation.py)
     |
     v
Processed Parquet Files (data/processed/*.parquet)
     |
     v
Database Batch Loader (backend/pipeline/database_loader.py)
     |
     v
PostgreSQL Relational Database (rail_signal — 2,283,664 rows)
     |
     v
FastAPI Backend API (backend/app/main.py)
     |
     v
Next.js Operations Dashboard (frontend/app/page.tsx)
```

---

## 📂 Project Organization

```text
RAIL-SIGNAL/
├── backend/
│   ├── app/
│   │   ├── config.py             # App & database configuration settings
│   │   ├── db.py                 # PostgreSQL connection pool & health checks
│   │   ├── schemas.py            # Pydantic request and response models
│   │   ├── services.py           # SQL queries & business logic
│   │   ├── main.py               # FastAPI application & route declarations
│   │   └── __init__.py
│   ├── pipeline/
│   │   ├── ingestion.py          # Memory-safe GeoJSON & chunked CSV ingestion
│   │   ├── validation.py         # Schema, coordinate bounds, & leakage checks
│   │   ├── transformation.py     # Data cleaning, quarantine, & Parquet writers
│   │   ├── database_loader.py    # PostgreSQL batch insertion & row verifier
│   │   ├── monitoring.py         # Pipeline execution tracking, history & audit
│   │   └── __init__.py
│   └── __init__.py
├── data/
│   ├── raw/
│   │   ├── datameet/             # stations.json, trains.json, schedules.json
│   │   └── operational_journeys/ # ir_train.csv, ir_test.csv, dictionaries
│   └── processed/
│       ├── stations.parquet      # 8,988 rows
│       ├── trains.parquet        # 5,207 rows
│       ├── schedules.parquet     # 394,469 rows
│       ├── journey_train.parquet # 1,500,000 rows
│       ├── journey_test.parquet  # 375,000 rows
│       ├── quality_report.json   # Pipeline execution metadata
│       ├── pipeline_runs.jsonl   # Redundant filesystem audit log
│       └── quarantine/           # JSON files with quarantined records & reasons
├── docs/
│   ├── architecture.md           # Architecture overview & design decisions
│   ├── data-dictionary.md        # Entity definitions, attributes, & types
│   ├── dataset-sources.md        # Origin URLs, licenses, & provenance notes
│   ├── ingestion-guide.md        # Extraction routines & chunked readers
│   ├── validation-guide.md       # Validation rules & leakage safeguards
│   ├── transformation-guide.md   # Cleaning rules & Parquet storage
│   ├── database-guide.md         # PostgreSQL loading & schema scripts
│   ├── pipeline-monitoring.md    # Execution history schema, monitoring & triggers
│   └── api-guide.md              # FastAPI endpoint documentation & examples
├── frontend/
│   ├── app/
│   │   ├── globals.css           # Custom railway styling tokens
│   │   ├── layout.tsx            # HTML root & metadata
│   │   └── page.tsx              # 6-section integrated dashboard
│   ├── lib/
│   │   ├── api.ts                # Centralized typed API client
│   │   └── utils.ts
│   ├── next.config.mjs           # Next.js build configuration (TypeScript enabled)
│   ├── package.json
│   └── tsconfig.json
├── sql/
│   ├── schema/
│   │   └── 01_pipeline_runs.sql  # Idempotent DDL for execution history table
│   └── analytics/
│       ├── 01_train_performance.sql
│       ├── 02_journey_delay.sql
│       ├── 03_passenger_utilisation.sql
│       └── 04_schedule_quality.sql
├── tests/
│   ├── test_ingestion.py             # Ingestion tests (8 passed)
│   ├── test_validation.py            # Validation tests (20 passed)
│   ├── test_transformation.py        # Transformation & Parquet tests (12 passed)
│   ├── test_database_loader.py       # Database loader tests (4 passed)
│   ├── test_api.py                   # FastAPI endpoint tests (10 passed)
│   └── test_pipeline_monitoring.py   # Execution history & trigger tests (12 passed)
├── .env.example
├── .gitignore
└── README.md
```

---

## 📊 Dataset Verification & Provenance

### 1. Physical Railway Infrastructure (DataMeet Indian Railways)
- **Source:** [DataMeet Indian Railways](https://github.com/datameet/railways)
- **License:** Open Database License (ODbL v1.0).
- **Type:** Verified real-world Indian railway network reference data.
- **Records:** 8,988 stations, 5,207 train services, 394,469 schedule stops.

### 2. Operational Journey Performance (Kaggle Competition Dataset)
- **Source:** [Kaggle Indian Railways Predict Train Delay](https://www.kaggle.com/competitions/indian-railways-predict-train-delay/data)
- **License:** Community competition rules / educational benchmark.
- **Type:** Synthetic educational modeling features.
- **Records:** 1,500,000 training journeys, 375,000 test journeys.
- **Provenance Safeguard:** Passenger utilisation percentages and delay indicators are simulated attributes from educational benchmark data. They are explicitly badged in the UI and documentation and must never be represented as live CRIS telemetry.
- **Target Leakage Protection:** Destination outcome fields (`primary_delay_cause`, `delay_minutes`) and target (`is_delayed`) are strictly excluded from approved model input features.

---

## 🗄️ PostgreSQL Database

Database name: `rail_signal`

| Table | Records Loaded | Description |
|---|---:|---|
| `stations` | 8,988 | Verified station codes, names, zones, states, and coordinates |
| `trains` | 5,207 | Train services, routes, durations, distances, and coach indicators |
| `schedules` | 394,469 | Stop schedules with arrival/departure times and sequence days |
| `journey_train` | 1,500,000 | Operational training journeys with delay and utilisation data |
| `journey_test` | 375,000 | Operational test journeys (zero leakage columns) |
| **Total** | **2,283,664** | **Verified relational database rows** |

---

## 🌐 FastAPI Backend Endpoints

Start the backend server on port 8000:

```powershell
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | System health check, database connectivity, and table counts |
| `GET` | `/api/overview` | Executive KPIs, delay distribution, train categories, and freshness |
| `GET` | `/api/trains` | Search, category filter (`train_type`), zone filter (`zone`), sorting (`sort_by`, `sort_order`), and pagination |
| `GET` | `/api/trains/{train_number}` | Train details and complete sequence of scheduled stops & waypoints |
| `GET` | `/api/analytics/train-performance` | Average distance and duration breakdown by train type |
| `GET` | `/api/analytics/delays` | On-time vs. delayed metrics and average delay minutes |
| `GET` | `/api/analytics/passenger-flow` | Average seat utilisation and 4-band distribution (`0–50%`, `50–75%`, `75–100%`, `100%+`) |
| `GET` | `/api/data-quality` | Accepted vs. quarantined records per dataset and rejection reasons |
| `GET` | `/api/pipeline/status` | Workflow stages, execution metadata, and output file sizes |
| `GET` | `/api/pipeline/history` | Paginated execution history with duration, status, and record counts |
| `GET` | `/api/pipeline/history/{run_id}` | Granular stage-level execution telemetry, timings, and recorded outcomes |
| `POST` | `/api/pipeline/run` | Safe, non-destructive pipeline validation trigger (prerequisite & integrity audit) |

Interactive Swagger documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 💻 Frontend Operations Dashboard

Start the Next.js development server:

```powershell
cd frontend
pnpm dev
# or: npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Dashboard Sections & Features:
1. **Overview:** Network topology schematic, key operational metrics, journey delay donut chart, processing summary, and live database metric refresh.
2. **Train Performance:** Searchable, filterable table across 5,207 trains with zone filtering (e.g. WR, NR, CR), multi-column sorting (distance, duration, name, number), and an interactive **Train Detail Drawer** displaying complete stop schedules, waypoints, day of journey, arrival/departure times, and stop filtering.
3. **Passenger Flow:** Seat utilisation averages, train-category comparisons, four occupancy bands, and clear educational provenance disclaimers distinguishing synthetic model parameters from physical CRIS counts.
4. **Data Pipeline & Execution Monitoring:** Live pipeline monitoring dashboard backed by PostgreSQL `pipeline_runs`. Features real aggregate execution metrics (total, successful, failed, latest runtime), interactive safe 4-stage validation execution (`POST /api/pipeline/run`), filterable execution history audit trail with pagination and manual refresh, and an interactive **Execution Telemetry Drawer** displaying stage-by-stage timings, verified record counts (2,283,664 rows), and diagnostics.
5. **Data Quality:** Quarantine audit summary detailing 22,614 isolated records and documented rejection reasons (e.g. missing station code or invalid day numbers).
6. **Technology Stack:** Curated 20-technology architectural registry verified against source manifests, category filters, and live System Health diagnostics.

### Architectural Note on Authentication:
RAIL / SIGNAL is designed as an educational, read-only railway data engineering and analytics platform. All underlying datasets are public reference feeds (DataMeet) and anonymized benchmark journey data (Kaggle). To maintain frictionless exploration without pseudo-security or decorative forms, sign-in/sign-up has been intentionally omitted.

---

## 🧪 Automated Testing

Execute the complete Python test suite (92 tests):

```powershell
python -m pytest tests -v
```

```text
tests/test_api.py (10 passed)
tests/test_database_loader.py (4 passed)
tests/test_ingestion.py (8 passed)
tests/test_orchestrator.py (18 passed)
tests/test_pipeline_monitoring.py (12 passed)
tests/test_schema_manager.py (8 passed)
tests/test_transformation.py (12 passed)
tests/test_validation.py (20 passed)
============================= 92 passed in 26.43s =============================
```

Execute frontend TypeScript and build checks:

```powershell
cd frontend
npx tsc --noEmit
npx next build
```

---

## ⚙️ Unified ETL Orchestration Engine (Phase 3)

The platform includes a unified CLI orchestrator (`backend/pipeline/orchestrator.py`) and schema management engine (`backend/pipeline/schema_manager.py`):

```powershell
# 1. Non-destructive Preflight Audit
python -m backend.pipeline.orchestrator --mode preflight

# 2. Deep Schema Validation
python -m backend.pipeline.orchestrator --mode schema-validate

# 3. Idempotent Schema Initialization
python -m backend.pipeline.orchestrator --mode schema-init

# 4. End-to-End Pipeline Validation
python -m backend.pipeline.orchestrator --mode validate

# 5. Dry-Run Simulation
python -m backend.pipeline.orchestrator --mode etl --dry-run
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.12+ (tested on Python 3.14.0)
- Node.js 20+ (tested on Node v24.12.0)
- PostgreSQL 16+ (tested on PostgreSQL 18.3)
- Git

### 2. Configure Environment
Copy `.env.example` to `.env` in the project root:
```ini
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=rail_signal
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
APP_PORT=8000
```

### 3. Run Backend
```powershell
uvicorn backend.app.main:app --port 8000 --reload
```

### 4. Run Frontend
```powershell
cd frontend
pnpm install
pnpm dev
```

---

## 👨‍💻 Developer
**Pratham** — [GitHub: Prathamcoder3000](https://github.com/Prathamcoder3000)
