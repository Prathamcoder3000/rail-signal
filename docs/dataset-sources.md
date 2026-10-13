# RAIL / SIGNAL - Dataset Sources and Operational Verification

This document catalogs candidate and ingested data sources for the **RAIL / SIGNAL** platform, detailing origin URLs, schema structures, license terms, compatibility, real vs. synthetic categorization, and target leakage boundaries.

---

## 1. Candidate Source Catalog & Verified Raw Files

### A. DataMeet Indian Railways Open Timetable & Station Geography
* **Source URL:** https://github.com/datameet/railways
* **License & Terms:** Open Database License (ODbL) / Open Data Commons Open Database License. Note: Community-contributed geographic datasets assembled from public timetable and station publications. Verify downstream attribution requirements per ODbL v1.0.
* **Dataset Type:** Real-world verified railway network infrastructure and timetable data.
* **Verified Present Raw Files (`data/raw/datameet/`):**
  1. `stations.json` (1,864,683 bytes | GeoJSON FeatureCollection): 8,990 features. Keys: `state`, `code`, `name`, `zone`, `address`. Coordinates: Point [lon, lat]. Primary Key: `code` (8,990 unique codes, 0 nulls).
  2. `trains.json` (14,768,598 bytes | GeoJSON FeatureCollection): 5,208 features. Keys: 21 property keys including `number`, `name`, `type`, `zone`, coach indicators, `distance`, origin/destination station codes and names. Coordinates: LineString. Primary Key: `number` (5,208 unique train numbers, 0 nulls).
  3. `schedules.json` (82,174,280 bytes | JSON Array): 417,080 records. Keys: `id`, `train_number`, `train_name`, `station_code`, `station_name`, `arrival`, `departure`, `day`. Primary Key: `id` (417,080 unique IDs, 0 nulls).
* **Operational Verification:**
  - Identifiers: Train numbers (5 digits) and Station Codes (2-5 alphabetical characters) adhere to official Indian Railways CRIS/IRCTC nomenclature.
  - Coverage: Comprehensive across all 18 Indian Railway administrative zones.
  - Limitations: Timetable schedules represent static scheduled timings, not live or retrospective delay events. (27,835 arrival and 27,827 departure entries are 'None' representing origin departure and terminus arrival endpoints).

### B. Kaggle: Indian Railways Predict Train Delay (Competition Dataset)
* **Source URL:** https://www.kaggle.com/competitions/indian-railways-predict-train-delay/data
* **License & Terms:** Kaggle Community Competition Rules / Educational Use. Commercial re-distribution restrictions may apply under Kaggle terms of service; treated strictly as an educational modeling reference dataset.
* **Dataset Type:** Synthetic / Simulated Educational Journey Performance & Delay Dataset.
* **Verified Present Raw Files (`data/raw/operational_journeys/`):**
  1. `ir_train.csv` (337,159,362 bytes): 45 columns, 1,500,000 data rows (excluding header).
  2. `ir_test.csv` (76,010,466 bytes): 42 columns, 375,000 data rows (excluding header).
  3. `ir_sample_submission.csv` (5,625,022 bytes): 2 columns (`journey_id`, `is_delayed`), 375,000 data rows (excluding header).
  4. `ir_data_dictionary.csv` (3,251 bytes): 3 columns (`column`, `type`, `description`), 45 rows describing all 45 train columns.

---

## 2. CRITICAL WARNING: Target Leakage & Synthetic Operational Attributes

### Target Leakage Precautions
- **Training Target:** `is_delayed` (binary classification: 1 = train arrived >15 min late at destination).
- **Leakage Columns Excluded from Features:**
  - `primary_delay_cause`: Categorical description of the delay cause or 'On Time'. (Found ONLY in `ir_train.csv`).
  - `delay_minutes`: Integer count of delay minutes at destination. (Found ONLY in `ir_train.csv`).
- **Confirmation:** Neither `primary_delay_cause` nor `delay_minutes` is present in `ir_test.csv` (which has 42 columns vs 45 in `ir_train.csv`).
- **Enforcement Rule:** Under no circumstances should `primary_delay_cause` or `delay_minutes` be utilized as model input features or ingested as predictive variables.

### Operational Integrity & Metric Provenance Notice
- Fields including `seat_utilisation_pct`, `is_overloaded`, and `is_delayed` from this Kaggle dataset are **synthetic modeling features generated for educational machine learning purposes**.
- **Never represent generated or synthetic delay values, seat utilisation percentages, or overload indicators as genuine CRIS/IRCTC physical telemetry.**
- The API and dashboard will prominently display provenance badges marking them as simulated / educational attributes.

---

## 3. Directory Layout Status

```
data/
+-- raw/ (VERIFIED PRESENT)
|   +-- datameet/
|   |   +-- stations.json (1.86 MB)
|   |   +-- trains.json (14.77 MB)
|   |   +-- schedules.json (82.17 MB)
|   +-- operational_journeys/
|       +-- ir_train.csv (337.16 MB)
|       +-- ir_test.csv (76.01 MB)
|       +-- ir_sample_submission.csv (5.63 MB)
|       +-- ir_data_dictionary.csv (3.25 KB)
+-- processed/ (INITIALIZED EMPTY - PARQUET OUTPUTS TO BE PRODUCED IN PHASE 2)
```

*(Note: Processed Parquet files and PostgreSQL tables are planned for Phase 2 and Phase 3 and are not yet created).*

---

## 4. Key Compatibility & Join Rules

1. **Stations Key:** `station_code` (e.g. `NDLS`, `HWH`, `MAS`, `SBC`, `CSMT`). Verified 8,990 unique codes.
2. **Trains Key:** `train_number` (String representation of 5-digit number, e.g. `'12301'`). Verified 5,208 unique train numbers.
3. **Schedules Key:** `id` (Unique integer stop sequence identifier, 417,080 records).
4. **Journey Performance Linking:** `journey_id` is the primary key for journey records (1,500,000 in train, 375,000 in test). `train_number` in journey datasets maps to `train_number` in `trains` and `schedules`. Unmatched records will be logged to quality audit tables rather than dropped silently.
