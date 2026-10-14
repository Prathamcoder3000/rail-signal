# Data Validation Guide — RAIL / SIGNAL

This document outlines the rules, architecture, and verification of the **Data Validation Layer** (`backend/pipeline/validation.py`).

---

## 1. Overview & Architectural Principles

The validation layer inspects ingested data records without modifying or repairing the underlying source data. It identifies missing required values, schema deviations, duplicate keys, boundary violations, and model target leakage risks.

### Key Tenets:
1. **Audit & Report, Don't Mutate:** Validation functions report anomalies; they do not alter or drop records.
2. **Clear Separation of Errors vs. Warnings:**
   - **Errors (`errors`):** Hard failures that invalidate the dataset (`is_valid = False`), such as duplicate primary keys, missing required identifiers (`journey_id`, `code`, `number`), coordinates outside geographic ranges, non-binary target variables, or negative physical distances.
   - **Warnings (`warnings`):** Non-blocking observations (`is_valid` remains `True` if no errors exist), such as missing optional station attributes (`zone`, `state`, `address`), unmatched foreign station references, or notification that training outcome fields exist and must be excluded from feature inputs.
3. **Model Target Leakage Protection:** Prohibits destination outcome fields (`primary_delay_cause`, `delay_minutes`) and the prediction target (`is_delayed`) from ever being supplied as input features to predictive models.
4. **Legitimate Journey Endpoint Handling:** Arrival and departure values of the literal string `'None'` (or `None`) are explicitly recognized as legitimate journey endpoints (origin departure has no arrival; terminus arrival has no departure).

---

## 2. Validation Module Reference

Module location: `backend/pipeline/validation.py`

### 2.1 Validators Available

| Function | Target Dataset | Core Checks |
| :--- | :--- | :--- |
| `validate_stations(records)` | Stations (from `read_stations_geojson`) | - Required `code` and `name` present and non-empty.<br>- `code` uniqueness across all records.<br>- Coordinates bounds: Longitude $\in [-180, 180]$, Latitude $\in [-90, 90]$.<br>- Missing `zone`, `state`, or `address` reported as warnings. |
| `validate_trains(records, valid_station_codes)` | Trains (from `read_trains_geojson`) | - Required `number` and `name` present and non-empty.<br>- `number` uniqueness (preserved as string with leading zeros).<br>- Referential checks on `from_station_code` and `to_station_code` against `valid_station_codes` if provided.<br>- Non-negative route distance and duration hours. |
| `validate_schedules(records, valid_train_numbers, valid_station_codes)` | Schedules (from `read_schedules_json`) | - `id` present, non-null, and unique.<br>- `train_number`, `station_code`, and `day` present.<br>- `day` must be a positive integer ($\ge 1$).<br>- Endpoint values `'None'` permitted without error.<br>- Non-endpoint time strings must match `HH:MM:SS`.<br>- Reference checks on train numbers and station codes if sets provided. |
| `validate_journey_dataframe(df, is_training, expected_column_count)` | Journey DataFrames (train / test) | - `journey_id` present, non-null, and unique.<br>- Format check on `departure_date`.<br>- If training: `is_delayed` target must be binary (0 or 1). Training outcome columns (`primary_delay_cause`, `delay_minutes`) flagged with warnings.<br>- If test: target and outcome columns are prohibited (raises error if present).<br>- Numeric ranges: distance $\ge 0$, stops $\ge 0$, travel hours $\ge 0$, seat utilisation $\in [0, 100]$. |
| `get_approved_model_features(available_columns)` | Feature Selection | Filters column list against `APPROVED_JOURNEY_FEATURE_COLUMNS`, strictly excluding `is_delayed`, `primary_delay_cause`, and `delay_minutes`. |

---

## 3. ValidationReport Structure

All validators return a `ValidationReport`:

```python
@dataclass
class ValidationReport:
    dataset_name: str
    total_records: int
    errors: List[str]
    warnings: List[str]

    @property
    def is_valid(self) -> bool:
        """True if and only if len(errors) == 0"""
```

Use `report.to_dict()` for JSON serialization and logging in pipeline observability metastores.

---

## 4. How to Run the Tests

Validation unit tests use isolated in-memory test fixtures and do not scan the large raw datasets:

```powershell
python -m pytest tests/test_ingestion.py tests/test_validation.py -v
```

All 28 tests verify:
- Valid station, train, schedule, and journey record structures.
- Duplicate detection on station codes, train numbers, schedule IDs, and journey IDs.
- Latitude/longitude geographic boundaries.
- Legitimate endpoint `'None'` arrival/departure handling.
- Strict `HH:MM:SS` time format validation.
- Target leakage protection for test and model feature selections.
