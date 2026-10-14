\# RAIL / SIGNAL — Database Guide



\## 1. Overview



RAIL / SIGNAL uses PostgreSQL 18 to store processed railway reference data and journey datasets for SQL analytics.



The database name is `rail\_signal`.



\## 2. Database Tables



| Table | Purpose | Expected Rows |

|---|---|---:|

| `stations` | Station names, codes, locations and zones | 8,988 |

| `trains` | Train details, routes, duration and facilities | 5,207 |

| `schedules` | Train station stops and scheduled times | 394,469 |

| `journey\_train` | Educational journey training dataset | 1,500,000 |

| `journey\_test` | Educational journey test dataset | 375,000 |



\## 3. Data Loading



The reusable loader is located at `backend/pipeline/database\_loader.py`.



Run it from the project root:



```powershell

python -m backend.pipeline.database\_loader

```



The loader reads the processed Parquet files from `data/processed`, inserts records in batches, verifies row counts and uses a transaction to roll back the load if an error occurs.



Database credentials are configured in the local `.env` file. Do not commit `.env` or expose its password.



\## 4. SQL Analytics



SQL queries are stored in `sql/analytics/`.



\- `01\_train\_performance.sql` — train counts, average route distance and duration by train type.

\- `02\_journey\_delay.sql` — delayed journeys, on-time journeys and delay statistics.

\- `03\_passenger\_utilisation.sql` — average seat utilisation and overloaded journey counts by train type.

\- `04\_schedule\_quality.sql` — schedule completeness and distinct train and station counts.



\## 5. Data Limitations



The journey datasets are educational/synthetic data and must not be presented as verified real-world railway telemetry.



The schedule dataset contains incomplete source records. Invalid records were quarantined during Phase 2; the accepted schedule output contains 394,469 records.



The training dataset contains outcome-related fields, including `delay\_minutes`, `primary\_delay\_cause` and `is\_delayed`. These must not be treated as approved model input features. The test dataset does not contain these fields.



\## 6. Verification



The database load was verified against the Phase 2 pipeline report:



\- Stations: 8,988 rows

\- Trains: 5,207 rows

\- Schedules: 394,469 rows

\- Journey training: 1,500,000 rows

\- Journey test: 375,000 rows



All five datasets reported matching row counts after loading.



