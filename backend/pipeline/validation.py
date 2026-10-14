"""
Data Validation Layer for RAIL / SIGNAL.

Provides modular, robust validation routines for:
1. Station records (coordinates bounds, code/name presence, uniqueness, optional attributes)
2. Train records (number/name presence, uniqueness, station reference integrity, string preservation)
3. Schedule records (endpoint 'None' handling, time format HH:MM:SS, positive day, reference checks)
4. Kaggle Journey DataFrames (schema adherence, journey_id uniqueness, date validity, target leakage protection)

All validators return a ValidationReport containing error/warning tallies, detailed messages,
and an `is_valid` status flag.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Set, Union

import pandas as pd

# Approved model feature list explicitly excludes target and destination outcome leakage columns
APPROVED_JOURNEY_FEATURE_COLUMNS = [
    "journey_id",
    "train_number",
    "train_type",
    "departure_date",
    "year",
    "month",
    "day_of_week",
    "departure_hour",
    "is_weekend",
    "is_night_departure",
    "is_peak_hour",
    "is_festival_season",
    "season",
    "zone",
    "zone_abbr",
    "source_station_category",
    "destination_station_category",
    "distance_km",
    "num_scheduled_stops",
    "scheduled_travel_hours",
    "track_doubled",
    "is_hdn_route",
    "traction_type",
    "is_electrified",
    "psr_count",
    "is_circular_route",
    "is_monsoon_season",
    "is_fog_risk",
    "fog_risk_score",
    "zone_fog_index",
    "zone_congestion_index",
    "season_severity_score",
    "loco_age_years",
    "coach_age_years",
    "has_lhb_coaches",
    "is_rake_shared",
    "maintenance_score",
    "seat_utilisation_pct",
    "is_overloaded",
    "late_incoming_rake",
    "is_special_train",
    "route_historical_ontime_pct",
]

# Prohibited destination outcome columns (target leakage)
LEAKAGE_COLUMNS = {"primary_delay_cause", "delay_minutes"}

# Target column
TARGET_COLUMN = "is_delayed"

# Strict 24-hour time regex HH:MM:SS (00:00:00 to 23:59:59)
TIME_REGEX = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$")


@dataclass
class ValidationReport:
    """Report detailing data validation results, error tallies, and warnings."""
    dataset_name: str
    total_records: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def is_valid(self) -> bool:
        """Returns True if there are zero validation errors."""
        return len(self.errors) == 0

    def add_error(self, message: str) -> None:
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "total_records": self.total_records,
            "is_valid": self.is_valid,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_stations(records: Sequence[Dict[str, Any]]) -> ValidationReport:
    """
    Validates station records produced by read_stations_geojson.

    Rules:
    - Required fields: 'code', 'name' must be present, non-null, and non-empty.
    - Station codes must be unique across the dataset.
    - Longitude must be numeric and between -180.0 and 180.0 when present.
    - Latitude must be numeric and between -90.0 and 90.0 when present.
    - Missing optional fields ('state', 'zone', 'address', or missing coords) reported as warnings.
    """
    report = ValidationReport(dataset_name="stations", total_records=len(records))

    seen_codes: Set[str] = set()

    for idx, rec in enumerate(records):
        rec_id = f"Record #{idx}"

        # 1. Required station code
        code = rec.get("code")
        if not code or not str(code).strip():
            report.add_error(f"{rec_id}: Missing or empty required 'code'")
        else:
            code_str = str(code).strip()
            if code_str in seen_codes:
                report.add_error(f"{rec_id}: Duplicate station code '{code_str}'")
            seen_codes.add(code_str)
            rec_id = f"Station '{code_str}' (#{idx})"

        # 2. Required station name
        name = rec.get("name")
        if not name or not str(name).strip():
            report.add_error(f"{rec_id}: Missing or empty required 'name'")

        # 3. Coordinate bounds validation
        lon = rec.get("longitude")
        if lon is not None:
            try:
                lon_f = float(lon)
                if not (-180.0 <= lon_f <= 180.0):
                    report.add_error(
                        f"{rec_id}: Longitude {lon_f} out of valid bounds [-180, 180]"
                    )
            except (ValueError, TypeError):
                report.add_error(f"{rec_id}: Non-numeric longitude value: {lon}")
        else:
            report.add_warning(f"{rec_id}: Longitude coordinate is missing")

        lat = rec.get("latitude")
        if lat is not None:
            try:
                lat_f = float(lat)
                if not (-90.0 <= lat_f <= 90.0):
                    report.add_error(
                        f"{rec_id}: Latitude {lat_f} out of valid bounds [-90, 90]"
                    )
            except (ValueError, TypeError):
                report.add_error(f"{rec_id}: Non-numeric latitude value: {lat}")
        else:
            report.add_warning(f"{rec_id}: Latitude coordinate is missing")

        # 4. Optional attribute presence checks (warnings)
        for opt in ("zone", "state", "address"):
            val = rec.get(opt)
            if val is None or not str(val).strip():
                report.add_warning(f"{rec_id}: Optional field '{opt}' is missing or empty")

    return report


def validate_trains(
    records: Sequence[Dict[str, Any]],
    valid_station_codes: Optional[Set[str]] = None,
) -> ValidationReport:
    """
    Validates train records produced by read_trains_geojson.

    Rules:
    - Required fields: 'number', 'name' must be present, non-null, and non-empty.
    - Train numbers must be unique across the dataset and preserved as strings.
    - Origin ('from_station_code') and destination ('to_station_code') checked against
      valid_station_codes if provided (missing/unmatched references logged as warnings).
    - Nullable timetable or duration fields ('duration_h', 'distance') checked for sensible
      positive values if present; null values are permitted.
    """
    report = ValidationReport(dataset_name="trains", total_records=len(records))

    seen_numbers: Set[str] = set()

    for idx, rec in enumerate(records):
        rec_id = f"Record #{idx}"

        # 1. Train number check
        number = rec.get("number")
        if number is None or not str(number).strip():
            report.add_error(f"{rec_id}: Missing or empty required 'number'")
        else:
            num_str = str(number).strip()
            if num_str in seen_numbers:
                report.add_error(f"{rec_id}: Duplicate train number '{num_str}'")
            seen_numbers.add(num_str)
            rec_id = f"Train '{num_str}' (#{idx})"

        # 2. Train name check
        name = rec.get("name")
        if not name or not str(name).strip():
            report.add_error(f"{rec_id}: Missing or empty required 'name'")

        # 3. Referential integrity for origin & destination stations
        if valid_station_codes is not None:
            from_code = rec.get("from_station_code")
            if from_code:
                from_code_clean = str(from_code).strip().upper()
                if from_code_clean not in valid_station_codes:
                    report.add_warning(
                        f"{rec_id}: Origin station '{from_code_clean}' not found in station reference set"
                    )
            else:
                report.add_warning(f"{rec_id}: Missing 'from_station_code'")

            to_code = rec.get("to_station_code")
            if to_code:
                to_code_clean = str(to_code).strip().upper()
                if to_code_clean not in valid_station_codes:
                    report.add_warning(
                        f"{rec_id}: Destination station '{to_code_clean}' not found in station reference set"
                    )
            else:
                report.add_warning(f"{rec_id}: Missing 'to_station_code'")

        # 4. Numeric fields check (distance, duration)
        distance = rec.get("distance")
        if distance is not None:
            try:
                dist_num = float(distance)
                if dist_num < 0:
                    report.add_error(f"{rec_id}: Negative route distance: {dist_num}")
            except (ValueError, TypeError):
                report.add_error(f"{rec_id}: Non-numeric route distance: {distance}")

        dur_h = rec.get("duration_h")
        if dur_h is not None:
            try:
                dur_num = float(dur_h)
                if dur_num < 0:
                    report.add_error(f"{rec_id}: Negative duration hours: {dur_num}")
            except (ValueError, TypeError):
                report.add_error(f"{rec_id}: Non-numeric duration hours: {dur_h}")

    return report


def validate_schedules(
    records: Sequence[Dict[str, Any]],
    valid_train_numbers: Optional[Set[str]] = None,
    valid_station_codes: Optional[Set[str]] = None,
) -> ValidationReport:
    """
    Validates timetable schedule stop records produced by read_schedules_json.

    Rules:
    - Schedule 'id' must be present, non-null, and unique.
    - 'train_number', 'station_code', and 'day' must be present.
    - 'day' must be a positive integer (>= 1).
    - 'arrival' and 'departure' values of the literal string 'None' or None are permitted
      as valid journey endpoints (origin departure or terminus arrival).
    - Non-null/non-'None' time strings must strictly conform to HH:MM:SS format (00:00:00 - 23:59:59).
    - Train and station references verified against reference sets if supplied (warnings if unmatched).
    """
    report = ValidationReport(dataset_name="schedules", total_records=len(records))

    seen_ids: Set[Any] = set()

    for idx, rec in enumerate(records):
        rec_id = f"Schedule record #{idx}"

        # 1. Schedule ID presence and uniqueness
        sched_id = rec.get("id")
        if sched_id is None:
            report.add_error(f"{rec_id}: Missing required schedule 'id'")
        else:
            if sched_id in seen_ids:
                report.add_error(f"{rec_id}: Duplicate schedule ID '{sched_id}'")
            seen_ids.add(sched_id)
            rec_id = f"Schedule #{sched_id}"

        # 2. Train number presence
        train_num = rec.get("train_number")
        if not train_num or not str(train_num).strip():
            report.add_error(f"{rec_id}: Missing required 'train_number'")
        elif valid_train_numbers is not None:
            clean_num = str(train_num).strip()
            if clean_num not in valid_train_numbers:
                report.add_warning(
                    f"{rec_id}: Train number '{clean_num}' not found in train reference set"
                )

        # 3. Station code presence
        st_code = rec.get("station_code")
        if not st_code or not str(st_code).strip():
            report.add_error(f"{rec_id}: Missing required 'station_code'")
        elif valid_station_codes is not None:
            clean_code = str(st_code).strip().upper()
            if clean_code not in valid_station_codes:
                report.add_warning(
                    f"{rec_id}: Station code '{clean_code}' not found in station reference set"
                )

        # 4. Day of journey must be positive integer
        day = rec.get("day")
        if day is None:
            report.add_error(f"{rec_id}: Missing required 'day'")
        else:
            try:
                day_val = int(day)
                if day_val < 1:
                    report.add_error(f"{rec_id}: 'day' must be a positive integer, got {day_val}")
            except (ValueError, TypeError):
                report.add_error(f"{rec_id}: Invalid non-integer 'day' value: {day}")

        # 5. Arrival and Departure timing format
        # Permitted endpoints: None, 'None', ''
        for time_field in ("arrival", "departure"):
            t_val = rec.get(time_field)
            if t_val is None or str(t_val).strip() in ("None", ""):
                # Legitimate journey endpoint (origin station or terminus station)
                continue
            time_str = str(t_val).strip()
            if not TIME_REGEX.match(time_str):
                report.add_error(
                    f"{rec_id}: Invalid {time_field} format '{time_str}'. Expected HH:MM:SS"
                )

    return report


def validate_journey_dataframe(
    df: pd.DataFrame,
    is_training: bool = True,
    expected_column_count: Optional[int] = None,
) -> ValidationReport:
    """
    Validates a Kaggle operational journey DataFrame (training or test).

    Rules:
    - Verifies presence of 'journey_id' and validates that it is non-null and strictly unique.
    - Verifies 'departure_date' format (YYYY-MM-DD) if present.
    - If is_training=True:
        - Checks for binary target 'is_delayed' (must contain only 0 and 1 values).
        - Verifies that 'primary_delay_cause' and 'delay_minutes' are flagged as training-only
          outcomes and never exposed to the approved model input feature set.
    - If is_training=False:
        - Confirms that test dataset does NOT contain 'is_delayed', 'primary_delay_cause', or 'delay_minutes'.
    - Validates numeric bounds:
        - distance_km >= 0
        - scheduled_travel_hours >= 0
        - num_scheduled_stops >= 0
        - seat_utilisation_pct between 0.0 and 100.0 (where present)
    - If expected_column_count provided, checks against actual column count.
    """
    ds_name = "ir_train" if is_training else "ir_test"
    report = ValidationReport(dataset_name=ds_name, total_records=len(df))

    if df.empty:
        report.add_warning(f"{ds_name}: DataFrame is empty")
        return report

    actual_cols = list(df.columns)

    # 1. Column count verification if specified
    if expected_column_count is not None and len(actual_cols) != expected_column_count:
        report.add_warning(
            f"{ds_name}: Expected {expected_column_count} columns, found {len(actual_cols)}"
        )

    # 2. journey_id check
    if "journey_id" not in df.columns:
        report.add_error(f"{ds_name}: Missing required column 'journey_id'")
    else:
        null_count = int(df["journey_id"].isna().sum())
        if null_count > 0:
            report.add_error(f"{ds_name}: Found {null_count} null journey_id entries")

        dup_count = int(df["journey_id"].duplicated().sum())
        if dup_count > 0:
            report.add_error(f"{ds_name}: Found {dup_count} duplicate journey_id entries")

    # 3. Target and Leakage validation
    if is_training:
        if TARGET_COLUMN not in df.columns:
            report.add_error(f"{ds_name}: Training dataset missing target column '{TARGET_COLUMN}'")
        else:
            # Check target binary values
            valid_targets = {0, 1, 0.0, 1.0, "0", "1"}
            target_series = df[TARGET_COLUMN].dropna()
            invalid_targets = set(target_series.unique()) - valid_targets
            if invalid_targets:
                report.add_error(
                    f"{ds_name}: Target column '{TARGET_COLUMN}' contains non-binary values: {invalid_targets}"
                )

        # Informational note regarding training outcome columns
        for col in LEAKAGE_COLUMNS:
            if col in df.columns:
                report.add_warning(
                    f"{ds_name}: Contains training outcome column '{col}'. "
                    f"Must be excluded from model input features."
                )
    else:
        # Test dataset MUST NOT contain target or leakage columns
        for col in LEAKAGE_COLUMNS | {TARGET_COLUMN}:
            if col in df.columns:
                report.add_error(
                    f"{ds_name}: Test set contains unauthorized target/leakage column '{col}'"
                )

    # 4. Departure date validation
    if "departure_date" in df.columns:
        date_series = df["departure_date"].dropna()
        if not date_series.empty:
            # Sample check or vectorized check
            try:
                pd.to_datetime(date_series.iloc[:100], format="%Y-%m-%d")
            except Exception as exc:
                report.add_error(f"{ds_name}: 'departure_date' contains invalid date format: {exc}")

    # 5. Numeric ranges validation
    if "distance_km" in df.columns:
        try:
            neg_dist = int((pd.to_numeric(df["distance_km"], errors="coerce") < 0).sum())
            if neg_dist > 0:
                report.add_error(f"{ds_name}: Found {neg_dist} negative values in 'distance_km'")
        except Exception:
            pass

    if "scheduled_travel_hours" in df.columns:
        try:
            neg_hours = int((pd.to_numeric(df["scheduled_travel_hours"], errors="coerce") < 0).sum())
            if neg_hours > 0:
                report.add_error(f"{ds_name}: Found {neg_hours} negative values in 'scheduled_travel_hours'")
        except Exception:
            pass

    if "num_scheduled_stops" in df.columns:
        try:
            neg_stops = int((pd.to_numeric(df["num_scheduled_stops"], errors="coerce") < 0).sum())
            if neg_stops > 0:
                report.add_error(f"{ds_name}: Found {neg_stops} negative values in 'num_scheduled_stops'")
        except Exception:
            pass

    if "seat_utilisation_pct" in df.columns:
        try:
            util_series = pd.to_numeric(df["seat_utilisation_pct"], errors="coerce").dropna()
            out_of_bounds = int(((util_series < 0.0) | (util_series > 100.0)).sum())
            if out_of_bounds > 0:
                report.add_error(
                    f"{ds_name}: Found {out_of_bounds} 'seat_utilisation_pct' values outside [0, 100]"
                )
        except Exception:
            pass

    return report


def get_approved_model_features(available_columns: Sequence[str]) -> List[str]:
    """
    Returns the list of verified, safe model input features from available columns,
    guaranteeing that target leakage columns ('primary_delay_cause', 'delay_minutes')
    and the prediction target ('is_delayed') are strictly excluded.
    """
    prohibited = LEAKAGE_COLUMNS | {TARGET_COLUMN}
    return [col for col in available_columns if col in APPROVED_JOURNEY_FEATURE_COLUMNS and col not in prohibited]
