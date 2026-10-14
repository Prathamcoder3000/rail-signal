"""
Unit tests for data validation layer in backend.pipeline.validation.
"""

from typing import Any, Dict, List

import pandas as pd
import pytest

from backend.pipeline.validation import (
    APPROVED_JOURNEY_FEATURE_COLUMNS,
    LEAKAGE_COLUMNS,
    TARGET_COLUMN,
    ValidationReport,
    get_approved_model_features,
    validate_journey_dataframe,
    validate_schedules,
    validate_stations,
    validate_trains,
)


# ==============================================================================
# A. Stations Validation Tests
# ==============================================================================

def test_validate_stations_valid():
    records = [
        {
            "code": "NDLS",
            "name": "New Delhi",
            "zone": "NR",
            "state": "Delhi",
            "address": "Pahar Ganj",
            "longitude": 77.2090,
            "latitude": 28.6139,
        },
        {
            "code": "CSMT",
            "name": "Chhatrapati Shivaji Maharaj Terminus",
            "zone": "CR",
            "state": "Maharashtra",
            "address": "Fort, Mumbai",
            "longitude": 72.8358,
            "latitude": 18.9398,
        },
    ]
    report = validate_stations(records)
    assert report.is_valid is True
    assert report.error_count == 0
    assert report.total_records == 2


def test_validate_stations_duplicate_code():
    records = [
        {"code": "NDLS", "name": "New Delhi", "longitude": 77.2, "latitude": 28.6},
        {"code": "NDLS", "name": "New Delhi Duplicate", "longitude": 77.2, "latitude": 28.6},
    ]
    report = validate_stations(records)
    assert report.is_valid is False
    assert any("Duplicate station code 'NDLS'" in err for err in report.errors)


def test_validate_stations_missing_required():
    records = [
        {"code": "", "name": "Missing Code Station"},
        {"code": "PUNE", "name": ""},
    ]
    report = validate_stations(records)
    assert report.is_valid is False
    assert any("Missing or empty required 'code'" in err for err in report.errors)
    assert any("Missing or empty required 'name'" in err for err in report.errors)


def test_validate_stations_invalid_coordinates():
    records = [
        {"code": "STN1", "name": "Bad Lon", "longitude": 195.0, "latitude": 20.0},
        {"code": "STN2", "name": "Bad Lat", "longitude": 75.0, "latitude": -100.0},
        {"code": "STN3", "name": "Non-numeric", "longitude": "abc", "latitude": 20.0},
    ]
    report = validate_stations(records)
    assert report.is_valid is False
    assert any("Longitude 195.0 out of valid bounds" in err for err in report.errors)
    assert any("Latitude -100.0 out of valid bounds" in err for err in report.errors)
    assert any("Non-numeric longitude" in err for err in report.errors)


def test_validate_stations_missing_optional_reports_warning():
    records = [
        {"code": "STN1", "name": "Valid Station", "longitude": 75.0, "latitude": 20.0}
    ]
    report = validate_stations(records)
    assert report.is_valid is True  # Warnings do not invalidate the report
    assert report.warning_count > 0
    assert any("Optional field 'zone' is missing" in w for w in report.warnings)


# ==============================================================================
# B. Trains Validation Tests
# ==============================================================================

def test_validate_trains_valid_and_leading_zeros():
    records = [
        {
            "number": "04601",
            "name": "Jammu Tawi Udhampur Special",
            "from_station_code": "JAT",
            "to_station_code": "UHP",
            "duration_h": 1,
            "duration_m": 35,
            "distance": 53,
        }
    ]
    report = validate_trains(records, valid_station_codes={"JAT", "UHP"})
    assert report.is_valid is True
    assert report.error_count == 0
    assert report.total_records == 1


def test_validate_trains_duplicate_number():
    records = [
        {"number": "12301", "name": "Rajdhani Exp"},
        {"number": "12301", "name": "Rajdhani Exp Duplicate"},
    ]
    report = validate_trains(records)
    assert report.is_valid is False
    assert any("Duplicate train number '12301'" in err for err in report.errors)


def test_validate_trains_unknown_station_reference_warning():
    records = [
        {
            "number": "12301",
            "name": "Rajdhani Exp",
            "from_station_code": "UNKNOWN_STN",
            "to_station_code": "NDLS",
        }
    ]
    report = validate_trains(records, valid_station_codes={"NDLS", "HWH"})
    assert report.is_valid is True  # Reference checks produce warnings, not hard failure
    assert report.warning_count >= 1
    assert any("Origin station 'UNKNOWN_STN' not found" in w for w in report.warnings)


def test_validate_trains_negative_numeric():
    records = [
        {"number": "12301", "name": "Rajdhani Exp", "distance": -50, "duration_h": -2}
    ]
    report = validate_trains(records)
    assert report.is_valid is False
    assert any("Negative route distance" in err for err in report.errors)
    assert any("Negative duration hours" in err for err in report.errors)


# ==============================================================================
# C. Schedules Validation Tests
# ==============================================================================

def test_validate_schedules_valid_endpoints():
    records = [
        {
            "id": 1,
            "train_number": "12301",
            "station_code": "HWH",
            "arrival": "None",  # Origin endpoint
            "departure": "16:55:00",
            "day": 1,
        },
        {
            "id": 2,
            "train_number": "12301",
            "station_code": "NDLS",
            "arrival": "10:00:00",
            "departure": "None",  # Terminus endpoint
            "day": 2,
        },
    ]
    report = validate_schedules(
        records,
        valid_train_numbers={"12301"},
        valid_station_codes={"HWH", "NDLS"},
    )
    assert report.is_valid is True
    assert report.error_count == 0
    assert report.total_records == 2


def test_validate_schedules_invalid_time_format():
    records = [
        {
            "id": 1,
            "train_number": "12301",
            "station_code": "HWH",
            "arrival": "25:70:99",  # Invalid time
            "departure": "06:00:00",
            "day": 1,
        }
    ]
    report = validate_schedules(records)
    assert report.is_valid is False
    assert any("Invalid arrival format '25:70:99'" in err for err in report.errors)


def test_validate_schedules_missing_or_duplicate_id():
    records = [
        {"id": None, "train_number": "12301", "station_code": "HWH", "day": 1},
        {"id": 100, "train_number": "12301", "station_code": "HWH", "day": 1},
        {"id": 100, "train_number": "12302", "station_code": "NDLS", "day": 1},
    ]
    report = validate_schedules(records)
    assert report.is_valid is False
    assert any("Missing required schedule 'id'" in err for err in report.errors)
    assert any("Duplicate schedule ID '100'" in err for err in report.errors)


def test_validate_schedules_non_positive_day():
    records = [
        {"id": 1, "train_number": "12301", "station_code": "HWH", "day": 0},
        {"id": 2, "train_number": "12301", "station_code": "NDLS", "day": -1},
    ]
    report = validate_schedules(records)
    assert report.is_valid is False
    assert any("'day' must be a positive integer, got 0" in err for err in report.errors)
    assert any("'day' must be a positive integer, got -1" in err for err in report.errors)


# ==============================================================================
# D. Kaggle Journey DataFrame Tests
# ==============================================================================

def test_validate_journey_dataframe_valid_train():
    df = pd.DataFrame(
        {
            "journey_id": ["J_1", "J_2"],
            "train_number": ["01234", "56789"],
            "departure_date": ["2024-01-01", "2024-01-02"],
            "distance_km": [500, 1200],
            "scheduled_travel_hours": [8.5, 16.0],
            "num_scheduled_stops": [5, 12],
            "seat_utilisation_pct": [75.5, 88.0],
            "is_delayed": [0, 1],
            "primary_delay_cause": ["On Time", "Signal"],
            "delay_minutes": [0, 25],
        }
    )
    report = validate_journey_dataframe(df, is_training=True)
    assert report.is_valid is True
    assert report.error_count == 0
    # Training outcome columns produce warnings
    assert report.warning_count >= 2
    assert any("primary_delay_cause" in w for w in report.warnings)


def test_validate_journey_dataframe_valid_test():
    df = pd.DataFrame(
        {
            "journey_id": ["J_TEST_1", "J_TEST_2"],
            "train_number": ["01234", "56789"],
            "departure_date": ["2024-02-01", "2024-02-02"],
            "distance_km": [500, 1200],
            "seat_utilisation_pct": [60.0, 95.0],
        }
    )
    report = validate_journey_dataframe(df, is_training=False)
    assert report.is_valid is True
    assert report.error_count == 0


def test_validate_journey_dataframe_missing_and_duplicate_id():
    df = pd.DataFrame(
        {
            "journey_id": ["J_1", "J_1", None],
            "is_delayed": [0, 1, 0],
        }
    )
    report = validate_journey_dataframe(df, is_training=True)
    assert report.is_valid is False
    assert any("duplicate journey_id entries" in err for err in report.errors)
    assert any("null journey_id entries" in err for err in report.errors)


def test_validate_journey_dataframe_invalid_binary_target():
    df = pd.DataFrame(
        {
            "journey_id": ["J_1", "J_2"],
            "is_delayed": [0, 5],  # 5 is not binary
        }
    )
    report = validate_journey_dataframe(df, is_training=True)
    assert report.is_valid is False
    assert any("Target column 'is_delayed' contains non-binary values" in err for err in report.errors)


def test_validate_journey_dataframe_negative_distance_and_utilization():
    df = pd.DataFrame(
        {
            "journey_id": ["J_1", "J_2"],
            "distance_km": [-10, 500],
            "seat_utilisation_pct": [120.0, -5.0],
            "is_delayed": [0, 1],
        }
    )
    report = validate_journey_dataframe(df, is_training=True)
    assert report.is_valid is False
    assert any("Found 1 negative values in 'distance_km'" in err for err in report.errors)
    assert any("values outside [0, 100]" in err for err in report.errors)


def test_validate_journey_dataframe_leakage_protection_in_test():
    # If test dataframe contains target or delay outcome columns, it must fail validation
    df_leakage = pd.DataFrame(
        {
            "journey_id": ["J_TEST_1"],
            "is_delayed": [1],
            "primary_delay_cause": ["Equipment"],
        }
    )
    report = validate_journey_dataframe(df_leakage, is_training=False)
    assert report.is_valid is False
    assert any("unauthorized target/leakage column 'is_delayed'" in err for err in report.errors)
    assert any("unauthorized target/leakage column 'primary_delay_cause'" in err for err in report.errors)


def test_get_approved_model_features_excludes_leakage():
    all_cols = [
        "journey_id",
        "train_number",
        "distance_km",
        "seat_utilisation_pct",
        "primary_delay_cause",  # LEAKAGE
        "delay_minutes",        # LEAKAGE
        "is_delayed",           # TARGET
        "unauthorized_column",
    ]
    approved = get_approved_model_features(all_cols)
    assert "journey_id" in approved
    assert "train_number" in approved
    assert "distance_km" in approved
    assert "seat_utilisation_pct" in approved

    # Must NOT contain target or leakage columns
    assert "primary_delay_cause" not in approved
    assert "delay_minutes" not in approved
    assert "is_delayed" not in approved
    assert "unauthorized_column" not in approved
