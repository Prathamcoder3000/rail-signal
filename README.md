# 🚆 RAIL / SIGNAL
### Railway Operations & Passenger Flow Data Engineering Platform

RAIL / SIGNAL is a data engineering project designed to process railway-related datasets, validate data quality, store structured information in PostgreSQL, and generate analytical insights into train performance, journey delays, passenger utilisation, and schedule quality.

The project demonstrates an end-to-end data engineering workflow, from raw data ingestion and transformation to database storage and analytics.

> **Project status:** Phase 3 completed — database integration and SQL analytics. Phase 4 — FastAPI backend — is planned next.

---

## 🎯 Project Objectives

- Build a structured railway data processing pipeline.
- Ingest and process large railway datasets using Python.
- Validate data and identify missing or invalid records.
- Store processed datasets in Parquet format.
- Load structured data into PostgreSQL.
- Write SQL queries to analyse train performance, journey delays, passenger utilisation, and schedule quality.
- Develop a backend API to make analytical data available to a frontend dashboard.

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Data processing and pipeline development |
| Pandas | Data cleaning and transformation |
| PyArrow / Parquet | Efficient columnar data storage |
| PostgreSQL 18 | Relational database |
| SQL | Analytical queries |
| psycopg2 | PostgreSQL connectivity |
| FastAPI | Planned backend API |
| React + Vite | Planned frontend |
| Tailwind CSS | Planned interface styling |
| Recharts | Planned data visualisations |
| Pytest | Automated testing |
| Git & GitHub | Version control |

## 🏗️ Project Architecture

```text
RAIL / SIGNAL
     |
     v
Raw Railway Datasets
     |
     v
Data Ingestion
     |
     v
Data Validation
     |
     v
Data Transformation
     |
     v
Processed Parquet Files
     |
     v
Python Database Loader
     |
     v
PostgreSQL Database
     |
     v
SQL Analytics
     |
     v
FastAPI Backend (Phase 4)
     |
     v
React Dashboard (Planned)
```

## 📂 Project Structure

```text
RAIL-SIGNAL/
├── backend/
│   ├── pipeline/
│   │   ├── ingestion.py
│   │   ├── validation.py
│   │   ├── transformation.py
│   │   └── database_loader.py
│   └── __init__.py
├── data/
│   ├── raw/
│   │   ├── datameet/
│   │   └── kaggle/
│   ├── processed/
│   └── quarantine/
├── docs/
│   ├── architecture.md
│   ├── data-dictionary.md
│   ├── dataset-sources.md
│   ├── ingestion-guide.md
│   ├── validation-guide.md
│   ├── transformation-guide.md
│   └── database-guide.md
├── frontend/
├── sql/
│   └── analytics/
│       ├── 01_train_performance.sql
│       ├── 02_journey_delay.sql
│       ├── 03_passenger_utilisation.sql
│       └── 04_schedule_quality.sql
├── tests/
│   ├── test_ingestion.py
│   ├── test_validation.py
│   ├── test_transformation.py
│   └── test_database_loader.py
├── .env.example
├── .gitignore
└── README.md
```

*Note: The structure above represents the main project organisation. Additional files may be present as development continues.*

## 📊 Data Sources

### 1. DataMeet — Indian Railways Data

DataMeet datasets are used as reference data for Indian railway stations, trains, and schedules.

Data includes:
- Railway station information and location coordinates.
- Train names, numbers, and route-related attributes.
- Scheduled stops and arrival/departure information.

Source: [DataMeet — Indian Railways](https://github.com/datameet/railways)

### 2. Kaggle — Indian Railways Train Delay Dataset

A separate dataset is used to explore journey delay patterns and passenger-utilisation-related analytics.

The dataset contains training and test records with journey-related attributes. Its delay and utilisation information must be interpreted according to the dataset's documentation.

**Data limitation:** These records are not a live railway feed. Results derived from the educational Kaggle dataset must not be presented as verified real-time Indian Railways statistics.

## ⚙️ Data Engineering Pipeline

### Phase 1 — Environment and Project Setup ✅

- Created the project directory structure.
- Configured the Python development environment.
- Set up PostgreSQL and Git.
- Collected the required datasets.
- Prepared initial project documentation.

### Phase 2 — Data Ingestion, Validation and Transformation ✅

- Loaded raw JSON and CSV datasets.
- Validated records and identified missing or invalid values.
- Transformed accepted records into structured datasets.
- Stored processed datasets in Parquet format.
- Generated a data quality report.
- Preserved invalid records in quarantine rather than inventing missing values.

Processed dataset counts:

| Dataset | Accepted records |
|---|---:|
| Stations | 8,988 |
| Trains | 5,207 |
| Schedules | 394,469 |
| Journey training data | 1,500,000 |
| Journey test data | 375,000 |

### Phase 3 — PostgreSQL Integration and SQL Analytics ✅

- Created the `rail_signal` PostgreSQL database.
- Created five database tables.
- Built a Python database loader using batch insertion.
- Loaded processed Parquet datasets into PostgreSQL.
- Verified the expected and actual row counts.
- Developed four SQL analytics queries.
- Added automated database-loader tests.
- Documented the database workflow.

**Total records loaded and verified: 2,283,664.**

### Phase 4 — FastAPI Backend 🔜

Planned work:
- Create the FastAPI application.
- Implement application and database health checks.
- Connect the API to PostgreSQL.
- Expose analytics through REST endpoints.
- Add typed response schemas and API tests.

### Phase 5 — Frontend Dashboard 🔜

Planned work:
- Build a React dashboard.
- Display train performance and delay analytics.
- Visualise passenger utilisation.
- Show pipeline status and data quality.
- Connect the dashboard to the backend APIs.

### Phase 6 — Testing, Documentation and Integration 🔜

- Run the complete test suite.
- Validate frontend and backend integration.
- Improve error handling and documentation.
- Verify the complete end-to-end workflow.

### Phase 7 — Optional Machine Learning Extension

A machine learning component may be added later to explore delay prediction using appropriate training features.

For model development, `is_delayed` is the training target, while `delay_minutes` and `primary_delay_cause` are outcome-related fields that must not be used as input features when doing so would leak the target information.

Machine learning is an optional extension, not a requirement for completing the core data engineering platform.

## 🗄️ PostgreSQL Database

Database name: `rail_signal`

| Table | Description |
|---|---|
| `stations` | Processed station reference data |
| `trains` | Train information |
| `schedules` | Scheduled train stops and timings |
| `journey_train` | Journey training dataset |
| `journey_test` | Journey test dataset |

Database configuration is stored locally in `.env`. The file is excluded from Git to help prevent accidental exposure of credentials.

## 📈 SQL Analytics

The project includes the following analytical queries:

**1. Train Performance — `01_train_performance.sql`**
- Train counts by train type.
- Average route distance.
- Average train duration.

**2. Journey Delay — `02_journey_delay.sql`**
- Total journey records.
- Delayed and on-time journeys.
- Delay percentages.
- Average recorded delay.

**3. Passenger Utilisation — `03_passenger_utilisation.sql`**
- Average seat utilisation.
- Journey counts by train type.
- Overload-related indicators.

**4. Schedule Quality — `04_schedule_quality.sql`**
- Total schedule records.
- Missing schedule information.
- Unique train and station counts.

## 🧪 Testing

Run the project's automated tests from the root directory:

```powershell
python -m pytest tests -v
```

**Latest completed result:** 44 tests passed.

The suite covers pipeline ingestion, validation, transformation, and database-loader checks.

## 🚀 Getting Started

### Prerequisites

Install or configure:
- Python.
- PostgreSQL.
- Git.
- Node.js and npm for the planned frontend.

### 1. Clone the repository

```powershell
git clone https://github.com/Prathamcoder3000/rail-signal.git
cd rail-signal
```

### 2. Install Python dependencies

Create and activate a virtual environment if you are setting up a fresh machine:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the project's required Python packages. The dependency list should be maintained in a `requirements.txt` file as the project evolves.

### 3. Configure environment variables

Create a local `.env` file in the project root using `.env.example` as a reference.

Configure the PostgreSQL host, port, database name, username, and password locally. Never commit real credentials.

### 4. Prepare the datasets

Obtain the required datasets from their original sources and place them in the corresponding `data/raw/` directories, following the project documentation.

### 5. Run the pipeline

Run the ingestion, validation, and transformation stages according to the instructions in:

- `docs/ingestion-guide.md`
- `docs/validation-guide.md`
- `docs/transformation-guide.md`

### 6. Load the processed data

After the required Parquet files have been generated and the database schema has been created, run:

```powershell
python -m backend.pipeline.database_loader
```

The loader checks the database configuration, inserts data in batches, and verifies row counts. Follow `docs/database-guide.md` for the exact setup procedure.

### 7. Execute SQL analytics

Open pgAdmin, connect to PostgreSQL, select the `rail_signal` database, and execute the queries in `sql/analytics/`.

*Note: A fresh clone does not automatically contain the raw datasets, processed Parquet files, database contents, or local credentials.*

## 🔐 Data Quality and Limitations

- Invalid records are quarantined instead of silently repaired.
- Missing values are not replaced with fabricated railway information.
- Processed record counts reflect accepted records, not all raw records.
- Dataset schemas and definitions must be checked before interpreting analytical results.
- The Kaggle dataset is not evidence of live railway conditions.
- The project does not currently claim integration with live railway operational systems.

## 👨‍💻 Developer

**Pratham**  
GitHub: [Prathamcoder3000](https://github.com/Prathamcoder3000)

## 📌 Current Status

**Completed:** Environment setup, data ingestion, validation, transformation, Parquet storage, PostgreSQL integration, SQL analytics, and 44 automated tests.

**Next milestone:** Phase 4 — FastAPI backend development.

---

*RAIL / SIGNAL — Turning railway datasets into structured, testable, and actionable analytics.*
